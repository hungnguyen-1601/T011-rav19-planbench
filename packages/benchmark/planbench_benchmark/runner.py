"""Benchmark execution: run every (algorithm, seed) pair fairly.

Fairness rules enforced here:

- All algorithms receive the identical map and scenario object; only
  the per-run seed varies, and the same seed list is used for every
  algorithm (paired comparison).
- A fresh controller instance is built per run, so no state leaks
  between seeds or algorithms.
- The conditions are hashed into a :class:`FairnessRecord` stored with
  the report, so a comparison can be proven valid after the fact.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from statistics import fmean

from planbench_benchmark.registry import build_local_planner
from planbench_benchmark.spec import (
    AlgorithmAggregate,
    AlgorithmSpec,
    BenchmarkReport,
    BenchmarkSpec,
    FairnessRecord,
    PairwiseComparison,
    RunRecord,
)
from planbench_metrics.statistics import bootstrap_ci, median_iqr, wilcoxon_compare
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun, run_stack

logger = logging.getLogger("planbench.benchmark")

#: spec section 8.6a: "≥30 seed mỗi cặp (scenario, algorithm)". Below
#: this, results are still computed and reported — see
#: BenchmarkReport.statistically_adequate — just flagged, not blocked.
MIN_SEEDS_FOR_STATISTICAL_ADEQUACY = 30


def run_single(
    map_data: MapData, scenario: Scenario, algorithm: AlgorithmSpec, seed: int
) -> StackRun:
    """Run one episode of one algorithm at one seed."""
    seeded = scenario.model_copy(update={"random_seed": seed})
    planner = build_local_planner(algorithm.id, algorithm.config)
    return run_stack(map_data, seeded, planner)


def run_benchmark(
    map_data: MapData,
    scenario: Scenario,
    spec: BenchmarkSpec,
    on_run: Callable[[RunRecord, StackRun], None] | None = None,
) -> BenchmarkReport:
    """Execute the whole benchmark sequentially and aggregate results.

    ``on_run`` receives each finished episode — the record plus the full
    :class:`StackRun` (trajectory, events, plan) — so callers can persist
    episodes for replay without re-running anything. It must not mutate
    what it receives.
    """
    fairness = FairnessRecord.build(map_data, scenario, spec.seeds)
    runs: list[RunRecord] = []
    episode_index = 0
    for algorithm in spec.algorithms:
        for seed in spec.seeds:
            stack_run = run_single(map_data, scenario, algorithm, seed)
            record = RunRecord(
                algorithm=algorithm.id,
                seed=seed,
                status=stack_run.result.status,
                reason=stack_run.result.reason,
                metrics=stack_run.metrics,
                trajectory_points=len(stack_run.result.trajectory),
                episode_index=episode_index,
            )
            runs.append(record)
            episode_index += 1
            logger.info(
                "benchmark episode finished",
                extra={
                    "context": {
                        "benchmark": spec.name,
                        "algorithm": algorithm.id,
                        "seed": seed,
                        "status": record.status.value,
                    }
                },
            )
            if on_run is not None:
                on_run(record, stack_run)

    aggregates = tuple(
        aggregate_algorithm(algorithm.id, [r for r in runs if r.algorithm == algorithm.id])
        for algorithm in spec.algorithms
    )
    return BenchmarkReport(
        spec=spec,
        fairness=fairness,
        runs=tuple(runs),
        aggregates=aggregates,
        comparisons=compare_algorithms(spec, runs, aggregates),
        statistically_adequate=len(spec.seeds) >= MIN_SEEDS_FOR_STATISTICAL_ADEQUACY,
        seed_count=len(spec.seeds),
    )


def compare_algorithms(
    spec: BenchmarkSpec, runs: Sequence[RunRecord], aggregates: Sequence[AlgorithmAggregate]
) -> tuple[PairwiseComparison, ...]:
    """Every algorithm compared against the best-success one, paired by
    seed on the binary success indicator.

    Nothing to compare with fewer than two algorithms or fewer than two
    seeds — Wilcoxon needs at least one pair, and one seed is one pair
    with no variation to rank.
    """
    if len(spec.algorithms) < 2 or len(spec.seeds) < 2:
        return ()
    by_algorithm_seed: dict[tuple[str, int], RunRecord] = {
        (run.algorithm, run.seed): run for run in runs
    }
    baseline = max(aggregates, key=lambda aggregate: aggregate.success_rate).algorithm

    def successes(algorithm: str) -> list[float]:
        return [
            1.0 if by_algorithm_seed[(algorithm, seed)].status is EpisodeStatus.SUCCESS else 0.0
            for seed in spec.seeds
        ]

    baseline_successes = successes(baseline)
    comparisons = []
    for algorithm in spec.algorithms:
        if algorithm.id == baseline:
            continue
        result = wilcoxon_compare(baseline_successes, successes(algorithm.id))
        comparisons.append(
            PairwiseComparison(
                baseline_algorithm=baseline,
                compared_algorithm=algorithm.id,
                metric="success",
                p_value=result.p_value,
                effect_size=result.effect_size,
                significant=result.significant,
            )
        )
    return tuple(comparisons)


def aggregate_algorithm(algorithm_id: str, runs: Sequence[RunRecord]) -> AlgorithmAggregate:
    """Aggregate one algorithm's runs (see AlgorithmAggregate for semantics)."""
    episodes = len(runs)
    if episodes == 0:
        raise ValueError(f"no runs to aggregate for {algorithm_id!r}")

    def rate(status: EpisodeStatus) -> float:
        return sum(1 for run in runs if run.status is status) / episodes

    successful = [run for run in runs if run.status is EpisodeStatus.SUCCESS]

    def mean_of(values: list[float]) -> float | None:
        return fmean(values) if values else None

    clearances = [
        run.metrics.min_clearance for run in runs if run.metrics.min_clearance is not None
    ]
    latencies = [
        run.metrics.mean_local_planning_latency
        for run in runs
        if run.metrics.mean_local_planning_latency is not None
    ]
    max_latencies = [
        run.metrics.max_local_planning_latency
        for run in runs
        if run.metrics.max_local_planning_latency is not None
    ]
    planning_times = [
        run.metrics.global_planning_time
        for run in runs
        if run.metrics.global_planning_time is not None
    ]

    success_indicator = [1.0 if run.status is EpisodeStatus.SUCCESS else 0.0 for run in runs]
    success_rate_ci95 = bootstrap_ci(success_indicator) if len(success_indicator) > 1 else None

    travel_times = [r.metrics.travel_time for r in successful]
    median_travel_time, iqr_travel_time = _median_and_iqr(travel_times)

    path_efficiencies = [
        r.metrics.path_efficiency for r in successful if r.metrics.path_efficiency is not None
    ]
    median_path_efficiency, iqr_path_efficiency = _median_and_iqr(path_efficiencies)

    return AlgorithmAggregate(
        algorithm=algorithm_id,
        episodes=episodes,
        success_rate=rate(EpisodeStatus.SUCCESS),
        collision_rate=rate(EpisodeStatus.COLLISION),
        timeout_rate=rate(EpisodeStatus.TIMEOUT),
        stuck_rate=rate(EpisodeStatus.STUCK),
        no_progress_rate=rate(EpisodeStatus.NO_PROGRESS),
        no_global_path_rate=rate(EpisodeStatus.NO_GLOBAL_PATH),
        mean_travel_time_successful=mean_of([r.metrics.travel_time for r in successful]),
        mean_trajectory_length_successful=mean_of(
            [r.metrics.trajectory_length for r in successful]
        ),
        mean_path_efficiency_successful=mean_of(
            [r.metrics.path_efficiency for r in successful if r.metrics.path_efficiency is not None]
        ),
        mean_smoothness_successful=mean_of([r.metrics.smoothness for r in successful]),
        mean_smoothness_per_metre_successful=mean_of(
            [r.metrics.smoothness_per_metre for r in successful]
        ),
        mean_min_clearance=mean_of(clearances),
        worst_min_clearance=min(clearances) if clearances else None,
        mean_local_planning_latency=mean_of(latencies),
        max_local_planning_latency=max(max_latencies) if max_latencies else None,
        mean_global_planning_time=mean_of(planning_times),
        success_rate_ci95=success_rate_ci95,
        median_travel_time_successful=median_travel_time,
        iqr_travel_time_successful=iqr_travel_time,
        median_path_efficiency_successful=median_path_efficiency,
        iqr_path_efficiency_successful=iqr_path_efficiency,
    )


def _median_and_iqr(values: list[float]) -> tuple[float | None, tuple[float, float] | None]:
    """None for both when fewer than 2 values — a spread needs more than
    one point, and a "median" of one point is just that point, not
    informative enough to report as a statistic."""
    if len(values) < 2:
        return None, None
    median, q1, q3 = median_iqr(values)
    return median, (q1, q3)
