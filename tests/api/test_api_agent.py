"""Agent endpoints over real HTTP (M8).

These run against the deterministic provider, so they assert on the
platform's guarantees — authentication, the approval gate, citation
integrity — rather than on model prose.
"""

from __future__ import annotations

from conftest import auth_headers

from planbench_agent.tools import FORBIDDEN_CAPABILITIES

# A*+DWA only: astar+ppo needs a checkpoint path, which the agent is not
# allowed to choose (see TestMissions below).
MISSION = "Benchmark DWA on the open_space scenario with seeds 1 2"


def submit_mission(client, headers, mission: str = MISSION, submit: bool = True) -> dict:
    response = client.post(
        "/api/v1/agent/missions", json={"mission": mission, "submit": submit}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestCapabilities:
    def test_requires_authentication(self, client):
        assert client.get("/api/v1/agent/capabilities").status_code == 401

    def test_reports_provider_tools_and_prohibitions(self, client, operator_headers):
        body = client.get("/api/v1/agent/capabilities", headers=operator_headers).json()
        assert body["provider"] == "mock"
        assert body["deterministic"] is True
        assert "run_benchmark" in body["tools"]
        assert set(body["forbidden"]) == FORBIDDEN_CAPABILITIES
        assert body["knowledge_documents"] > 0

    def test_lists_every_configurable_provider_and_what_is_missing(self, client, operator_headers):
        # So "why is it still on the mock?" is answerable from the API
        # rather than from server logs.
        body = client.get("/api/v1/agent/capabilities", headers=operator_headers).json()
        names = {entry["name"] for entry in body["providers"]}
        assert {"anthropic", "openai", "gemini", "local"} <= names
        for entry in body["providers"]:
            assert entry["ready"] is False
            assert entry["missing"], entry

    def test_no_tool_can_actuate_or_approve(self, client, operator_headers):
        tools = client.get("/api/v1/agent/capabilities", headers=operator_headers).json()["tools"]
        assert not [
            tool for tool in tools if any(word in tool for word in ("drive", "cmd_vel", "approve"))
        ]


class TestChat:
    def test_answers_with_the_tools_it_used(self, client, operator_headers):
        body = client.post(
            "/api/v1/agent/chat",
            json={"message": "which scenarios exist?"},
            headers=operator_headers,
        ).json()
        assert "list_scenarios" in body["turn"]["tools_used"]
        assert body["deterministic"] is True

    def test_rejects_an_empty_message(self, client, operator_headers):
        response = client.post("/api/v1/agent/chat", json={"message": ""}, headers=operator_headers)
        assert response.status_code == 422

    def test_a_reviewer_may_also_ask(self, client, reviewer_headers):
        response = client.post(
            "/api/v1/agent/chat", json={"message": "list the algorithms"}, headers=reviewer_headers
        )
        assert response.status_code == 200


class TestMissions:
    def test_reviewers_cannot_create_missions(self, client, reviewer_headers):
        response = client.post(
            "/api/v1/agent/missions", json={"mission": MISSION}, headers=reviewer_headers
        )
        assert response.status_code == 403

    def test_an_unparseable_mission_returns_a_refusal_not_a_benchmark(
        self, client, operator_headers
    ):
        body = submit_mission(client, operator_headers, "make the robot go faster", submit=True)
        assert body["draft"] is None
        assert body["refusal"]["reason"]
        assert body["benchmark"] is None
        assert client.get("/api/v1/benchmarks", headers=operator_headers).json() == []

    def test_a_stack_needing_a_checkpoint_is_refused(self, client, operator_headers):
        body = submit_mission(
            client, operator_headers, "Compare DWA and PPO on open_space", submit=True
        )
        assert body["benchmark"] is None
        assert any("model_path" in error for error in body["refusal"]["errors"])

    def test_a_valid_mission_drafts_without_submitting(self, client, operator_headers):
        body = submit_mission(client, operator_headers, submit=False)
        assert body["draft"]["scenario"] == "open_space"
        assert body["benchmark"] is None
        assert body["session"]["state"] == "mission_parsed"

    def test_submitting_stops_at_pending_approval(self, client, operator_headers):
        body = submit_mission(client, operator_headers)
        assert body["benchmark"]["state"] == "pending_approval"
        assert "must approve" in body["next_step"]

    def test_the_benchmark_is_attributed_to_the_calling_user(self, client, operator_headers):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        stored = client.get(f"/api/v1/benchmarks/{benchmark_id}", headers=operator_headers).json()
        assert stored["created_by"] == "op-alice"

    def test_the_agent_only_uses_library_scenarios(self, client, operator_headers):
        body = submit_mission(client, operator_headers)
        scenario_id = body["benchmark"]["scenario_id"]
        scenario = client.get(f"/api/v1/scenarios/{scenario_id}", headers=operator_headers).json()
        assert scenario["scenario"]["name"] == "open_space"


class TestApprovalGate:
    def test_agent_run_is_refused_before_approval(self, client, operator_headers):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        response = client.post(
            f"/api/v1/agent/benchmarks/{benchmark_id}/run", headers=operator_headers
        )
        assert response.status_code == 409
        assert "approve" in response.json()["error"]["message"]

    def test_the_operator_cannot_approve_their_own_agent_benchmark(self, client, operator_headers):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=operator_headers
        )
        assert response.status_code == 403

    def test_agent_runs_once_a_reviewer_approves(self, client, operator_headers, reviewer_headers):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        approved = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=reviewer_headers
        )
        assert approved.status_code == 200, approved.text

        response = client.post(
            f"/api/v1/agent/benchmarks/{benchmark_id}/run", headers=operator_headers
        )
        assert response.status_code == 200, response.text
        # Gate 2: results wait for a reviewer; the agent cannot accept them.
        assert response.json()["state"] == "pending_review"

    def test_running_an_unknown_benchmark_is_a_404(self, client, operator_headers):
        response = client.post(
            "/api/v1/agent/benchmarks/deadbeef1234/run", headers=operator_headers
        )
        assert response.status_code == 404


class TestEvidenceAndReport:
    def test_evidence_is_empty_of_metrics_before_a_run(self, client, operator_headers):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        body = client.get(
            f"/api/v1/agent/benchmarks/{benchmark_id}/evidence", headers=operator_headers
        ).json()
        assert len(body["items"]) == 1
        assert not any("success_rate" in item["statement"] for item in body["items"])

    def test_report_cites_only_real_evidence_after_a_run(
        self, client, operator_headers, reviewer_headers
    ):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        client.post(f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=reviewer_headers)
        run = client.post(f"/api/v1/agent/benchmarks/{benchmark_id}/run", headers=operator_headers)
        assert run.status_code == 200, run.text

        evidence = client.get(
            f"/api/v1/agent/benchmarks/{benchmark_id}/evidence", headers=operator_headers
        ).json()
        known = {
            item["citation"]["kind"] + ":" + item["citation"]["locator"]
            for item in evidence["items"]
        }

        report = client.post(
            f"/api/v1/agent/benchmarks/{benchmark_id}/report",
            json={"question": "Which stack succeeded more often?"},
            headers=operator_headers,
        ).json()
        assert report["citations"], report
        assert set(report["citations"]) <= known
        assert report["provisional"] is True  # nobody has accepted the results
        assert "not a safety certification" in report["text"]

    def test_report_for_an_unknown_benchmark_is_a_404(self, client, operator_headers):
        response = client.post(
            "/api/v1/agent/benchmarks/deadbeef1234/report", json={}, headers=operator_headers
        )
        assert response.status_code == 404


class TestSeparationOfDuties:
    def test_a_second_operator_still_cannot_approve(
        self, client, operator_headers, operator2_headers
    ):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        # Role, not identity: no operator may approve, even a different one.
        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=operator2_headers
        )
        assert response.status_code == 403

    def test_an_admin_can_approve_an_agent_benchmark(self, client, operator_headers, app):
        benchmark_id = submit_mission(client, operator_headers)["benchmark"]["id"]
        from conftest import ADMIN

        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve",
            json={},
            headers=auth_headers(client, ADMIN),
        )
        assert response.status_code == 200
