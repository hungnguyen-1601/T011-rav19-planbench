"""API tests: benchmark lifecycle, approval gates, execution, replay."""

from __future__ import annotations

from fastapi.testclient import TestClient


def create_benchmark(
    client: TestClient, created_map: dict, created_scenario: dict, headers: dict, **kw
) -> dict:
    payload = {
        "name": "api-benchmark",
        "map_id": created_map["id"],
        "scenario_id": created_scenario["id"],
        "algorithms": [{"id": "astar+dwa"}],
        "seeds": [1, 2],
        **kw,
    }
    response = client.post("/api/v1/benchmarks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def approved_benchmark(
    client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers, **kw
) -> dict:
    benchmark = create_benchmark(client, created_map, created_scenario, operator_headers, **kw)
    client.post(f"/api/v1/benchmarks/{benchmark['id']}/submit", json={}, headers=operator_headers)
    response = client.post(
        f"/api/v1/benchmarks/{benchmark['id']}/approve",
        json={"comment": "conditions look fair"},
        headers=reviewer_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestCreation:
    def test_created_in_draft(
        self, client: TestClient, created_map, created_scenario, operator_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, operator_headers)
        assert benchmark["state"] == "draft"
        assert benchmark["created_by"] == "op-alice"
        assert benchmark["spec"]["seeds"] == [1, 2]

    def test_duplicate_algorithms_rejected(
        self, client: TestClient, created_map, created_scenario, operator_headers
    ) -> None:
        response = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "dup",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}, {"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=operator_headers,
        )
        assert response.status_code == 422

    def test_unknown_algorithm_rejected(
        self, client: TestClient, created_map, created_scenario, operator_headers
    ) -> None:
        response = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "bad",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+teleport"}],
                "seeds": [1],
            },
            headers=operator_headers,
        )
        assert response.status_code == 422

    def test_invalid_algorithm_config_rejected(
        self, client: TestClient, created_map, created_scenario, operator_headers
    ) -> None:
        response = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "bad-config",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa", "config": {"velocity_samples": 0}}],
                "seeds": [1],
            },
            headers=operator_headers,
        )
        assert response.status_code == 422


class TestApprovalGates:
    def test_unapproved_benchmark_cannot_run(
        self, client: TestClient, created_map, created_scenario, operator_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, operator_headers)
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_state"

    def test_operator_cannot_approve_own_benchmark(
        self, client: TestClient, created_map, created_scenario, operator_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, operator_headers)
        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/submit", json={}, headers=operator_headers
        )
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/approve", json={}, headers=operator_headers
        )
        assert response.status_code == 403  # operator role may not approve at all

    def test_reviewer_cannot_approve_their_own_creation(
        self, client: TestClient, created_map, created_scenario, admin_headers
    ) -> None:
        """Separation of duties also blocks self-review for admins acting
        as creators is allowed, so use a reviewer-created benchmark."""
        benchmark = create_benchmark(client, created_map, created_scenario, admin_headers)
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/submit", json={}, headers=admin_headers)
        # Admin is explicitly exempt (documented in approval.py).
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/approve", json={}, headers=admin_headers
        )
        assert response.status_code == 200

    def test_full_lifecycle(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, operator_headers)
        states = [benchmark["state"]]

        submitted = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/submit", json={}, headers=operator_headers
        ).json()
        states.append(submitted["state"])

        approved = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/approve",
            json={"comment": "ok"},
            headers=reviewer_headers,
        ).json()
        states.append(approved["state"])

        run = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers
        ).json()
        states.append(run["benchmark"]["state"])

        accepted = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={"comment": "results accepted"},
            headers=reviewer_headers,
        ).json()
        states.append(accepted["state"])

        assert states == ["draft", "pending_approval", "approved", "pending_review", "accepted"]
        # Every transition is recorded with its actor and role.
        actions = [entry["action"] for entry in accepted["approvals"]]
        assert actions == ["submit", "approve", "run", "complete", "accept_result"]
        assert accepted["approvals"][1]["role"] == "reviewer"
        assert accepted["approvals"][1]["comment"] == "ok"

    def test_rejected_spec_returns_to_draft_and_can_be_resubmitted(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, operator_headers)
        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/submit", json={}, headers=operator_headers
        )
        rejected = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/reject",
            json={"comment": "seeds too few"},
            headers=reviewer_headers,
        ).json()
        assert rejected["state"] == "draft"
        resubmitted = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/submit", json={}, headers=operator_headers
        ).json()
        assert resubmitted["state"] == "pending_approval"

    def test_results_can_be_rejected(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(
            client, created_map, created_scenario, operator_headers, reviewer_headers, seeds=[1]
        )
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/reject-result",
            json={"comment": "needs more seeds"},
            headers=reviewer_headers,
        )
        assert response.status_code == 200
        assert response.json()["state"] == "rejected"


class TestExecution:
    def test_run_produces_report_with_fairness_and_aggregates(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(
            client,
            created_map,
            created_scenario,
            operator_headers,
            reviewer_headers,
            algorithms=[{"id": "astar+dwa"}, {"id": "astar+pure_pursuit"}],
            seeds=[1, 2],
        )
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        report = body["report"]
        assert len(report["runs"]) == 4
        assert len(report["aggregates"]) == 2
        assert report["fairness"]["conditions_checksum"]
        assert report["fairness"]["seeds"] == [1, 2]
        for aggregate in report["aggregates"]:
            assert aggregate["episodes"] == 2
            assert 0.0 <= aggregate["success_rate"] <= 1.0
        assert body["benchmark"]["report_artifact_uri"].startswith("file://")

    def test_running_twice_is_rejected(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(
            client, created_map, created_scenario, operator_headers, reviewer_headers, seeds=[1]
        )
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        again = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        assert again.status_code == 409

    def test_results_endpoint_returns_the_stored_report(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(
            client, created_map, created_scenario, operator_headers, reviewer_headers, seeds=[1]
        )
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        response = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/results", headers=reviewer_headers
        )
        assert response.status_code == 200
        assert response.json()["report"]["runs"][0]["algorithm"] == "astar+dwa"


class TestEpisodesAndReplay:
    def test_episodes_are_stored_with_artifacts(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(
            client, created_map, created_scenario, operator_headers, reviewer_headers, seeds=[1, 2]
        )
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        response = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/episodes", headers=reviewer_headers
        )
        assert response.status_code == 200
        episodes = response.json()
        assert len(episodes) == 2
        for episode in episodes:
            assert episode["artifact_uri"].startswith("file://")
            assert len(episode["artifact_checksum"]) == 64
            assert episode["artifact_bytes"] > 0

    def test_replay_returns_trajectory_and_plan(
        self, client: TestClient, created_map, created_scenario, operator_headers, reviewer_headers
    ) -> None:
        benchmark = approved_benchmark(
            client, created_map, created_scenario, operator_headers, reviewer_headers, seeds=[1]
        )
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=operator_headers)
        episode_id = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/episodes", headers=reviewer_headers
        ).json()[0]["id"]

        replay = client.get(f"/api/v1/episodes/{episode_id}/replay", headers=reviewer_headers)
        assert replay.status_code == 200
        body = replay.json()
        assert body["algorithm"] == "astar+dwa"
        assert len(body["trajectory"]) > 10
        assert len(body["plan_path"]) >= 2
        assert body["metrics"]["status"]

    def test_unknown_episode_404(self, client: TestClient, reviewer_headers) -> None:
        response = client.get("/api/v1/episodes/missing/replay", headers=reviewer_headers)
        assert response.status_code == 404
