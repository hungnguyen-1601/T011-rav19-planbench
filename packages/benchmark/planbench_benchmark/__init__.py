"""Benchmark engine: fair multi-seed comparison of navigation stacks."""

from planbench_benchmark.failure import (
    Confidence,
    Evidence,
    FailureCategory,
    FailureReport,
    Finding,
    analyse_episode,
)
from planbench_benchmark.observation import OBSERVATION_CLASSES, ObservationClass
from planbench_benchmark.registry import (
    ALGORITHMS,
    AlgorithmInfo,
    algorithm_info,
    build_global_planner,
    build_local_planner,
    list_algorithms,
    validate_algorithm_config,
)
from planbench_benchmark.runner import run_benchmark, run_single
from planbench_benchmark.scenarios import (
    CURRICULUM_ORDER,
    SCENARIO_LIBRARY,
    build_scenario,
)
from planbench_benchmark.spec import (
    AlgorithmAggregate,
    AlgorithmSpec,
    BenchmarkReport,
    BenchmarkSpec,
    FairnessRecord,
    RunRecord,
)

__all__ = [
    "ALGORITHMS",
    "CURRICULUM_ORDER",
    "OBSERVATION_CLASSES",
    "SCENARIO_LIBRARY",
    "AlgorithmAggregate",
    "AlgorithmInfo",
    "AlgorithmSpec",
    "BenchmarkReport",
    "BenchmarkSpec",
    "FairnessRecord",
    "ObservationClass",
    "RunRecord",
    "Confidence",
    "algorithm_info",
    "Evidence",
    "FailureCategory",
    "FailureReport",
    "Finding",
    "analyse_episode",
    "build_global_planner",
    "build_local_planner",
    "build_scenario",
    "list_algorithms",
    "run_benchmark",
    "run_single",
    "validate_algorithm_config",
]
