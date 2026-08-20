"""Comparing two candidates while an episode plays — E4.3.

The decision page could show two columns of end-of-episode numbers and
leave the subtraction to the reader. What it could not do is answer the
question somebody actually has while scrubbing a replay: *right now, who
is doing better, and at what?*

**The clock is the whole design.** At one wall-clock instant the two
robots are at different places on the task, so a single "comparison at
time t" is two different questions wearing one label:

``at equal time``
    who is **ahead** — progress, replans so far, compute against budget.
``at equal progress``
    who did the **same work** better — how long it took to get here, the
    worst clearance on the way, how straight the route was.

Comparing worst-clearance at equal *time* compares two different parts
of the map, and the number that comes out is not about either
candidate. So every metric here declares which clock it belongs to, and
the two are never mixed in one row.

**Nothing here invents a score.** The composite reuses
:func:`~planbench_decision.objectives._safety` and ``_efficiency`` — the
platform's own objective curves, resolved against this deployment's own
anchors — fed with prefix versions of the same four inputs the episode
metrics use. A second scoring path computing "roughly U_S" is exactly
the parallel source this codebase refuses everywhere else, and it would
disagree with the card the first time an anchor moved.

**The composite is not ΔU, and is not labelled as one.** ``U_R`` is
*did it reach the goal*, which has no value halfway through an episode;
a prefix ΔU would invent one, and it inverts — a candidate behind at ten
seconds can win the episode. What is shown is the deployment's own
trade-off between safety and efficiency over *the part that has
happened*, with the weights renormalised over the two objectives that
are defined on a prefix. At the terminal step the caller replaces it
with the episode's stored ``episode_decision_utility``, which is the
real number over all four — and is authoritative, because the running
value measures efficiency against the replay's reference line rather
than against ``L_ref``. See :func:`partial_utility`.

**Every quantity is dimensionless or normalised to something the
deployment declared**, so the same schema reads the same way in every
episode and for every algorithm. Nothing reads a planner-specific
counter — no expanded nodes, no tree size, which A* and RRT* and an
end-to-end policy do not share. Compute is measured as latency against
``T_cycle``, which every stack pays.
"""

from __future__ import annotations

from bisect import insort
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_decision.objectives import DecisionSettings, ResolvedAnchors, _efficiency, _safety

#: Which clock a quantity may be compared on. Carried on the schema
#: rather than left to a reader, because the wrong pairing produces a
#: number that looks fine and means nothing.
TIME_SYNC_METRICS: tuple[str, ...] = ("progress_fraction", "progress_rate", "compute_budget")
PROGRESS_SYNC_METRICS: tuple[str, ...] = (
    "elapsed_s",
    "safety_margin",
    "exposure_s",
    "path_efficiency",
)


class RunningMetricsRefusal(ValueError):
    """A running comparison that cannot honestly be computed."""


class TraceSlice(BaseModel):
    """One candidate's episode, in the columns these metrics need.

    A slice rather than a trace object: this module is fed by whoever
    already read the Parquet, and taking the file itself would put an
    I/O dependency in the one layer that is supposed to be pure.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_id: str = Field(min_length=1)
    t: tuple[float, ...]
    x: tuple[float, ...]
    y: tuple[float, ...]
    clearance_m: tuple[float, ...]
    planner_latency_ms: tuple[float, ...]
    #: Arc length along the shared reference line at each sample, from
    #: the E2 projection. Supplied rather than computed here for the
    #: reason the projection is server-side at all: one implementation.
    progress_m: tuple[float, ...]
    #: Trace row indices that carry a ``replan`` event.
    replan_indices: tuple[int, ...] = ()

    @model_validator(mode="after")
    def _columns_agree(self) -> TraceSlice:
        """Every column indexed in lockstep, or none of them.

        These metrics read ``clearance_m[step]`` at a row chosen from
        ``t``, so a short column is an ``IndexError`` at best and, when
        it is merely shorter than the row asked for, a reading of the
        wrong instant. A trace whose columns disagree is not a trace
        this can measure — and the caller reads the columns out of a
        payload with ``.get(name, [])``, so an absent one arrives here
        as empty rather than as an error at the source.
        """
        lengths = {
            "t": len(self.t),
            "x": len(self.x),
            "y": len(self.y),
            "clearance_m": len(self.clearance_m),
            "planner_latency_ms": len(self.planner_latency_ms),
            "progress_m": len(self.progress_m),
        }
        if len(set(lengths.values())) > 1:
            detail = ", ".join(f"{name}={count}" for name, count in lengths.items())
            raise RunningMetricsRefusal(
                f"{self.candidate_id}: trace columns disagree in length ({detail}); "
                "reading one column at another's row index would report a different "
                "moment of the episode than the one asked for"
            )
        return self


class Deployment(BaseModel):
    """The thresholds the numbers are normalised against.

    All declared by the deployment, none by a candidate — the same rule
    that keeps a stack from choosing its own exam.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    robot_radius_m: float = Field(gt=0)
    #: G4's own budget. Latency is reported as a fraction of it, so 0.8
    #: means the same thing in every episode.
    control_period_s: float = Field(gt=0)
    clearance_warning_m: float = Field(ge=0)
    #: Straight-line-optimal speed, for the time-efficiency reference.
    max_linear_velocity: float = Field(gt=0)
    reference_length_m: float = Field(gt=0)


class RunningSample(BaseModel):
    """One candidate's standing at one point of the episode."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    #: 0–1 along the reference line. The task, as a fraction done.
    progress_fraction: float = Field(ge=0.0)
    #: Metres of progress per second, over a trailing window. Distinct
    #: from speed: a robot oscillating at full speed has speed and no
    #: progress rate, and the difference is the whole point.
    progress_rate: float
    elapsed_s: float = Field(ge=0.0)
    #: Worst clearance **so far**, in robot radii. A running minimum
    #: rather than the current value: safety is a worst case, and a
    #: number that recovers after a near miss forgets the near miss.
    safety_margin: float
    #: Cumulative seconds spent inside the deployment's warning
    #: distance. One brief dip and thirty seconds of hugging a wall are
    #: different episodes, and a minimum alone cannot tell them apart.
    exposure_s: float = Field(ge=0.0)
    #: ``p99`` of planner latency so far, over ``T_cycle``. 1.0 is at
    #: the gate's threshold.
    compute_budget: float = Field(ge=0.0)
    #: Progress over distance actually driven. 1.0 is a straight line.
    path_efficiency: float = Field(ge=0.0, le=1.0)
    replans: int = Field(ge=0)


class RunningComparison(BaseModel):
    """Both candidates at one point, and the composite between them."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    a: RunningSample
    b: RunningSample
    #: The deployment's safety-versus-efficiency trade-off over what has
    #: happened, as ``A − B``. **Not ΔU** — see the module docstring.
    partial_advantage: float
    #: Which objectives went into it. Present so a reader is never left
    #: to assume it was all four.
    partial_objectives: tuple[str, ...] = ("U_S", "U_E")


def _index_at_time(times: Sequence[float], moment: float) -> int | None:
    """The last sample at or before ``moment``. ``None`` before the first."""
    if not times or moment < times[0]:
        return None
    low, high = 0, len(times) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if times[middle] <= moment:
            low = middle
        else:
            high = middle - 1
    return low


def _index_at_progress(progress: Sequence[float], reached: float) -> int | None:
    """The first sample at or past ``reached``. ``None`` if never reached.

    Forward-only: a run that slid backwards along the reference line
    would otherwise report having reached a rung twice, and the second
    reading would be the slower one.
    """
    for index, value in enumerate(progress):
        if value >= reached:
            return index
    return None


def _driven_distance(slice_: TraceSlice, upto: int) -> float:
    total = 0.0
    for index in range(1, upto + 1):
        total += (
            (slice_.x[index] - slice_.x[index - 1]) ** 2
            + (slice_.y[index] - slice_.y[index - 1]) ** 2
        ) ** 0.5
    return total


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile. Matches how G4 pools latency."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(fraction * len(ordered)))))
    return ordered[rank - 1]


def sample_series(
    slice_: TraceSlice,
    *,
    deployment: Deployment,
    rate_window_s: float = 2.0,
) -> tuple[RunningSample, ...]:
    """Every row of one candidate's episode, in one pass.

    **The single implementation of these eight numbers.**
    :func:`sample_at` indexes into this rather than recomputing, because
    two functions producing "the running minimum clearance" is two
    definitions free to drift — and the drift would be invisible: both
    would render, both would look like clearances.

    The series exists because the decision page shows these under each
    canvas at whatever moment the scrubber is on, which is a value per
    trace row, not a value per rung of the progress ladder. Computing it
    row by row through a prefix-scanning ``sample_at`` would be
    quadratic in the trace length; the accumulators here carry forward
    instead.
    """
    if not slice_.t:
        raise RunningMetricsRefusal(f"{slice_.candidate_id} has no samples")

    out: list[RunningSample] = []
    driven = 0.0
    worst = slice_.clearance_m[0]
    exposure = 0.0
    # Nearest-rank p99 over the prefix. Kept sorted by insertion rather
    # than re-sorted per row: the same number G4 pools, arrived at in
    # linear-ish time.
    latencies: list[float] = []
    # Trailing edge of the rate window, walked forward rather than
    # searched: the window only ever moves one way.
    earlier = 0
    replans = 0
    replan_at = sorted(slice_.replan_indices)
    next_replan = 0

    for index in range(len(slice_.t)):
        if index > 0:
            driven += (
                (slice_.x[index] - slice_.x[index - 1]) ** 2
                + (slice_.y[index] - slice_.y[index - 1]) ** 2
            ) ** 0.5
            # Exposure is measured in seconds, not samples: a control
            # loop that ticks twice as often would otherwise look twice
            # as exposed.
            if slice_.clearance_m[index] < deployment.clearance_warning_m:
                exposure += slice_.t[index] - slice_.t[index - 1]
        worst = min(worst, slice_.clearance_m[index])
        if slice_.planner_latency_ms[index] > 0.0:
            insort(latencies, slice_.planner_latency_ms[index])
        while next_replan < len(replan_at) and replan_at[next_replan] <= index:
            replans += 1
            next_replan += 1

        cutoff = slice_.t[index] - rate_window_s
        while earlier + 1 <= index and slice_.t[earlier + 1] <= cutoff:
            earlier += 1

        progress = slice_.progress_m[index]
        window = slice_.t[index] - slice_.t[earlier]
        rate = (progress - slice_.progress_m[earlier]) / window if window > 0 else 0.0
        efficiency = min(progress / driven, 1.0) if driven > 0 else 0.0

        out.append(
            RunningSample(
                progress_fraction=min(progress / deployment.reference_length_m, 1.0),
                progress_rate=rate,
                elapsed_s=slice_.t[index] - slice_.t[0],
                safety_margin=worst / deployment.robot_radius_m,
                exposure_s=exposure,
                compute_budget=_percentile(latencies, 0.99)
                / (deployment.control_period_s * 1000.0),
                path_efficiency=efficiency,
                replans=replans,
            )
        )
    return tuple(out)


def sample_at(
    slice_: TraceSlice,
    index: int,
    *,
    deployment: Deployment,
    rate_window_s: float = 2.0,
) -> RunningSample:
    """One candidate's standing at trace row ``index``.

    A lookup into :func:`sample_series`, not a second derivation. Rows
    past either end clamp, so a caller holding a scrubber position does
    not have to bounds-check what the platform can bound itself.
    """
    series = sample_series(slice_, deployment=deployment, rate_window_s=rate_window_s)
    return series[max(0, min(index, len(series) - 1))]


def partial_utility(
    slice_: TraceSlice,
    index: int,
    *,
    deployment: Deployment,
    settings: DecisionSettings,
    anchors: ResolvedAnchors,
) -> float:
    """The deployment's own U_S and U_E over the episode so far.

    Computed by calling the platform's objective functions with prefix
    versions of the four inputs they already take — running minimum
    clearance, near misses per metre driven, progress over distance
    driven, and ideal-time over elapsed.

    **Two of those four are prefix analogues, not the same quantity.**
    The episode metrics measure efficiency against ``L_ref``, the
    shortest route the map allows between the mission's start and goal.
    This measures it against progress along the **reference line the
    replay is synchronised on**, which E2 takes from the planned path
    and, failing that, from a candidate's own trajectory. Where the two
    lines differ the ratios differ with them, so this number tracks the
    episode's and does not converge to it exactly.

    That is why the caller replaces it at the terminal step with the
    stored ``episode_decision_utility`` rather than letting the running
    value stand as the answer. Saying it converges would have been the
    easier docstring and the wrong one.

    The weights are the deployment's ``w_s`` and ``w_e``, renormalised
    over the two: leaving them at their four-objective values would
    report a number that cannot reach 1 and would look like every
    candidate underperforming.
    """
    if not slice_.t:
        raise RunningMetricsRefusal(f"{slice_.candidate_id} has no samples")
    index = max(0, min(index, len(slice_.t) - 1))

    driven = _driven_distance(slice_, index)
    progress = slice_.progress_m[index]
    elapsed = slice_.t[index] - slice_.t[0]

    clearances = slice_.clearance_m[: index + 1]
    near_misses = sum(1 for value in clearances if value < deployment.clearance_warning_m)
    # The platform's own convention: a stationary robot with a near miss
    # gets the count spread over one metre rather than a zero
    # denominator, which is the most pessimistic reading the data
    # supports and the safe direction for a safety metric.
    near_miss_rate = near_misses / driven if driven > 0 else float(near_misses)

    path_efficiency = min(progress / driven, 1.0) if driven > 0 else 0.0
    ideal = progress / deployment.max_linear_velocity
    time_efficiency = min(ideal / elapsed, 1.0) if elapsed > 0 else 0.0

    u_s = _safety(anchors, near_miss_rate, min(clearances) if clearances else 0.0)
    u_e = _efficiency(anchors, settings, path_efficiency, time_efficiency)

    weights = settings.weights
    total = weights.w_s + weights.w_e
    if total <= 0:
        raise RunningMetricsRefusal(
            "this deployment gives safety and efficiency no weight at all, so there is "
            "nothing to compare over the part of an episode that has happened"
        )
    return (weights.w_s * u_s + weights.w_e * u_e) / total


def compare_at_time(
    a: TraceSlice,
    b: TraceSlice,
    moment: float,
    *,
    deployment: Deployment,
    settings: DecisionSettings,
    anchors: ResolvedAnchors,
) -> RunningComparison | None:
    """Both candidates at one wall-clock instant. ``None`` before both start.

    The honest reading of this pairing is *who is ahead*. Read
    ``safety_margin`` off it and the comparison is between two different
    parts of the map — use :func:`compare_at_progress` for that.
    """
    index_a = _index_at_time(a.t, moment)
    index_b = _index_at_time(b.t, moment)
    if index_a is None or index_b is None:
        return None
    return RunningComparison(
        a=sample_at(a, index_a, deployment=deployment),
        b=sample_at(b, index_b, deployment=deployment),
        partial_advantage=(
            partial_utility(a, index_a, deployment=deployment, settings=settings, anchors=anchors)
            - partial_utility(
                b, index_b, deployment=deployment, settings=settings, anchors=anchors
            )
        ),
    )


def compare_at_progress(
    a: TraceSlice,
    b: TraceSlice,
    reached_m: float,
    *,
    deployment: Deployment,
    settings: DecisionSettings,
    anchors: ResolvedAnchors,
) -> RunningComparison | None:
    """Both candidates at the same point of the task. ``None`` if either never got there.

    This is the pairing that makes safety and efficiency comparable:
    same stretch of the world, same obstacles met, and the difference is
    what the two stacks did about them.
    """
    index_a = _index_at_progress(a.progress_m, reached_m)
    index_b = _index_at_progress(b.progress_m, reached_m)
    if index_a is None or index_b is None:
        return None
    return RunningComparison(
        a=sample_at(a, index_a, deployment=deployment),
        b=sample_at(b, index_b, deployment=deployment),
        partial_advantage=(
            partial_utility(a, index_a, deployment=deployment, settings=settings, anchors=anchors)
            - partial_utility(
                b, index_b, deployment=deployment, settings=settings, anchors=anchors
            )
        ),
    )
