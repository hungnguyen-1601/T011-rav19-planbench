"""Empirically-calibrated scenario difficulty (spec section 8.6d, P03).

Difficulty is **not** obstacle count or map size — it is
``1 - success_rate`` of a fixed, version-pinned reference stack
(``astar+dwa`` with default config) over :data:`REFERENCE_SEEDS` seeds.
A scenario is only as hard as it measurably is for a real planner; two
scenarios with the same obstacle count can have wildly different
difficulty, and this is the number that says so.

Calibration is expensive (10 scenarios x 30 seeds = 300 episodes) and
its answer does not change between requests, so it runs once via
``scripts/calibrate_difficulty.py`` and the result is cached to
:data:`CACHE_PATH`, checked into the repository. Recalibrate by rerunning
the script whenever the simulator, the reference stack's defaults, or
the scenario library itself changes enough that old numbers would lie.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

REFERENCE_ALGORITHM = "astar+dwa"
REFERENCE_SEEDS: tuple[int, ...] = tuple(range(1, 31))
CACHE_PATH = Path(__file__).parent / "difficulty_cache.json"


class DifficultyEntry(BaseModel):
    """One scenario's calibrated difficulty."""

    model_config = ConfigDict(frozen=True)

    scenario: str
    difficulty: float
    success_rate: float
    seeds: int
    reference_algorithm: str
    calibrated_at: str


def calibrate_difficulty(
    scenario_names: list[str] | None = None,
    *,
    seeds: tuple[int, ...] = REFERENCE_SEEDS,
    algorithm: str = REFERENCE_ALGORITHM,
) -> dict[str, DifficultyEntry]:
    """Run the reference stack over every scenario and compute difficulty.

    Pure computation — no file I/O — so it is testable without touching
    disk; :func:`save_difficulty_cache` handles persistence separately.
    Imports the benchmark runner lazily to avoid a circular import
    (``runner`` does not depend on this module, but importing at call
    time rather than module load time keeps that direction explicit).
    """
    from planbench_benchmark.runner import run_benchmark
    from planbench_benchmark.scenarios import SCENARIO_LIBRARY, build_scenario
    from planbench_benchmark.spec import AlgorithmSpec, BenchmarkSpec

    names = scenario_names if scenario_names is not None else list(SCENARIO_LIBRARY)
    now = datetime.now(UTC).isoformat()
    results: dict[str, DifficultyEntry] = {}
    for name in names:
        map_data, scenario = build_scenario(name)
        spec = BenchmarkSpec(
            name=f"difficulty-calibration-{name}",
            algorithms=(AlgorithmSpec(id=algorithm, config={}),),
            seeds=seeds,
        )
        report = run_benchmark(map_data, scenario, spec)
        success_rate = report.aggregates[0].success_rate
        results[name] = DifficultyEntry(
            scenario=name,
            difficulty=1.0 - success_rate,
            success_rate=success_rate,
            seeds=len(seeds),
            reference_algorithm=algorithm,
            calibrated_at=now,
        )
    return results


def save_difficulty_cache(entries: dict[str, DifficultyEntry], path: Path = CACHE_PATH) -> None:
    payload = {name: entry.model_dump() for name, entry in entries.items()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_difficulty_cache(path: Path = CACHE_PATH) -> dict[str, DifficultyEntry]:
    """Empty dict when the cache has never been generated — a missing
    calibration is a "not yet run" state, not an error the caller should
    have to handle with a try/except."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {name: DifficultyEntry.model_validate(entry) for name, entry in raw.items()}


__all__ = [
    "CACHE_PATH",
    "REFERENCE_ALGORITHM",
    "REFERENCE_SEEDS",
    "DifficultyEntry",
    "calibrate_difficulty",
    "load_difficulty_cache",
    "save_difficulty_cache",
]
