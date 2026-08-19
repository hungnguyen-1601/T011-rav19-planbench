"""Behaviour a trace shows, found by rule rather than by reading — E3.

A detector answers *what happened*, never *why*. `stuck_cluster` says
the robot stopped four times in the same stretch of corridor; it does
not say a local minimum caused it, and nothing here reaches for a
mechanism. That separation is the whole architecture: detectors feed the
case packet, an analyst proposes mechanisms, a checker verifies them,
and the promotion matrix decides what may be said. A detector that
guessed at causes would put an unverifiable claim upstream of every one
of those gates.

**Pure functions of a trace, tested like metrics.** Same inputs, same
detections, no hidden state, no map lookups except the ones passed in.
The thresholds live in :class:`DetectorSettings` where they can be read
and changed, rather than as numbers sprinkled through the code — a
detector whose sensitivity is a literal buried three functions down is
one nobody can calibrate.

**Where a detection happened, honestly.** The design sketches regions
with names like ``aisle_B7``. The platform has no map-region vocabulary
and inventing one here would attach a confident label to an arbitrary
bounding box, so a detection carries the *arc-length window* it covers
on the reference line the caller chose — a measurement, with the
reference's own declared quality travelling beside it. Naming regions is
a later, separate piece of work, and it can key off exactly these
windows when it exists.

**Prevalence is an aggregate, not a detection.** "Detour appears in
27 of 30 episode pairs" is what a reader needs, and it is computed by
:func:`summarise` over per-episode detections rather than guessed at
from one episode. One episode cannot know how many others exist.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.replay_sync import (
    ProjectionQuality,
    ReferenceLine,
    TrackPoint,
    project,
)

#: What a detector can report. Closed, and named for the *behaviour*
#: rather than for a cause: ``stuck_cluster`` is a description a reader
#: can check against the replay, while "local minimum" is a hypothesis
#: about why.
DetectionType = Literal[
    "detour",
    "stuck_cluster",
    "near_miss_cluster",
    "replan_storm",
    "oscillation",
    "latency_spike",
    "narrow_gap_refusal",
]

KNOWN_DETECTIONS: tuple[DetectionType, ...] = (
    "detour",
    "stuck_cluster",
    "near_miss_cluster",
    "replan_storm",
    "oscillation",
    "latency_spike",
    "narrow_gap_refusal",
)


class DetectorRefusal(ValueError):
    """The trace on hand cannot support the detector requested."""


class DetectorSettings(BaseModel):
    """Every threshold a detector uses, in one place a person can read.

    Defaults are deliberately conservative: a detector that fires on
    ordinary driving fills the packet with noise, and an analyst reading
    thirty detections per episode learns nothing from any of them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    #: Below this speed the robot counts as stopped.
    stopped_speed_mps: float = Field(default=0.05, gt=0)
    #: A stop shorter than this is traffic, not a symptom.
    stop_seconds: float = Field(default=1.0, gt=0)
    #: Stops closer together than this are one cluster.
    stop_gap_seconds: float = Field(default=5.0, gt=0)
    #: Clearance under this counts as a near miss. Measured from the
    #: robot's surface (HĐ-8.2), so it is not a distance with a radius
    #: still to subtract.
    near_miss_clearance_m: float = Field(default=0.15, gt=0)
    #: Fewer than this many near misses in a window is a single event.
    near_miss_count: int = Field(default=3, ge=2)
    #: Window for both near-miss and replan clustering.
    cluster_window_seconds: float = Field(default=10.0, gt=0)
    #: Replans inside one window before it counts as a storm.
    replan_count: int = Field(default=3, ge=2)
    #: Heading reversals per window that count as oscillation.
    oscillation_reversals: int = Field(default=4, ge=2)
    #: Latency above this is a spike. Absolute rather than a percentile
    #: of this episode: a percentile always finds a "spike", even in a
    #: run whose worst tick was 8 ms.
    latency_spike_ms: float = Field(default=100.0, gt=0)
    #: Extra distance over the reference before a route counts as a
    #: detour, as a fraction of the reference length.
    detour_excess_fraction: float = Field(default=0.15, gt=0)


class ArcWindow(BaseModel):
    """Where on the reference line a detection sits, and when."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    start_m: float = Field(ge=0.0)
    end_m: float = Field(ge=0.0)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(ge=0.0)
    #: What the arc length was measured along. Travels with the window
    #: because "at 14 m along the route" means something different when
    #: the route is a straight line drawn between start and goal.
    projection_quality: ProjectionQuality

    @model_validator(mode="after")
    def _check(self) -> ArcWindow:
        if self.end_m < self.start_m:
            raise DetectorRefusal(f"window ends at {self.end_m} m, before it starts")
        if self.end_s < self.start_s:
            raise DetectorRefusal(f"window ends at {self.end_s} s, before it starts")
        return self


class Detection(BaseModel):
    """One episode, one candidate, one thing that happened."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    type: DetectionType
    candidate_id: str = Field(min_length=1)
    episode_context_id: str = Field(min_length=1)
    #: ``None`` for a detection with no location — a refusal to plan
    #: happens at a pose, not along a stretch.
    window: ArcWindow | None = None
    #: The numbers that made it fire, in their own units. A reader
    #: checking the detection against the replay needs the value, not
    #: only the verdict.
    measurements: dict[str, float] = Field(default_factory=dict)


class Observation(BaseModel):
    """A detection type summarised across the episodes it was looked for.

    This is what reaches the case packet. ``episodes_seen`` over
    ``episodes_total`` is the part that keeps a single vivid episode
    from being read as a pattern: *one* detour in thirty is an anecdote,
    twenty-seven is a property of the pairing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    type: DetectionType
    candidate_id: str = Field(min_length=1)
    episodes_seen: int = Field(ge=0)
    episodes_total: int = Field(ge=1)
    #: Median of each measurement over the episodes that fired. Median
    #: rather than mean: one runaway episode should not set the number a
    #: reader takes as typical.
    typical: dict[str, float] = Field(default_factory=dict)
    #: The worst episode, for a reader who wants to watch that rather
    #: than a typical one. "Worst" is per detection type and knows which
    #: direction is bad (:data:`SEVERITY`) — for a near miss the
    #: *smallest* clearance, not the largest number.
    worst_episode_context_id: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Observation:
        if self.episodes_seen > self.episodes_total:
            raise DetectorRefusal(
                f"{self.type} seen in {self.episodes_seen} of {self.episodes_total} "
                "episodes; a pattern cannot appear in more episodes than were run"
            )
        return self

    @property
    def prevalence(self) -> float:
        return self.episodes_seen / self.episodes_total


#: Which measurement says how bad each detection is, and which way.
#:
#: **The direction is the point.** An earlier version took whichever key
#: sorted first alphabetically and called the largest value the worst,
#: which for ``near_miss_cluster`` picked ``min_clearance_m`` and then
#: reported the *safest* episode as the one to watch: 0.14 m ranked
#: above 0.01 m. Clearance is worse when it is smaller and every other
#: measurement here is worse when it is larger, so each type says which
#: it is rather than a rule guessing.
SEVERITY: dict[DetectionType, tuple[str, Literal["higher", "lower"]]] = {
    "detour": ("extra_distance_m", "higher"),
    "stuck_cluster": ("stopped_seconds", "higher"),
    "near_miss_cluster": ("min_clearance_m", "lower"),
    "replan_storm": ("replans", "higher"),
    "oscillation": ("reversals", "higher"),
    "latency_spike": ("peak_latency_ms", "higher"),
    "narrow_gap_refusal": ("margin_m", "lower"),
}


def severity_of(detection: Detection) -> float | None:
    """How bad this detection is, on a scale where **larger is worse**.

    Normalising the direction here is what lets one comparison serve
    every type: a clearance of 0.01 m becomes a larger number than one
    of 0.14 m, so "the worst episode" means the same thing everywhere.
    """
    key, direction = SEVERITY[detection.type]
    value = detection.measurements.get(key)
    if value is None:
        return None
    return value if direction == "higher" else -value


def severity_key(detection: Detection) -> float:
    """:func:`severity_of`, with "no measurement" sorted last.

    A separate function because the obvious inline spelling —
    ``severity_of(item) or -math.inf`` — is wrong on the most important
    input there is. Zero is falsy, so a near miss with **0.00 m** of
    clearance, which is contact, became negative infinity and lost the
    ranking to a 0.10 m one. The comparison has to distinguish "no
    number" from "the worst possible number".
    """
    value = severity_of(detection)
    return -math.inf if value is None else value


def summarise(detections: Sequence[Detection], *, episodes_total: int) -> tuple[Observation, ...]:
    """Per-episode detections into per-candidate observations.

    ``episodes_total`` is passed in rather than counted from the
    detections, because the denominator is *episodes looked at* and the
    detections only cover the ones that fired. Counting them would make
    every pattern universal.

    **One episode, one vote.** Detections are folded to the worst one
    per episode before anything is averaged. An episode that produced
    four near-miss clusters is still one episode, and letting each
    cluster into the median would weight a busy episode four times —
    which is not what "median over the episodes that fired" means.
    """
    if episodes_total < 1:
        raise DetectorRefusal("a prevalence needs at least one episode in the denominator")

    grouped: dict[tuple[DetectionType, str], list[Detection]] = {}
    for detection in detections:
        grouped.setdefault((detection.type, detection.candidate_id), []).append(detection)

    observations = []
    for (kind, candidate_id), group in sorted(grouped.items()):
        per_episode = _worst_per_episode(group)
        keys = sorted({key for item in per_episode.values() for key in item.measurements})
        typical = {
            key: _median(
                [
                    item.measurements[key]
                    for item in per_episode.values()
                    if key in item.measurements
                ]
            )
            for key in keys
            if any(key in item.measurements for item in per_episode.values())
        }
        worst = max(
            per_episode.values(),
            key=lambda item: (severity_key(item), item.episode_context_id),
            default=None,
        )
        observations.append(
            Observation(
                type=kind,
                candidate_id=candidate_id,
                episodes_seen=len(per_episode),
                episodes_total=episodes_total,
                typical=typical,
                worst_episode_context_id=worst.episode_context_id if worst else None,
            )
        )
    return tuple(observations)


def _worst_per_episode(group: Sequence[Detection]) -> dict[str, Detection]:
    """One detection per episode: the worst one that episode produced.

    Ties fall to the detection that comes first in the trace, which is
    stable because detections are produced in time order.
    """
    chosen: dict[str, Detection] = {}
    for detection in group:
        current = chosen.get(detection.episode_context_id)
        if current is None:
            chosen[detection.episode_context_id] = detection
            continue
        if severity_key(detection) > severity_key(current):
            chosen[detection.episode_context_id] = detection
    return chosen


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)


class TraceView(BaseModel):
    """One episode's trace, in the shape every detector wants.

    Built once per episode by :func:`read_trace` so seven detectors do
    not each re-derive speeds and event times from the raw columns —
    and, more to the point, cannot each derive them slightly differently.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_id: str = Field(min_length=1)
    episode_context_id: str = Field(min_length=1)
    track: tuple[TrackPoint, ...]
    clearance_m: tuple[float, ...]
    latency_ms: tuple[float, ...]
    #: ``(time, name)``, sparse.
    events: tuple[tuple[float, str], ...]

    @model_validator(mode="after")
    def _check(self) -> TraceView:
        if not self.track:
            raise DetectorRefusal("a trace with no samples shows nothing")
        return self

    @property
    def duration_s(self) -> float:
        return self.track[-1].time - self.track[0].time

    def speeds(self) -> tuple[float, ...]:
        """Speed between consecutive samples, one shorter than the track."""
        return tuple(
            math.dist((a.x, a.y), (b.x, b.y)) / (b.time - a.time) if b.time > a.time else 0.0
            for a, b in zip(self.track, self.track[1:], strict=False)
        )

    def path_length_m(self) -> float:
        return float(
            sum(
                math.dist((a.x, a.y), (b.x, b.y))
                for a, b in zip(self.track, self.track[1:], strict=False)
            )
        )


def read_trace(trace: Mapping[str, Any]) -> TraceView:
    """The served trace payload, in detector shape. Refuses a ragged one."""
    times = list(trace.get("t") or [])
    xs = list(trace.get("x") or [])
    ys = list(trace.get("y") or [])
    if not times:
        raise DetectorRefusal("trace has no samples")
    if not len(times) == len(xs) == len(ys):
        raise DetectorRefusal(
            f"trace columns disagree (t={len(times)}, x={len(xs)}, y={len(ys)}); pairing "
            "a timestamp with another sample's pose would place the robot where it never was"
        )

    clearance = list(trace.get("clearance_m") or [])
    latency = list(trace.get("planner_latency_ms") or [])
    events = []
    for entry in trace.get("events") or []:
        index, name = entry.get("index"), entry.get("event")
        if isinstance(index, int) and name and 0 <= index < len(times):
            events.append((float(times[index]), str(name)))

    return TraceView(
        candidate_id=str(trace.get("candidate_id") or ""),
        episode_context_id=str(trace.get("episode_context_id") or ""),
        track=tuple(
            TrackPoint(time=float(t), x=float(x), y=float(y))
            for t, x, y in zip(times, xs, ys, strict=True)
        ),
        clearance_m=tuple(float(value) for value in clearance),
        latency_ms=tuple(float(value) for value in latency),
        events=tuple(events),
    )


def detect_all(
    view: TraceView,
    *,
    reference: ReferenceLine,
    settings: DetectorSettings | None = None,
    narrowest_passage_m: float | None = None,
    required_passage_width_m: float | None = None,
) -> tuple[Detection, ...]:
    """Every detector, over one episode, in a fixed order.

    ``narrowest_passage_m`` and ``required_passage_width_m`` come from the
    map features and the robot; without them ``narrow_gap_refusal``
    simply does not run rather than guessing at a width.
    """
    config = settings or DetectorSettings()
    found: list[Detection] = []
    for detector in (
        _detour,
        _stuck_clusters,
        _near_miss_clusters,
        _replan_storms,
        _oscillations,
        _latency_spikes,
    ):
        found.extend(detector(view, reference, config))
    found.extend(
        _narrow_gap_refusal(
            view,
            reference,
            config,
            narrowest_passage_m=narrowest_passage_m,
            required_passage_width_m=required_passage_width_m,
        )
    )
    return tuple(found)


def _window(
    view: TraceView,
    reference: ReferenceLine,
    start_index: int,
    end_index: int,
) -> ArcWindow:
    projected = project(view.track, reference)
    start = projected.samples[min(start_index, len(projected.samples) - 1)]
    end = projected.samples[min(end_index, len(projected.samples) - 1)]
    return ArcWindow(
        start_m=min(start.progress_m, end.progress_m),
        end_m=max(start.progress_m, end.progress_m),
        start_s=min(start.time, end.time),
        end_s=max(start.time, end.time),
        projection_quality=reference.quality,
    )


def _detour(view: TraceView, reference: ReferenceLine, config: DetectorSettings) -> list[Detection]:
    """Drove materially further than the reference route.

    Compared against the reference line's own length, and the line's
    quality travels on the window: against a straight start→goal line
    every route through a corridor is a "detour", which is why the
    quality is not decoration.
    """
    reference_length = reference.length_m
    driven = view.path_length_m()
    excess = driven - reference_length
    if reference_length <= 0 or excess / reference_length < config.detour_excess_fraction:
        return []
    return [
        Detection(
            type="detour",
            candidate_id=view.candidate_id,
            episode_context_id=view.episode_context_id,
            window=_window(view, reference, 0, len(view.track) - 1),
            measurements={
                "extra_distance_m": excess,
                "excess_fraction": excess / reference_length,
                "reference_length_m": reference_length,
            },
        )
    ]


def _stuck_clusters(
    view: TraceView, reference: ReferenceLine, config: DetectorSettings
) -> list[Detection]:
    """Stopped long enough to matter, more than once, in one stretch."""
    speeds = view.speeds()
    stops: list[tuple[int, int]] = []
    start: int | None = None
    for index, speed in enumerate(speeds):
        if speed <= config.stopped_speed_mps:
            start = index if start is None else start
            continue
        if start is not None:
            stops.append((start, index))
            start = None
    if start is not None:
        stops.append((start, len(speeds)))

    long_stops = [
        (a, b)
        for a, b in stops
        if view.track[min(b, len(view.track) - 1)].time - view.track[a].time >= config.stop_seconds
    ]
    if not long_stops:
        return []

    clusters: list[list[tuple[int, int]]] = [[long_stops[0]]]
    for stop in long_stops[1:]:
        previous_end = view.track[min(clusters[-1][-1][1], len(view.track) - 1)].time
        if view.track[stop[0]].time - previous_end <= config.stop_gap_seconds:
            clusters[-1].append(stop)
        else:
            clusters.append([stop])

    detections = []
    for cluster in clusters:
        total = sum(
            view.track[min(b, len(view.track) - 1)].time - view.track[a].time for a, b in cluster
        )
        detections.append(
            Detection(
                type="stuck_cluster",
                candidate_id=view.candidate_id,
                episode_context_id=view.episode_context_id,
                window=_window(view, reference, cluster[0][0], cluster[-1][1]),
                measurements={"stopped_seconds": total, "stops": float(len(cluster))},
            )
        )
    return detections


def _near_miss_clusters(
    view: TraceView, reference: ReferenceLine, config: DetectorSettings
) -> list[Detection]:
    """Several samples inside the near-miss band, close together in time."""
    if not view.clearance_m:
        return []
    indices = [
        index
        for index, value in enumerate(view.clearance_m)
        if index < len(view.track) and value <= config.near_miss_clearance_m
    ]
    return _cluster_by_time(
        view,
        reference,
        indices,
        window_seconds=config.cluster_window_seconds,
        minimum=config.near_miss_count,
        kind="near_miss_cluster",
        measure=lambda group: {
            "samples": float(len(group)),
            "min_clearance_m": min(view.clearance_m[index] for index in group),
        },
    )


def _replan_storms(
    view: TraceView, reference: ReferenceLine, config: DetectorSettings
) -> list[Detection]:
    """Replanned repeatedly inside one window."""
    times = [time for time, name in view.events if name == "replan"]
    indices = [_index_at(view, time) for time in times]
    return _cluster_by_time(
        view,
        reference,
        indices,
        window_seconds=config.cluster_window_seconds,
        minimum=config.replan_count,
        kind="replan_storm",
        measure=lambda group: {"replans": float(len(group))},
    )


def _oscillations(
    view: TraceView, reference: ReferenceLine, config: DetectorSettings
) -> list[Detection]:
    """Heading reversed back and forth inside one window.

    Counted from the *driven* heading rather than from a commanded one:
    the trace records where the robot went, and a controller's intent is
    not in it.
    """
    if len(view.track) < 3:
        return []
    headings = [
        math.atan2(b.y - a.y, b.x - a.x) for a, b in zip(view.track, view.track[1:], strict=False)
    ]
    reversals = [
        index
        for index, (before, after) in enumerate(zip(headings, headings[1:], strict=False))
        if abs(_angle_diff(after, before)) > math.pi / 2
    ]
    return _cluster_by_time(
        view,
        reference,
        reversals,
        window_seconds=config.cluster_window_seconds,
        minimum=config.oscillation_reversals,
        kind="oscillation",
        measure=lambda group: {"reversals": float(len(group))},
    )


def _latency_spikes(
    view: TraceView, reference: ReferenceLine, config: DetectorSettings
) -> list[Detection]:
    """Control ticks that took far longer than a control period should."""
    if not view.latency_ms:
        return []
    indices = [
        index
        for index, value in enumerate(view.latency_ms)
        if index < len(view.track) and value >= config.latency_spike_ms
    ]
    return _cluster_by_time(
        view,
        reference,
        indices,
        window_seconds=config.cluster_window_seconds,
        minimum=1,
        kind="latency_spike",
        measure=lambda group: {
            "peak_latency_ms": max(view.latency_ms[index] for index in group),
            "ticks": float(len(group)),
        },
    )


def _narrow_gap_refusal(
    view: TraceView,
    reference: ReferenceLine,
    config: DetectorSettings,
    *,
    narrowest_passage_m: float | None,
    required_passage_width_m: float | None,
) -> list[Detection]:
    """The planner refused, and the route's narrowest passage is too narrow.

    Two facts side by side, not a mechanism: this says the refusal and
    the geometry are both present, which is exactly the shape of thing a
    ``gap_vs_footprint`` check exists to turn into a verified mechanism
    (E5/E6). Without the map feature or the robot's clearance the
    detector does not run — half of this pair is not a weaker version of
    it.

    **Both sides are widths.** ``required_passage_width_m`` is
    ``2 * (radius + margin)`` — the corridor a configuration needs, not
    the half of it a radius describes. The two were compared as a width
    against a radius until E6a, which made a doorway look passable at
    half the width the stack actually needs.

    **``narrowest_passage_m`` must be a measured width, never a lower
    bound.** ``RouteFeatures`` now returns ``None`` rather than a bound
    for exactly this caller: "the passage is at least 0.3 m" and "the
    robot needs 0.74 m" do not combine into "the passage is too narrow",
    because the unmapped side may open into a five-metre hall.
    """
    if narrowest_passage_m is None or required_passage_width_m is None:
        return []
    if not any(name in ("no_path", "stuck") for _, name in view.events):
        return []
    if narrowest_passage_m >= required_passage_width_m:
        return []
    return [
        Detection(
            type="narrow_gap_refusal",
            candidate_id=view.candidate_id,
            episode_context_id=view.episode_context_id,
            measurements={
                "narrowest_passage_m": narrowest_passage_m,
                "required_passage_width_m": required_passage_width_m,
                "margin_m": narrowest_passage_m - required_passage_width_m,
            },
        )
    ]


def _cluster_by_time(
    view: TraceView,
    reference: ReferenceLine,
    indices: Sequence[int],
    *,
    window_seconds: float,
    minimum: int,
    kind: DetectionType,
    measure,  # type: ignore[no-untyped-def]
) -> list[Detection]:
    """Group sample indices that fall within one window, keep the busy ones."""
    if not indices:
        return []
    groups: list[list[int]] = [[indices[0]]]
    for index in indices[1:]:
        if view.track[index].time - view.track[groups[-1][0]].time <= window_seconds:
            groups[-1].append(index)
        else:
            groups.append([index])
    return [
        Detection(
            type=kind,
            candidate_id=view.candidate_id,
            episode_context_id=view.episode_context_id,
            window=_window(view, reference, group[0], group[-1]),
            measurements=measure(group),
        )
        for group in groups
        if len(group) >= minimum
    ]


def _index_at(view: TraceView, time: float) -> int:
    """The last sample at or before ``time``."""
    chosen = 0
    for index, point in enumerate(view.track):
        if point.time > time:
            break
        chosen = index
    return chosen


def _angle_diff(after: float, before: float) -> float:
    return (after - before + math.pi) % (2 * math.pi) - math.pi
