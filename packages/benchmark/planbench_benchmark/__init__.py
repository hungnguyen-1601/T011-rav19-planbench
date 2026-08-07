"""Benchmark engine: fair multi-seed comparison of navigation stacks."""

from planbench_benchmark.difficulty import (
    DifficultyEntry,
    calibrate_difficulty,
    load_difficulty_cache,
)
from planbench_benchmark.failure import (
    Confidence,
    Evidence,
    FailureCategory,
    FailureReport,
    Finding,
    analyse_episode,
)
from planbench_benchmark.registry import (
    ALGORITHMS,
    AlgorithmInfo,
    build_global_planner,
    build_local_planner,
    list_algorithms,
    validate_algorithm_config,
)
from planbench_benchmark.runner import compare_algorithms, run_benchmark, run_single
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
    PairwiseComparison,
    RunRecord,
)
from planbench_benchmark.tuning import (
    SEARCH_SPACES,
    TuningResult,
    load_tuning_cache,
)

__all__ = [
    "build_global_planner",
    "compare_algorithms",
    "SEARCH_SPACES",
    "calibrate_difficulty",
    "DifficultyEntry",
    "load_difficulty_cache",
    "load_tuning_cache",
    "TuningResult",
    "ALGORITHMS",
    "CURRICULUM_ORDER",
    "SCENARIO_LIBRARY",
    "AlgorithmAggregate",
    "AlgorithmInfo",
    "AlgorithmSpec",
    "BenchmarkReport",
    "BenchmarkSpec",
    "PairwiseComparison",
    "FairnessRecord",
    "RunRecord",
    "Confidence",
    "Evidence",
    "FailureCategory",
    "FailureReport",
    "Finding",
    "analyse_episode",
    "build_local_planner",
    "build_scenario",
    "list_algorithms",
    "run_benchmark",
    "run_single",
    "validate_algorithm_config",
]
