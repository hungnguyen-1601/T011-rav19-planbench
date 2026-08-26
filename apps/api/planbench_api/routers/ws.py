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
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from planbench_api.config import get_settings
from planbench_api.errors import NotFoundError

router = APIRouter()


@router.websocket("/ws/simulations/{simulation_id}")
async def stream_simulation(websocket: WebSocket, simulation_id: str) -> None:
    await websocket.accept()
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
                "plan_path": [{"x": p.x, "y": p.y} for p in run.plan.path],
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
