"""API tests for M5: scenario library, background worker, leaderboard, failures."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def import_library(client: TestClient, headers: dict, name: str = "open_space") -> dict:
    response = client.post(f"/api/v1/scenario-library/{name}/import", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def approved_benchmark(
    client: TestClient, operator_headers: dict, reviewer_headers: dict, **kw
) -> dict:
    imported = import_library(client, operator_headers, kw.pop("library", "open_space"))
    payload = {
        "name": "m5-benchmark",
        "map_id": imported["map_id"],
        "scenario_id": imported["scenario_id"],
        "algorithms": [{"id": "astar+dwa"}],
        "seeds": [1, 2],
        **kw,
    }
    created = client.post("/api/v1/benchmarks", json=payload, headers=operator_headers)
    assert created.status_code == 201, created.text
    benchmark_id = created.json()["id"]
    client.post(f"/api/v1/benchmarks/{benchmark_id}/submit", json={}, headers=operator_headers)
    approved = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=reviewer_headers
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


class TestScenarioLibrary:
    def test_lists_scenarios_in_curriculum_order(self, client: TestClient) -> None:
        response = client.get("/api/v1/scenario-library")
        assert response.status_code == 200
        entries = response.json()
        assert entries[0]["name"] == "open_space"
        assert entries[-1]["name"] == "dynamic_warehouse"
        assert [e["curriculum_index"] for e in entries] == list(range(len(entries)))
        warehouse = entries[-1]
        assert warehouse["dynamic_obstacles"] == 3

    def test_import_creates_map_and_scenario(self, client: TestClient, operator_headers) -> None:
        imported = import_library(client, operator_headers, "doorway")
        assert imported["library_name"] == "doorway"
        assert client.get(f"/api/v1/maps/{imported['map_id']}").status_code == 200
        stored = client.get(f"/api/v1/scenarios/{imported['scenario_id']}")
        assert stored.status_code == 200
        assert stored.json()["scenario"]["name"] == "doorway"

    def test_import_of_dynamic_scenario_carries_obstacles(
        self, client: TestClient, operator_headers
    ) -> None:
        imported = import_library(client, operator_headers, "crossing_obstacle")
        assert len(imported["scenario"]["dynamic_obstacles"]) == 1
        assert imported["scenario"]["dynamic_obstacles"][0]["name"] == "pedestrian"

    def test_unknown_library_scenario_rejected(self, client: TestClient, operator_headers) -> None:
        response = client.post(
            "/api/v1/scenario-library/mars_colony/import", headers=operator_headers
        )
        assert response.status_code == 422

    def test_import_requires_operator(self, client: TestClient, reviewer_headers) -> None:
        response = client.post(
            "/api/v1/scenario-library/open_space/import", headers=reviewer_headers
        )
        assert response.status_code == 403


class TestBackgroundWorker:
    def test_run_async_completes_and_reports_progress(
        self, client: TestClient, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(client, operator_headers, reviewer_headers)
        queued = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run-async", headers=operator_headers
        )
        assert queued.status_code == 202
        assert queued.json()["total"] == 2

        deadline = time.monotonic() + 120
        state = queued.json()["state"]
        while state in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.2)
            state = client.get(
                f"/api/v1/benchmarks/{benchmark['id']}/job", headers=operator_headers
            ).json()["state"]
        final = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/job", headers=operator_headers
        ).json()
        assert final["state"] == "succeeded", final
        assert final["progress"] == 2

        results = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/results", headers=reviewer_headers
        ).json()
        assert results["benchmark"]["state"] == "pending_review"
        assert len(results["report"]["runs"]) == 2

    def test_unapproved_benchmark_cannot_be_queued(
        self, client: TestClient, operator_headers
    ) -> None:
        imported = import_library(client, operator_headers)
        created = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "unapproved",
                "map_id": imported["map_id"],
                "scenario_id": imported["scenario_id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=operator_headers,
        ).json()
        queued = client.post(
            f"/api/v1/benchmarks/{created['id']}/run-async", headers=operator_headers
        )
        assert queued.status_code == 202  # queued, then rejected by the gate
        deadline = time.monotonic() + 30
        state = "queued"
        while state in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.1)
            state = client.get(
                f"/api/v1/benchmarks/{created['id']}/job", headers=operator_headers
            ).json()["state"]
        job = client.get(f"/api/v1/benchmarks/{created['id']}/job", headers=operator_headers).json()
        assert job["state"] == "failed"
        assert "invalid_state" in job["error"] or "cannot run" in job["error"]
        # And nothing was recorded.
        results = client.get(
            f"/api/v1/benchmarks/{created['id']}/results", headers=operator_headers
        ).json()
        assert results["report"] is None

    def test_job_status_404_for_unknown_benchmark(
        self, client: TestClient, operator_headers
    ) -> None:
        assert (
            client.get("/api/v1/benchmarks/missing/job", headers=operator_headers).status_code
            == 404
        )


class TestFailureAnalysisEndpoint:
    def test_reports_evidence_for_an_episode(
        self, client: TestClient, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(client, operator_headers, reviewer_headers, seeds=[1])
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        episode_id = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/episodes", headers=reviewer_headers
        ).json()[0]["id"]

        response = client.get(f"/api/v1/episodes/{episode_id}/failures", headers=reviewer_headers)
        assert response.status_code == 200
        report = response.json()
        assert report["primary"]["category"] in {"none", "timeout", "stuck", "no_progress"}
        assert report["primary"]["confidence"] in {"high", "medium", "low"}
        # Findings must always be checkable.
        assert isinstance(report["primary"]["evidence"], list)


class TestLeaderboard:
    def test_only_accepted_benchmarks_are_ranked(
        self, client: TestClient, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(client, operator_headers, reviewer_headers, seeds=[1])
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)

        before = client.get("/api/v1/leaderboard", headers=reviewer_headers).json()
        assert before["groups"] == []  # pending review -> not published

        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={"comment": "ok"},
            headers=reviewer_headers,
        )
        after = client.get("/api/v1/leaderboard", headers=reviewer_headers).json()
        assert len(after["groups"]) == 1
        entry = after["groups"][0]["entries"][0]
        assert entry["algorithm"] == "astar+dwa"
        assert 0.0 <= entry["overall_score"] <= 1.0
        assert after["score_formula"]
        assert after["weights"]["success"] == 0.40

    def test_unreviewed_results_visible_only_on_request(
        self, client: TestClient, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(client, operator_headers, reviewer_headers, seeds=[1])
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        response = client.get("/api/v1/leaderboard?accepted_only=false", headers=reviewer_headers)
        assert len(response.json()["groups"]) == 1

    def test_weights_are_configurable_and_returned(
        self, client: TestClient, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(client, operator_headers, reviewer_headers, seeds=[1])
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={},
            headers=reviewer_headers,
        )
        response = client.get(
            "/api/v1/leaderboard?weight_success=1&weight_safety=0"
            "&weight_efficiency=0&weight_smoothness=0",
            headers=reviewer_headers,
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
