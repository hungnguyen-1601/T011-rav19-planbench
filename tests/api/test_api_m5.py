"""API tests for M5: scenario library, background worker, leaderboard, failures."""

from __future__ import annotations

import time

import pytest
from conftest import ADMIN, auth_headers
from fastapi.testclient import TestClient


def import_library(client: TestClient, headers: dict, name: str = "open_space") -> dict:
    response = client.post(f"/api/v1/scenario-library/{name}/import", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def owned_benchmark(client: TestClient, alice_headers: dict, **kw) -> dict:
    """A benchmark in DRAFT, owned by the caller. Still needs the spec
    gate cleared (see approve_via_admin_override) before it can run."""
    imported = import_library(client, alice_headers, kw.pop("library", "open_space"))
    payload = {
        "name": "m5-benchmark",
        "map_id": imported["map_id"],
        "scenario_id": imported["scenario_id"],
        "algorithms": [{"id": "astar+dwa"}],
        "seeds": [1, 2],
        **kw,
    }
    created = client.post("/api/v1/benchmarks", json=payload, headers=alice_headers)
    assert created.status_code == 201, created.text
    return created.json()


def approve_via_admin_override(client: TestClient, benchmark_id: str) -> None:
    """Clear the spec gate the fastest legitimate way for a test that
    is not about the approval gate itself. Requires
    PLANBENCH_ADMIN_OVERRIDE_ENABLED=true, set by conftest."""
    response = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/admin-override-approve",
        json={"comment": "test fixture"},
        headers=auth_headers(client, ADMIN),
    )
    assert response.status_code == 200, response.text


def run_owned_benchmark(client: TestClient, alice_headers: dict, **kw) -> dict:
    """Create, clear the spec gate, and run — the common case for tests
    in this file that are not about the approval gate itself."""
    benchmark = owned_benchmark(client, alice_headers, **kw)
    approve_via_admin_override(client, benchmark["id"])
    run = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
    assert run.status_code == 200, run.text
    return benchmark


class TestScenarioLibrary:
    def test_lists_scenarios_in_curriculum_order(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        response = client.get("/api/v1/scenario-library", headers=alice_headers)
        assert response.status_code == 200
        entries = response.json()
        assert entries[0]["name"] == "open_space"
        assert entries[-1]["name"] == "dynamic_warehouse"
        assert [e["curriculum_index"] for e in entries] == list(range(len(entries)))
        warehouse = entries[-1]
        assert warehouse["dynamic_obstacles"] == 3

    def test_split_marks_the_two_holdout_scenarios(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        """P05: intersection and dynamic_warehouse are report-only."""
        entries = {
            e["name"]: e
            for e in client.get(
                "/api/v1/scenario-library", headers=alice_headers
            ).json()
        }
        assert entries["intersection"]["split"] == "holdout"
        assert entries["dynamic_warehouse"]["split"] == "holdout"
        assert entries["open_space"]["split"] == "dev"

    def test_difficulty_is_null_or_a_fraction(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        """P03: null until scripts/calibrate_difficulty.py has run; a
        fraction in [0, 1] once it has — either is a valid response, an
        exception is not."""
        entries = client.get("/api/v1/scenario-library", headers=alice_headers).json()
        for entry in entries:
            difficulty = entry["difficulty"]
            assert difficulty is None or 0.0 <= difficulty <= 1.0

    def test_import_creates_map_and_scenario(self, client: TestClient, alice_headers) -> None:
        imported = import_library(client, alice_headers, "doorway")
        assert imported["library_name"] == "doorway"
        assert (
            client.get(f"/api/v1/maps/{imported['map_id']}", headers=alice_headers).status_code
            == 200
        )
        stored = client.get(
            f"/api/v1/scenarios/{imported['scenario_id']}", headers=alice_headers
        )
        assert stored.status_code == 200
        assert stored.json()["scenario"]["name"] == "doorway"

    def test_import_of_dynamic_scenario_carries_obstacles(
        self, client: TestClient, alice_headers
    ) -> None:
        imported = import_library(client, alice_headers, "crossing_obstacle")
        assert len(imported["scenario"]["dynamic_obstacles"]) == 1
        assert imported["scenario"]["dynamic_obstacles"][0]["name"] == "pedestrian"

    def test_unknown_library_scenario_rejected(self, client: TestClient, alice_headers) -> None:
        response = client.post("/api/v1/scenario-library/mars_colony/import", headers=alice_headers)
        assert response.status_code == 422

    def test_import_requires_a_signed_in_member(self, client: TestClient) -> None:
        """Importing writes to the shared library, so it needs an account."""
        assert client.post("/api/v1/scenario-library/open_space/import").status_code == 401


class TestBackgroundWorker:
    def test_run_async_completes_and_reports_progress(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        benchmark = owned_benchmark(client, alice_headers)
        approve_via_admin_override(client, benchmark["id"])
        queued = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run-async", headers=alice_headers
        )
        assert queued.status_code == 202
        assert queued.json()["total"] == 2

        deadline = time.monotonic() + 120
        state = queued.json()["state"]
        while state in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.2)
            state = client.get(
                f"/api/v1/benchmarks/{benchmark['id']}/job", headers=alice_headers
            ).json()["state"]
        final = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/job", headers=alice_headers
        ).json()
        assert final["state"] == "succeeded", final
        assert final["progress"] == 2

        results = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/results", headers=carol_headers
        ).json()
        assert results["benchmark"]["state"] == "pending_review"
        assert len(results["report"]["runs"]) == 2

    def test_a_benchmark_under_spec_review_cannot_be_queued(
        self, client: TestClient, alice_headers, bob_headers
    ) -> None:
        """The gate is applied before queueing, not inside the worker."""
        benchmark = owned_benchmark(client, alice_headers, seeds=[1])
        sent = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/review-requests",
            json={"reviewer_nickname": "bob", "stage": "spec"},
            headers=alice_headers,
        )
        assert sent.status_code == 201, sent.text
        queued = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run-async", headers=alice_headers
        )
        assert queued.status_code == 403
        # Nothing ran, so there is nothing to publish.
        results = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/results", headers=alice_headers
        ).json()
        assert results["report"] is None

    def test_job_status_404_for_unknown_benchmark(self, client: TestClient, alice_headers) -> None:
        assert (
            client.get("/api/v1/benchmarks/missing/job", headers=alice_headers).status_code == 404
        )


class TestFailureAnalysisEndpoint:
    def test_reports_evidence_for_an_episode(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        benchmark = run_owned_benchmark(client, alice_headers, seeds=[1])
        episode_id = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/episodes", headers=carol_headers
        ).json()[0]["id"]

        response = client.get(f"/api/v1/episodes/{episode_id}/failures", headers=carol_headers)
        assert response.status_code == 200
        report = response.json()
        assert report["primary"]["category"] in {"none", "timeout", "stuck", "no_progress"}
        assert report["primary"]["confidence"] in {"high", "medium", "low"}
        # Findings must always be checkable.
        assert isinstance(report["primary"]["evidence"], list)


class TestLeaderboard:
    def test_only_accepted_benchmarks_are_ranked(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        benchmark = run_owned_benchmark(client, alice_headers, seeds=[1])

        before = client.get("/api/v1/leaderboard", headers=carol_headers).json()
        assert before["groups"] == []  # pending review -> not published

        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={"comment": "ok"},
            headers=alice_headers,
        )
        after = client.get("/api/v1/leaderboard", headers=carol_headers).json()
        assert len(after["groups"]) == 1
        entry = after["groups"][0]["entries"][0]
        assert entry["algorithm"] == "astar+dwa"
        assert 0.0 <= entry["overall_score"] <= 1.0
        assert after["score_formula"]
        assert after["weights"]["success"] == 0.40
        # P02: every entry declares what it was allowed to see.
        assert entry["observation_class"] == "lidar_only"
        assert after["groups"][0]["mixed_observation_classes"] is False
        # P04: one algorithm, one group -> it ranked first, average 1.0.
        assert after["algorithm_ranks"] == {"astar+dwa": 1.0}

    def test_generalization_gap_spans_dev_and_holdout_scenarios(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        """P05: an algorithm accepted on both a dev and a holdout
        scenario gets a reported gap; the sign/magnitude are not the
        point here, only that the field is actually populated."""
        dev = run_owned_benchmark(client, alice_headers, seeds=[1], library="open_space")
        client.post(
            f"/api/v1/benchmarks/{dev['id']}/accept-result", json={}, headers=alice_headers
        )
        holdout = run_owned_benchmark(client, alice_headers, seeds=[1], library="intersection")
        client.post(
            f"/api/v1/benchmarks/{holdout['id']}/accept-result", json={}, headers=alice_headers
        )
        after = client.get("/api/v1/leaderboard", headers=carol_headers).json()
        assert len(after["groups"]) == 2
        assert "astar+dwa" in after["generalization_gap"]
        assert -1.0 <= after["generalization_gap"]["astar+dwa"] <= 1.0

    def test_difficulty_curve_present_when_a_scenario_is_calibrated(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        """P03: a point only appears for scenarios with a cached
        calibration — skips gracefully if the cache has never been
        generated (see scripts/calibrate_difficulty.py)."""
        from planbench_benchmark.difficulty import load_difficulty_cache

        if "open_space" not in load_difficulty_cache():
            pytest.skip("difficulty cache not generated — run scripts/calibrate_difficulty.py")
        benchmark = run_owned_benchmark(client, alice_headers, seeds=[1], library="open_space")
        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result", json={}, headers=alice_headers
        )
        after = client.get("/api/v1/leaderboard", headers=carol_headers).json()
        assert after["difficulty_curve"]["astar+dwa"]
        difficulty, success_rate = after["difficulty_curve"]["astar+dwa"][0]
        assert 0.0 <= difficulty <= 1.0
        assert 0.0 <= success_rate <= 1.0

    def test_unreviewed_results_visible_only_on_request(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        benchmark = run_owned_benchmark(client, alice_headers, seeds=[1])
        response = client.get("/api/v1/leaderboard?accepted_only=false", headers=carol_headers)
        assert len(response.json()["groups"]) == 1

    def test_weights_are_configurable_and_returned(
        self, client: TestClient, alice_headers, carol_headers
    ) -> None:
        benchmark = run_owned_benchmark(client, alice_headers, seeds=[1])
        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={},
            headers=alice_headers,
        )
        response = client.get(
            "/api/v1/leaderboard?weight_success=1&weight_safety=0"
            "&weight_efficiency=0&weight_smoothness=0",
            headers=carol_headers,
        ).json()
        assert response["weights"] == {
            "success": 1.0,
            "safety": 0.0,
            "efficiency": 0.0,
            "smoothness": 0.0,
        }
        entry = response["groups"][0]["entries"][0]
        # With only success weighted, the score equals the success rate.
        assert entry["overall_score"] == entry["success_rate"]

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/leaderboard").status_code == 401
