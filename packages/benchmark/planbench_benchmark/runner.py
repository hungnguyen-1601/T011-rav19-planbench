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

from planbench_benchmark.registry import (
    algorithm_info,
    build_global_planner,
    build_local_planner,
)
from planbench_benchmark.spec import (
    AlgorithmAggregate,
    AlgorithmSpec,
    BenchmarkReport,
    BenchmarkSpec,
    FairnessRecord,
    RunRecord,
)
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun, run_stack

logger = logging.getLogger("planbench.benchmark")


def run_single(
    map_data: MapData, scenario: Scenario, algorithm: AlgorithmSpec, seed: int
) -> StackRun:
    """Run one episode of one algorithm at one seed.

    The same seed drives the scenario (dynamic obstacles) and the global
    planner. A sampling planner therefore grows a different tree per
    seed instead of replaying one lucky tree for the whole sweep, while
    every algorithm still faces the identical set of conditions.
    """
    seeded = scenario.model_copy(update={"random_seed": seed})
    planner = build_local_planner(algorithm.id, algorithm.config)
    global_planner = build_global_planner(algorithm.id, episode_seed=seed)
    return run_stack(map_data, seeded, planner, global_planner)


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
    return BenchmarkReport(spec=spec, fairness=fairness, runs=tuple(runs), aggregates=aggregates)


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

    # Copy the information-parity declaration into the result rather
    # than resolving it when the leaderboard renders: the registry can
    # change, these numbers cannot.
    info = algorithm_info(algorithm_id)

    return AlgorithmAggregate(
        algorithm=algorithm_id,
        global_observation_class=info.global_observation_class if info else None,
        local_observation_class=info.local_observation_class if info else None,
        requires_global_path=info.requires_global_path if info else None,
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
        mean_min_clearance=mean_of(clearances),
        worst_min_clearance=min(clearances) if clearances else None,
        mean_local_planning_latency=mean_of(latencies),
        max_local_planning_latency=max(max_latencies) if max_latencies else None,
        mean_global_planning_time=mean_of(planning_times),
    )
