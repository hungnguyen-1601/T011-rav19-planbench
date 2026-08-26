"""Provider abstraction, deterministic mock, and the Anthropic adapter.

The Anthropic tests never touch the network: they assert on the request
payload the adapter builds and on how it reads a response object, which
is where translation bugs actually live.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from planbench_agent.anthropic_provider import (
    API_KEY_ENV,
    DEFAULT_MODEL,
    STREAMING_THRESHOLD,
    AnthropicProvider,
    _from_wire,
    _to_wire,
)
from planbench_agent.factory import build_provider
from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockProvider,
    ProviderError,
    ProviderUnavailable,
    RecordingProvider,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
)


def request(text: str = "hello", **kwargs) -> LLMRequest:
    return LLMRequest(system="sys", messages=(LLMMessage.user(text),), **kwargs)


class TestMockProvider:
    def test_is_a_provider_and_reports_determinism(self):
        provider = MockProvider()
        assert isinstance(provider, LLMProvider)
        assert provider.deterministic is True
        assert provider.model == "deterministic-mock"

    def test_same_request_gives_the_same_response(self):
        first = MockProvider().complete(request("compare dwa and ppo on doorway"))
        second = MockProvider().complete(request("compare dwa and ppo on doorway"))
        assert first == second

    def test_script_is_consumed_in_order_then_raises(self):
        provider = MockProvider(script=[LLMResponse(text="a"), LLMResponse(text="b")])
        assert provider.complete(request()).text == "a"
        assert provider.complete(request()).text == "b"
        with pytest.raises(ProviderError, match="exhausted"):
            provider.complete(request())

    def test_records_requests_for_prompt_assertions(self):
        provider = MockProvider(script=[LLMResponse(text="x")])
        provider.complete(request("mission text"))
        assert provider.calls[0].messages[0].text == "mission text"

    def test_custom_responder_takes_priority(self):
        provider = MockProvider(responder=lambda req: LLMResponse(text=req.system.upper()))
        assert provider.complete(request()).text == "SYS"


class TestRecordingProvider:
    def test_captures_every_exchange_for_audit(self):
        inner = MockProvider(script=[LLMResponse(text="one"), LLMResponse(text="two")])
        provider = RecordingProvider(inner=inner)
        provider.complete(request("a"))
        provider.complete(request("b"))
        assert [response.text for _, response in provider.exchanges] == ["one", "two"]
        assert provider.name == "recording:mock"
        assert provider.deterministic is True


class TestFactory:
    def test_mock_is_explicit_and_always_available(self):
        assert build_provider("mock").name == "mock"

    def test_auto_falls_back_to_mock_without_a_key(self, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV, raising=False)
        assert build_provider("auto").deterministic is True

    def test_auto_selects_anthropic_when_a_key_is_present(self, monkeypatch):
        monkeypatch.setattr(AnthropicProvider, "available", staticmethod(lambda: True))
        provider = build_provider("auto")
        assert provider.name == "anthropic"
        assert provider.model == DEFAULT_MODEL

    def test_unknown_provider_is_rejected(self):
        with pytest.raises(ValueError, match="unknown provider"):
            build_provider("gpt-whatever")


class TestAnthropicPayload:
    """Request/response translation, with no client constructed."""

    def test_payload_uses_adaptive_thinking_and_effort(self):
        provider = AnthropicProvider(api_key="unused-in-this-test", effort="high")
        payload = provider._payload(request("hi"))
        assert payload["model"] == DEFAULT_MODEL
        assert payload["thinking"] == {"type": "adaptive"}
        assert payload["output_config"]["effort"] == "high"
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        assert "tools" not in payload

    def test_tools_are_declared_strict(self):
        provider = AnthropicProvider(api_key="unused-in-this-test")
        schema = {"type": "object", "properties": {}, "additionalProperties": False}
        tool = ToolSpec(name="t", description="d", input_schema=schema)
        payload = provider._payload(request(tools=(tool,)))
        assert payload["tools"] == [
            {"name": "t", "description": "d", "input_schema": schema, "strict": True}
        ]

    def test_output_schema_becomes_a_json_schema_format(self):
        provider = AnthropicProvider(api_key="unused-in-this-test")
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        payload = provider._payload(request(output_schema=schema))
        assert payload["output_config"]["format"] == {"type": "json_schema", "schema": schema}

    def test_streaming_threshold_is_above_the_default_request(self):
        # Guards the rule "stream only when a non-streaming call would
        # risk an HTTP timeout" against an accidental default change.
        assert LLMRequest(system="", messages=()).max_tokens <= STREAMING_THRESHOLD

    def test_tool_results_ride_one_user_message(self):
        message = LLMMessage.results(
            [
                ToolResult(call_id="c1", name="a", content="ok"),
                ToolResult(call_id="c2", name="b", content="boom", is_error=True),
            ]
        )
        wire = _to_wire(message)
        assert wire["role"] == "user"
        assert [block["tool_use_id"] for block in wire["content"]] == ["c1", "c2"]
        assert wire["content"][1]["is_error"] is True

    def test_assistant_tool_calls_round_trip(self):
        message = LLMMessage.assistant(
            "thinking out loud", [ToolCall(id="c1", name="get", arguments={"x": 1})]
        )
        wire = _to_wire(message)
        assert wire["content"][0] == {"type": "text", "text": "thinking out loud"}
        assert wire["content"][1] == {
            "type": "tool_use",
            "id": "c1",
            "name": "get",
            "input": {"x": 1},
        }

    def test_reads_text_tool_calls_and_usage(self):
        message = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="answer"),
                SimpleNamespace(type="tool_use", id="c1", name="get", input={"k": "v"}),
            ],
            stop_reason="tool_use",
            model=DEFAULT_MODEL,
            usage=SimpleNamespace(input_tokens=11, output_tokens=22),
        )
        response = _from_wire(message, expect_structured=False)
        assert response.text == "answer"
        assert response.stop_reason is StopReason.TOOL_USE
        assert response.tool_calls[0].arguments == {"k": "v"}
        assert (response.input_tokens, response.output_tokens) == (11, 22)

    def test_refusal_stop_reason_is_preserved(self):
        message = SimpleNamespace(content=[], stop_reason="refusal", model="m", usage=None)
        assert _from_wire(message, False).stop_reason is StopReason.REFUSAL

    def test_structured_output_is_parsed_when_requested(self):
        message = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"scenario": "doorway"}')],
            stop_reason="end_turn",
            model="m",
            usage=None,
        )
        assert _from_wire(message, True).structured == {"scenario": "doorway"}

    def test_non_json_structured_output_leaves_structured_unset(self):
        # The caller then refuses, which is the correct outcome — better
        # than half-parsing something the model got wrong.
        message = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="sorry, I cannot")],
            stop_reason="end_turn",
            model="m",
            usage=None,
        )
        assert _from_wire(message, True).structured is None

    def test_missing_key_raises_provider_unavailable(self, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV, raising=False)
        with pytest.raises(ProviderUnavailable, match=API_KEY_ENV):
            AnthropicProvider()._client()

    def test_available_is_false_without_a_key(self, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV, raising=False)
        assert AnthropicProvider.available() is False
