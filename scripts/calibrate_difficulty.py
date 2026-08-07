#!/usr/bin/env python3
"""Calibrate scenario difficulty (spec section 8.6d, P03) and cache it.

Runs the reference stack (A*+DWA, default config) 30 seeds against every
scenario in the library, computes ``difficulty = 1 - success_rate``, and
writes the result to
``packages/benchmark/planbench_benchmark/difficulty_cache.json``.

Slow by design: 10 scenarios x 30 seeds = 300 episodes. Run it from the
repository root with the project virtualenv whenever the simulator, the
reference stack's defaults, or the scenario library changes enough that
the cached numbers would no longer be honest:

    PYTHONPATH= .venv/bin/python scripts/calibrate_difficulty.py

The output file is checked into git so the API can read it without
recomputing on every request — see planbench_benchmark.difficulty.
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
    "services/simulator",
):
    sys.path.insert(0, str(REPO_ROOT / relative))

from planbench_benchmark.difficulty import (  # noqa: E402
    CACHE_PATH,
    REFERENCE_ALGORITHM,
    REFERENCE_SEEDS,
    calibrate_difficulty,
    save_difficulty_cache,
)
from planbench_benchmark.scenarios import SCENARIO_LIBRARY  # noqa: E402


def main() -> None:
    names = list(SCENARIO_LIBRARY)
    print(
        f"Calibrating {len(names)} scenarios x {len(REFERENCE_SEEDS)} seeds "
        f"with {REFERENCE_ALGORITHM!r}..."
    )
    started = time.monotonic()
    entries = {}
    for name in names:
        scenario_started = time.monotonic()
        entries.update(calibrate_difficulty([name]))
        entry = entries[name]
        elapsed = time.monotonic() - scenario_started
        print(
            f"  {name:<24} difficulty={entry.difficulty:.3f} "
            f"success_rate={entry.success_rate:.3f}  ({elapsed:.1f}s)"
        )
    save_difficulty_cache(entries)
    total = time.monotonic() - started
    print(f"Wrote {CACHE_PATH} in {total:.1f}s")


if __name__ == "__main__":
    main()
