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

    def test_reports_provider_tools_and_prohibitions(self, client, alice_headers):
        body = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()
        assert body["provider"] == "mock"
        assert body["deterministic"] is True
        assert "run_benchmark" in body["tools"]
        assert set(body["forbidden"]) == FORBIDDEN_CAPABILITIES
        assert body["knowledge_documents"] > 0

    def test_lists_every_configurable_provider_and_what_is_missing(self, client, alice_headers):
        # So "why is it still on the mock?" is answerable from the API
        # rather than from server logs.
        body = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()
        names = {entry["name"] for entry in body["providers"]}
        assert {"anthropic", "openai", "gemini", "local"} <= names
        # Readiness depends on the developer's own keys and installed
        # SDKs, so assert the shape and the invariant — not that nothing
        # happens to be configured on this machine.
        for entry in body["providers"]:
            if entry["ready"]:
                assert entry["missing"] == "", entry
            else:
                assert entry["missing"] != "", entry
            # A provider that needs no key must not claim to want one.
            if entry["name"] == "local":
                assert entry["api_key_env"] == ""
            else:
                assert entry["api_key_env"].endswith("_API_KEY"), entry

    def test_no_tool_can_actuate_or_approve(self, client, alice_headers):
        tools = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()["tools"]
        assert not [
            tool for tool in tools if any(word in tool for word in ("drive", "cmd_vel", "approve"))
        ]


class TestChat:
    def test_answers_with_the_tools_it_used(self, client, alice_headers):
        body = client.post(
            "/api/v1/agent/chat",
            json={"message": "which scenarios exist?"},
            headers=alice_headers,
        ).json()
        assert "list_scenarios" in body["turn"]["tools_used"]
        assert body["deterministic"] is True

    def test_rejects_an_empty_message(self, client, alice_headers):
        response = client.post("/api/v1/agent/chat", json={"message": ""}, headers=alice_headers)
        assert response.status_code == 422

    def test_a_reviewer_may_also_ask(self, client, carol_headers):
        response = client.post(
            "/api/v1/agent/chat", json={"message": "list the algorithms"}, headers=carol_headers
        )
        assert response.status_code == 200


def approve_spec(client, benchmark_id: str, owner_headers: dict, reviewer_headers: dict) -> None:
    """Clear the spec gate with a real second person.

    The agent must never approve its own work, so a benchmark it drafted
    can only be run once a human has cleared the gate. Here that human is
    a reviewer; the owner's alternative is to press Run themselves, which
    also runs it and so is no use to a test about the agent running it.
    """
    request = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/review-requests",
        json={"reviewer_nickname": "bob", "stage": "spec"},
        headers=owner_headers,
    )
    assert request.status_code == 201, request.text
    approved = client.post(
        f"/api/v1/reviews/{request.json()['id']}/approve", json={}, headers=reviewer_headers
    )
    assert approved.status_code == 200, approved.text


class TestMissions:
    def test_missions_require_authentication(self, client):
        assert client.post("/api/v1/agent/missions", json={"mission": MISSION}).status_code == 401

    def test_an_unparseable_mission_returns_a_refusal_not_a_benchmark(self, client, alice_headers):
        body = submit_mission(client, alice_headers, "make the robot go faster", submit=True)
        assert body["draft"] is None
        assert body["refusal"]["reason"]
        assert body["benchmark"] is None
        assert client.get("/api/v1/benchmarks", headers=alice_headers).json() == []

    def test_a_stack_needing_a_checkpoint_is_refused(self, client, alice_headers):
        body = submit_mission(
            client, alice_headers, "Compare DWA and PPO on open_space", submit=True
        )
        assert body["benchmark"] is None
        assert any("model_id" in error for error in body["refusal"]["errors"])

    def test_a_valid_mission_drafts_without_submitting(self, client, alice_headers):
        body = submit_mission(client, alice_headers, submit=False)
        assert body["draft"]["scenario"] == "open_space"
        assert body["benchmark"] is None
        assert body["session"]["state"] == "mission_parsed"

    def test_submitting_stops_short_of_running(self, client, alice_headers):
        """The agent drafts and submits; a human still decides to run."""
        body = submit_mission(client, alice_headers)
        assert body["benchmark"]["state"] == "pending_approval"
        assert "Run it yourself" in body["next_step"]

    def test_the_benchmark_is_attributed_to_the_calling_user(self, client, alice_headers):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        stored = client.get(f"/api/v1/benchmarks/{benchmark_id}", headers=alice_headers).json()
        assert stored["created_by"] == "alice"
        assert stored["is_owner"] is True

    def test_the_agent_only_uses_library_scenarios(self, client, alice_headers):
        body = submit_mission(client, alice_headers)
        scenario_id = body["benchmark"]["scenario_id"]
        scenario = client.get(f"/api/v1/scenarios/{scenario_id}", headers=alice_headers).json()
        assert scenario["scenario"]["name"] == "open_space"


class TestApprovalGate:
    def test_agent_run_is_refused_before_approval(self, client, alice_headers):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        response = client.post(
            f"/api/v1/agent/benchmarks/{benchmark_id}/run", headers=alice_headers
        )
        assert response.status_code == 409
        assert "approve" in response.json()["error"]["message"]

    def test_the_operator_cannot_approve_their_own_agent_benchmark(self, client, alice_headers):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=alice_headers
        )
        assert response.status_code == 403

    def test_agent_runs_once_the_gate_is_cleared(self, client, alice_headers, bob_headers):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        approve_spec(client, benchmark_id, alice_headers, bob_headers)

        response = client.post(
            f"/api/v1/agent/benchmarks/{benchmark_id}/run", headers=alice_headers
        )
        assert response.status_code == 200, response.text
        # Gate 2: results wait for a human; the agent cannot accept them.
        assert response.json()["state"] == "pending_review"

    def test_running_an_unknown_benchmark_is_a_404(self, client, alice_headers):
        response = client.post("/api/v1/agent/benchmarks/deadbeef1234/run", headers=alice_headers)
        assert response.status_code == 404


class TestEvidenceAndReport:
    def test_evidence_is_empty_of_metrics_before_a_run(self, client, alice_headers):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        body = client.get(
            f"/api/v1/agent/benchmarks/{benchmark_id}/evidence", headers=alice_headers
        ).json()
        assert len(body["items"]) == 1
        assert not any("success_rate" in item["statement"] for item in body["items"])

    def test_report_cites_only_real_evidence_after_a_run(self, client, alice_headers, bob_headers):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        approve_spec(client, benchmark_id, alice_headers, bob_headers)
        run = client.post(f"/api/v1/agent/benchmarks/{benchmark_id}/run", headers=alice_headers)
        assert run.status_code == 200, run.text

        evidence = client.get(
            f"/api/v1/agent/benchmarks/{benchmark_id}/evidence", headers=alice_headers
        ).json()
        known = {
            item["citation"]["kind"] + ":" + item["citation"]["locator"]
            for item in evidence["items"]
        }

        report = client.post(
            f"/api/v1/agent/benchmarks/{benchmark_id}/report",
            json={"question": "Which stack succeeded more often?"},
            headers=alice_headers,
        ).json()
        assert report["citations"], report
        assert set(report["citations"]) <= known
        assert report["provisional"] is True  # nobody has accepted the results
        assert "not a safety certification" in report["text"]

    def test_report_for_an_unknown_benchmark_is_a_404(self, client, alice_headers):
        response = client.post(
            "/api/v1/agent/benchmarks/deadbeef1234/report", json={}, headers=alice_headers
        )
        assert response.status_code == 404


class TestProviderFailures:
    """A broken upstream model must not read as a broken PlanBench."""

    def _break_provider(self, app, error):
        from planbench_agent.provider import LLMProvider

        class Failing(LLMProvider):
            name = "gemini"
            model = "gemini-3.5-flash-lite"
            deterministic = False

            def complete(self, request):
                raise error

        app.state.agent_provider = Failing()

    def test_a_provider_error_is_502_with_the_upstream_message(self, client, app, alice_headers):
        # "Function call is missing a thought_signature" is the piece
        # that tells the reader what to fix; a bare 500 loses it.
        from planbench_agent.provider import ProviderError

        self._break_provider(
            app, ProviderError("gemini request failed: missing a thought_signature")
        )
        response = client.post(
            "/api/v1/agent/chat", json={"message": "list the benchmarks"}, headers=alice_headers
        )
        assert response.status_code == 502
        body = response.json()["error"]
        assert body["code"] == "provider_error"
        assert "thought_signature" in body["message"]

    def test_an_unconfigured_provider_is_503_with_the_fix(self, client, app, alice_headers):
        from planbench_agent.provider import ProviderUnavailable

        self._break_provider(
            app, ProviderUnavailable("no API key for 'gemini': set GEMINI_API_KEY")
        )
        response = client.post(
            "/api/v1/agent/chat", json={"message": "anything"}, headers=alice_headers
        )
        assert response.status_code == 503
        body = response.json()["error"]
        assert body["code"] == "provider_unavailable"
        assert "GEMINI_API_KEY" in body["message"]

    def test_a_failing_provider_does_not_leak_a_stack_trace(self, client, app, alice_headers):
        from planbench_agent.provider import ProviderError

        self._break_provider(app, ProviderError("upstream exploded"))
        response = client.post(
            "/api/v1/agent/missions",
            json={"mission": "Benchmark DWA on open_space", "submit": False},
            headers=alice_headers,
        )
        assert response.status_code == 502
        assert "Traceback" not in response.text


class TestSeparationOfDuties:
    def test_an_uninvolved_member_cannot_approve(self, client, alice_headers, bob_headers):
        """Being signed in is not being asked."""
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=bob_headers
        )
        assert response.status_code == 403

    def test_the_agent_cannot_clear_the_gate_for_its_own_draft(self, client, alice_headers):
        """The LLM drafts and submits; it never approves.

        Its owner cannot use the approve route either — pressing Run is a
        deliberate human act recorded as ``self_approved``, and that
        distinction is what keeps "an agent proposed this" legible.
        """
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve", json={}, headers=alice_headers
        )
        assert response.status_code == 403

    def test_an_admin_can_approve_an_agent_benchmark(self, client, alice_headers, app):
        benchmark_id = submit_mission(client, alice_headers)["benchmark"]["id"]
        from conftest import ADMIN

        response = client.post(
            f"/api/v1/benchmarks/{benchmark_id}/approve",
            json={},
            headers=auth_headers(client, ADMIN),
        )
        assert response.status_code == 200
