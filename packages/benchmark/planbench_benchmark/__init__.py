"""Benchmark engine: fair multi-seed comparison of navigation stacks.

**Every export resolves on demand.** Importing this package used to pull
the whole engine — ``comparison`` → ``spec`` → ``planbench_metrics`` →
``planbench_simulator`` — which is right for anything running a
benchmark and wrong for the one place that only wants a table of
algorithm natures.

The analyst image is that place. ``docker/Dockerfile.analyst`` copies
``packages/benchmark`` (four analyst modules read ``TraitSource`` and
``TraitEntry`` from ``traits_store``, and that module imports nothing but
pydantic) and deliberately does **not** copy ``services/simulator``: a
container that grades an explanation has no business carrying the code
that drives a robot. With an eager package body, ``import
planbench_analyst`` died in that image on ``No module named
'planbench_simulator'`` — every module, down to ``sanitize`` and
``prompts``, because the analyst package body imports its own engine.

A lazy body fails only when something actually reaches for a name that
needs the simulator, which in the container nothing legitimately does.
Same shape as ``planbench_explanation.__getattr__``, added in W0 for the
same reason: a package that a stripped image cannot import is a package
that image cannot use at all.

The mapping is written out rather than discovered by walking the
submodules, because discovery would have to import them to find out what
they export — which is the eager body again, wearing a different hat.
"""

from __future__ import annotations

import importlib

_EXPORTS: dict[str, str] = {
    # comparison
    "DEFAULT_COMPARISON_METRIC": "planbench_benchmark.comparison",
    "MIN_PAIRS_FOR_TEST": "planbench_benchmark.comparison",
    "SIGNIFICANCE_LEVEL": "planbench_benchmark.comparison",
    "build_comparisons": "planbench_benchmark.comparison",
    "compare_pair": "planbench_benchmark.comparison",
    # difficulty
    "BAND_THRESHOLDS": "planbench_benchmark.difficulty",
    "CALIBRATION_FILE": "planbench_benchmark.difficulty",
    "DEFAULT_CALIBRATION_SEEDS": "planbench_benchmark.difficulty",
    "MIDRANGE_DIFFICULTY": "planbench_benchmark.difficulty",
    "MIN_CALIBRATION_SEEDS": "planbench_benchmark.difficulty",
    "MIN_MIDRANGE_SCENARIOS": "planbench_benchmark.difficulty",
    "BaselineSpec": "planbench_benchmark.difficulty",
    "DifficultyBand": "planbench_benchmark.difficulty",
    "DifficultyCalibration": "planbench_benchmark.difficulty",
    "DifficultyCalibrationError": "planbench_benchmark.difficulty",
    "DifficultyCoverage": "planbench_benchmark.difficulty",
    "DifficultyLabel": "planbench_benchmark.difficulty",
    "ScenarioCalibration": "planbench_benchmark.difficulty",
    "calibration_version": "planbench_benchmark.difficulty",
    "difficulty_band": "planbench_benchmark.difficulty",
    "difficulty_coverage": "planbench_benchmark.difficulty",
    "get_difficulty": "planbench_benchmark.difficulty",
    "load_calibration": "planbench_benchmark.difficulty",
    "parse_calibration": "planbench_benchmark.difficulty",
    # failure
    "Confidence": "planbench_benchmark.failure",
    "Evidence": "planbench_benchmark.failure",
    "FailureCategory": "planbench_benchmark.failure",
    "FailureReport": "planbench_benchmark.failure",
    "Finding": "planbench_benchmark.failure",
    "analyse_episode": "planbench_benchmark.failure",
    # generalization
    "COMPARABLE_SPLITS": "planbench_benchmark.generalization",
    "GAP_METRICS": "planbench_benchmark.generalization",
    "GapMetric": "planbench_benchmark.generalization",
    "GeneralizationEntry": "planbench_benchmark.generalization",
    "GeneralizationSummary": "planbench_benchmark.generalization",
    "HoldoutUse": "planbench_benchmark.generalization",
    "SplitSummary": "planbench_benchmark.generalization",
    "build_generalization": "planbench_benchmark.generalization",
    # observation
    "OBSERVATION_CLASSES": "planbench_benchmark.observation",
    "ObservationClass": "planbench_benchmark.observation",
    # registry
    "ALGORITHMS": "planbench_benchmark.registry",
    "AlgorithmInfo": "planbench_benchmark.registry",
    "algorithm_info": "planbench_benchmark.registry",
    "build_global_planner": "planbench_benchmark.registry",
    "build_local_planner": "planbench_benchmark.registry",
    "list_algorithms": "planbench_benchmark.registry",
    "validate_algorithm_config": "planbench_benchmark.registry",
    # runner
    "run_benchmark": "planbench_benchmark.runner",
    "run_single": "planbench_benchmark.runner",
    # scenario_protocol
    "PROTOCOL_FILE": "planbench_benchmark.scenario_protocol",
    "SCENARIO_SPLITS": "planbench_benchmark.scenario_protocol",
    "ScenarioProtocol": "planbench_benchmark.scenario_protocol",
    "ScenarioProtocolError": "planbench_benchmark.scenario_protocol",
    "ScenarioProtocolMetadata": "planbench_benchmark.scenario_protocol",
    "ScenarioSplit": "planbench_benchmark.scenario_protocol",
    "load_protocol": "planbench_benchmark.scenario_protocol",
    "protocol_version": "planbench_benchmark.scenario_protocol",
    "scenario_protocol_metadata": "planbench_benchmark.scenario_protocol",
    "scenario_split": "planbench_benchmark.scenario_protocol",
    "scenarios_in_split": "planbench_benchmark.scenario_protocol",
    # scenarios
    "CURRICULUM_ORDER": "planbench_benchmark.scenarios",
    "SCENARIO_LIBRARY": "planbench_benchmark.scenarios",
    "build_scenario": "planbench_benchmark.scenarios",
    # spec
    "AlgorithmAggregate": "planbench_benchmark.spec",
    "AlgorithmSpec": "planbench_benchmark.spec",
    "BenchmarkReport": "planbench_benchmark.spec",
    "BenchmarkSpec": "planbench_benchmark.spec",
    "FairnessRecord": "planbench_benchmark.spec",
    "PairwiseComparison": "planbench_benchmark.spec",
    "RunRecord": "planbench_benchmark.spec",
    # tuning
    "SEARCH_SPACES": "planbench_benchmark.tuning",
    "TuningResult": "planbench_benchmark.tuning",
    "load_tuning_cache": "planbench_benchmark.tuning",
}

__all__ = [
    "SEARCH_SPACES",
    "load_tuning_cache",
    "TuningResult",
    "ALGORITHMS",
    "BAND_THRESHOLDS",
    "CALIBRATION_FILE",
    "COMPARABLE_SPLITS",
    "CURRICULUM_ORDER",
    "DEFAULT_CALIBRATION_SEEDS",
    "DEFAULT_COMPARISON_METRIC",
    "GAP_METRICS",
    "MIDRANGE_DIFFICULTY",
    "MIN_CALIBRATION_SEEDS",
    "MIN_MIDRANGE_SCENARIOS",
    "MIN_PAIRS_FOR_TEST",
    "OBSERVATION_CLASSES",
    "PROTOCOL_FILE",
    "SCENARIO_LIBRARY",
    "SCENARIO_SPLITS",
    "SIGNIFICANCE_LEVEL",
    "AlgorithmAggregate",
    "AlgorithmInfo",
    "AlgorithmSpec",
    "BaselineSpec",
    "BenchmarkReport",
    "BenchmarkSpec",
    "DifficultyBand",
    "DifficultyCalibration",
    "DifficultyCalibrationError",
    "DifficultyCoverage",
    "DifficultyLabel",
    "FairnessRecord",
    "GapMetric",
    "GeneralizationEntry",
    "GeneralizationSummary",
    "HoldoutUse",
    "ObservationClass",
    "PairwiseComparison",
    "RunRecord",
    "ScenarioCalibration",
    "ScenarioProtocol",
    "ScenarioProtocolError",
    "ScenarioProtocolMetadata",
    "ScenarioSplit",
    "SplitSummary",
    "Confidence",
    "algorithm_info",
    "build_comparisons",
    "build_generalization",
    "calibration_version",
    "compare_pair",
    "difficulty_band",
    "difficulty_coverage",
    "get_difficulty",
    "load_calibration",
    "load_protocol",
    "parse_calibration",
    "protocol_version",
    "scenario_protocol_metadata",
    "scenario_split",
    "scenarios_in_split",
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


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Resolve one export, importing only the module that carries it."""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)


def __dir__() -> list[str]:
    return sorted(__all__)
