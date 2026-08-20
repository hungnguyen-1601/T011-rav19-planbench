#!/usr/bin/env python3
"""Tune every registered planner's parameters under an equal Optuna
budget (spec section 8.6c, P01) and cache the result.

Runs 30 trials per stack (default) x 5 seeds x 2 stacks = 300 episodes
on the "static_obstacles" dev scenario, and writes the result to
``packages/benchmark/planbench_benchmark/tuning_cache.json``.

Requires optuna (requirements-optional.txt, section 5) — not part of
the core install. Run from the repository root with the project
virtualenv whenever the simulator, a planner's cost function, or the
search space in planbench_benchmark.tuning changes enough that the
cached numbers would no longer be honest:

    PYTHONPATH= .venv/bin/python scripts/tune_hyperparameters.py

The output file is checked into git so the API can serve it without
recomputing on every request — see planbench_benchmark.tuning and
GET /tuning.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "packages/schemas",
    "packages/planning",
    "packages/metrics",
    "packages/benchmark",
    "packages/explanation",
    "packages/plugin_sdk",
    "services/simulator",
):
    sys.path.insert(0, str(REPO_ROOT / relative))

from planbench_benchmark.tuning import (  # noqa: E402
    CACHE_PATH,
    DEFAULT_N_TRIALS,
    SEARCH_SPACES,
    TUNING_SCENARIO,
    TUNING_SEEDS,
    save_tuning_cache,
    tune_algorithm,
)


def main() -> None:
    algorithms = list(SEARCH_SPACES)
    print(
        f"Tuning {len(algorithms)} stacks x {DEFAULT_N_TRIALS} trials x "
        f"{len(TUNING_SEEDS)} seeds on {TUNING_SCENARIO!r}..."
    )
    started = time.monotonic()
    results = {}
    for algorithm_id in algorithms:
        algorithm_started = time.monotonic()
        result = tune_algorithm(algorithm_id, n_trials=DEFAULT_N_TRIALS)
        results[algorithm_id] = result
        elapsed = time.monotonic() - algorithm_started
        print(
            f"  {algorithm_id:<16} best_value={result.best_value:.4f} "
            f"best_params={result.best_params}  ({elapsed:.1f}s)"
        )
    save_tuning_cache(results)
    total = time.monotonic() - started
    print(f"Wrote {CACHE_PATH} in {total:.1f}s")


if __name__ == "__main__":
    main()
