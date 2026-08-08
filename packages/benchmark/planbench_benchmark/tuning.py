"""Optuna hyperparameter tuning under an equal trial budget (spec
section 8.6c, P01).

Every planner's parameter space is declared up front (:data:`SEARCH_SPACES`,
readable directly from code) and gets the same number of trials — the
budget fairness the spec asks for. The full search history is kept
(:class:`TuningResult.trials`) plus a running-best curve
(:class:`TuningResult.best_so_far_curve`), so a report can show whether
a planner saturates early or is still improving at the trial budget's
edge.

Tuning is expensive (default 30 trials x 5 seeds x 2 planners = 300
episodes) and its answer does not change between requests, so — same
pattern as :mod:`planbench_benchmark.difficulty` (P03) — it runs once
via ``scripts/tune_hyperparameters.py`` and the result is cached to
:data:`CACHE_PATH`, checked into the repository.

``astar+ppo`` is deliberately not tunable here: "tuning" a trained
policy means retraining per trial, which is a different, much more
expensive process than an Optuna search over a handful of numeric
weights — see docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from planbench_benchmark.spec import AlgorithmAggregate

TUNING_SCENARIO = "static_obstacles"
TUNING_SEEDS: tuple[int, ...] = tuple(range(1, 6))
DEFAULT_N_TRIALS = 30
CACHE_PATH = Path(__file__).parent / "tuning_cache.json"


def _search_space_astar_dwa(trial: Any) -> dict:
    return {
        "weight_goal": trial.suggest_float("weight_goal", 0.5, 4.0),
        "weight_heading": trial.suggest_float("weight_heading", 0.0, 3.0),
        "weight_path": trial.suggest_float("weight_path", 0.0, 3.0),
        "weight_clearance": trial.suggest_float("weight_clearance", 0.0, 3.0),
        "weight_velocity": trial.suggest_float("weight_velocity", 0.0, 2.0),
        "weight_smoothness": trial.suggest_float("weight_smoothness", 0.0, 1.0),
        "weight_oscillation": trial.suggest_float("weight_oscillation", 0.0, 1.0),
    }


def _search_space_rrtstar_dwa(trial: Any) -> dict:
    return {
        "step_size": trial.suggest_float("step_size", 0.2, 1.0),
        "goal_bias": trial.suggest_float("goal_bias", 0.0, 0.3),
        "rewire_radius": trial.suggest_float("rewire_radius", 0.5, 2.0),
    }


#: Declared-up-front parameter space per tunable stack (P01's "khai báo
#: trước không gian tham số"). Keys are the same stack ids the registry
#: (packages/benchmark/planbench_benchmark/registry.py) uses.
SEARCH_SPACES: dict[str, Callable[[Any], dict]] = {
    "astar+dwa": _search_space_astar_dwa,
    "rrtstar+dwa": _search_space_rrtstar_dwa,
}


class TrialRecord(BaseModel):
    """One Optuna trial's parameters and resulting score."""

    model_config = ConfigDict(frozen=True)

    number: int
    params: dict
    value: float


class TuningResult(BaseModel):
    """Full tuning run for one algorithm: history, best point, curve."""

    model_config = ConfigDict(frozen=True)

    algorithm: str
    scenario: str
    seeds: int
    n_trials: int
    best_value: float
    best_params: dict
    trials: tuple[TrialRecord, ...]
    #: Running-best score after each trial, in trial order — the
    #: "đường cong hiệu năng theo ngân sách" the spec asks for.
    best_so_far_curve: tuple[float, ...]
    tuned_at: str


def _score(aggregate: AlgorithmAggregate, robot_radius: float) -> float:
    """Weighted [0, 1] score — same formula and weights as
    apps/api/planbench_api/leaderboard.py's ``overall_score()``,
    duplicated rather than imported: packages/ must not depend on
    apps/api. Keep the weights in sync by hand if leaderboard's change.
    """
    parts: list[tuple[float, float]] = [(0.40, aggregate.success_rate)]
    if aggregate.worst_min_clearance is not None and robot_radius > 0:
        parts.append((0.30, min(1.0, max(0.0, aggregate.worst_min_clearance / robot_radius))))
    if aggregate.mean_path_efficiency_successful is not None:
        parts.append((0.20, min(1.0, max(0.0, aggregate.mean_path_efficiency_successful))))
    # ``mean_smoothness_successful`` is the per-metre heading-change rate
    # (see episode_metrics): the score clamps to [0, 1], and the raw
    # Σ(Δθ)² in ``smoothness_squared`` exceeds 1 on nearly every episode,
    # which would flatten every stack to 0 on this axis.
    if aggregate.mean_smoothness_successful is not None:
        parts.append((0.10, 1.0 - min(1.0, max(0.0, aggregate.mean_smoothness_successful))))
    weight_sum = sum(weight for weight, _ in parts)
    if weight_sum <= 0:
        return 0.0
    return sum(weight * value for weight, value in parts) / weight_sum


def tune_algorithm(
    algorithm_id: str,
    n_trials: int = DEFAULT_N_TRIALS,
    scenario_name: str = TUNING_SCENARIO,
    seeds: tuple[int, ...] = TUNING_SEEDS,
) -> TuningResult:
    """Run an Optuna study for one registered stack's parameter space.

    Imports optuna lazily (function-local, not module-level) so this
    module stays importable without optuna installed — only calling
    this function requires it. See requirements-optional.txt.
    """
    import optuna

    from planbench_benchmark.runner import run_benchmark
    from planbench_benchmark.scenarios import build_scenario
    from planbench_benchmark.spec import AlgorithmSpec, BenchmarkSpec

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    search_space = SEARCH_SPACES[algorithm_id]
    map_data, scenario = build_scenario(scenario_name)

    def objective(trial: Any) -> float:
        config = search_space(trial)
        spec = BenchmarkSpec(
            name=f"tuning-{algorithm_id}",
            algorithms=(AlgorithmSpec(id=algorithm_id, config=config),),
            seeds=seeds,
        )
        report = run_benchmark(map_data, scenario, spec)
        return _score(report.aggregates[0], scenario.robot.radius)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
    study.optimize(objective, n_trials=n_trials)

    trials = tuple(
        TrialRecord(number=t.number, params=t.params, value=t.value if t.value is not None else 0.0)
        for t in study.trials
    )
    best_so_far: list[float] = []
    running_best = float("-inf")
    for t in trials:
        running_best = max(running_best, t.value)
        best_so_far.append(running_best)

    return TuningResult(
        algorithm=algorithm_id,
        scenario=scenario_name,
        seeds=len(seeds),
        n_trials=n_trials,
        best_value=study.best_value,
        best_params=study.best_params,
        trials=trials,
        best_so_far_curve=tuple(best_so_far),
        tuned_at=datetime.now(UTC).isoformat(),
    )


def save_tuning_cache(results: dict[str, TuningResult], path: Path = CACHE_PATH) -> None:
    payload = {name: result.model_dump() for name, result in results.items()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_tuning_cache(path: Path = CACHE_PATH) -> dict[str, TuningResult]:
    """Empty dict when tuning has never been run — a missing cache is a
    "not yet run" state, not an error the caller should handle."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {name: TuningResult.model_validate(entry) for name, entry in raw.items()}


__all__ = [
    "CACHE_PATH",
    "DEFAULT_N_TRIALS",
    "SEARCH_SPACES",
    "TUNING_SCENARIO",
    "TUNING_SEEDS",
    "TrialRecord",
    "TuningResult",
    "load_tuning_cache",
    "save_tuning_cache",
    "tune_algorithm",
]
