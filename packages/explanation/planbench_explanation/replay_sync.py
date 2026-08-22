"""Two replays, two ways of lining them up, and one warning that travels — E2.

Time-sync — both panels on one clock — is what the comparison page
already does, and it is the honest default: at a shared timestamp the
two robots saw the *same world*, dynamic obstacles included.

Progress-sync answers a different question — "what did each stack do at
this part of the map?" — by driving both panels from arc length along a
reference line instead of from the clock. It is the view that makes a
geometric cause visible, and it is also the view that quietly lies:
**the two robots reached that place at different times**, so the traffic
around them was not the same. That warning is not advice in a docstring
here; :class:`ProgressSyncPlan` cannot be constructed without it.

**The reference line is the thing the platform mostly does not have.**
Projecting onto "the route" presumes a route, and a trace holds only
what the robot actually drove. The global plan lives in the episode
JSON, and for every run recorded before that was kept it is simply
absent. So the reference is *chosen*, the choice is *declared*, and the
declaration is a required field with no default:

``reference_plan``
    the planner's own path. What projection is supposed to mean.
``degraded_candidate_path``
    one candidate's driven trajectory, used as the yardstick for both.
    Workable, and biased by construction: the candidate that supplied
    the line has a cross-track offset of zero everywhere.
``degraded_straight_line``
    start to goal. Says nothing about the corridor structure, so
    progress along it is only loosely "how far through the task".

A panel that cannot say which of these it used may not draw
progress-sync at all. That is why ``quality`` has no default value —
"did not say" must not be readable as "reference plan".
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: What the arc length was measured along. No default: an unstated
#: projection quality would be read as the best one.
ProjectionQuality = Literal[
    "reference_plan",
    "degraded_candidate_path",
    "degraded_straight_line",
]

#: Qualities that are not the planner's own route. Carried as data so a
#: renderer can decide what to grey out without re-deriving the rule.
DEGRADED_QUALITIES: tuple[ProjectionQuality, ...] = (
    "degraded_candidate_path",
    "degraded_straight_line",
)

#: The sentence that must accompany every progress-synced view. Fixed
#: text rather than a caller-supplied string: a warning a caller can
#: reword is a warning a caller can water down.
PROGRESS_SYNC_WARNING = (
    "same place is not the same situation: the two runs reached this point at "
    "different times, so the dynamic obstacles around them were not the same. "
    "Progress-sync is valid for static geometric causes only."
)

#: Below this, two points are the same point and the segment between
#: them has no direction to project onto.
_MIN_SEGMENT_M = 1e-9


class ReplaySyncRefusal(ValueError):
    """The trajectories on hand cannot support the alignment requested."""


class TrackPoint(BaseModel):
    """One sample of a driven trajectory: when, and where."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    time: float = Field(ge=0.0)
    x: float
    y: float


class ReferenceLine(BaseModel):
    """The polyline arc length is measured along, and where it came from."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    points: tuple[tuple[float, float], ...]
    quality: ProjectionQuality

    @model_validator(mode="after")
    def _check(self) -> ReferenceLine:
        if len(self.points) < 2:
            raise ReplaySyncRefusal(
                f"a reference line needs at least two points, got {len(self.points)}; "
                "there is no direction to project onto"
            )
        if self.length_m <= _MIN_SEGMENT_M:
            raise ReplaySyncRefusal(
                "reference line has zero length; every sample would project to the "
                "same progress and the two panels would appear perfectly synchronised"
            )
        return self

    @property
    def segments(self) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
        return tuple(zip(self.points, self.points[1:], strict=False))

    @property
    def length_m(self) -> float:
        return float(sum(math.dist(start, end) for start, end in self.segments))

    @property
    def is_degraded(self) -> bool:
        return self.quality in DEGRADED_QUALITIES


def choose_reference(
    *,
    planned_path: Sequence[tuple[float, float]] | None,
    candidate_path: Sequence[tuple[float, float]] | None = None,
    start: tuple[float, float] | None = None,
    goal: tuple[float, float] | None = None,
) -> ReferenceLine:
    """Pick a reference line and say what it is.

    The order is a preference, not a fallback chain that hides
    failures: each step down is recorded in ``quality``, and a caller
    that reaches the last one still gets a usable line and an honest
    label rather than an exception.
    """
    for points, quality in (
        (planned_path, "reference_plan"),
        (candidate_path, "degraded_candidate_path"),
    ):
        cleaned = _dedupe(points or ())
        if len(cleaned) >= 2:
            return ReferenceLine(points=cleaned, quality=quality)  # type: ignore[arg-type]

    if start is None or goal is None:
        raise ReplaySyncRefusal(
            "no planned path, no usable candidate path, and no start/goal to fall "
            "back on; progress-sync has nothing to measure progress along"
        )
    if math.dist(start, goal) <= _MIN_SEGMENT_M:
        raise ReplaySyncRefusal("start and goal are the same point; there is no route")
    return ReferenceLine(points=(tuple(start), tuple(goal)), quality="degraded_straight_line")


def _dedupe(points: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Drop consecutive duplicates — a stopped robot repeats its pose."""
    kept: list[tuple[float, float]] = []
    for point in points:
        pair = (float(point[0]), float(point[1]))
        if not kept or math.dist(kept[-1], pair) > _MIN_SEGMENT_M:
            kept.append(pair)
    return tuple(kept)


class ProjectedSample(BaseModel):
    """One trajectory sample, expressed against the reference line."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    time: float = Field(ge=0.0)
    #: Arc length of the projection foot, metres from the line's start.
    progress_m: float = Field(ge=0.0)
    #: Signed distance from the line; left of travel is positive. Signed
    #: rather than absolute because two runs passing an obstacle on
    #: opposite sides is the interesting case, and ``|e|`` erases it.
    cross_track_m: float


class ProjectedPath(BaseModel):
    """A driven trajectory in reference coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    samples: tuple[ProjectedSample, ...]
    #: Samples whose progress went *backwards*. Not an error: a robot
    #: that reverses out of a dead end really did lose ground. It is
    #: reported because progress-sync interpolates on a monotone series,
    #: and a run with many of these is being shown through a lens that
    #: cannot represent what it did.
    backward_samples: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> ProjectedPath:
        if not self.samples:
            raise ReplaySyncRefusal("a projected path with no samples aligns nothing")
        return self

    @property
    def monotone_progress(self) -> tuple[float, ...]:
        """Running maximum of progress — what interpolation runs on."""
        best = 0.0
        out: list[float] = []
        for sample in self.samples:
            best = max(best, sample.progress_m)
            out.append(best)
        return tuple(out)

    @property
    def max_progress_m(self) -> float:
        return self.monotone_progress[-1]

    def time_at_progress(self, progress_m: float) -> float | None:
        """When this run first reached ``progress_m`` (linear between samples).

        ``None`` past the end: a run that stopped short did not reach
        that part of the map, and inventing a timestamp for it would
        draw a robot where none was.
        """
        return self._interpolate(progress_m, lambda sample: sample.time)

    def cross_track_at_progress(self, progress_m: float) -> float | None:
        """Offset from the line at ``progress_m``, interpolated.

        Interpolated rather than "the next sample's value", which was
        the first cut: with metre-spaced samples that reports a two
        metre offset a whole metre before the run actually left the
        line, and the divergence search then names a place the runs were
        still side by side.
        """
        return self._interpolate(progress_m, lambda sample: sample.cross_track_m)

    def _interpolate(self, progress_m: float, value) -> float | None:  # type: ignore[no-untyped-def]
        progress = self.monotone_progress
        if progress_m > progress[-1] + _MIN_SEGMENT_M:
            return None
        for index, reached in enumerate(progress):
            if reached < progress_m:
                continue
            if index == 0:
                return value(self.samples[0])
            previous = progress[index - 1]
            span = reached - previous
            if span <= _MIN_SEGMENT_M:
                return value(self.samples[index])
            ratio = (progress_m - previous) / span
            earlier, later = value(self.samples[index - 1]), value(self.samples[index])
            return earlier + ratio * (later - earlier)
        return value(self.samples[-1])


def project(track: Sequence[TrackPoint], reference: ReferenceLine) -> ProjectedPath:
    """Express a driven trajectory as (arc length, offset) on the reference."""
    if not track:
        raise ReplaySyncRefusal("cannot project an empty trajectory")

    starts: list[float] = []
    total = 0.0
    for segment_start, segment_end in reference.segments:
        starts.append(total)
        total += math.dist(segment_start, segment_end)

    samples: list[ProjectedSample] = []
    backward = 0
    previous = -math.inf
    for point in track:
        progress, offset = _project_point(point, reference, starts)
        if progress < previous - _MIN_SEGMENT_M:
            backward += 1
        previous = progress
        samples.append(ProjectedSample(time=point.time, progress_m=progress, cross_track_m=offset))
    return ProjectedPath(samples=tuple(samples), backward_samples=backward)


def _project_point(
    point: TrackPoint,
    reference: ReferenceLine,
    segment_starts: Sequence[float],
) -> tuple[float, float]:
    """Nearest point on the polyline: its arc length and the signed offset."""
    best: tuple[float, float, float] | None = None  # (distance, progress, offset)
    for index, (segment_start, segment_end) in enumerate(reference.segments):
        dx = segment_end[0] - segment_start[0]
        dy = segment_end[1] - segment_start[1]
        length = math.hypot(dx, dy)
        if length <= _MIN_SEGMENT_M:
            continue
        ratio = ((point.x - segment_start[0]) * dx + (point.y - segment_start[1]) * dy) / (
            length * length
        )
        ratio = min(1.0, max(0.0, ratio))
        foot_x = segment_start[0] + ratio * dx
        foot_y = segment_start[1] + ratio * dy
        distance = math.dist((point.x, point.y), (foot_x, foot_y))
        # Positive to the left of travel, by the 2-D cross product.
        side = (dx * (point.y - segment_start[1]) - dy * (point.x - segment_start[0])) / length
        candidate = (distance, segment_starts[index] + ratio * length, side)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:  # pragma: no cover - ReferenceLine forbids a zero-length line
        raise ReplaySyncRefusal("reference line has no projectable segment")
    return best[1], best[2]


class ProgressSyncRow(BaseModel):
    """One rung of the progress ladder, and where each run was on it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    progress_m: float = Field(ge=0.0)
    #: ``None`` when that run never got this far.
    time_a: float | None
    time_b: float | None
    cross_track_a: float | None
    cross_track_b: float | None

    @property
    def separation_m(self) -> float | None:
        """Lateral gap between the two runs at this progress."""
        if self.cross_track_a is None or self.cross_track_b is None:
            return None
        return abs(self.cross_track_a - self.cross_track_b)


class ProgressSyncPlan(BaseModel):
    """Everything a viewer needs to drive two panels from arc length.

    The warning is a field with one legal value, not a note in the
    documentation: a panel that renders this object cannot obtain the
    rows without also obtaining the sentence that qualifies them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    reference: ReferenceLine
    rows: tuple[ProgressSyncRow, ...]
    backward_samples_a: int = Field(ge=0)
    backward_samples_b: int = Field(ge=0)
    warning: str = PROGRESS_SYNC_WARNING

    @model_validator(mode="after")
    def _check(self) -> ProgressSyncPlan:
        if not self.rows:
            raise ReplaySyncRefusal("a progress-sync plan with no rows synchronises nothing")
        if self.warning != PROGRESS_SYNC_WARNING:
            raise ReplaySyncRefusal(
                "the progress-sync warning may not be reworded; a caller-supplied "
                "version of it is a caller-controlled caveat"
            )
        progresses = [row.progress_m for row in self.rows]
        if progresses != sorted(progresses):
            raise ReplaySyncRefusal("progress rows must be ordered by arc length")
        return self

    @property
    def common_progress_m(self) -> float:
        """How far both runs got — beyond this the panels are not comparable."""
        both = [
            row.progress_m for row in self.rows if row.time_a is not None and row.time_b is not None
        ]
        return max(both) if both else 0.0


def build_progress_sync(
    path_a: ProjectedPath,
    path_b: ProjectedPath,
    *,
    reference: ReferenceLine,
    steps: int = 200,
) -> ProgressSyncPlan:
    """Sample the shared arc-length range and place both runs on it."""
    if steps < 2:
        raise ReplaySyncRefusal(f"steps must be at least 2, got {steps}")

    limit = min(path_a.max_progress_m, path_b.max_progress_m)
    if limit <= _MIN_SEGMENT_M:
        raise ReplaySyncRefusal(
            "the two runs share no progress along the reference line; there is "
            "nothing to place side by side"
        )

    rows = []
    for step in range(steps):
        progress = limit * step / (steps - 1)
        rows.append(
            ProgressSyncRow(
                progress_m=progress,
                time_a=path_a.time_at_progress(progress),
                time_b=path_b.time_at_progress(progress),
                cross_track_a=path_a.cross_track_at_progress(progress),
                cross_track_b=path_b.cross_track_at_progress(progress),
            )
        )
    return ProgressSyncPlan(
        reference=reference,
        rows=tuple(rows),
        backward_samples_a=path_a.backward_samples,
        backward_samples_b=path_b.backward_samples,
    )


#: Events cheap enough to anchor a divergence on without a detector.
#: ``detour`` is deliberately absent: it needs the E3 detectors, and
#: guessing at it here would put a second, weaker definition of detour
#: in the codebase.
ANCHOR_EVENTS: tuple[str, ...] = ("replan", "stuck", "collision", "no_path")


class DivergencePoint(BaseModel):
    """Where the two runs stopped doing the same thing."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["sustained_cross_track", "event"]
    progress_m: float = Field(ge=0.0)
    time_a: float | None
    time_b: float | None
    separation_m: float | None = None
    #: For ``event``: which event, and on which side it fired.
    event: str | None = None
    side: Literal["a", "b"] | None = None

    @model_validator(mode="after")
    def _check(self) -> DivergencePoint:
        if self.kind == "event" and (self.event is None or self.side is None):
            raise ReplaySyncRefusal("an event divergence must name the event and the side")
        if self.kind == "sustained_cross_track" and self.separation_m is None:
            raise ReplaySyncRefusal("a cross-track divergence must state the separation")
        return self


class DivergenceReport(BaseModel):
    """The first sustained parting, plus the cheap event anchors."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    sustained: DivergencePoint | None
    anchors: tuple[DivergencePoint, ...] = ()

    @property
    def earliest(self) -> DivergencePoint | None:
        candidates = [point for point in (self.sustained, *self.anchors) if point is not None]
        return min(candidates, key=lambda point: point.progress_m) if candidates else None


def find_divergence(
    plan: ProgressSyncPlan,
    *,
    threshold_m: float = 0.5,
    sustain_m: float = 1.0,
    events_a: Sequence[tuple[float, str]] = (),
    events_b: Sequence[tuple[float, str]] = (),
) -> DivergenceReport:
    """First place the runs part company, by geometry and by event.

    **Sustained, not first-crossing.** Two runs weaving inside the same
    corridor cross a half-metre threshold constantly; what marks a real
    parting is staying apart. The window is measured in *arc length*
    rather than in samples, so a fast run and a slow one are held to the
    same standard — a sample-count window would call the slower run
    divergent for driving slowly.
    """
    if threshold_m <= 0:
        raise ReplaySyncRefusal(f"threshold_m must be positive, got {threshold_m}")
    if sustain_m <= 0:
        raise ReplaySyncRefusal(f"sustain_m must be positive, got {sustain_m}")

    sustained = _first_sustained(plan, threshold_m=threshold_m, sustain_m=sustain_m)
    anchors = tuple(
        sorted(
            (
                anchor
                for side, events in (("a", events_a), ("b", events_b))
                for anchor in _event_anchors(plan, side, events)  # type: ignore[arg-type]
            ),
            key=lambda point: point.progress_m,
        )
    )
    return DivergenceReport(sustained=sustained, anchors=anchors)


def _first_sustained(
    plan: ProgressSyncPlan, *, threshold_m: float, sustain_m: float
) -> DivergencePoint | None:
    opened: ProgressSyncRow | None = None
    for row in plan.rows:
        separation = row.separation_m
        if separation is None or separation <= threshold_m:
            opened = None
            continue
        if opened is None:
            opened = row
        if row.progress_m - opened.progress_m >= sustain_m:
            return DivergencePoint(
                kind="sustained_cross_track",
                progress_m=opened.progress_m,
                time_a=opened.time_a,
                time_b=opened.time_b,
                separation_m=opened.separation_m,
            )
    return None


def _event_anchors(
    plan: ProgressSyncPlan, side: Literal["a", "b"], events: Sequence[tuple[float, str]]
) -> list[DivergencePoint]:
    """The first occurrence of each anchor event, placed on the ladder."""
    first: dict[str, float] = {}
    for time, name in events:
        if name in ANCHOR_EVENTS and (name not in first or time < first[name]):
            first[name] = time
    anchors = []
    for name, time in sorted(first.items()):
        row = _row_at_time(plan, side, time)
        if row is None:
            continue
        anchors.append(
            DivergencePoint(
                kind="event",
                progress_m=row.progress_m,
                time_a=row.time_a,
                time_b=row.time_b,
                event=name,
                side=side,
            )
        )
    return anchors


def _row_at_time(
    plan: ProgressSyncPlan, side: Literal["a", "b"], time: float
) -> ProgressSyncRow | None:
    """The first rung this side had reached by ``time``."""
    for row in plan.rows:
        stamp = row.time_a if side == "a" else row.time_b
        if stamp is not None and stamp >= time:
            return row
    return None
