"""P03: measured scenario difficulty, its cache and the calibration script.

The point of difficulty calibration is that the number is *measured* and
the measurement is *identified*. So these tests are mostly about the ways
a number could stop meaning what it says: a hand-edited cache, a cache
whose baseline nobody recorded, a difficulty that outlived the scenario
it was measured on, or a scale so flat it separates nothing.

Two properties get their own tests at the top of the file because the
rest of the design rests on them: calibrating changes no checksum, and a
scenario carries no difficulty field.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from planbench_benchmark import difficulty as difficulty_module
from planbench_benchmark.difficulty import (
    MIN_CALIBRATION_SEEDS,
    DifficultyCalibrationError,
    calibration_version,
    difficulty_band,
    difficulty_coverage,
    get_difficulty,
    load_calibration,
    parse_calibration,
)
from planbench_benchmark.scenarios import CURRICULUM_ORDER, build_scenario
from planbench_benchmark.spec import FairnessRecord, _scenario_checksum
from planbench_schemas.scenario import Scenario

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import calibrate_difficulty as script  # noqa: E402


def _entry(scenario_name: str, difficulty: float, **overrides) -> dict:
    """A cache entry that matches the scenario as the code builds it now."""
    map_data, scenario = build_scenario(scenario_name)
    entry = {
        "difficulty": difficulty,
        "ci95": [max(0.0, difficulty - 0.1), min(1.0, difficulty + 0.1)],
        "success_rate": 1.0 - difficulty,
        "episodes": 30,
        "status_counts": {"success": 30},
        "map_checksum": map_data.checksum(),
        "scenario_checksum": _scenario_checksum(scenario),
        "scenario_split": "dev",
    }
    entry.update(overrides)
    return entry


def _cache(scenarios: dict, *, version: str = "1.0.0", seeds: list[int] | None = None) -> dict:
    return {
        "calibration_version": version,
        "baseline": {
            "algorithm": "astar+dwa",
            "algorithm_config": {},
            "replanning_enabled": False,
            "seeds": seeds if seeds is not None else list(range(30)),
            "robot_profile": {"radius": 0.3},
            "benchmark_spec_version": "1",
            "protocol_version": "1.0.0",
            "git_sha": "deadbeef",
        },
        "scenarios": scenarios,
    }


@pytest.fixture
def install_cache(tmp_path, monkeypatch):
    """Point the module at a temporary cache and clear the read-through cache."""

    def _install(payload: dict | str | None) -> Path:
        path = tmp_path / "difficulty_calibration.json"
        if payload is not None:
            path.write_text(
                payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
            )
        monkeypatch.setattr(difficulty_module, "CALIBRATION_FILE", path)
        load_calibration.cache_clear()
        return path

    yield _install
    load_calibration.cache_clear()


class TestCalibrationChangesNothingItShouldNot:
    """The two properties the whole design rests on."""

    def test_calibrating_changes_no_conditions_checksum(self, install_cache) -> None:
        """Difficulty is measured *from* benchmarks; it must not redefine them.

        If difficulty lived on the scenario it would be hashed into the
        fairness record, and re-calibrating would make every earlier
        benchmark on that scenario look like it ran under different
        physics. This is the test that would fail if someone moved it
        there.
        """
        map_data, scenario = build_scenario("doorway")
        before = FairnessRecord.build(map_data, scenario, (0, 1)).conditions_checksum
        install_cache(_cache({"doorway": _entry("doorway", 0.42)}))
        assert get_difficulty("doorway") is not None
        after = FairnessRecord.build(map_data, scenario, (0, 1)).conditions_checksum
        assert before == after

    def test_scenario_schema_has_no_difficulty_field(self) -> None:
        """Difficulty is an outcome of running a scenario, not part of it."""
        assert "difficulty" not in Scenario.model_fields
        _, scenario = build_scenario("open_space")
        assert not hasattr(scenario, "difficulty")


class TestBands:
    @pytest.mark.parametrize(
        ("value", "band"),
        [
            (0.0, "easy"),
            (0.2, "easy"),
            (0.21, "moderate"),
            (0.6, "moderate"),
            (0.61, "hard"),
            (0.999, "hard"),
            (1.0, "unsolved"),
        ],
    )
    def test_band_boundaries(self, value: float, band: str) -> None:
        assert difficulty_band(value) == band

    def test_never_solved_is_not_merely_hard(self) -> None:
        """1.0 is the end of the scale, not a point on it.

        Two scenarios the baseline never solved cannot be ordered against
        each other; calling both "hard" would hide that the measurement
        ran out of resolution.
        """
        assert difficulty_band(1.0) == "unsolved"
        assert difficulty_band(0.99) == "hard"


class TestCacheValidation:
    def test_no_cache_means_no_difficulty(self, install_cache) -> None:
        install_cache(None)
        assert load_calibration() is None
        assert calibration_version() is None
        assert get_difficulty("open_space") is None

    def test_malformed_json_raises(self, install_cache) -> None:
        install_cache("{not json")
        with pytest.raises(DifficultyCalibrationError):
            load_calibration()

    def test_unknown_key_is_rejected(self) -> None:
        """A typo must fail loudly, not become a scenario with no difficulty."""
        payload = _cache({"open_space": _entry("open_space", 0.1)})
        payload["scenarios"]["open_space"]["dificulty"] = 0.9
        with pytest.raises(DifficultyCalibrationError):
            parse_calibration(payload)

    @pytest.mark.parametrize("value", [-0.1, 1.5])
    def test_difficulty_outside_zero_one_is_rejected(self, value: float) -> None:
        payload = _cache({"open_space": _entry("open_space", 0.1)})
        payload["scenarios"]["open_space"]["difficulty"] = value
        with pytest.raises(DifficultyCalibrationError):
            parse_calibration(payload)

    @pytest.mark.parametrize(
        "field", ["algorithm", "seeds", "robot_profile", "git_sha", "benchmark_spec_version"]
    )
    def test_baseline_must_be_complete(self, field: str) -> None:
        """A baseline missing any of its pins is not a baseline.

        "astar+dwa" alone is a name: the same stack on a different robot,
        with different seeds or at a different commit measures a different
        scale, and a reader comparing two caches could not tell.
        """
        payload = _cache({"open_space": _entry("open_space", 0.1)})
        del payload["baseline"][field]
        with pytest.raises(DifficultyCalibrationError):
            parse_calibration(payload)

    def test_empty_seed_list_is_rejected(self) -> None:
        payload = _cache({"open_space": _entry("open_space", 0.1)}, seeds=[])
        with pytest.raises(DifficultyCalibrationError):
            parse_calibration(payload)

    def test_shipped_cache_is_valid_and_covers_the_library(self) -> None:
        """Guards against a hand-edited cache reaching the repository."""
        load_calibration.cache_clear()
        calibration = load_calibration()
        if calibration is None:
            pytest.skip("no calibration cache installed")
        assert set(calibration.scenarios) == set(CURRICULUM_ORDER)
        assert len(calibration.baseline.seeds) >= MIN_CALIBRATION_SEEDS
        assert len(set(calibration.baseline.seeds)) == len(calibration.baseline.seeds)


class TestLookup:
    def test_returns_the_measurement_with_its_baseline(self, install_cache) -> None:
        install_cache(_cache({"doorway": _entry("doorway", 0.4)}))
        label = get_difficulty("doorway")
        assert label is not None
        assert label.value == pytest.approx(0.4)
        assert label.band == "moderate"
        assert label.baseline_algorithm == "astar+dwa"
        assert label.calibration_version == "1.0.0"
        assert label.seed_count == 30
        assert label.adequate is True
        assert label.stale is False

    def test_uncalibrated_scenario_is_none_not_zero(self, install_cache) -> None:
        install_cache(_cache({"doorway": _entry("doorway", 0.4)}))
        assert get_difficulty("open_space") is None

    def test_unknown_scenario_does_not_raise(self, install_cache) -> None:
        """A scenario authored in the app is uncalibrated, not an error."""
        install_cache(_cache({"doorway": _entry("doorway", 0.4)}))
        assert get_difficulty("something-a-user-made") is None

    def test_version_mismatch_returns_none(self, install_cache) -> None:
        """Asking for a calibration that is not installed gets nothing back.

        Not the installed one relabelled: a report pinned to calibration
        1.0.0 must not silently start quoting 2.0.0's numbers.
        """
        install_cache(_cache({"doorway": _entry("doorway", 0.4)}, version="2.0.0"))
        assert get_difficulty("doorway", "1.0.0") is None
        assert get_difficulty("doorway", "2.0.0") is not None
        assert get_difficulty("doorway") is not None

    def test_edited_scenario_marks_the_number_stale(self, install_cache) -> None:
        """The number survives, flagged — a blank would read as never measured."""
        install_cache(_cache({"doorway": _entry("doorway", 0.4, scenario_checksum="0" * 64)}))
        label = get_difficulty("doorway")
        assert label is not None
        assert label.stale is True
        assert label.value == pytest.approx(0.4)

    def test_few_seeds_are_marked_provisional(self, install_cache) -> None:
        install_cache(_cache({"doorway": _entry("doorway", 0.4)}, seeds=[0, 1, 2]))
        label = get_difficulty("doorway")
        assert label is not None
        assert label.adequate is False


class TestCoverage:
    def test_uncalibrated_platform_says_so(self, install_cache) -> None:
        install_cache(None)
        coverage = difficulty_coverage()
        assert coverage.scenario_count == 0
        assert set(coverage.uncalibrated) == set(CURRICULUM_ORDER)
        assert any("no difficulty calibration" in w for w in coverage.warnings)

    def test_narrow_range_is_reported(self, install_cache) -> None:
        """A scale everything sits on one point of ranks nothing."""
        install_cache(
            _cache(
                {
                    "open_space": _entry("open_space", 0.0),
                    "doorway": _entry("doorway", 0.05),
                }
            )
        )
        coverage = difficulty_coverage(("open_space", "doorway"))
        assert coverage.spread == pytest.approx(0.05)
        assert any("does not separate stacks" in w for w in coverage.warnings)
        assert any("headroom" in w for w in coverage.warnings)

    def test_all_hard_is_reported(self, install_cache) -> None:
        install_cache(
            _cache(
                {
                    "open_space": _entry("open_space", 0.7),
                    "doorway": _entry("doorway", 1.0),
                }
            )
        )
        coverage = difficulty_coverage(("open_space", "doorway"))
        assert any("failures dominate" in w for w in coverage.warnings)
        assert any("never solved" in w for w in coverage.warnings)
        assert coverage.band_counts == {"hard": 1, "unsolved": 1}

    def test_useful_spread_produces_no_spread_warning(self, install_cache) -> None:
        install_cache(
            _cache(
                {
                    "open_space": _entry("open_space", 0.0),
                    "doorway": _entry("doorway", 0.5),
                }
            )
        )
        coverage = difficulty_coverage(("open_space", "doorway"))
        assert coverage.spread == pytest.approx(0.5)
        assert not any("does not separate" in w for w in coverage.warnings)

    def test_a_full_spread_with_an_empty_middle_is_still_reported(self, install_cache) -> None:
        """The failure the spread check cannot see.

        Scenarios split between 0.0 and 1.0 score a perfect spread of 1.0
        and separate nothing: every competent stack passes the same ones
        and fails the same ones. This is what the real calibration of the
        built-in library looks like, so the check has to exist.
        """
        install_cache(
            _cache(
                {
                    "open_space": _entry("open_space", 0.0),
                    "doorway": _entry("doorway", 0.0),
                    "narrow_corridor": _entry("narrow_corridor", 1.0),
                    "sudden_stop": _entry("sudden_stop", 1.0),
                }
            )
        )
        coverage = difficulty_coverage(("open_space", "doorway", "narrow_corridor", "sudden_stop"))
        assert coverage.spread == pytest.approx(1.0)
        assert coverage.midrange_count == 0
        assert any("sit between" in w for w in coverage.warnings)
        assert not any("does not separate stacks by difficulty" in w for w in coverage.warnings)

    def test_scenarios_in_the_middle_satisfy_the_check(self, install_cache) -> None:
        install_cache(
            _cache(
                {
                    "open_space": _entry("open_space", 0.0),
                    "doorway": _entry("doorway", 0.35),
                    "narrow_corridor": _entry("narrow_corridor", 0.6),
                    "sudden_stop": _entry("sudden_stop", 1.0),
                }
            )
        )
        coverage = difficulty_coverage(("open_space", "doorway", "narrow_corridor", "sudden_stop"))
        assert coverage.midrange_count == 2
        assert not any("sit between" in w for w in coverage.warnings)

    def test_missing_scenarios_are_counted_not_ignored(self, install_cache) -> None:
        install_cache(_cache({"open_space": _entry("open_space", 0.0)}))
        coverage = difficulty_coverage()
        assert "doorway" in coverage.uncalibrated
        assert any("not calibrated" in w for w in coverage.warnings)

    def test_provisional_seed_count_is_reported(self, install_cache) -> None:
        install_cache(
            _cache(
                {
                    "open_space": _entry("open_space", 0.0),
                    "doorway": _entry("doorway", 0.5),
                },
                seeds=[0, 1, 2],
            )
        )
        coverage = difficulty_coverage(("open_space", "doorway"))
        assert any("provisional" in w for w in coverage.warnings)


class TestCalibrationScript:
    """The script is the only sanctioned way a difficulty is produced."""

    def test_dry_run_writes_nothing_and_marks_itself(self, tmp_path, capsys) -> None:
        output = tmp_path / "cache.json"
        exit_code = script.main(
            [
                "--dry-run",
                "--dry-run-seeds",
                "1",
                "--scenarios",
                "open_space",
                "--output",
                str(output),
                "--write",
            ]
        )
        assert exit_code == 0
        assert not output.exists(), "a dry run must never install a calibration"
        assert "DRY RUN" in capsys.readouterr().out

    def test_dry_run_version_cannot_be_mistaken_for_the_real_scale(self) -> None:
        calibration = script.build_calibration(
            ("open_space",),
            algorithm="astar+dwa",
            algorithm_config={},
            seeds=(0,),
            version="1.0.0-dryrun",
            notes=None,
        )
        assert calibration.calibration_version.endswith("-dryrun")

    def test_same_baseline_and_seeds_reproduce_the_cache(self) -> None:
        """The cache is a function of code plus baseline, nothing else.

        Nothing is time-stamped, so two runs of the same calibration are
        byte-identical — which is what makes "re-run it and check" a
        usable answer to "is this number still right?".
        """
        kwargs = {
            "algorithm": "astar+dwa",
            "algorithm_config": {},
            "seeds": (0, 1),
            "version": "test",
            "notes": None,
        }
        first = script.build_calibration(("open_space",), **kwargs)
        second = script.build_calibration(("open_space",), **kwargs)
        assert script.serialise(first) == script.serialise(second)

    def test_difficulty_is_one_minus_success_rate(self) -> None:
        entry, _ = script.calibrate_scenario(
            "open_space", algorithm="astar+dwa", algorithm_config={}, seeds=(0, 1)
        )
        assert entry.difficulty == pytest.approx(1.0 - entry.success_rate)
        assert entry.episodes == 2
        assert sum(entry.status_counts.values()) == 2

    def test_interval_brackets_the_difficulty(self) -> None:
        """Zero failures out of two seeds is not proof of an easy scenario."""
        entry, _ = script.calibrate_scenario(
            "open_space", algorithm="astar+dwa", algorithm_config={}, seeds=(0, 1)
        )
        low, high = entry.ci95
        assert low <= entry.difficulty <= high
        assert high > entry.difficulty, "an interval from two seeds cannot be a point"

    def test_entry_records_what_it_measured(self) -> None:
        entry, _ = script.calibrate_scenario(
            "doorway", algorithm="astar+dwa", algorithm_config={}, seeds=(0,)
        )
        map_data, scenario = build_scenario("doorway")
        assert entry.map_checksum == map_data.checksum()
        assert entry.scenario_checksum == _scenario_checksum(scenario)
        assert entry.scenario_split == "dev"

    def test_unknown_scenario_is_refused(self) -> None:
        with pytest.raises(SystemExit):
            script.main(["--dry-run", "--scenarios", "not_a_scenario"])

    def test_serialised_cache_round_trips(self) -> None:
        calibration = script.build_calibration(
            ("open_space",),
            algorithm="astar+dwa",
            algorithm_config={},
            seeds=(0,),
            version="test",
            notes="round trip",
        )
        assert parse_calibration(json.loads(script.serialise(calibration))) == calibration

    def test_git_sha_is_stated_even_when_unknown(self) -> None:
        sha = script.git_sha()
        assert sha, "a missing commit must be recorded as unknown, not omitted"


class TestCalibratingAnAuthoredScenario:
    """A scenario drawn in the editor (plan 2.3) can get on the scale.

    It is not in the built-in library, so there is nothing to build by
    name; the calibration takes a bundle exported from the API instead.
    Without this, the editor could fill the empty middle of the
    difficulty range and nobody could measure that it had.
    """

    def _bundle(self, tmp_path, *, wrapped: bool = False) -> Path:
        map_data, scenario = build_scenario("open_space")
        renamed = scenario.model_copy(update={"name": "authored_scenario"})
        payload = (
            {
                # The shapes GET /maps/{id} and GET /scenarios/{id} return,
                # which is what someone pasting two curl outputs will have.
                "map": {"id": "m1", "map_data": map_data.model_dump(mode="json")},
                "scenario": {"id": "s1", "scenario": renamed.model_dump(mode="json")},
            }
            if wrapped
            else {
                "map": map_data.model_dump(mode="json"),
                "scenario": renamed.model_dump(mode="json"),
            }
        )
        path = tmp_path / "bundle.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_bundle_loads_bare_objects(self, tmp_path) -> None:
        map_data, scenario = script.load_bundle(self._bundle(tmp_path))
        assert scenario.name == "authored_scenario"
        assert map_data.name == "open-space"

    def test_bundle_loads_api_resources(self, tmp_path) -> None:
        map_data, scenario = script.load_bundle(self._bundle(tmp_path, wrapped=True))
        assert scenario.name == "authored_scenario"
        assert map_data.name == "open-space"

    def test_bundle_missing_a_half_is_refused(self, tmp_path) -> None:
        path = tmp_path / "half.json"
        path.write_text(json.dumps({"scenario": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="map and a scenario"):
            script.load_bundle(path)

    def test_an_authored_scenario_is_calibrated_as_unassigned(self, tmp_path) -> None:
        """Measuring how hard it is says nothing about where it belongs.

        Difficulty and split are separate facts (P03 and P05); a
        calibration run must not be a back door into the dev set.
        """
        map_data, scenario = script.load_bundle(self._bundle(tmp_path))
        calibration = script.build_calibration(
            ("authored_scenario",),
            algorithm="astar+dwa",
            algorithm_config={},
            seeds=(0,),
            version="authored",
            notes=None,
            sources={"authored_scenario": (map_data, scenario)},
        )
        entry = calibration.scenarios["authored_scenario"]
        assert entry.scenario_split == "unassigned"
        assert 0.0 <= entry.difficulty <= 1.0
        assert entry.map_checksum == map_data.checksum()

    def test_a_bundle_scenario_is_not_rejected_as_unknown(self, tmp_path, capsys) -> None:
        exit_code = script.main(
            [
                "--dry-run",
                "--dry-run-seeds",
                "1",
                "--scenario-file",
                str(self._bundle(tmp_path)),
            ]
        )
        assert exit_code == 0
        assert "authored_scenario" in capsys.readouterr().out
