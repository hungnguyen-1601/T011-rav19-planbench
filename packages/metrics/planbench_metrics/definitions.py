"""The one place a metric is defined (CONTRACTS HĐ-6).

> Each metric has **exactly one** definition, written in **exactly one**
> place in the code, and has **exactly one** role.

Two rules from the contract are load-bearing here, and both are enforced
rather than described.

**The trace is the only input.** Nothing is computed during simulation
and handed over; everything below is recomputed from the Parquet file of
HĐ-5 plus the ``TaskProfile`` that states the thresholds. That is what
makes a stored run re-analysable: change an anchor or a tolerance, and
the metrics can be recomputed without re-running 300 episodes. It is also
why :class:`EpisodeMetricSet` carries no field that the file cannot
support.

**Every threshold is read from the profile, never hardcoded.** Goal
tolerance, the near-miss clearance and ``v_max`` all come from the
deployment. A constant in this module would be a threshold nobody
declared, which is exactly the HĐ-7 violation the gates exist to
prevent.

This module deliberately lives beside the older
:mod:`planbench_metrics.episode_metrics`, which computes the previous
topic's metrics from in-memory episode results. The two are kept in
parallel on purpose (see the backlog: no migration of the old names).
The decision layer reads **this** module and nothing else.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from planbench_decision.candidate import (
    ArtifactResourceProfile,
    ResourceProfile,
    StructuralResourceProfile,
)
from planbench_metrics.reference_path import reference_path_length
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.geometry import Point2D, normalize_angle
from planbench_schemas.map import MapData
from planbench_schemas.task_profile import Mission, TaskProfile
from planbench_simulator.trace import LoadedTrace

__all__ = [
    "BYTES_PER_MB",
    "EpisodeMetricSet",
    "FailureReason",
    "MetricError",
    "compute_metrics",
    "memory_estimate_mb",
    "pooled_p99_latency_ms",
]

BYTES_PER_MB = 1024 * 1024

FailureReason = Literal["no_path", "collision", "timeout", "stuck"]

#: Speed below which the robot counts as stopped, for
#: ``stop_and_go_count``. A pure zero would miss a controller that idles
#: at 1e-9 m/s, and anything larger would start counting slow corners as
#: stops. Diagnostic-only metric, so this is a reporting convention
#: rather than a deployment threshold — no candidate is judged on it.
STOP_SPEED_EPS = 1e-3


class MetricError(ValueError):
    """The trace and the profile cannot both be right.

    Raised rather than returned: every case below means a number that
    would look plausible on a Decision Card was produced under rules
    other than the ones stated.
    """


class EpisodeMetricSet(BaseModel):
    """Every HĐ-6 metric for one episode, and nothing else.

    Fields are named exactly as the contract names them so a reader can
    put the table and this class side by side. The role of each metric
    (Gate / Score / Diagnostic) is *not* stored here — it belongs to the
    gates and objectives that consume it, and duplicating it would give
    two places to disagree.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    episode_context_id: str
    candidate_id: str

    success: bool
    failure_reason: FailureReason | None
    collision_count: int

    min_clearance: float
    near_miss_rate: float

    path_length_m: float
    travel_time_s: float
    l_ref_m: float
    path_efficiency: float
    t_ideal_s: float
    time_efficiency: float

    smoothness: float
    stop_and_go_count: int

    p99_latency_ms: float
    peak_search_nodes: int
    peak_tree_nodes: int
    costmap_cells: int
    memory_estimate_mb: float | None = None

    #: Diagnostic only (HĐ-6). Never compare with ``available_ram_mb``.
    peak_rss_mb: float
    cpu_time_per_mission_s: float


def compute_metrics(
    trace: LoadedTrace,
    profile: TaskProfile,
    context: EpisodeContext,
    map_data: MapData,
    *,
    resource_profile: ResourceProfile | None = None,
) -> EpisodeMetricSet:
    """Recompute every HĐ-6 metric for one episode from its trace.

    ``context`` is required because HĐ-5 metadata stores the *hash* of
    the context, not the mission it came from, and the hash cannot be
    reversed. The runner has the context; a later re-analysis reads it
    from the manifest (HĐ-13), which is why the manifest has to store the
    context records and not only their ids.

    ``resource_profile`` is optional so metrics can be computed for a
    trace whose candidate is not at hand; ``memory_estimate_mb`` is then
    ``None`` and G5 has nothing to judge, which is the honest outcome —
    the estimate is a statement about the *target* implementation and
    cannot be invented from the trace.
    """
    _require_matching_ids(trace, context)
    mission = _mission_of(profile, context)

    t = trace.column("t")
    xs = trace.column("x")
    ys = trace.column("y")
    thetas = trace.column("theta")
    speeds = trace.column("v")
    clearances = trace.column("clearance_m")
    latencies = trace.column("planner_latency_ms")
    events = trace.column("event")

    collision_count = sum(1 for event in events if event == "collision")
    travel_time_s = float(t[-1] - t[0])
    path_length_m = _polyline_length(xs, ys)

    final = Point2D(x=xs[-1], y=ys[-1])
    goal_reached = _goal_reached(events, final, thetas[-1], mission, profile)
    timed_out = "timeout" in events
    success = goal_reached and collision_count == 0 and not timed_out

    l_ref = reference_path_length(map_data, mission.start.position, mission.goal.position)
    if l_ref is None:
        raise MetricError(
            f"mission {mission.id!r} has no route on map {map_data.name!r}, so no efficiency "
            "can be quoted against it. Every candidate fails this mission for a property of "
            "the profile; fix the profile rather than reporting a ratio"
        )

    v_max = profile.robot.max_linear_velocity
    t_ideal_s = l_ref / v_max

    return EpisodeMetricSet(
        episode_context_id=trace.metadata.episode_context_id,
        candidate_id=trace.metadata.candidate_id,
        success=success,
        failure_reason=None if success else _failure_reason(events, timed_out, collision_count),
        collision_count=collision_count,
        min_clearance=float(min(clearances)),
        near_miss_rate=_near_miss_rate(clearances, path_length_m, profile),
        path_length_m=path_length_m,
        travel_time_s=travel_time_s,
        l_ref_m=l_ref,
        path_efficiency=_ratio(l_ref, path_length_m),
        t_ideal_s=t_ideal_s,
        time_efficiency=_ratio(t_ideal_s, travel_time_s),
        smoothness=_smoothness(thetas),
        stop_and_go_count=_stop_and_go_count(speeds),
        p99_latency_ms=float(np.percentile(np.asarray(latencies, dtype=float), 99)),
        peak_search_nodes=trace.metadata.peak_search_nodes,
        peak_tree_nodes=trace.metadata.peak_tree_nodes,
        costmap_cells=trace.metadata.costmap_cells,
        memory_estimate_mb=(
            None
            if resource_profile is None
            else memory_estimate_mb(
                resource_profile,
                peak_search_nodes=trace.metadata.peak_search_nodes,
                peak_tree_nodes=trace.metadata.peak_tree_nodes,
                costmap_cells=trace.metadata.costmap_cells,
            )
        ),
        peak_rss_mb=trace.metadata.peak_rss_mb,
        cpu_time_per_mission_s=trace.metadata.cpu_time_s,
    )


def pooled_p99_latency_ms(traces: Sequence[LoadedTrace]) -> float:
    """G4's figure: the 99th percentile over **every** control step run.

    Not the worst episode's p99, and not an average of per-episode p99s.
    A percentile of percentiles is a statistic of nothing, and the worst
    episode makes the gate a function of the unluckiest moment on the
    benchmark host — which the first vertical slice demonstrated the hard
    way. Five of thirty A\\* episodes were measured while a test suite was
    running on the same machine; their p99 reached 119 ms against a
    100 ms budget, while the same candidate on an idle machine measured
    5 ms. The gate eliminated a candidate for the load, not for its cost.

    That failure mode is not merely inconvenient, it inverts the only
    thing the host phase is good for. G4 on the benchmark host is a
    *necessary* condition — failing there proves failure on the slower
    target board (HĐ-7.2) — and a false failure destroys exactly that
    implication. Pooling makes one unlucky episode one episode's worth of
    tail among thirty, instead of the whole verdict.

    Steps are pooled unweighted, so a long episode contributes more
    samples than a short one. That is the intended reading: the question
    is what fraction of the control steps this deployment will actually
    execute would miss their deadline, and a long episode really does
    execute more of them.
    """
    samples: list[float] = []
    for trace in traces:
        samples.extend(trace.column("planner_latency_ms"))
    if not samples:
        raise MetricError(
            "no control steps to take a latency percentile over; G4 would be comparing "
            "the deadline against nothing"
        )
    return float(np.percentile(np.asarray(samples, dtype=float), 99))


def memory_estimate_mb(
    profile: ResourceProfile,
    *,
    peak_search_nodes: int = 0,
    peak_tree_nodes: int = 0,
    costmap_cells: int = 0,
) -> float:
    """G5's memory figure, exactly as HĐ-7.3 writes it.

    For a ``structural`` profile the simulator's counters are multiplied
    by the *target implementation's* byte sizes — which is the whole
    point: the counts are algorithm behaviour and transfer between
    languages, the byte sizes do not, so they are declared rather than
    measured. For an ``artifact`` profile nothing is counted; the model
    and its runtime are declared at registration (and, with
    ``source: declared``, may only disqualify a candidate, never certify
    one).

    Never derived from ``peak_rss_mb`` — see HĐ-6 and §17 ban 13.
    """
    if isinstance(profile, ArtifactResourceProfile):
        return profile.model_artifact_mb + profile.runtime_footprint_mb
    if isinstance(profile, StructuralResourceProfile):
        total_bytes = (
            peak_search_nodes * profile.bytes_per_search_node
            + peak_tree_nodes * profile.bytes_per_tree_node
            + costmap_cells * profile.bytes_per_costmap_cell * profile.costmap_layers
        )
        return total_bytes / BYTES_PER_MB + profile.fixed_overhead_mb
    raise MetricError(f"unknown resource profile {type(profile).__name__}")


def _require_matching_ids(trace: LoadedTrace, context: EpisodeContext) -> None:
    if trace.metadata.episode_context_id != context.episode_context_id:
        raise MetricError(
            f"trace {trace.path.name} was recorded under context "
            f"{trace.metadata.episode_context_id} but is being scored against "
            f"{context.episode_context_id}; the metrics would describe one episode using "
            "another episode's mission and seed"
        )


def _mission_of(profile: TaskProfile, context: EpisodeContext) -> Mission:
    for mission in profile.missions:
        if mission.id == context.mission_id:
            return mission
    raise MetricError(
        f"task profile {profile.id!r} has no mission {context.mission_id!r}; the trace was "
        "produced under a different profile than the one being used to score it"
    )


def _goal_reached(
    events: Sequence[str | None],
    final: Point2D,
    final_theta: float,
    mission: Mission,
    profile: TaskProfile,
) -> bool:
    """Did the episode end at the goal, by *this profile's* tolerance?

    Both the recorded ``goal_reached`` event and the geometry have to
    say yes, and the two disagreeing is only an error in one direction.

    *Claimed but not within tolerance* is refused: the run judged arrival
    against a threshold other than the profile's — a hardcoded tolerance,
    which HĐ-7 forbids — and the result is a success rate nobody can
    reproduce from the stored data.

    *Within tolerance but not claimed* is legitimate and common: a robot
    can time out or be stopped while standing near its goal. The run's
    verdict stands; drifting within a tolerance of the goal is not
    arriving.
    """
    declared = "goal_reached" in events
    tolerance_m = profile.constraints.goal_tolerance_m
    tolerance_rad = profile.constraints.goal_tolerance_rad
    within = (
        math.dist((final.x, final.y), (mission.goal.x, mission.goal.y)) <= tolerance_m
        and abs(normalize_angle(final_theta - mission.goal.theta)) <= tolerance_rad
    )
    if declared and not within:
        raise MetricError(
            f"trace claims goal_reached but the final pose is outside the profile's "
            f"tolerance ({tolerance_m} m, {tolerance_rad} rad) of mission {mission.id!r}. "
            "The episode was judged against a different tolerance than the deployment "
            "declares (HĐ-7)"
        )
    return declared and within


def _failure_reason(
    events: Sequence[str | None], timed_out: bool, collision_count: int
) -> FailureReason:
    """Why the episode failed, in HĐ-6's four buckets.

    Ordered by what a reader has to act on first: a collision outranks a
    timeout because "it crashed, then ran out of time" is a crash.
    """
    if collision_count:
        return "collision"
    if "no_path" in events:
        return "no_path"
    if timed_out:
        return "timeout"
    if "stuck" in events:
        return "stuck"
    # No terminal event at all: the episode was cut short by something
    # outside the candidate's control. Reported as stuck rather than
    # invented as a new bucket — HĐ-6 fixes the four.
    return "stuck"


def _polyline_length(xs: Sequence[float], ys: Sequence[float]) -> float:
    return float(sum(math.dist((xs[i], ys[i]), (xs[i + 1], ys[i + 1])) for i in range(len(xs) - 1)))


def _near_miss_rate(
    clearances: Sequence[float], path_length_m: float, profile: TaskProfile
) -> float:
    """Near misses per metre driven (HĐ-6).

    A robot that never moved has no near-miss *rate*: the denominator is
    zero, and reporting 0.0 would score standing still as perfectly safe.
    Reported as the count instead would change the unit. So a stationary
    episode gets 0.0 only when it also had no near miss; otherwise the
    count is spread over one metre, which is the most pessimistic
    reading the data supports — and the safe direction for a safety
    metric.
    """
    threshold = profile.constraints.clearance_warning_m
    count = sum(1 for value in clearances if value < threshold)
    if path_length_m <= 0.0:
        return float(count)
    return count / path_length_m


def _ratio(reference: float, actual: float) -> float:
    """``reference / actual``, clipped to [0, 1] with a stated reason.

    Both efficiency metrics are ratios of an optimum to what happened, so
    they live in (0, 1] by construction — unless the robot never moved
    (``actual = 0``), where the episode achieved none of the optimum and
    the honest value is 0.0. Values above 1 mean the reference is wrong,
    not that the candidate beat physics; they are clipped here and caught
    by HĐ-15.1's acceptance criterion, which compares the raw numbers.
    """
    if actual <= 0.0:
        return 0.0
    return min(reference / actual, 1.0)


def _smoothness(thetas: Sequence[float]) -> float:
    """``Σ (Δθ_i)²`` over consecutive headings, in rad².

    Heading differences are normalised: without it a robot crossing the
    ±π wrap once would add ~39 rad² of "roughness" for driving straight.
    """
    return float(
        sum(normalize_angle(thetas[i + 1] - thetas[i]) ** 2 for i in range(len(thetas) - 1))
    )


def _stop_and_go_count(speeds: Sequence[float]) -> int:
    """Times the robot stopped and started again.

    The initial standstill is not a stop: every episode begins at rest,
    and counting it would give a constant offset that says nothing about
    the controller.
    """
    count = 0
    moving = False
    ever_moved = False
    for speed in speeds:
        if abs(speed) > STOP_SPEED_EPS:
            if ever_moved and not moving:
                count += 1
            moving = True
            ever_moved = True
        else:
            moving = False
    return count
