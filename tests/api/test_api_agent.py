"""Agent endpoints over real HTTP.

Two routes now, and the tests are mostly about the boundary rather than
the answers: who may call them, what the published surface admits to,
and what a caller sees when the upstream model breaks. Prose is the
model's business; these assert the platform's guarantees.

The suite runs against the deterministic provider, so nothing here needs
a key and nothing here is flaky on a model's mood.
"""

from __future__ import annotations

from planbench_agent.tools import FORBIDDEN_CAPABILITIES


class TestCapabilities:
    def test_requires_authentication(self, client):
        assert client.get("/api/v1/agent/capabilities").status_code == 401

    def test_it_names_the_provider_and_whether_it_is_a_model(self, client, alice_headers):
        """A mock answer and a model answer read alike; this is how a
        caller tells them apart without guessing."""
        body = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()
        assert body["provider"]
        assert isinstance(body["deterministic"], bool)

    def test_it_publishes_the_tools_it_has(self, client, alice_headers):
        tools = set(client.get("/api/v1/agent/capabilities", headers=alice_headers).json()["tools"])
        assert {"list_decision_runs", "get_decision_run", "get_gate_table"} <= tools

    def test_it_publishes_what_it_must_never_do(self, client, alice_headers):
        """Published so the claim is checkable rather than promised."""
        body = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()
        assert set(body["forbidden"]) == set(FORBIDDEN_CAPABILITIES)

    def test_the_tools_and_the_forbidden_list_never_overlap(self, client, alice_headers):
        body = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()
        assert not set(body["tools"]) & set(body["forbidden"])

    def test_it_does_not_advertise_a_documentation_corpus(self, client, alice_headers):
        """There is none. The field used to say how many of the team's own
        Markdown files were indexed, and a design note that disagrees with
        the code is worse than no note: it makes the agent confidently
        wrong. Answers come from the database now."""
        body = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()
        assert "knowledge_documents" not in body
        assert not [name for name in body["tools"] if "knowledge" in name]

    def test_it_says_which_providers_are_ready_and_what_is_missing(self, client, alice_headers):
        """So "why is it still on the mock?" is answerable from the API
        rather than from server logs."""
        providers = client.get("/api/v1/agent/capabilities", headers=alice_headers).json()[
            "providers"
        ]
        assert providers
        assert all({"name", "ready", "api_key_env"} <= set(entry) for entry in providers)


class TestChat:
    def test_requires_authentication(self, client):
        assert client.post("/api/v1/agent/chat", json={"message": "hi"}).status_code == 401

    def test_an_empty_message_is_rejected_by_the_schema(self, client, alice_headers):
        response = client.post("/api/v1/agent/chat", json={"message": ""}, headers=alice_headers)
        assert response.status_code == 422

    def test_it_answers_and_reports_which_tools_ran(self, client, alice_headers):
        """`tools_used` is the evidence an answer came from stored data."""
        response = client.post(
            "/api/v1/agent/chat",
            json={"message": "which decision runs exist?"},
            headers=alice_headers,
        )
        assert response.status_code == 200, response.text
        turn = response.json()["turn"]
        assert isinstance(turn["tools_used"], list)
        assert isinstance(turn["truncated"], bool)

    def test_the_response_carries_the_provider_identity(self, client, alice_headers):
        body = client.post(
            "/api/v1/agent/chat", json={"message": "hello"}, headers=alice_headers
        ).json()
        assert body["provider"]
        assert isinstance(body["deterministic"], bool)


class TestTheAgentCannotAct:
    def test_no_agent_route_publishes_a_write_verb(self, client):
        """Asserted against the OpenAPI document, not against intent.

        A route is only a risk once it is advertised, and the document
        is what a caller reads. `/agent/chat` is a POST because it takes
        a body, not because it changes anything.
        """
        paths = client.get("/openapi.json").json()["paths"]
        agent_paths = {path: ops for path, ops in paths.items() if "/agent" in path}
        assert agent_paths
        for path, operations in agent_paths.items():
            assert set(operations) <= {"get", "post"}, path
            for forbidden in ("run", "approve", "accept", "reject", "drive", "mission"):
                assert forbidden not in path, path

    def test_the_retired_benchmark_routes_are_gone(self, client):
        """P6 removed the pages; leaving the routes would describe a
        system a caller cannot open."""
        paths = client.get("/openapi.json").json()["paths"]
        assert not [path for path in paths if path.startswith("/api/v1/ai/")]
        assert not [path for path in paths if "/agent/benchmarks" in path]


class TestProviderFailures:
    """A broken upstream model must not read as a broken PlanBench."""

    def _break_provider(self, app, error):
        from planbench_agent.provider import LLMProvider

        class Failing(LLMProvider):
            name = "gemini"
            model = "gemini-3-flash-preview"
            deterministic = False

            def complete(self, request):
                raise error

        app.state.agent_provider = Failing()

    def test_a_provider_error_is_502_with_the_upstream_message(self, client, app, alice_headers):
        # "missing a thought_signature" is the piece that tells the
        # reader what to fix; a bare 500 loses it.
        from planbench_agent.provider import ProviderError

        self._break_provider(
            app, ProviderError("gemini request failed: missing a thought_signature")
        )
        response = client.post(
            "/api/v1/agent/chat", json={"message": "anything"}, headers=alice_headers
        )
        assert response.status_code == 502
        body = response.json()["error"]
        assert body["code"] == "provider_error"
        assert "thought_signature" in body["message"]

    def test_an_unexpected_error_does_not_leak_a_stack_trace(self, client, app, alice_headers):
        self._break_provider(app, RuntimeError("connection reset by peer"))
        response = client.post(
            "/api/v1/agent/chat", json={"message": "anything"}, headers=alice_headers
        )
        assert response.status_code >= 500
        assert "Traceback" not in response.text
