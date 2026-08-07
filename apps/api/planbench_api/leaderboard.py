"""Leaderboard: rank stacks across accepted benchmark reports.

Only reports whose benchmark reached ``ACCEPTED`` count — a leaderboard
built from unreviewed runs would let anyone publish a favourable number
without a Reviewer ever seeing it (spec section 21).

Rows are grouped by ``conditions_checksum``: entries under different
checksums faced different maps, scenarios or seeds and are **not**
comparable. The API returns the group so a client can never mix them
silently.

The optional overall score is a transparent weighted sum of normalized
components; the weights travel with the response and the trade-offs stay
visible (spec section 17). It is never the only number shown.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_api.approval import BenchmarkState
from planbench_api.repositories import StoredBenchmark
from planbench_benchmark import AlgorithmAggregate


class ScoreWeights(BaseModel):
    """Weights for the optional overall score. Higher weight = matters more."""

    model_config = ConfigDict(frozen=True)

    success: float = Field(default=0.40, ge=0)
    safety: float = Field(default=0.30, ge=0)
    efficiency: float = Field(default=0.20, ge=0)
    smoothness: float = Field(default=0.10, ge=0)

    @property
    def total(self) -> float:
        return self.success + self.safety + self.efficiency + self.smoothness


class LeaderboardEntry(BaseModel):
    """One stack's standing under one set of conditions."""

    model_config = ConfigDict(frozen=True)

    algorithm: str
    benchmark_id: str
    benchmark_name: str
    conditions_checksum: str
    map_name: str
    scenario_name: str
    episodes: int
    success_rate: float
    collision_rate: float
    mean_travel_time: float | None
    mean_path_efficiency: float | None
    mean_smoothness: float | None
    worst_min_clearance: float | None
    mean_local_planning_latency: float | None
    overall_score: float | None


class LeaderboardGroup(BaseModel):
    """Entries that are genuinely comparable (identical conditions)."""

    model_config = ConfigDict(frozen=True)

    conditions_checksum: str
    map_name: str
    scenario_name: str
    seeds: tuple[int, ...]
    entries: tuple[LeaderboardEntry, ...]


class Leaderboard(BaseModel):
    model_config = ConfigDict(frozen=True)

    weights: ScoreWeights
    score_formula: str
    groups: tuple[LeaderboardGroup, ...]

    @property
    def total_entries(self) -> int:
        return sum(len(group.entries) for group in self.groups)


SCORE_FORMULA = (
    "score = (w_success * success_rate "
    "+ w_safety * clamp(worst_min_clearance / robot_radius, 0, 1) "
    "+ w_efficiency * clamp(mean_path_efficiency, 0, 1) "
    "+ w_smoothness * (1 - clamp(mean_smoothness, 0, 1))) / sum(weights); "
    "components missing for an algorithm are dropped and the weights "
    "renormalized, so a stack is never rewarded for missing data."
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def overall_score(
    aggregate: AlgorithmAggregate, robot_radius: float, weights: ScoreWeights
) -> float | None:
    """Weighted, normalized score in [0, 1]; None when nothing is scorable."""
    parts: list[tuple[float, float]] = [(weights.success, aggregate.success_rate)]
    if aggregate.worst_min_clearance is not None and robot_radius > 0:
        parts.append((weights.safety, _clamp(aggregate.worst_min_clearance / robot_radius)))
    if aggregate.mean_path_efficiency_successful is not None:
        parts.append((weights.efficiency, _clamp(aggregate.mean_path_efficiency_successful)))
    # per_metre, không phải smoothness thô: điểm số kẹp giá trị vào
    # [0, 1], mà tổng bình phương chưa chuẩn hóa thì vượt 1 ở gần như
    # mọi episode — mọi stack sẽ cùng được 0 ở trục này và trọng số
    # smoothness thành vô nghĩa.
    if aggregate.mean_smoothness_per_metre_successful is not None:
        parts.append(
            (weights.smoothness, 1.0 - _clamp(aggregate.mean_smoothness_per_metre_successful))
        )
    weight_sum = sum(weight for weight, _ in parts)
    if weight_sum <= 0:
        return None
    return sum(weight * value for weight, value in parts) / weight_sum


def build_leaderboard(
    benchmarks: list[StoredBenchmark],
    weights: ScoreWeights | None = None,
    *,
    scenario_name: str | None = None,
    algorithm: str | None = None,
    accepted_only: bool = True,
) -> Leaderboard:
    """Rank accepted benchmark results, grouped by identical conditions."""
    weights = weights or ScoreWeights()
    groups: dict[str, list[LeaderboardEntry]] = {}
    metadata: dict[str, tuple[str, str, tuple[int, ...]]] = {}

    for stored in benchmarks:
        if stored.report is None:
            continue
        if accepted_only and stored.state is not BenchmarkState.ACCEPTED:
            continue
        fairness = stored.report.fairness
        if scenario_name and fairness.scenario_name != scenario_name:
            continue
        checksum = fairness.conditions_checksum
        metadata[checksum] = (fairness.map_name, fairness.scenario_name, fairness.seeds)
        for aggregate in stored.report.aggregates:
            if algorithm and aggregate.algorithm != algorithm:
                continue
            groups.setdefault(checksum, []).append(
                LeaderboardEntry(
                    algorithm=aggregate.algorithm,
                    benchmark_id=stored.id,
                    benchmark_name=stored.spec.name,
                    conditions_checksum=checksum,
                    map_name=fairness.map_name,
                    scenario_name=fairness.scenario_name,
                    episodes=aggregate.episodes,
                    success_rate=aggregate.success_rate,
                    collision_rate=aggregate.collision_rate,
                    mean_travel_time=aggregate.mean_travel_time_successful,
                    mean_path_efficiency=aggregate.mean_path_efficiency_successful,
                    mean_smoothness=aggregate.mean_smoothness_successful,
                    worst_min_clearance=aggregate.worst_min_clearance,
                    mean_local_planning_latency=aggregate.mean_local_planning_latency,
                    overall_score=overall_score(aggregate, fairness.robot_radius, weights),
                )
            )

    ordered = []
    for checksum, entries in sorted(groups.items()):
        map_name, scenario, seeds = metadata[checksum]
        ranked = sorted(
            entries,
            key=lambda entry: (
                -(entry.overall_score if entry.overall_score is not None else -1.0),
                -entry.success_rate,
                entry.mean_travel_time if entry.mean_travel_time is not None else float("inf"),
            ),
        )
        ordered.append(
            LeaderboardGroup(
                conditions_checksum=checksum,
                map_name=map_name,
                scenario_name=scenario,
                seeds=seeds,
                entries=tuple(ranked),
            )
        )
    return Leaderboard(weights=weights, score_formula=SCORE_FORMULA, groups=tuple(ordered))
