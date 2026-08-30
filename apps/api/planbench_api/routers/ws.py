"""WebSocket robot-state streaming.

Design (decision D16): benchmark episodes run headless and
faster-than-real-time, so the socket streams the *recorded* trajectory
of a finished simulation rather than driving the engine over the wire.

Two delivery modes (query parameters):

- ``pace=true`` (default): server-side pacing at ``speed`` × simulation
  time, capped at ``settings.ws_max_rate_hz``; frames beyond the cap are
  skipped, never delayed. Use for a plain live view.
- ``pace=false``: every frame is delivered as fast as the socket allows,
  no skipping. Use when the client owns playback (pause/scrub/speed) —
  this is what the web UI does.

**Authentication is a ticket, not the bearer token.** The socket used to
accept every connection unconditionally, which made a recorded run
readable by anyone who could guess an id. A browser cannot put a header
on a WebSocket, and the usual workaround — passing the JWT as a query
parameter — writes an hour-long credential into every access log on the
path. So the caller mints a single-use, one-minute ticket over ordinary
HTTP first (``POST /api/v1/ws/tickets``) and connects with that; see
:mod:`planbench_api.ws_tickets`.

Two routers, and the split is the point. The socket lives outside
``/api/v1`` because a WebSocket route is not a versioned resource; the
ticket endpoint is an ordinary authenticated POST and belongs with every
other one, under the prefix. Putting them together only *looked* tidy —
it left the one route in this file that needs a bearer token sitting
where no other API route is, which is exactly where a client goes
looking for it and does not find it.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from planbench_api.auth import SimulatingUser
from planbench_api.config import get_settings
from planbench_api.errors import NotFoundError
from planbench_api.ws_tickets import TICKET_TTL

#: The socket itself. Mounted without a prefix (see the module docstring).
router = APIRouter()

#: The HTTP half, mounted under the API prefix like every other route
#: that authenticates with a bearer token.
tickets_router = APIRouter(prefix="/ws", tags=["ws"])

#: Closed before the handshake completes, per RFC 6455 §7.4.2's private
#: range. A browser cannot read a status code from a rejected upgrade, so
#: the ticket is also refused *after* accepting, with a message — that is
#: the path a person actually sees.
WS_UNAUTHORISED = 4401


class TicketResponse(BaseModel):
    """A one-minute, single-use credential for one socket."""

    ticket: str
    expires_in: int


@tickets_router.post("/tickets", response_model=TicketResponse)
def mint_ticket(request: Request, user: SimulatingUser) -> TicketResponse:
    """Trade a bearer token for something safe to put in a URL."""
    ticket = request.app.state.ws_tickets.issue(user.id)
    return TicketResponse(ticket=ticket.value, expires_in=int(TICKET_TTL.total_seconds()))


@router.websocket("/ws/simulations/{simulation_id}")
async def stream_simulation(websocket: WebSocket, simulation_id: str) -> None:
    await websocket.accept()
    # Accepted first, then checked, so the refusal arrives as a message a
    # browser can actually read. A rejected upgrade gives the page a bare
    # "connection failed" and nothing to show anyone.
    viewer = websocket.app.state.ws_tickets.redeem(websocket.query_params.get("ticket", ""))
    if viewer is None:
        await websocket.send_json(
            {
                "type": "error",
                "code": "unauthorised",
                "message": "this socket needs a ticket from POST /api/v1/ws/tickets",
            }
        )
        await websocket.close(code=WS_UNAUTHORISED)
        return
    repos = websocket.app.state.repos
    try:
        speed = float(websocket.query_params.get("speed", "1.0"))
    except ValueError:
        speed = 1.0
    speed = max(0.1, min(speed, 1000.0))
    pace = websocket.query_params.get("pace", "true").lower() not in ("false", "0", "no")

    try:
        stored = repos.simulations.get(simulation_id)
    except NotFoundError:
        await websocket.send_json(
            {"type": "error", "code": "not_found", "message": f"simulation {simulation_id!r}"}
        )
        await websocket.close()
        return
    if stored.state != "finished" or stored.run is None:
        await websocket.send_json(
            {
                "type": "error",
                "code": "not_ready",
                "message": "simulation has not been run yet",
            }
        )
        await websocket.close()
        return

    run = stored.run
    min_interval = 1.0 / get_settings().ws_max_rate_hz
    try:
        await websocket.send_json(
            {
                "type": "start",
                "simulation_id": stored.id,
                "steps": run.result.steps,
                # The route the episode set out on. Kept as its own field
                # rather than folded into `plans`: a client that only
                # wants the first plan should not have to understand the
                # handover rule to find it, and every episode has one
                # while only some have replans on record.
                "plan_path": [{"x": p.x, "y": p.y} for p in run.plan.path],
                "plans": _planned_routes(run),
            }
        )
        last_sent_time: float | None = None
        for point in run.result.trajectory:
            if pace and last_sent_time is not None:
                wait = (point.time - last_sent_time) / speed
                if wait < min_interval and point is not run.result.trajectory[-1]:
                    continue  # skip frames beyond the rate cap
                await asyncio.sleep(max(0.0, wait))
            last_sent_time = point.time
            await websocket.send_json(
                {
                    "type": "state",
                    "time": point.time,
                    "x": point.x,
                    "y": point.y,
                    "theta": point.theta,
                    "linear_velocity": point.linear_velocity,
                    "angular_velocity": point.angular_velocity,
                    # Ground truth, and **replay only**. The engine records
                    # where the traffic actually was at this sample; no
                    # planner is ever handed it (HĐ-4). Dropping it here
                    # was why a watched episode showed a robot swerving
                    # around nothing — the one screen where seeing the
                    # obstacle is the entire point.
                    "obstacles": [
                        {"name": o.name, "x": o.x, "y": o.y, "radius": o.radius}
                        for o in point.obstacles
                    ],
                }
            )
        await websocket.send_json(
            {
                "type": "result",
                "status": run.result.status.value,
                "reason": run.result.reason,
                "elapsed_time": run.result.elapsed_time,
                "metrics": run.metrics.model_dump(),
            }
        )
        await websocket.close()
    except WebSocketDisconnect:
        return


def _planned_routes(run) -> list[dict]:
    """Every route the global planner returned, and when each took over.

    **Why the test bench needed this at all.** The socket sent one
    `plan_path` at `start` and nothing after it, so a replanning episode
    drew the route it began with for its whole length — a dashed line
    that stayed put while the robot drove somewhere else, which is the
    picture that makes a replan look like a controller ignoring its
    plan.

    **Paired by time, and that is exact here rather than a conversion.**
    `decision_service` refuses to place routes when the sidecar's tick
    counter and the trace's control steps disagree, because those are two
    clocks. This is not that case: the events and the trajectory are both
    stamped by the engine from one `self._time`, so a replan's time lands
    on the trajectory without arithmetic.

    **Silent rather than wrong when the counts do not line up.** A
    refused replan is an event with no plan behind it — `StackRun.plans`
    documents that it holds no refusals — and an episode stored before
    `plans` existed carries none at all. Either way the routes cannot be
    placed, and a route drawn at the wrong moment is a picture of a
    decision nobody made. The client keeps the opening plan and draws one
    fewer thing.
    """
    plans = getattr(run, "plans", ()) or ()
    if not plans:
        return []
    replan_times = [float(event.time) for event in run.result.events if event.type == "replan"]
    if len(plans) != len(replan_times) + 1:
        return []
    starts = [0.0, *replan_times]
    return [
        {
            # 1-based, matching the sidecar's own numbering so the two
            # screens colour the same attempt the same way.
            "attempt": index + 1,
            "from_time": start,
            "points": [{"x": point.x, "y": point.y} for point in plan.path],
        }
        for index, (plan, start) in enumerate(zip(plans, starts, strict=True))
    ]
