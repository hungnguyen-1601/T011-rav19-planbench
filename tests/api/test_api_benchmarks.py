"""API tests: benchmark lifecycle, gates, execution, replay.

Running requires APPROVED, and only an Approver's decision or an admin
override reaches it — an Engineer cannot clear their own spec gate (see
apps/api/planbench_api/approval.py). Most of these tests are not about
that gate at all, so ``run_benchmark`` clears it the fastest legitimate
way available in a single-fixture-app test: an admin override. The gate
itself, exercised through a real Approver, is tested in
tests/api/test_api_reviews.py; the override path itself is tested in
TestSoloLifecycle below.
"""

from __future__ import annotations

from conftest import ADMIN, auth_headers
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


def admin_override_approve(client: TestClient, benchmark_id: str, comment: str = "") -> dict:
    """Clear the spec gate as the fixture admin. Requires
    PLANBENCH_ADMIN_OVERRIDE_ENABLED=true, set in conftest's isolated
    environment for exactly this reason.
    """
    response = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/admin-override-approve",
        json={"comment": comment},
        headers=auth_headers(client, ADMIN),
    )
    assert response.status_code == 200, response.text
    return response.json()


def run_benchmark(client: TestClient, created_map, created_scenario, headers, **kw) -> dict:
    """Create, clear the spec gate via admin override, and run."""
    benchmark = create_benchmark(client, created_map, created_scenario, headers, **kw)
    admin_override_approve(client, benchmark["id"], comment="test fixture: no Approver in this flow")
    response = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["benchmark"]


class TestCreation:
    def test_created_in_draft_and_owned_by_the_creator(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        assert benchmark["state"] == "draft"
        assert benchmark["created_by"] == "alice"
        assert benchmark["is_owner"] is True
        assert benchmark["owner_user_id"]
        assert benchmark["spec"]["seeds"] == [1, 2]

    def test_somebody_else_is_not_the_owner(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        seen_by_bob = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}", headers=bob_headers
        ).json()
        assert seen_by_bob["is_owner"] is False
        # Visible, though: the leaderboard is shared.
        assert seen_by_bob["id"] == benchmark["id"]

    def test_duplicate_algorithms_rejected(
        self, client: TestClient, created_map, created_scenario, alice_headers
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
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_unknown_algorithm_rejected(
        self, client: TestClient, created_map, created_scenario, alice_headers
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
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_invalid_algorithm_config_rejected(
        self, client: TestClient, created_map, created_scenario, alice_headers
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
            headers=alice_headers,
        )
        assert response.status_code == 422


class TestSoloLifecycle:
    """One owner, an admin override for the spec gate, no Approver involved."""

    def test_owner_creates_runs_and_accepts(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(
            client, created_map, created_scenario, alice_headers, seeds=[1]
        )
        admin_override_approve(client, benchmark["id"])
        run = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers).json()
        assert run["benchmark"]["state"] == "pending_review"

        accepted = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={"comment": "looks right"},
            headers=alice_headers,
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["state"] == "accepted"

    def test_running_via_override_is_recorded_distinctly_from_a_real_approval(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        """The audit trail must never claim an Approver looked when an
        admin cleared the gate instead."""
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        actions = [entry["action"] for entry in benchmark["approvals"]]
        assert actions == ["admin_override_approve", "run", "complete"]
        assert "approve" not in actions
        assert "self_approved" not in actions

    def test_the_audit_trail_carries_the_user_id(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        me = client.get("/api/v1/auth/me", headers=alice_headers).json()
        override_entry, *owner_entries = benchmark["approvals"]
        # The override belongs to the admin, not the owner — that is the
        # entire point of recording it separately.
        assert override_entry["action"] == "admin_override_approve"
        assert override_entry["user"] == ADMIN[0]
        assert override_entry["role"] == "admin"
        for entry in owner_entries:
            assert entry["user_id"] == me["id"]
            assert entry["user"] == "alice"
            assert entry["role"] == "engineer"

    def test_a_member_cannot_run_somebody_elses_benchmark(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        response = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=bob_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"

    def test_a_member_cannot_accept_somebody_elses_results(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result",
            json={},
            headers=bob_headers,
        )
        assert response.status_code == 403

    def test_rejecting_your_own_results_returns_the_benchmark_to_rejected(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/reject-result",
            json={"comment": "needs more seeds"},
            headers=alice_headers,
        )
        assert response.status_code == 200
        assert response.json()["state"] == "rejected"

    def test_a_rejected_benchmark_can_be_run_again(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/reject-result", json={}, headers=alice_headers
        )
        # REJECTED needs the spec gate cleared again, same as DRAFT.
        admin_override_approve(client, benchmark["id"], comment="re-approving after rejection")
        again = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
        assert again.status_code == 200, again.text
        assert again.json()["benchmark"]["state"] == "pending_review"


class TestExecution:
    def test_run_produces_report_with_fairness_and_aggregates(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(
            client,
            created_map,
            created_scenario,
            alice_headers,
            algorithms=[{"id": "astar+dwa"}, {"id": "astar+pure_pursuit"}],
            seeds=[1, 2],
        )
        admin_override_approve(client, benchmark["id"])
        response = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
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
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        again = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
        assert again.status_code == 409

    def test_results_endpoint_returns_the_stored_report(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        response = client.get(f"/api/v1/benchmarks/{benchmark['id']}/results", headers=bob_headers)
        assert response.status_code == 200
        assert response.json()["report"]["runs"][0]["algorithm"] == "astar+dwa"


class TestReplayDynamicObstacles:
    def test_replay_trajectory_carries_obstacle_snapshots(
        self, client: TestClient, alice_headers
    ) -> None:
        """F08: dynamic obstacle positions are recorded per trajectory
        sample, so a replay UI can draw them moving frame by frame."""
        imported = client.post(
            "/api/v1/scenario-library/crossing_obstacle/import", headers=alice_headers
        ).json()
        payload = {
            "name": "obstacle-replay-benchmark",
            "map_id": imported["map_id"],
            "scenario_id": imported["scenario_id"],
            "algorithms": [{"id": "astar+dwa"}],
            "seeds": [1],
        }
        created = client.post("/api/v1/benchmarks", json=payload, headers=alice_headers)
        assert created.status_code == 201, created.text
        benchmark_id = created.json()["id"]
        admin_override_approve(client, benchmark_id)
        run = client.post(f"/api/v1/benchmarks/{benchmark_id}/run", headers=alice_headers)
        assert run.status_code == 200, run.text

        episode_id = client.get(
            f"/api/v1/benchmarks/{benchmark_id}/episodes", headers=alice_headers
        ).json()[0]["id"]
        replay = client.get(f"/api/v1/episodes/{episode_id}/replay", headers=alice_headers)
        assert replay.status_code == 200
        trajectory = replay.json()["trajectory"]
        obstacle_frames = [point for point in trajectory if point["obstacles"]]
        assert obstacle_frames, "no trajectory sample carried an obstacle snapshot"
        assert obstacle_frames[0]["obstacles"][0]["name"] == "pedestrian"


class TestReportMarkdown:
    def test_downloads_a_markdown_report_after_a_run(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        response = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/report.md", headers=alice_headers
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "attachment" in response.headers["content-disposition"]
        assert "astar+dwa" in response.text

    def test_before_a_run_is_a_409(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        response = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/report.md", headers=alice_headers
        )
        assert response.status_code == 409

    def test_unauthenticated_is_rejected(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        response = client.get(f"/api/v1/benchmarks/{benchmark['id']}/report.md")
        assert response.status_code == 401


class TestEpisodesAndReplay:
    def test_episodes_are_stored_with_artifacts(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(
            client, created_map, created_scenario, alice_headers, seeds=[1, 2]
        )
        response = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/episodes", headers=alice_headers
        )
        assert response.status_code == 200
        episodes = response.json()
        assert len(episodes) == 2
        for episode in episodes:
            assert episode["artifact_uri"].startswith("file://")
            assert len(episode["artifact_checksum"]) == 64
            assert episode["artifact_bytes"] > 0

    def test_replay_returns_trajectory_and_plan(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        episode_id = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/episodes", headers=alice_headers
        ).json()[0]["id"]

        replay = client.get(f"/api/v1/episodes/{episode_id}/replay", headers=bob_headers)
        assert replay.status_code == 200
        body = replay.json()
        assert body["algorithm"] == "astar+dwa"
        assert len(body["trajectory"]) > 10
        assert len(body["plan_path"]) >= 2
        assert body["metrics"]["status"]

    def test_unknown_episode_404(self, client: TestClient, alice_headers) -> None:
        response = client.get("/api/v1/episodes/missing/replay", headers=alice_headers)
        assert response.status_code == 404
