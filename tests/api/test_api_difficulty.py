"""API tests for P03: measured difficulty on the library and its own endpoint.

The API's job here is to hand out a measurement without ever inventing
one. So these tests are about the null cases as much as the populated
ones: an uncalibrated scenario comes back ``null`` rather than borrowing
the curriculum position, and an uncalibrated platform answers with an
empty scale and a warning rather than a 500.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from planbench_benchmark import difficulty as difficulty_module
from planbench_benchmark.difficulty import load_calibration
from planbench_benchmark.scenarios import build_scenario
from planbench_benchmark.spec import _scenario_checksum


def _cache(scenario_names: tuple[str, ...], *, version: str = "9.9.9") -> dict:
    scenarios = {}
    for index, name in enumerate(scenario_names):
        map_data, scenario = build_scenario(name)
        value = round(index / max(1, len(scenario_names) - 1), 3)
        scenarios[name] = {
            "difficulty": value,
            "ci95": [max(0.0, value - 0.1), min(1.0, value + 0.1)],
            "success_rate": 1.0 - value,
            "episodes": 30,
            "status_counts": {"success": 30},
            "map_checksum": map_data.checksum(),
            "scenario_checksum": _scenario_checksum(scenario),
            "scenario_split": "dev",
        }
    return {
        "calibration_version": version,
        "baseline": {
            "algorithm": "astar+dwa",
            "algorithm_config": {},
            "replanning_enabled": False,
            "seeds": list(range(30)),
            "robot_profile": {"radius": 0.3},
            "benchmark_spec_version": "1",
            "protocol_version": "1.0.0",
            "git_sha": "abc123def456",
        },
        "scenarios": scenarios,
        "notes": "test calibration",
    }


@pytest.fixture
def calibrated(tmp_path, monkeypatch):
    """Install a known calibration for the duration of one test."""

    def _install(payload: dict | None):
        path = tmp_path / "difficulty_calibration.json"
        if payload is not None:
            path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(difficulty_module, "CALIBRATION_FILE", path)
        load_calibration.cache_clear()

    yield _install
    load_calibration.cache_clear()


class TestLibraryEntries:
    def test_calibrated_scenario_carries_its_difficulty(
        self, client: TestClient, calibrated
    ) -> None:
        calibrated(_cache(("open_space", "doorway")))
        entries = {row["name"]: row for row in client.get("/api/v1/scenario-library").json()}
        label = entries["open_space"]["difficulty"]
        assert label["value"] == 0.0
        assert label["band"] == "easy"
        assert label["baseline_algorithm"] == "astar+dwa"
        assert label["calibration_version"] == "9.9.9"
        assert label["seed_count"] == 30
        assert label["adequate"] is True
        assert label["ci95"][0] <= label["value"] <= label["ci95"][1]

    def test_uncalibrated_scenario_is_null_not_a_curriculum_index(
        self, client: TestClient, calibrated
    ) -> None:
        """The two must never be confused: one is measured, one is intent."""
        calibrated(_cache(("open_space",)))
        entries = {row["name"]: row for row in client.get("/api/v1/scenario-library").json()}
        assert entries["intersection"]["difficulty"] is None
        assert entries["intersection"]["curriculum_index"] == 8

    def test_no_calibration_leaves_every_entry_null(self, client: TestClient, calibrated) -> None:
        calibrated(None)
        entries = client.get("/api/v1/scenario-library").json()
        assert all(row["difficulty"] is None for row in entries)


class TestDifficultyCalibrationEndpoint:
    def test_reports_the_scale_and_its_baseline(self, client: TestClient, calibrated) -> None:
        calibrated(_cache(("open_space", "doorway", "intersection")))
        body = client.get("/api/v1/difficulty-calibration").json()
        assert body["calibration_version"] == "9.9.9"
        assert body["baseline"]["algorithm"] == "astar+dwa"
        assert body["baseline"]["replanning_enabled"] is False
        assert len(body["baseline"]["seeds"]) == 30
        assert body["baseline"]["git_sha"] == "abc123def456"
        assert {row["scenario_name"] for row in body["scenarios"]} == {
            "open_space",
            "doorway",
            "intersection",
        }

    def test_coverage_reports_the_range_and_the_gaps(self, client: TestClient, calibrated) -> None:
        calibrated(_cache(("open_space", "doorway", "intersection")))
        coverage = client.get("/api/v1/difficulty-calibration").json()["coverage"]
        assert coverage["scenario_count"] == 3
        assert coverage["min_difficulty"] == 0.0
        assert coverage["max_difficulty"] == 1.0
        assert coverage["spread"] == 1.0
        # The seven library scenarios this cache says nothing about are
        # named, not silently left out of the picture.
        assert len(coverage["uncalibrated"]) == 7
        assert any("not calibrated" in w for w in coverage["warnings"])

    def test_uncalibrated_platform_answers_instead_of_failing(
        self, client: TestClient, calibrated
    ) -> None:
        """ "Not measured" is a normal state and must not read as an outage."""
        calibrated(None)
        response = client.get("/api/v1/difficulty-calibration")
        assert response.status_code == 200
        body = response.json()
        assert body["calibration_version"] is None
        assert body["baseline"] is None
        assert body["scenarios"] == []
        assert any("no difficulty calibration" in w for w in body["coverage"]["warnings"])

    def test_endpoint_is_read_only(self, client: TestClient) -> None:
        """A difficulty that can be set from a form is not a measurement."""
        assert client.post("/api/v1/difficulty-calibration", json={}).status_code == 405
