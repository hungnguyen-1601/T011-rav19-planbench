"""Benchmark contract: spec, per-run records, aggregates, fairness proof."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_metrics import EpisodeMetrics
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.map import MapData
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
    conditions_checksum: str

    @staticmethod
    def build(map_data: MapData, scenario: Scenario, seeds: tuple[int, ...]) -> FairnessRecord:
        scenario_checksum = _scenario_checksum(scenario)
        payload = "|".join(
            [
                map_data.checksum(),
                scenario_checksum,
                ",".join(str(seed) for seed in seeds),
            ]
        )
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

    Rates are over *all* episodes. Means marked ``_successful`` use only
    successful episodes, because travel time and path efficiency are
    undefined for a robot that never arrived — mixing them would reward
    fast failures.
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
    mean_travel_time_successful: float | None = None
    mean_trajectory_length_successful: float | None = None
    mean_path_efficiency_successful: float | None = None
    #: Trung bình của episode.smoothness — công thức đúng theo spec
    #: 8.2, Σ(Δθ)², KHÔNG chuẩn hóa theo độ dài. So sánh nó giữa các
    #: episode dài ngắn khác nhau sẽ lẫn "đường dài" với "đường gồ ghề";
    #: dùng trường dưới cho việc đó.
    mean_smoothness_successful: float | None = None
    #: Trung bình của episode.smoothness_per_metre — Σ|Δθ| chia độ dài,
    #: rad/m. Đây là công thức PlanBench dùng từ đầu, và là trường mà
    #: leaderboard tính điểm, vì chỉ nó mới so sánh được giữa các
    #: episode có độ dài khác nhau.
    mean_smoothness_per_metre_successful: float | None = None
    #: Khoảng tin cậy 95% của success_rate, tính bằng bootstrap. None khi
    #: chỉ có một episode — một điểm dữ liệu không có khoảng tin cậy.
    success_rate_ci95: tuple[float, float] | None = None
    #: Median/IQR thay cho mean/std: metric robot lệch phải, vài episode
    #: chậm kéo trung bình lên mà không đại diện cho lần chạy điển hình.
    median_travel_time_successful: float | None = None
    iqr_travel_time_successful: tuple[float, float] | None = None
    median_path_efficiency_successful: float | None = None
    iqr_path_efficiency_successful: tuple[float, float] | None = None
    mean_min_clearance: float | None = None
    worst_min_clearance: float | None = None
    mean_local_planning_latency: float | None = None
    max_local_planning_latency: float | None = None
    mean_global_planning_time: float | None = None


class PairwiseComparison(BaseModel):
    """One algorithm compared against the run's best performer on
    success (Wilcoxon signed-rank, paired by seed — see
    planbench_metrics.statistics.wilcoxon_compare).

    Absent when there is only one algorithm in the spec, or fewer than
    two seeds (nothing to pair).
    """

    model_config = ConfigDict(frozen=True)

    baseline_algorithm: str
    compared_algorithm: str
    metric: str
    p_value: float
    effect_size: float
    significant: bool


class BenchmarkReport(BaseModel):
    """Full benchmark outcome: conditions, per-run records, aggregates."""

    model_config = ConfigDict(frozen=True)

    spec: BenchmarkSpec
    fairness: FairnessRecord
    runs: tuple[RunRecord, ...]
    aggregates: tuple[AlgorithmAggregate, ...]
    #: So sánh Wilcoxon theo cặp với thuật toán có success cao nhất.
    #: Rỗng khi chỉ có một thuật toán để so.
    comparisons: tuple[PairwiseComparison, ...] = ()
    #: len(spec.seeds) >= 30. Benchmark nhỏ hơn vẫn chạy và vẫn báo cáo
    #: — đây là cảnh báo cho người đọc, không phải chặn.
    statistically_adequate: bool = False
    seed_count: int = 0
