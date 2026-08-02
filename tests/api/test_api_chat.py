"""The assistant conversation.

The property under test throughout: **the assistant proposes, a person
disposes**. It can read, it can suggest, and it cannot create or run
anything without a separate act by the user.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_api_models import METADATA, upload


@pytest.fixture
def conversation(client: TestClient, alice_headers) -> str:
    response = client.post("/api/v1/ai/conversations", json={"locale": "en"}, headers=alice_headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def say(client: TestClient, headers: dict, conversation_id: str, text: str) -> dict:
    response = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"message": text},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestConversations:
    def test_a_member_can_start_one(self, client: TestClient, conversation: str) -> None:
        assert conversation

    def test_messages_are_kept_in_order(
        self, client: TestClient, alice_headers, conversation: str
    ) -> None:
        say(client, alice_headers, conversation, "hello")
        say(client, alice_headers, conversation, "again")
        detail = client.get(
            f"/api/v1/ai/conversations/{conversation}", headers=alice_headers
        ).json()
        roles = [message["role"] for message in detail["messages"]]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_the_title_comes_from_the_first_message(
        self, client: TestClient, alice_headers, conversation: str
    ) -> None:
        say(client, alice_headers, conversation, "test the robot in a warehouse")
        listed = client.get("/api/v1/ai/conversations", headers=alice_headers).json()
        assert listed[0]["title"].startswith("test the robot")

    def test_another_member_cannot_read_it(
        self, client: TestClient, alice_headers, bob_headers, conversation: str
    ) -> None:
        say(client, alice_headers, conversation, "something private")
        # 404 rather than 403: a conversation id is not a secret, and
        # confirming whose it is tells an outsider something.
        assert (
            client.get(f"/api/v1/ai/conversations/{conversation}", headers=bob_headers).status_code
            == 404
        )

    def test_another_member_cannot_post_to_it(
        self, client: TestClient, bob_headers, conversation: str
    ) -> None:
        response = client.post(
            f"/api/v1/ai/conversations/{conversation}/messages",
            json={"message": "hi"},
            headers=bob_headers,
        )
        assert response.status_code == 404

    def test_it_requires_a_signed_in_member(self, client: TestClient) -> None:
        assert client.post("/api/v1/ai/conversations", json={"locale": "en"}).status_code == 401

    def test_an_empty_message_is_refused(
        self, client: TestClient, alice_headers, conversation: str
    ) -> None:
        response = client.post(
            f"/api/v1/ai/conversations/{conversation}/messages",
            json={"message": ""},
            headers=alice_headers,
        )
        assert response.status_code == 422


class TestClarification:
    """It asks rather than guesses."""

    def test_it_asks_which_scenario_when_there_are_several(
        self, client: TestClient, alice_headers, conversation, created_map, created_scenario
    ) -> None:
        # A second scenario makes the choice ambiguous.
        client.post(
            "/api/v1/scenarios",
            json={"map_id": created_map["id"], "scenario": {**created_scenario["scenario"]}},
        )
        reply = say(client, alice_headers, conversation, "benchmark something")
        assert reply["proposal"]["missing_fields"] == ["scenario"]
        assert reply["content"] == "chat.needScenario"

    def test_it_asks_which_model_when_ppo_is_requested(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "benchmark with PPO")
        assert "ppo_model" in reply["proposal"]["missing_fields"]
        assert reply["content"] == "chat.needModel"
        # And it says the reason: nothing has been uploaded.
        assert "no_models_uploaded" in reply["proposal"]["warnings"]

    def test_a_single_scenario_is_not_ambiguous(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "run a benchmark")
        assert reply["proposal"]["scenario_id"] == created_scenario["id"]
        assert reply["proposal"]["missing_fields"] == []

    def test_it_reads_the_number_of_runs_from_the_sentence(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "run a benchmark 5 times")
        assert reply["proposal"]["seeds"] == [1, 2, 3, 4, 5]

    def test_it_reads_explicit_seeds(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "benchmark with seeds 7, 8, 9")
        assert reply["proposal"]["seeds"] == [7, 8, 9]

    def test_an_assumed_default_is_declared_as_an_assumption(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        # Guessing is allowed only when the guess is visible.
        reply = say(client, alice_headers, conversation, "run a benchmark")
        assert reply["proposal"]["seeds"] == [1, 2, 3]
        assert reply["proposal"]["assumptions"]

    def test_it_recognises_algorithms_by_name_not_by_id(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        # Nobody types "astar+dwa".
        reply = say(client, alice_headers, conversation, "compare DWA and pure pursuit")
        assert set(reply["proposal"]["stacks"]) == {"astar+dwa", "astar+pure_pursuit"}

    def test_it_understands_vietnamese(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "kiểm thử robot, chạy 4 lần")
        assert reply["proposal"] is not None
        assert reply["proposal"]["seeds"] == [1, 2, 3, 4]


class TestTheAssistantCannotActAlone:
    """The rule the whole design exists to enforce."""

    def test_a_message_never_creates_a_benchmark(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        say(client, alice_headers, conversation, "run a benchmark now, immediately, please")
        assert client.get("/api/v1/benchmarks", headers=alice_headers).json() == []

    def test_confirming_creates_a_draft_and_only_a_draft(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "run a benchmark")
        confirmed = client.post(
            f"/api/v1/ai/conversations/{conversation}/confirm-draft",
            json={"proposal_id": reply["proposal"]["id"]},
            headers=alice_headers,
        )
        assert confirmed.status_code == 200, confirmed.text

        benchmarks = client.get("/api/v1/benchmarks", headers=alice_headers).json()
        assert len(benchmarks) == 1
        # Draft, not running and not approved: the run is still the
        # user's move.
        assert benchmarks[0]["state"] == "draft"
        assert confirmed.json()["content"] == "chat.draftCreated"

    def test_there_is_no_run_endpoint_on_the_assistant(self, client: TestClient) -> None:
        """Enforced by absence, checked against the public surface.

        The OpenAPI document is what a client can actually reach, which
        makes it the right thing to assert on: a route that exists but
        is not published is still reachable, and one that is published
        is the whole risk.
        """
        paths = client.get("/openapi.json").json()["paths"]
        assistant = [path for path in paths if "/ai/" in path]
        assert assistant, "the assistant should have routes"
        for path in assistant:
            for forbidden in ("run", "approve", "accept", "reject", "drive"):
                assert forbidden not in path, f"{path} exposes {forbidden!r} to the assistant"

    def test_an_incomplete_proposal_cannot_be_confirmed(
        self, client: TestClient, alice_headers, conversation
    ) -> None:
        # No scenario exists at all, so the proposal is incomplete.
        reply = say(client, alice_headers, conversation, "benchmark something")
        response = client.post(
            f"/api/v1/ai/conversations/{conversation}/confirm-draft",
            json={"proposal_id": reply["proposal"]["id"]},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "not complete" in response.json()["error"]["message"]

    def test_an_invented_proposal_id_is_a_404(
        self, client: TestClient, alice_headers, conversation
    ) -> None:
        response = client.post(
            f"/api/v1/ai/conversations/{conversation}/confirm-draft",
            json={"proposal_id": "made-up"},
            headers=alice_headers,
        )
        assert response.status_code == 404

    def test_another_member_cannot_confirm_my_proposal(
        self, client: TestClient, alice_headers, bob_headers, conversation, created_scenario
    ) -> None:
        reply = say(client, alice_headers, conversation, "run a benchmark")
        response = client.post(
            f"/api/v1/ai/conversations/{conversation}/confirm-draft",
            json={"proposal_id": reply["proposal"]["id"]},
            headers=bob_headers,
        )
        assert response.status_code == 404


class TestPpoThroughTheAssistant:
    def test_it_offers_an_uploaded_model_and_confirms_with_its_id(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        profiles = client.get("/api/v1/robot-profiles", headers=alice_headers).json()
        model_id = upload(client, alice_headers, profiles[0]["id"]).json()["id"]

        reply = say(client, alice_headers, conversation, "benchmark with PPO")
        proposal = reply["proposal"]
        assert proposal["model_id"] == model_id
        assert proposal["missing_fields"] == []

        client.post(
            f"/api/v1/ai/conversations/{conversation}/confirm-draft",
            json={"proposal_id": proposal["id"]},
            headers=alice_headers,
        )
        benchmark = client.get("/api/v1/benchmarks", headers=alice_headers).json()[0]
        config = benchmark["spec"]["algorithms"][0]["config"]
        # A model id, never a path — the same rule the form follows.
        assert config["model_id"] == model_id
        assert "model_path" not in config or not config["model_path"]

    def test_an_incompatible_model_is_not_offered_as_ready(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        profiles = client.get("/api/v1/robot-profiles", headers=alice_headers).json()
        metadata = {**METADATA, "observation": {**METADATA["observation"], "lidar_beams": 36}}
        upload(client, alice_headers, profiles[0]["id"], metadata=metadata)

        reply = say(client, alice_headers, conversation, "benchmark with PPO")
        # A model that failed validation is not usable, so it is not
        # offered — the assistant asks instead of proposing something
        # that would be refused at launch.
        assert "ppo_model" in reply["proposal"]["missing_fields"]


class TestExplainingResults:
    def test_it_says_so_when_there_is_nothing_to_explain(
        self, client: TestClient, alice_headers, conversation
    ) -> None:
        reply = say(client, alice_headers, conversation, "why did the robot get stuck?")
        assert reply["content"] == "chat.noResults"
        assert reply["proposal"] is None

    def test_the_result_card_is_read_from_the_stored_report(
        self, client: TestClient, alice_headers, created_map, created_scenario
    ) -> None:
        benchmark = client.post(
            "/api/v1/benchmarks",
            headers=alice_headers,
            json={
                "name": "for analysis",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
        ).json()
        client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)

        card = client.get(f"/api/v1/ai/results/{benchmark['id']}", headers=alice_headers).json()
        assert card is not None
        assert card["name"] == "for analysis"
        assert card["aggregates"][0]["algorithm"] == "astar+dwa"
        # Every figure comes from the report the run produced, so it
        # cannot be misquoted.
        report = client.get(
            f"/api/v1/benchmarks/{benchmark['id']}/results", headers=alice_headers
        ).json()["report"]
        assert card["aggregates"][0]["success_rate"] == report["aggregates"][0]["success_rate"]
        assert card["conditions_checksum"] == report["fairness"]["conditions_checksum"]

    def test_a_benchmark_that_has_not_run_has_no_card(
        self, client: TestClient, alice_headers, created_map, created_scenario
    ) -> None:
        benchmark = client.post(
            "/api/v1/benchmarks",
            headers=alice_headers,
            json={
                "name": "unrun",
                "map_id": created_map["id"],
                "scenario_id": created_scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
        ).json()
        assert (
            client.get(f"/api/v1/ai/results/{benchmark['id']}", headers=alice_headers).json()
            is None
        )


class TestNoTechnicalLeakage:
    """Nothing about providers, keys or internal tools reaches the user."""

    FORBIDDEN = (
        "gemini",
        "openai",
        "anthropic",
        "api_key",
        "API_KEY",
        "provider",
        "pip install",
        "list_scenarios",
        "create_benchmark_draft",
        "run_benchmark",
        "drive_robot",
    )

    def test_a_reply_mentions_none_of_them(
        self, client: TestClient, alice_headers, conversation, created_scenario
    ) -> None:
        body = client.post(
            f"/api/v1/ai/conversations/{conversation}/messages",
            json={"message": "run a benchmark with PPO"},
            headers=alice_headers,
        ).text.lower()
        for word in self.FORBIDDEN:
            assert word.lower() not in body, f"{word!r} leaked into a chat reply"

    def test_the_conversation_list_mentions_none_of_them(
        self, client: TestClient, alice_headers, conversation
    ) -> None:
        body = client.get("/api/v1/ai/conversations", headers=alice_headers).text.lower()
        for word in self.FORBIDDEN:
            assert word.lower() not in body
