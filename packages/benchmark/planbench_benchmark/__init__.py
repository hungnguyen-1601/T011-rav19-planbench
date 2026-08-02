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
    ObservationClass,
    build_global_planner,
    build_local_planner,
    list_algorithms,
    validate_algorithm_config,
)
from planbench_benchmark.runner import compare_algorithms, run_benchmark, run_single
from planbench_benchmark.scenarios import (
    CURRICULUM_ORDER,
    HOLDOUT_SCENARIOS,
    SCENARIO_LIBRARY,
    build_scenario,
    scenario_split,
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
    save_tuning_cache,
    tune_algorithm,
)

__all__ = [
    "ALGORITHMS",
    "CURRICULUM_ORDER",
    "HOLDOUT_SCENARIOS",
    "SCENARIO_LIBRARY",
    "SEARCH_SPACES",
    "AlgorithmAggregate",
    "AlgorithmInfo",
    "AlgorithmSpec",
    "BenchmarkReport",
    "BenchmarkSpec",
    "DifficultyEntry",
    "FairnessRecord",
    "ObservationClass",
    "PairwiseComparison",
    "RunRecord",
    "TuningResult",
    "Confidence",
    "Evidence",
    "FailureCategory",
    "FailureReport",
    "Finding",
    "analyse_episode",
    "build_global_planner",
    "build_local_planner",
    "build_scenario",
    "calibrate_difficulty",
    "compare_algorithms",
    "list_algorithms",
    "load_difficulty_cache",
    "load_tuning_cache",
    "run_benchmark",
    "run_single",
    "save_tuning_cache",
    "scenario_split",
    "tune_algorithm",
    "validate_algorithm_config",
]
