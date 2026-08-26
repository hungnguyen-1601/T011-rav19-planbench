"""Multi-step tool calling against an OpenAI-compatible provider.

The bug this pins down: Gemini signs every function call with a
``thought_signature`` and rejects the *next* request if the assistant
turn comes back without it —

    Function call is missing a thought_signature

The adapter used to rebuild that assistant message from the fields it
had parsed (text + tool calls), which silently dropped everything else
the vendor attached. The fix is to replay the provider's own payload
verbatim; these tests assert that the signature survives a full
round trip, and that the parts which must *not* change still work.

No network and no key: a fake client stands in for the OpenAI SDK. The
fake's message objects are pydantic models with ``extra="allow"``, which
is what the real SDK uses — so "the extra field survives model_dump()"
is a property of the same machinery in the test and in production.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from agent_fakes import FakeGateway
from pydantic import BaseModel, ConfigDict

from planbench_agent.anthropic_provider import WIRE_FORMAT as ANTHROPIC_WIRE
from planbench_agent.openai_provider import WIRE_FORMAT, OpenAICompatibleProvider
from planbench_agent.provider import (
    LLMMessage,
    LLMRequest,
    ProviderError,
    ProviderTurn,
    StopReason,
    ToolCall,
    ToolResult,
)
from planbench_agent.workflow import AgentService

#: An opaque, provider-issued token. Its only job here is to be carried
#: through untouched, so the value is arbitrary but must never change.
THOUGHT_SIGNATURE = "CjkBhZ5s0RTeSTsignature-value-from-gemini=="


# -- a stand-in for the OpenAI SDK ------------------------------------
#
# extra="allow" mirrors the SDK's own models: fields the SDK has never
# heard of are kept and included in model_dump(). That is exactly how a
# `thought_signature` reaches this adapter in production.


class SdkModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class SdkFunction(SdkModel):
    name: str
    arguments: str


class SdkToolCall(SdkModel):
    id: str
    type: str = "function"
    function: SdkFunction


class SdkMessage(SdkModel):
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[SdkToolCall] | None = None
    refusal: str | None = None


class SdkChoice(SdkModel):
    message: SdkMessage
    finish_reason: str = "stop"


class SdkUsage(SdkModel):
    prompt_tokens: int = 11
    completion_tokens: int = 7


class SdkCompletion(SdkModel):
    choices: list[SdkChoice]
    model: str = "gemini-3.5-flash-lite"
    usage: SdkUsage = SdkUsage()


class FakeCompletions:
    """Records every request body and replays a scripted list of turns."""

    def __init__(self, script: list[SdkCompletion]) -> None:
        self._script = list(script)
        self.requests: list[dict[str, Any]] = []

    def create(self, **payload: Any) -> SdkCompletion:
        self.requests.append(payload)
        if not self._script:
            raise AssertionError("the provider made more calls than the script allows")
        return self._script.pop(0)


class FakeClient:
    def __init__(self, script: list[SdkCompletion]) -> None:
        self.chat = type("Chat", (), {"completions": FakeCompletions(script)})()

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self.chat.completions.requests


def gemini_with(script: list[SdkCompletion]) -> tuple[OpenAICompatibleProvider, FakeClient]:
    """A Gemini provider whose HTTP client is the fake above.

    The key is a placeholder that never leaves this process; nothing here
    reads GEMINI_API_KEY.
    """
    provider = OpenAICompatibleProvider.for_provider(
        "gemini", model_id="gemini-3.5-flash-lite", api_key="not-a-real-key"
    )
    client = FakeClient(script)
    provider._cached_client = client
    return provider, client


def tool_call_turn(
    *, signature: str | None = THOUGHT_SIGNATURE, arguments: str = "{}"
) -> SdkCompletion:
    """An assistant turn asking for `list_benchmarks`, as Gemini sends it."""
    call = SdkToolCall(
        id="call_list_benchmarks_1",
        function=SdkFunction(name="list_decision_runs", arguments=arguments),
    )
    if signature is not None:
        # Gemini attaches this to the function call itself. The adapter
        # must not need to know that — it copies the whole object.
        call.thought_signature = signature  # type: ignore[attr-defined]
    return SdkCompletion(
        choices=[SdkChoice(message=SdkMessage(tool_calls=[call]), finish_reason="tool_calls")]
    )


def text_turn(text: str) -> SdkCompletion:
    return SdkCompletion(choices=[SdkChoice(message=SdkMessage(content=text))])


@pytest.fixture
def gateway() -> FakeGateway:
    fake = FakeGateway()
    fake.add_deployment()
    fake.add_run("a1b2c3d4e5f6")
    return fake


class TestCapture:
    def test_the_signature_reaches_the_response(self):
        provider, _ = gemini_with([tool_call_turn()])
        response = provider.complete(
            LLMRequest(system="s", messages=(LLMMessage.user("list the decision runs"),))
        )
        assert response.stop_reason is StopReason.TOOL_USE
        assert response.tool_calls[0].name == "list_decision_runs"

        turn = response.provider_turn
        assert turn is not None
        assert turn.format == WIRE_FORMAT
        assert turn.payload["tool_calls"][0]["thought_signature"] == THOUGHT_SIGNATURE

    def test_a_plain_text_turn_is_captured_too(self):
        provider, _ = gemini_with([text_turn("hello")])
        response = provider.complete(LLMRequest(system="s", messages=(LLMMessage.user("hi"),)))
        assert response.provider_turn is not None
        assert response.provider_turn.payload["content"] == "hello"


class TestReplay:
    def test_the_signature_survives_into_the_next_request(self):
        """The exact failure: turn two must still carry the signature."""
        provider, client = gemini_with([tool_call_turn(), text_turn("There is 1 benchmark.")])

        first = provider.complete(
            LLMRequest(system="s", messages=(LLMMessage.user("list the decision runs"),))
        )
        provider.complete(
            LLMRequest(
                system="s",
                messages=(
                    LLMMessage.user("list the decision runs"),
                    LLMMessage.assistant(
                        first.text, first.tool_calls, provider_turn=first.provider_turn
                    ),
                    LLMMessage.results(
                        [
                            ToolResult(
                                call_id="call_list_benchmarks_1",
                                name="list_decision_runs",
                                content="[]",
                            )
                        ]
                    ),
                ),
            )
        )

        assistant = [m for m in client.requests[1]["messages"] if m["role"] == "assistant"]
        assert len(assistant) == 1
        assert assistant[0]["tool_calls"][0]["thought_signature"] == THOUGHT_SIGNATURE

    def test_replay_keeps_the_tool_call_id_and_arguments(self):
        provider, client = gemini_with(
            [tool_call_turn(arguments='{"benchmark_id": "abc"}'), text_turn("done")]
        )
        first = provider.complete(LLMRequest(system="s", messages=(LLMMessage.user("go"),)))
        provider.complete(
            LLMRequest(
                system="s",
                messages=(
                    LLMMessage.user("go"),
                    LLMMessage.assistant(
                        first.text, first.tool_calls, provider_turn=first.provider_turn
                    ),
                ),
            )
        )
        call = client.requests[1]["messages"][-1]["tool_calls"][0]
        assert call["id"] == "call_list_benchmarks_1"
        assert json.loads(call["function"]["arguments"]) == {"benchmark_id": "abc"}

    def test_null_fields_are_dropped_from_the_replay(self):
        # The SDK fills in refusal=None and content=None; a stricter
        # compatibility layer can reject those, and they carry no meaning.
        provider, client = gemini_with([tool_call_turn(), text_turn("done")])
        first = provider.complete(LLMRequest(system="s", messages=(LLMMessage.user("go"),)))
        provider.complete(
            LLMRequest(
                system="s",
                messages=(
                    LLMMessage.user("go"),
                    LLMMessage.assistant(
                        first.text, first.tool_calls, provider_turn=first.provider_turn
                    ),
                ),
            )
        )
        replayed = client.requests[1]["messages"][-1]
        assert "refusal" not in replayed
        # content stays, because "no text on a tool-call turn" is itself
        # information the API expects.
        assert replayed["content"] is None
        assert replayed["role"] == "assistant"

    def test_a_turn_from_another_wire_format_is_rebuilt_not_replayed(self):
        # A transcript can outlive a provider switch. Replaying Anthropic
        # content blocks into a Chat Completions request would be worse
        # than rebuilding from the parsed fields.
        provider, client = gemini_with([text_turn("ok")])
        foreign = ProviderTurn(
            format=ANTHROPIC_WIRE,
            payload={"content": [{"type": "thinking", "thinking": "…", "signature": "x"}]},
        )
        provider.complete(
            LLMRequest(
                system="s",
                messages=(
                    LLMMessage.user("go"),
                    LLMMessage.assistant(
                        "earlier",
                        [ToolCall(id="c1", name="get", arguments={"a": 1})],
                        provider_turn=foreign,
                    ),
                ),
            )
        )
        rebuilt = client.requests[0]["messages"][-1]
        assert rebuilt["content"] == "earlier"
        assert rebuilt["tool_calls"][0]["id"] == "c1"
        assert "thinking" not in json.dumps(rebuilt)

    def test_a_turn_with_no_provider_payload_still_works(self):
        # Transcripts recorded before this fix, and the mock provider,
        # have no captured turn at all.
        provider, client = gemini_with([text_turn("ok")])
        provider.complete(
            LLMRequest(
                system="s",
                messages=(
                    LLMMessage.user("go"),
                    LLMMessage.assistant("earlier", [ToolCall(id="c1", name="get", arguments={})]),
                ),
            )
        )
        rebuilt = client.requests[0]["messages"][-1]
        assert rebuilt["role"] == "assistant"
        assert rebuilt["tool_calls"][0]["function"]["name"] == "get"


class TestFullLoop:
    """user request → list_benchmarks → tool result → final answer."""

    def test_the_whole_exchange_completes(self, gateway):
        provider, client = gemini_with(
            [tool_call_turn(), text_turn("There is 1 benchmark: a1b2c3d4e5f6.")]
        )
        service = AgentService(provider, gateway)

        turn, messages = service.converse("list the decision runs")

        assert turn.text == "There is 1 benchmark: a1b2c3d4e5f6."
        assert turn.tools_used == ("list_decision_runs",)
        assert turn.tool_errors == ()
        assert turn.iterations == 2
        assert turn.truncated is False

        # Two round trips: the tool call, then the answer.
        assert len(client.requests) == 2

        second = client.requests[1]["messages"]
        roles = [entry["role"] for entry in second]
        assert roles == ["system", "user", "assistant", "tool"]

        # The signature made it through the agent loop, not just the
        # adapter — this is the regression the bug report describes.
        assert second[2]["tool_calls"][0]["thought_signature"] == THOUGHT_SIGNATURE
        assert second[3]["tool_call_id"] == "call_list_benchmarks_1"

    def test_the_tool_actually_ran_and_its_result_was_sent(self, gateway):
        provider, client = gemini_with([tool_call_turn(), text_turn("done")])
        AgentService(provider, gateway).converse("list the decision runs")

        tool_message = client.requests[1]["messages"][-1]
        payload = json.loads(tool_message["content"])
        assert [entry["id"] for entry in payload] == ["a1b2c3d4e5f6"]

    def test_a_provider_without_a_signature_still_completes(self, gateway):
        # Not every OpenAI-compatible vendor signs its calls; the replay
        # path must not depend on the field existing.
        provider, client = gemini_with([tool_call_turn(signature=None), text_turn("done")])
        turn, _ = AgentService(provider, gateway).converse("list the decision runs")

        assert turn.text == "done"
        assert "thought_signature" not in json.dumps(client.requests[1]["messages"])


class TestErrorSurface:
    def test_an_sdk_failure_becomes_a_provider_error(self):
        class Exploding:
            def create(self, **_: Any):
                raise RuntimeError("Function call is missing a thought_signature")

        provider, _ = gemini_with([])
        provider._cached_client.chat.completions = Exploding()

        with pytest.raises(ProviderError) as exc:
            provider.complete(LLMRequest(system="s", messages=(LLMMessage.user("go"),)))
        # The upstream message is preserved: it is the actionable part.
        assert "thought_signature" in str(exc.value)
        assert "gemini request failed" in str(exc.value)
