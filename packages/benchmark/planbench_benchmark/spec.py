"""Benchmark contract: spec, per-run records, aggregates, fairness proof."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from planbench_benchmark.observation import ObservationClass
from planbench_benchmark.scenario_protocol import ScenarioSplit
from planbench_metrics import EpisodeMetrics
from planbench_metrics.statistics import statistically_adequate as _statistically_adequate
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.map import MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.scenario import Scenario

BENCHMARK_SPEC_VERSION = "1"


class AlgorithmSpec(BaseModel):
    """One stack under test plus its configuration overrides."""

    model_config = ConfigDict(frozen=True)

    id: str
    config: dict = Field(default_factory=dict)


class BenchmarkSpec(BaseModel):
    """What to run. Every algorithm sees exactly these conditions.

    ``seeds`` drives every stochastic component (dynamic obstacles,
    sampling planners, RL policies). The list is shared by all
    algorithms so runs are paired seed-by-seed.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    algorithms: tuple[AlgorithmSpec, ...] = Field(min_length=1)
    seeds: tuple[int, ...] = Field(min_length=1)
    spec_version: str = BENCHMARK_SPEC_VERSION
    #: Whether a blocked robot may ask for a new global path, and how
    #: often. One rule for the whole benchmark, deliberately: replanning
    #: sits here rather than in ``AlgorithmSpec.config`` so it cannot be
    #: granted to one stack and withheld from another. Disabled by
    #: default, and a disabled benchmark hashes exactly as it did before
    #: the field existed.
    replanning: ReplanningConfig = NO_REPLANNING

    @model_validator(mode="after")
    def _validate(self) -> BenchmarkSpec:
        ids = [algorithm.id for algorithm in self.algorithms]
        duplicates = {value for value in ids if ids.count(value) > 1}
        if duplicates:
            raise ValueError(f"duplicate algorithms in benchmark: {sorted(duplicates)}")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        return self


class FairnessRecord(BaseModel):
    """Evidence that all algorithms ran under identical conditions.

    ``conditions_checksum`` hashes everything that is *not* the
    algorithm: map content, scenario parameters and the seed list. Two
    benchmark reports with the same checksum are directly comparable;
    different checksums mean the comparison is invalid.
    """

    model_config = ConfigDict(frozen=True)

    map_name: str
    map_checksum: str
    scenario_name: str
    scenario_checksum: str
    seeds: tuple[int, ...]
    timeout_seconds: float
    simulation_dt: float
    robot_radius: float
    max_linear_velocity: float
    max_angular_velocity: float
    lidar_num_rays: int
    lidar_max_range: float
    #: The replanning rule every algorithm ran under. Part of the
    #: conditions, not of any algorithm: a stack allowed three replans is
    #: solving an easier problem than one allowed none, and a report that
    #: does not state which was in force cannot be checked.
    replanning_enabled: bool = False
    max_replans: int = 0
    conditions_checksum: str

    @staticmethod
    def build(
        map_data: MapData,
        scenario: Scenario,
        seeds: tuple[int, ...],
        replanning: ReplanningConfig | None = None,
    ) -> FairnessRecord:
        scenario_checksum = _scenario_checksum(scenario)
        replanning = replanning or NO_REPLANNING
        parts = [
            map_data.checksum(),
            scenario_checksum,
            ",".join(str(seed) for seed in seeds),
        ]
        # Appended only when replanning is actually on. The alternative —
        # always hashing it — would change the checksum of every
        # benchmark ever stored on the day this field shipped, announcing
        # that all previous results had become incomparable when nothing
        # about their conditions had changed.
        if not replanning.is_default:
            parts.append(replanning.checksum_payload())
        payload = "|".join(parts)
        return FairnessRecord(
            map_name=map_data.name,
            map_checksum=map_data.checksum(),
            scenario_name=scenario.name,
            scenario_checksum=scenario_checksum,
            seeds=seeds,
            timeout_seconds=scenario.timeout_seconds,
            simulation_dt=scenario.simulation_dt,
            robot_radius=scenario.robot.radius,
            max_linear_velocity=scenario.robot.max_linear_velocity,
            max_angular_velocity=scenario.robot.max_angular_velocity,
            lidar_num_rays=scenario.lidar.num_rays,
            lidar_max_range=scenario.lidar.max_range,
            replanning_enabled=replanning.enabled,
            max_replans=replanning.max_replans,
            conditions_checksum=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        )


def _scenario_checksum(scenario: Scenario) -> str:
    """Stable hash over everything except the scenario's own seed field.

    The per-run seed is supplied by the benchmark, so a scenario's
    stored ``random_seed`` must not change the fairness identity.
    """
    payload = scenario.model_dump(mode="json", exclude={"random_seed", "description"})
    canonical = _canonical(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{_canonical(v)}" for k, v in sorted(value.items())) + "}"
    if isinstance(value, list | tuple):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    return repr(value)


class RunRecord(BaseModel):
    """One episode of one algorithm at one seed."""

    model_config = ConfigDict(frozen=True)

    algorithm: str
    seed: int
    status: EpisodeStatus
    reason: str
    metrics: EpisodeMetrics
    trajectory_points: int
    episode_index: int


class AlgorithmAggregate(BaseModel):
    """Aggregate over all seeds for one algorithm.

    Rates are over *all* episodes. Values marked ``_successful`` use only
    successful episodes, because travel time and path efficiency are
    undefined for a robot that never arrived — mixing them would reward
    fast failures.

    Read the medians, not the means (P04). Per-seed benchmark numbers are
    skewed: one episode where the robot dithers until the timeout drags
    the mean past anything that actually happened, while the median plus
    its interquartile range says what a typical run looked like and how
    much the runs disagreed. The ``mean_*`` fields are kept because
    stored reports and existing clients read them, and removing a field
    breaks both; they are deprecated, not maintained as the answer.
    """

    model_config = ConfigDict(frozen=True)

    algorithm: str
    episodes: int
    success_rate: float
    collision_rate: float
    timeout_rate: float
    stuck_rate: float
    no_progress_rate: float
    no_global_path_rate: float
    #: Deprecated in favour of ``median_travel_time_successful``. Still
    #: returned, still computed; not the number to quote.
    mean_travel_time_successful: float | None = None
    mean_trajectory_length_successful: float | None = None
    #: Deprecated in favour of ``median_path_efficiency_successful``.
    mean_path_efficiency_successful: float | None = None
    #: Deprecated in favour of ``median_smoothness_successful``.
    mean_smoothness_successful: float | None = None
    mean_min_clearance: float | None = None
    worst_min_clearance: float | None = None
    mean_local_planning_latency: float | None = None
    max_local_planning_latency: float | None = None
    mean_global_planning_time: float | None = None
    #: Information parity snapshot (P02): what this stack was declared to
    #: see *at the time the benchmark ran*. Snapshotted rather than looked
    #: up on read, because a later edit to the registry must not silently
    #: relabel numbers that were produced under the old declaration.
    #:
    #: Nullable only for backward compatibility: reports stored before
    #: P02 carry no declaration, and inventing one for them would be the
    #: fabrication this field exists to prevent. A missing value must be
    #: displayed as unknown, never treated as ``lidar_only``.
    global_observation_class: ObservationClass | None = None
    local_observation_class: ObservationClass | None = None
    requires_global_path: bool | None = None

    #: Robust summaries (P04). ``iqr_*`` is ``(q1, q3)`` — the range the
    #: middle half of the runs fell in — and ``ci95_*`` is a percentile
    #: bootstrap interval for the median itself. The two answer different
    #: questions: the IQR is how much the runs varied, the CI is how well
    #: this many seeds pin the median down. A report that shows one
    #: without the other invites the reader to mistake a tight estimate
    #: of a wildly varying quantity for a consistent algorithm.
    #:
    #: All optional: a stack that never succeeded has no distribution to
    #: describe, a single success has no interval, and reports written
    #: before P04 have none of these. ``None`` means "not computed", and
    #: must be displayed as such rather than as zero.
    median_travel_time_successful: float | None = None
    iqr_travel_time_successful: tuple[float, float] | None = None
    ci95_travel_time_successful: tuple[float, float] | None = None
    median_path_efficiency_successful: float | None = None
    iqr_path_efficiency_successful: tuple[float, float] | None = None
    ci95_path_efficiency_successful: tuple[float, float] | None = None
    median_smoothness_successful: float | None = None
    iqr_smoothness_successful: tuple[float, float] | None = None
    ci95_smoothness_successful: tuple[float, float] | None = None
    #: Wilson score interval for the success rate. Exact rather than
    #: bootstrapped, so it needs no seed and stays inside [0, 1] at the
    #: extremes — where a success rate usually sits, and where a naive
    #: interval would report certainty nobody has after five episodes.
    ci95_success_rate: tuple[float, float] | None = None


class PairwiseComparison(BaseModel):
    """One head-to-head result, with everything needed to discount it.

    Lives in the contract module rather than beside the code that builds
    it (``planbench_benchmark.comparison``) because a stored report
    contains these: the schema has to be importable without pulling in
    the statistics stack.

    ``statistic``, ``p_value`` and ``effect_size`` are all optional. Too
    few paired seeds is a normal outcome of a small benchmark, and the
    honest answer then is "no test was run", not a number carrying a
    footnote nobody reads.
    """

    model_config = ConfigDict(frozen=True)

    algorithm_a: str
    algorithm_b: str
    metric: str
    #: Wilcoxon signed-rank statistic; None when no test was run.
    statistic: float | None = None
    p_value: float | None = None
    #: Cliff's delta of A against B — how big the difference is, not just
    #: how unlikely. Negative means A's values are lower, which for
    #: travel time means A is faster; the metric decides which is better.
    effect_size: float | None = None
    #: Only ever True when a test actually ran on enough pairs.
    significant: bool = False
    #: How many seeds contributed a pair. The headline caveat: "A was
    #: faster on the four seeds where both arrived" is a different claim
    #: from "A was faster".
    paired_seed_count: int = 0
    #: Why the reader should hesitate: dropped seeds, too few pairs,
    #: mismatched seed sets. None when there is nothing to disclose.
    warning: str | None = None


class BenchmarkReport(BaseModel):
    """Full benchmark outcome: conditions, per-run records, aggregates."""

    model_config = ConfigDict(frozen=True)

    spec: BenchmarkSpec
    fairness: FairnessRecord
    runs: tuple[RunRecord, ...]
    aggregates: tuple[AlgorithmAggregate, ...]
    #: Head-to-head tests, paired seed by seed (P04). Empty on reports
    #: written before P04 and on benchmarks with a single algorithm.
    comparisons: tuple[PairwiseComparison, ...] = ()
    #: Evaluation-protocol snapshot (P05): which split this scenario was
    #: in, and under which protocol version, *at the time this benchmark
    #: ran*. Snapshotted rather than resolved on read for the same reason
    #: as the observation classes: promoting a scenario to holdout next
    #: month must not turn last month's dev numbers into holdout numbers.
    #:
    #: ``protocol_version`` is None only on reports stored before P05.
    #: ``scenario_split`` defaults to ``unassigned``, which is also what
    #: those old reports read as — correct, because nobody had classified
    #: anything when they were written.
    protocol_version: str | None = None
    scenario_split: ScenarioSplit = "unassigned"
    #: Dev-minus-holdout, per metric, when one report spans both splits.
    #:
    #: Always None today: a benchmark runs exactly one scenario, so a
    #: single report is entirely one split and has nothing to subtract
    #: from. The generalization gap is computed *across* reports —
    #: ``planbench_benchmark.generalization`` — and the field is here so
    #: that a future multi-scenario benchmark can carry its own gap
    #: without a schema break. A reader must treat None as "not
    #: computed", never as "no gap".
    generalization_gap: dict[str, float] | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def seed_count(self) -> int:
        """How many seeds every algorithm faced.

        Derived from the spec rather than stored, so it is right for
        reports written before this field existed too.
        """
        return len(self.spec.seeds)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def statistically_adequate(self) -> bool:
        """Whether the seed count supports a conclusion, not just a number.

        False does not block anything: a 5-seed benchmark still runs,
        still stores, still displays. It marks the report as evidence
        that a difference is worth investigating rather than evidence
        that one algorithm is better.
        """
        return _statistically_adequate(self.seed_count)
