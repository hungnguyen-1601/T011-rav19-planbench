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

from statistics import fmean

from pydantic import BaseModel, ConfigDict, Field

from planbench_api.approval import BenchmarkState
from planbench_api.repositories import StoredBenchmark
from planbench_benchmark import (
    AlgorithmAggregate,
    ObservationClass,
    list_algorithms,
    load_difficulty_cache,
    scenario_split,
)
from planbench_metrics.statistics import average_rank


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
    #: What the stack was allowed to see (spec section 8.6b, P02).
    #: None for an algorithm id no longer in the registry (a report from
    #: a stack that has since been removed) — the leaderboard must still
    #: render old results, just without a class to group them by.
    observation_class: ObservationClass | None = None


class LeaderboardGroup(BaseModel):
    """Entries that are genuinely comparable (identical conditions)."""

    model_config = ConfigDict(frozen=True)

    conditions_checksum: str
    map_name: str
    scenario_name: str
    seeds: tuple[int, ...]
    entries: tuple[LeaderboardEntry, ...]
    #: True when this group's entries do not all share one
    #: observation_class (spec section 8.6b) — cross-class comparison is
    #: still shown, never hidden, but flagged so a reader does not read
    #: "DWA beat the privileged planner" as an apples-to-apples result.
    mixed_observation_classes: bool = False


class Leaderboard(BaseModel):
    model_config = ConfigDict(frozen=True)

    weights: ScoreWeights
    score_formula: str
    groups: tuple[LeaderboardGroup, ...]
    #: Average rank per algorithm across every group it appears in (spec
    #: section 8.6a) — lets "algorithm X averaged rank 1.8 across 5
    #: scenarios" be said even though raw metrics are not comparable
    #: across scenarios. None when there are no groups yet.
    algorithm_ranks: dict[str, float] | None = None
    #: mean(success_rate on dev scenarios) - mean(success_rate on
    #: holdout scenarios), per algorithm (spec section 8.6e, P05). Only
    #: for algorithms with accepted results in both splits; a large gap
    #: means the algorithm (or its tuning) overfit the dev scenarios.
    generalization_gap: dict[str, float] | None = None
    #: (difficulty, success_rate) points per algorithm, sorted by
    #: difficulty, built from scenarios that have been calibrated (spec
    #: section 8.6d, P03 — see scripts/calibrate_difficulty.py). Empty
    #: for a scenario with no calibration cached yet.
    difficulty_curve: dict[str, list[tuple[float, float]]] | None = None

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
    if aggregate.mean_smoothness_successful is not None:
        parts.append((weights.smoothness, 1.0 - _clamp(aggregate.mean_smoothness_successful)))
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
    observation_classes = {info.id: info.observation_class for info in list_algorithms()}
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
                    observation_class=observation_classes.get(aggregate.algorithm),
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
        classes = {entry.observation_class for entry in ranked if entry.observation_class}
        ordered.append(
            LeaderboardGroup(
                conditions_checksum=checksum,
                map_name=map_name,
                scenario_name=scenario,
                seeds=seeds,
                entries=tuple(ranked),
                mixed_observation_classes=len(classes) > 1,
            )
        )
    return Leaderboard(
        weights=weights,
        score_formula=SCORE_FORMULA,
        groups=tuple(ordered),
        algorithm_ranks=_algorithm_ranks(ordered) or None,
        generalization_gap=_generalization_gap(ordered) or None,
        difficulty_curve=_difficulty_curve(ordered) or None,
    )


def _algorithm_ranks(groups: list[LeaderboardGroup]) -> dict[str, float]:
    """Average rank per algorithm across every group (scenario) it
    appears in — spec section 8.6a."""
    scores_by_group = [
        {entry.algorithm: entry.overall_score for entry in group.entries if entry.overall_score is not None}
        for group in groups
    ]
    return average_rank(scores_by_group)


def _generalization_gap(groups: list[LeaderboardGroup]) -> dict[str, float]:
    """mean(success_rate on dev) - mean(success_rate on holdout), per
    algorithm — spec section 8.6e. Only for algorithms with at least one
    accepted result in each split."""
    dev_rates: dict[str, list[float]] = {}
    holdout_rates: dict[str, list[float]] = {}
    for group in groups:
        bucket = holdout_rates if scenario_split(group.scenario_name) == "holdout" else dev_rates
        for entry in group.entries:
            bucket.setdefault(entry.algorithm, []).append(entry.success_rate)
    return {
        algorithm: fmean(dev_rates[algorithm]) - fmean(holdout_rates[algorithm])
        for algorithm in dev_rates
        if algorithm in holdout_rates
    }


def _difficulty_curve(groups: list[LeaderboardGroup]) -> dict[str, list[tuple[float, float]]]:
    """(difficulty, success_rate) points per algorithm, sorted by
    difficulty — spec section 8.6d. Only scenarios with a cached
    calibration (scripts/calibrate_difficulty.py) contribute a point."""
    cache = load_difficulty_cache()
    points: dict[str, list[tuple[float, float]]] = {}
    for group in groups:
        calibrated = cache.get(group.scenario_name)
        if calibrated is None:
            continue
        for entry in group.entries:
            points.setdefault(entry.algorithm, []).append(
                (calibrated.difficulty, entry.success_rate)
            )
    return {
        algorithm: sorted(series, key=lambda point: point[0]) for algorithm, series in points.items()
    }
