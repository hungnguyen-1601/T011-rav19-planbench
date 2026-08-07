"""Tests for P01 Optuna tuning and its cache (spec section 8.6c).

Real Optuna studies, not mocks — trial count/seed count are kept small
so the suite stays fast, but the search itself runs for real.
"""

from __future__ import annotations

import pytest

pytest.importorskip("optuna")

from pathlib import Path  # noqa: E402

from planbench_benchmark.tuning import (  # noqa: E402
    SEARCH_SPACES,
    TrialRecord,
    TuningResult,
    load_tuning_cache,
    save_tuning_cache,
    tune_algorithm,
)


class TestTuneAlgorithm:
    def test_astar_dwa_search_space_and_history(self) -> None:
        result = tune_algorithm("astar+dwa", n_trials=2, seeds=(1, 2))
        assert result.algorithm == "astar+dwa"
        assert result.n_trials == 2
        assert result.seeds == 2
        assert len(result.trials) == 2
        assert set(result.best_params) == {
            "weight_goal",
            "weight_heading",
            "weight_path",
            "weight_clearance",
            "weight_velocity",
            "weight_smoothness",
            "weight_oscillation",
        }
        assert 0.5 <= result.best_params["weight_goal"] <= 4.0
        assert 0.0 <= result.best_value <= 1.0

    def test_rrtstar_dwa_search_space(self) -> None:
        result = tune_algorithm("rrtstar+dwa", n_trials=2, seeds=(1, 2))
        assert set(result.best_params) == {"step_size", "goal_bias", "rewire_radius"}
        assert 0.2 <= result.best_params["step_size"] <= 1.0
        assert 0.0 <= result.best_params["goal_bias"] <= 0.3
        assert 0.5 <= result.best_params["rewire_radius"] <= 2.0

    def test_best_so_far_curve_is_a_running_max(self) -> None:
        result = tune_algorithm("astar+dwa", n_trials=5, seeds=(1,))
        assert len(result.best_so_far_curve) == 5
        for previous, current in zip(
            result.best_so_far_curve, result.best_so_far_curve[1:], strict=False
        ):
            assert current >= previous
        assert result.best_so_far_curve[-1] == result.best_value

    def test_registered_stacks_match_the_algorithm_registry(self) -> None:
        assert set(SEARCH_SPACES) == {"astar+dwa", "rrtstar+dwa"}


class TestTuningCache:
    def test_missing_cache_is_an_empty_dict_not_an_error(self, tmp_path: Path) -> None:
        assert load_tuning_cache(tmp_path / "does-not-exist.json") == {}

    def test_round_trips_through_json(self, tmp_path: Path) -> None:
        results = {
            "astar+dwa": TuningResult(
                algorithm="astar+dwa",
                scenario="static_obstacles",
                seeds=5,
                n_trials=30,
                best_value=0.82,
                best_params={"weight_goal": 2.1},
                trials=(TrialRecord(number=0, params={"weight_goal": 2.1}, value=0.82),),
                best_so_far_curve=(0.82,),
                tuned_at="2026-01-01T00:00:00+00:00",
            )
        }
        path = tmp_path / "tuning_cache.json"
        save_tuning_cache(results, path)
        loaded = load_tuning_cache(path)
        assert loaded == results

    def test_the_checked_in_cache_is_valid_if_present(self) -> None:
        """Doesn't require it to exist (scripts/tune_hyperparameters.py
        must be run manually first — see docs/KNOWN_LIMITATIONS.md), but
        if it does, it must actually parse."""
        from planbench_benchmark.tuning import CACHE_PATH

        if not CACHE_PATH.exists():
            return
        cache = load_tuning_cache()
        assert cache
        for algorithm_id, result in cache.items():
            assert algorithm_id in SEARCH_SPACES
            assert 0.0 <= result.best_value <= 1.0
            assert len(result.trials) == result.n_trials
