"""The tool loop: what bounds it, and what it says when it stops.

The loop is small, so the tests are about its edges rather than its
middle. Three of them matter most: it must stop, it must report stopping
rather than answering anyway, and it must carry the provider's own turn
payload forward — a detail with no visible symptom until a signing
provider rejects the follow-up request.
"""

from __future__ import annotations

from collections.abc import Sequence

from agent_fakes import populated_gateway

from planbench_agent.provider import (
    LLMRequest,
    LLMResponse,
    MockProvider,
    ProviderTurn,
    StopReason,
    ToolCall,
)
from planbench_agent.rag import KnowledgeBase, split_markdown
from planbench_agent.workflow import CHAT_SYSTEM, MAX_TOOL_ITERATIONS, AgentService


def scripted(*responses: LLMResponse) -> MockProvider:
    """A provider that returns the given responses in order, then repeats."""

    class _Scripted(MockProvider):
        def __init__(self) -> None:
            super().__init__()
            self.requests: list[LLMRequest] = []
            self._queue = list(responses)

        def complete(self, request: LLMRequest) -> LLMResponse:
            self.requests.append(request)
            return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]

    return _Scripted()


def tool_turn(name: str, **arguments) -> LLMResponse:
    return LLMResponse(
        tool_calls=(ToolCall(id="c1", name=name, arguments=arguments),),
        stop_reason=StopReason.TOOL_USE,
    )


def answer(text: str) -> LLMResponse:
    return LLMResponse(text=text, stop_reason=StopReason.END_TURN)


def service(provider: MockProvider, knowledge: KnowledgeBase | None = None) -> AgentService:
    return AgentService(provider=provider, gateway=populated_gateway(), knowledge=knowledge)


class TestItAnswers:
    def test_a_direct_answer_reports_no_tools(self) -> None:
        turn, _ = service(scripted(answer("Two deployments."))).converse("how many?")
        assert turn.text == "Two deployments."
        assert turn.tools_used == ()
        assert turn.iterations == 1

    def test_a_tool_call_is_executed_and_named(self) -> None:
        provider = scripted(tool_turn("list_deployments"), answer("One: hall_v1."))
        turn, _ = service(provider).converse("which deployments exist?")
        assert turn.tools_used == ("list_deployments",)
        assert turn.text == "One: hall_v1."

    def test_the_tool_result_reaches_the_next_request(self) -> None:
        """Otherwise the model answers the second turn blind."""
        provider = scripted(tool_turn("list_deployments"), answer("done"))
        service(provider).converse("q")
        final = provider.requests[-1]
        assert any(message.tool_results for message in final.messages)


class TestItStops:
    def test_the_budget_is_enforced(self) -> None:
        provider = scripted(tool_turn("list_deployments"))
        turn, _ = service(provider).converse("q")
        assert turn.truncated
        assert turn.iterations == MAX_TOOL_ITERATIONS

    def test_a_truncated_turn_asserts_nothing(self) -> None:
        """The dangerous outcome is a confident summary of a loop that
        never finished, so the text says so instead."""
        turn, _ = service(scripted(tool_turn("list_deployments"))).converse("q")
        assert "Nothing is asserted" in turn.text

    def test_a_lower_budget_is_honoured(self) -> None:
        turn, _ = service(scripted(tool_turn("list_deployments"))).converse("q", max_iterations=2)
        assert turn.iterations == 2

    def test_a_refusal_ends_the_loop(self) -> None:
        provider = scripted(LLMResponse(text="I will not.", stop_reason=StopReason.REFUSAL))
        turn, _ = service(provider).converse("q")
        assert turn.text == "I will not."
        assert turn.iterations == 1


class TestItReportsToolFailures:
    def test_an_error_is_recorded_without_ending_the_turn(self) -> None:
        provider = scripted(tool_turn("get_decision_run", run_id="nope"), answer("not found"))
        turn, _ = service(provider).converse("tell me about run nope")
        assert turn.tool_errors
        assert "get_decision_run" in turn.tool_errors[0]
        assert turn.text == "not found"

    def test_a_failed_tool_still_counts_as_used(self) -> None:
        """A reader tracing an answer needs the attempt, not just the wins."""
        provider = scripted(tool_turn("get_decision_run", run_id="nope"), answer("x"))
        turn, _ = service(provider).converse("q")
        assert turn.tools_used == ("get_decision_run",)


class TestTheProviderTurnIsCarriedForward:
    def test_the_raw_assistant_payload_survives_the_round_trip(self) -> None:
        """Some vendors sign tool calls and reject a follow-up that drops
        the signature. Nothing here is visible until that happens."""
        signed = ProviderTurn(format="test", payload={"signature": "abc"})
        provider = scripted(
            LLMResponse(
                tool_calls=(ToolCall(id="c1", name="list_deployments", arguments={}),),
                stop_reason=StopReason.TOOL_USE,
                provider_turn=signed,
            ),
            answer("done"),
        )
        service(provider).converse("q")
        assistant = [message for message in provider.requests[-1].messages if message.provider_turn]
        assert assistant and assistant[0].provider_turn.payload == {"signature": "abc"}


class TestThePromptStatesTheRules:
    def test_it_forbids_answering_from_memory(self) -> None:
        assert "never answer from memory" in CHAT_SYSTEM

    def test_it_forbids_claiming_safety(self) -> None:
        assert "safe" in CHAT_SYSTEM

    def test_it_states_that_gates_are_not_scores(self) -> None:
        """The single most available wrong reading of a gate table."""
        assert "conditions of entry" in CHAT_SYSTEM

    def test_it_says_an_unranked_run_is_still_a_result(self) -> None:
        assert "ranked nobody is a result" in CHAT_SYSTEM

    def test_it_disclaims_the_authority_the_agent_does_not_have(self) -> None:
        assert "cannot run a comparison" in CHAT_SYSTEM


class TestToolsAreOfferedToTheModel:
    def test_the_request_carries_the_tool_specs(self) -> None:
        provider = scripted(answer("hi"))
        service(provider).converse("q")
        names = {spec.name for spec in provider.requests[0].tools}
        assert "get_decision_run" in names

    def test_knowledge_search_appears_only_with_a_corpus(self) -> None:
        base = KnowledgeBase(split_markdown("CONTRACTS.md", "# G2\ncollision bound\n"))
        with_docs = scripted(answer("hi"))
        service(with_docs, base).converse("q")
        assert "search_knowledge" in {spec.name for spec in with_docs.requests[0].tools}

        without = scripted(answer("hi"))
        service(without).converse("q")
        assert "search_knowledge" not in {spec.name for spec in without.requests[0].tools}


def test_history_is_prepended_to_the_conversation() -> None:
    from planbench_agent.provider import LLMMessage

    provider = scripted(answer("ok"))
    history: Sequence[LLMMessage] = (LLMMessage.user("earlier"), LLMMessage.assistant("noted"))
    service(provider).converse("now", history=history)
    texts = [message.text for message in provider.requests[0].messages]
    assert texts[:2] == ["earlier", "noted"]
