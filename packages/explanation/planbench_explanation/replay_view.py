"""Assembling a progress-synced view from two served traces — E2.

The projection lives in :mod:`planbench_explanation.replay_sync`; this
module is the one place that turns *what the trace endpoint already
serves* into that machinery's inputs, so the API layer stays three lines
long and the arithmetic stays testable without a Parquet file.

**One implementation, not two.** The obvious alternative was to project
in the browser, where the trajectories already are. That puts a second
copy of the arc-length rules in TypeScript, and the two copies would
disagree the first time either is fixed — with the disagreement showing
up as a panel that draws a divergence the report does not mention.

**The pairing is checked here, not assumed.** Two panels side by side
only mean something if they are the same episode under the same
conditions (HĐ-3.2). Serving a view built from two different episodes
would be the most convincing wrong picture the platform could produce,
so it is refused rather than rendered.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.replay_sync import (
    DivergenceReport,
    ProgressSyncPlan,
    ReplaySyncRefusal,
    TrackPoint,
    build_progress_sync,
    choose_reference,
    find_divergence,
    project,
)


class ReplaySyncView(BaseModel):
    """Everything the comparison page needs to switch to progress-sync."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    episode_context_id: str = Field(min_length=1)
    candidate_a: str = Field(min_length=1)
    candidate_b: str = Field(min_length=1)
    plan: ProgressSyncPlan
    divergence: DivergenceReport
    #: Which candidate's driven path became the yardstick, when one did.
    #: Named because that candidate's cross-track offset is zero by
    #: construction, and a reader comparing the two curves has to know
    #: which one is the ruler.
    reference_source_candidate_id: str | None = None

    @model_validator(mode="after")
    def _check(self) -> ReplaySyncView:
        if self.candidate_a == self.candidate_b:
            raise ReplaySyncRefusal("a replay view compares a candidate with itself")
        if (
            self.plan.reference.quality == "degraded_candidate_path"
            and self.reference_source_candidate_id is None
        ):
            raise ReplaySyncRefusal(
                "the reference is a candidate's own path but the view does not say "
                "whose; that candidate's offset is zero everywhere and a reader "
                "cannot tell the ruler from the measurement"
            )
        if (
            self.plan.reference.quality != "degraded_candidate_path"
            and self.reference_source_candidate_id is not None
        ):
            raise ReplaySyncRefusal(
                f"reference quality {self.plan.reference.quality!r} names a source "
                "candidate; only a candidate-path reference has one"
            )
        return self


def build_replay_sync_view(
    trace_a: Mapping[str, Any],
    trace_b: Mapping[str, Any],
    *,
    planned_path: Sequence[tuple[float, float]] | None = None,
    steps: int = 200,
    threshold_m: float = 0.5,
    sustain_m: float = 1.0,
) -> ReplaySyncView:
    """Build the progress-synced view from two trace payloads.

    ``planned_path`` is the global planner's route when the platform has
    it. It does not today — the plan is written to the episode JSON and
    older runs have none — so the reference falls to a driven path or to
    start→goal, and the view reports which. The argument exists so that
    the day the API can supply the route, nothing here changes except
    that ``quality`` stops saying ``degraded_*``.
    """
    episode = _same_episode(trace_a, trace_b)
    candidate_a = str(trace_a.get("candidate_id") or "")
    candidate_b = str(trace_b.get("candidate_id") or "")
    if not candidate_a or not candidate_b:
        raise ReplaySyncRefusal("both traces must name their candidate")

    track_a = _track(trace_a)
    track_b = _track(trace_b)

    start, goal = _mission_ends(trace_a)
    reference = choose_reference(
        planned_path=planned_path,
        candidate_path=[(point.x, point.y) for point in track_a],
        start=start,
        goal=goal,
    )
    source = candidate_a if reference.quality == "degraded_candidate_path" else None

    plan = build_progress_sync(
        project(track_a, reference),
        project(track_b, reference),
        reference=reference,
        steps=steps,
    )
    divergence = find_divergence(
        plan,
        threshold_m=threshold_m,
        sustain_m=sustain_m,
        events_a=_events(trace_a),
        events_b=_events(trace_b),
    )
    return ReplaySyncView(
        episode_context_id=episode,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        plan=plan,
        divergence=divergence,
        reference_source_candidate_id=source,
    )


def _same_episode(trace_a: Mapping[str, Any], trace_b: Mapping[str, Any]) -> str:
    left = str(trace_a.get("episode_context_id") or "")
    right = str(trace_b.get("episode_context_id") or "")
    if not left or not right:
        raise ReplaySyncRefusal("both traces must name their episode")
    if left != right:
        raise ReplaySyncRefusal(
            f"traces are from different episodes ({left} and {right}); two panels "
            "side by side claim a paired comparison, and this would not be one"
        )
    return left


def _track(trace: Mapping[str, Any]) -> list[TrackPoint]:
    """The column-oriented payload as points, refusing a ragged one."""
    times = list(trace.get("t") or [])
    xs = list(trace.get("x") or [])
    ys = list(trace.get("y") or [])
    if not times:
        raise ReplaySyncRefusal(
            f"trace for {trace.get('candidate_id')!r} has no samples; there is no run to align"
        )
    if not len(times) == len(xs) == len(ys):
        raise ReplaySyncRefusal(
            f"trace columns disagree in length (t={len(times)}, x={len(xs)}, y={len(ys)}); "
            "pairing a timestamp with somebody else's pose would place the robot "
            "somewhere it never was"
        )
    return [
        TrackPoint(time=float(time), x=float(x), y=float(y))
        for time, x, y in zip(times, xs, ys, strict=True)
    ]


def _events(trace: Mapping[str, Any]) -> list[tuple[float, str]]:
    """Sparse events as ``(time, name)``, dropping any that index nowhere."""
    times = list(trace.get("t") or [])
    out: list[tuple[float, str]] = []
    for entry in trace.get("events") or []:
        index = entry.get("index")
        name = entry.get("event")
        if not isinstance(index, int) or not name or not 0 <= index < len(times):
            continue
        out.append((float(times[index]), str(name)))
    return out


def _mission_ends(
    trace: Mapping[str, Any],
) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    """The first mission's endpoints, for the last-resort reference."""
    missions = trace.get("missions") or []
    if not missions:
        return None, None
    mission = missions[0]
    start, goal = mission.get("start"), mission.get("goal")
    if not start or not goal:
        return None, None
    return (float(start["x"]), float(start["y"])), (float(goal["x"]), float(goal["y"]))
