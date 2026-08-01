"""Tests for P03 difficulty calibration and its cache (spec section 8.6d).

Real runs, not mocks — this is exactly the module that computes a
number people will use to say a scenario is easy or hard, so a fake
result here would defeat the point of testing it.
"""

from __future__ import annotations

from pathlib import Path

from planbench_benchmark.difficulty import (
    DifficultyEntry,
    calibrate_difficulty,
    load_difficulty_cache,
    save_difficulty_cache,
)


class TestCalibrateDifficulty:
    def test_open_space_is_easy_for_the_reference_stack(self) -> None:
        """A straight, empty hall should be solved almost every seed —
        low difficulty is the expected, checkable answer here."""
        result = calibrate_difficulty(["open_space"], seeds=tuple(range(1, 6)))
        entry = result["open_space"]
        assert entry.scenario == "open_space"
        assert entry.success_rate > 0.8
        assert entry.difficulty < 0.2
        assert entry.seeds == 5
        assert entry.reference_algorithm == "astar+dwa"

    def test_difficulty_is_one_minus_success_rate(self) -> None:
        result = calibrate_difficulty(["static_obstacles"], seeds=tuple(range(1, 4)))
        entry = result["static_obstacles"]
        assert entry.difficulty == 1.0 - entry.success_rate

    def test_calibrates_only_the_requested_scenarios(self) -> None:
        result = calibrate_difficulty(["open_space", "doorway"], seeds=(1, 2))
        assert set(result) == {"open_space", "doorway"}


class TestDifficultyCache:
    def test_missing_cache_is_an_empty_dict_not_an_error(self, tmp_path: Path) -> None:
        assert load_difficulty_cache(tmp_path / "does-not-exist.json") == {}

    def test_round_trips_through_json(self, tmp_path: Path) -> None:
        entries = {
            "open_space": DifficultyEntry(
                scenario="open_space",
                difficulty=0.02,
                success_rate=0.98,
                seeds=30,
                reference_algorithm="astar+dwa",
                calibrated_at="2026-01-01T00:00:00+00:00",
            )
        }
        path = tmp_path / "difficulty_cache.json"
        save_difficulty_cache(entries, path)
        loaded = load_difficulty_cache(path)
        assert loaded == entries

    def test_the_checked_in_cache_is_valid_if_present(self) -> None:
        """Doesn't require it to exist (scripts/calibrate_difficulty.py
        must be run manually first — see docs/KNOWN_LIMITATIONS.md #79),
        but if it does, it must actually parse."""
        from planbench_benchmark.difficulty import CACHE_PATH
        from planbench_benchmark.scenarios import SCENARIO_LIBRARY

        if not CACHE_PATH.exists():
            return
        cache = load_difficulty_cache()
        assert cache
        for name, entry in cache.items():
            assert name in SCENARIO_LIBRARY
            assert 0.0 <= entry.difficulty <= 1.0
            assert entry.seeds >= 1
