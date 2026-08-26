"""Multi-provider support: presets, selection, and wire translation.

No network. The OpenAI-compatible adapter is exercised by asserting on
the request body it builds and on how it reads a response object —
which is where translation bugs live. Whether a given vendor is up is
not something a unit test can settle; `scripts/check_agent_provider.py`
answers that with one real call.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from planbench_agent.factory import (
    ANTHROPIC,
    AUTO_ORDER,
    PROVIDERS,
    build_provider,
    describe_unavailable,
    provider_status,
    require_provider,
)
from planbench_agent.openai_provider import (
    PRESETS,
    OpenAICompatibleProvider,
    _completion_ceiling,
    _from_wire,
    _schema_is_strict,
    _to_wire,
)
from planbench_agent.provider import (
    LLMMessage,
    LLMRequest,
    ProviderError,
    ProviderUnavailable,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
)

ALL_KEY_ENVS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
)


@pytest.fixture
def no_keys(monkeypatch):
    """A clean environment: no provider is configured."""
    for name in ALL_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)


def provider(kind: str = "openai", **kwargs) -> OpenAICompatibleProvider:
    kwargs.setdefault("model_id", "test-model")
    kwargs.setdefault("api_key", "unused-in-this-test")
    return OpenAICompatibleProvider.for_provider(kind, **kwargs)


def request(text: str = "hello", **kwargs) -> LLMRequest:
    return LLMRequest(system="sys", messages=(LLMMessage.user(text),), **kwargs)


class TestPresets:
    def test_every_preset_is_selectable_by_name(self):
        assert set(PRESETS).issubset(set(PROVIDERS))

    @pytest.mark.parametrize("kind", sorted(PRESETS))
    def test_each_preset_is_complete(self, kind):
        preset = PRESETS[kind]
        assert preset.name == kind
        assert preset.max_tokens_field in {"max_tokens", "max_completion_tokens"}
        if preset.requires_key:
            assert preset.api_key_env.endswith("_API_KEY")

    def test_openai_uses_the_sdk_default_endpoint(self):
        assert PRESETS["openai"].base_url is None

    def test_other_vendors_pin_an_endpoint(self):
        for kind in ("gemini", "openrouter", "groq", "deepseek", "xai"):
            assert PRESETS[kind].base_url.startswith("http")

    def test_gemini_uses_its_openai_compatible_endpoint(self):
        assert PRESETS["gemini"].base_url.endswith("/openai/")

    def test_local_needs_no_key(self):
        assert PRESETS["local"].requires_key is False

    def test_unknown_preset_is_rejected(self):
        with pytest.raises(ValueError, match="unknown OpenAI-compatible provider"):
            OpenAICompatibleProvider.for_provider("mistral-but-not-configured")

    def test_key_is_read_from_the_preset_env_var(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk-from-environment")
        assert OpenAICompatibleProvider.for_provider("groq").api_key == "gsk-from-environment"

    def test_explicit_base_url_wins_over_the_preset(self):
        custom = provider("openai", base_url="https://proxy.internal/v1")
        assert custom.base_url == "https://proxy.internal/v1"


class TestPayload:
    def test_system_prompt_becomes_the_first_message(self):
        payload = provider()._payload(request("hi"))
        assert payload["messages"][0] == {"role": "system", "content": "sys"}
        assert payload["messages"][1] == {"role": "user", "content": "hi"}

    def test_openai_uses_max_completion_tokens(self):
        payload = provider("openai")._payload(request())
        assert "max_completion_tokens" in payload
        assert "max_tokens" not in payload

    def test_other_vendors_use_max_tokens(self):
        payload = provider("gemini")._payload(request())
        assert "max_tokens" in payload
        assert "max_completion_tokens" not in payload

    def test_tools_are_wrapped_as_functions(self):
        schema = {
            "type": "object",
            "properties": {"benchmark_id": {"type": "string"}},
            "required": ["benchmark_id"],
            "additionalProperties": False,
        }
        tool = ToolSpec(name="get_benchmark", description="d", input_schema=schema)
        payload = provider()._payload(request(tools=(tool,)))
        function = payload["tools"][0]["function"]
        assert payload["tools"][0]["type"] == "function"
        assert function["name"] == "get_benchmark"
        assert function["parameters"] == schema

    def test_strict_is_claimed_only_when_the_schema_qualifies(self):
        # Strict mode requires a closed object with every property
        # required. Several of our tools have optional arguments, and
        # claiming strict for those is rejected by the API.
        closed = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
            "additionalProperties": False,
        }
        optional = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "additionalProperties": False,
        }
        assert _schema_is_strict(closed) is True
        assert _schema_is_strict(optional) is False

        tools = (
            ToolSpec(name="closed", description="d", input_schema=closed),
            ToolSpec(name="optional", description="d", input_schema=optional),
        )
        functions = [
            tool["function"] for tool in provider()._payload(request(tools=tools))["tools"]
        ]
        assert functions[0]["strict"] is True
        assert "strict" not in functions[1]

    def test_output_schema_becomes_a_response_format(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
            "additionalProperties": False,
        }
        payload = provider()._payload(request(output_schema=schema))
        response_format = payload["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["schema"] == schema
        assert response_format["json_schema"]["strict"] is True

    def test_strict_is_judged_all_the_way_down(self):
        """The rules apply to every object, not only the outermost one.

        Judging the root alone claimed strict for the advisor schema,
        whose nested object left one property out of ``required``, and
        every advisory call came back 400 for months — read downstream as
        "the model added nothing", because a rejected request and an
        unhelpful answer both degrade to the rules.
        """
        nested_open = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
                        "required": ["a"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        }
        assert _schema_is_strict(nested_open) is False
        nested_open["properties"]["items"]["items"]["required"] = ["a", "b"]
        assert _schema_is_strict(nested_open) is True

    def test_the_real_advisor_schema_qualifies_for_strict_mode(self):
        """The advisory routes' schema, held to the same bar as critique.

        Every test of the advisor uses a scripted provider, so nothing
        else in the suite would notice the API refusing this schema.
        """
        from planbench_agent.advisor import advisor_schema

        payload = provider()._payload(request(output_schema=advisor_schema()))
        assert payload["response_format"]["json_schema"]["strict"] is True

    def test_the_real_critique_schema_qualifies_for_strict_mode(self):
        """The one schema this project actually sends.

        Strict mode is refused for schemas that leave a door open, so a
        change to the critique schema that quietly drops
        additionalProperties: false would show up here rather than as a
        provider rejecting the request in production.
        """
        from planbench_agent.critique import critique_schema

        payload = provider()._payload(request(output_schema=critique_schema()))
        assert payload["response_format"]["json_schema"]["strict"] is True

    def test_extra_options_are_merged(self):
        custom = provider(extra_options={"reasoning_effort": "high"})
        assert custom._payload(request())["reasoning_effort"] == "high"


class TestMessageTranslation:
    def test_tool_results_become_one_message_each(self):
        # The key difference from Anthropic, where they are grouped into
        # a single user turn.
        message = LLMMessage.results(
            [
                ToolResult(call_id="c1", name="a", content="ok"),
                ToolResult(call_id="c2", name="b", content="missing", is_error=True),
            ]
        )
        wire = _to_wire(message)
        assert [entry["role"] for entry in wire] == ["tool", "tool"]
        assert wire[0] == {"role": "tool", "tool_call_id": "c1", "content": "ok"}

    def test_errors_are_marked_in_the_text(self):
        # There is no is_error flag on this API, so the model has to read
        # the failure out of the content.
        wire = _to_wire(
            LLMMessage.results([ToolResult(call_id="c1", name="a", content="nope", is_error=True)])
        )
        assert wire[0]["content"] == "ERROR: nope"

    def test_assistant_tool_calls_serialise_arguments_as_json(self):
        message = LLMMessage.assistant(
            "working", [ToolCall(id="c1", name="get", arguments={"x": 1})]
        )
        wire = _to_wire(message)[0]
        assert wire["content"] == "working"
        assert wire["tool_calls"][0]["function"]["arguments"] == '{"x": 1}'

    def test_a_toolless_assistant_turn_has_no_tool_calls_key(self):
        assert "tool_calls" not in _to_wire(LLMMessage.assistant("just text"))[0]

    def test_empty_assistant_text_becomes_null_content(self):
        assert _to_wire(LLMMessage.assistant(""))[0]["content"] is None


def completion(
    content: str | None = "answer",
    tool_calls=None,
    finish_reason: str = "stop",
    model: str = "test-model",
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        model=model,
        usage=SimpleNamespace(prompt_tokens=7, completion_tokens=9),
    )


class TestResponseTranslation:
    def test_reads_text_and_usage(self):
        response = _from_wire(completion(), expect_structured=False)
        assert response.text == "answer"
        assert (response.input_tokens, response.output_tokens) == (7, 9)
        assert response.stop_reason is StopReason.END_TURN

    def test_parses_tool_calls_from_a_json_string(self):
        call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="get_benchmark", arguments='{"benchmark_id": "abc"}'),
        )
        response = _from_wire(
            completion(content=None, tool_calls=[call], finish_reason="tool_calls"),
            expect_structured=False,
        )
        assert response.stop_reason is StopReason.TOOL_USE
        assert response.tool_calls[0].arguments == {"benchmark_id": "abc"}

    def test_malformed_tool_arguments_yield_an_empty_map(self):
        # The tool then reports a missing-argument error the model can
        # see and correct — better than killing the loop.
        call = SimpleNamespace(id="c", function=SimpleNamespace(name="get", arguments="{oops"))
        response = _from_wire(
            completion(content=None, tool_calls=[call], finish_reason="tool_calls"),
            expect_structured=False,
        )
        assert response.tool_calls[0].arguments == {}

    @pytest.mark.parametrize(
        ("finish_reason", "expected"),
        [
            ("stop", StopReason.END_TURN),
            ("tool_calls", StopReason.TOOL_USE),
            ("length", StopReason.MAX_TOKENS),
            ("content_filter", StopReason.REFUSAL),
            ("something_new", StopReason.END_TURN),
        ],
    )
    def test_finish_reasons_map_onto_the_domain(self, finish_reason, expected):
        assert _from_wire(completion(finish_reason=finish_reason), False).stop_reason is expected

    def test_structured_output_is_parsed(self):
        response = _from_wire(completion(content='{"scenario": "doorway"}'), True)
        assert response.structured == {"scenario": "doorway"}

    def test_non_json_structured_output_leaves_structured_unset(self):
        assert _from_wire(completion(content="sorry, I cannot"), True).structured is None

    def test_an_empty_choice_list_is_an_error(self):
        from planbench_agent.provider import ProviderError

        empty = SimpleNamespace(choices=[], model="m", usage=None)
        with pytest.raises(ProviderError, match="no choices"):
            _from_wire(empty, False)


class TestClientConstruction:
    def test_missing_key_is_reported_before_anything_else(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ProviderUnavailable, match="OPENAI_API_KEY"):
            OpenAICompatibleProvider.for_provider("openai", model_id="m")._client()

    def test_missing_model_is_reported_with_where_to_look(self):
        with pytest.raises(ProviderUnavailable, match="PLANBENCH_AGENT_MODEL"):
            OpenAICompatibleProvider.for_provider("gemini", api_key="k", model_id="")._client()

    def test_local_needs_no_key_but_still_needs_a_model(self, monkeypatch):
        with pytest.raises(ProviderUnavailable, match="PLANBENCH_AGENT_MODEL"):
            OpenAICompatibleProvider.for_provider("local")._client()


class TestSelection:
    def test_auto_falls_back_to_the_mock_with_nothing_configured(self, no_keys):
        assert build_provider("auto").deterministic is True

    def test_auto_order_covers_every_key_bearing_provider(self):
        assert ANTHROPIC in AUTO_ORDER
        keyed = {kind for kind, preset in PRESETS.items() if preset.requires_key}
        assert keyed.issubset(set(AUTO_ORDER))

    def test_local_is_never_chosen_automatically(self):
        # An unreachable localhost port should not silently become the
        # configured provider.
        assert "local" not in AUTO_ORDER

    def test_auto_picks_a_configured_openai_compatible_provider(self, no_keys, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(OpenAICompatibleProvider, "sdk_installed", staticmethod(lambda: True))
        chosen = build_provider("auto", model="gemini-test-model")
        assert chosen.name == "gemini"
        assert chosen.model == "gemini-test-model"

    def test_auto_skips_a_keyed_provider_with_no_model(self, no_keys, monkeypatch):
        # A key alone is not enough: the first request would fail.
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setattr(OpenAICompatibleProvider, "sdk_installed", staticmethod(lambda: True))
        assert build_provider("auto").deterministic is True

    def test_anthropic_wins_when_several_are_configured(self, no_keys, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setattr(OpenAICompatibleProvider, "sdk_installed", staticmethod(lambda: True))
        from planbench_agent.anthropic_provider import AnthropicProvider

        monkeypatch.setattr(AnthropicProvider, "available", staticmethod(lambda: True))
        assert build_provider("auto", model="some-model").name == "anthropic"

    def test_naming_a_provider_never_silently_downgrades(self, no_keys):
        # Building succeeds (nothing has been called yet); the failure
        # surfaces on use, naming the missing key rather than quietly
        # answering from the mock.
        chosen = build_provider("openai", model="m")
        assert chosen.name == "openai"
        with pytest.raises(ProviderUnavailable):
            chosen.complete(request())

    def test_unknown_provider_name_is_rejected(self):
        with pytest.raises(ValueError, match="unknown provider"):
            build_provider("chatgpt-5-turbo-ultra")


class TestStatusReporting:
    def test_status_lists_every_provider(self, no_keys):
        names = {status.name for status in provider_status()}
        assert names == {ANTHROPIC, *PRESETS}

    def test_missing_says_what_to_do(self, no_keys):
        status = next(s for s in provider_status() if s.name == "openai")
        assert status.ready is False
        assert "set OPENAI_API_KEY" in status.missing

    def test_local_only_ever_misses_the_sdk(self, no_keys):
        status = next(s for s in provider_status() if s.name == "local")
        assert "set " not in status.missing

    def test_describe_unavailable_is_empty_when_ready(self, no_keys, monkeypatch):
        monkeypatch.setenv("XAI_API_KEY", "test-key")
        monkeypatch.setattr(
            "planbench_agent.factory._can_import", lambda module: module == "openai"
        )
        assert describe_unavailable("xai") == ""

    def test_require_provider_raises_with_the_fix(self, no_keys):
        with pytest.raises(ProviderUnavailable, match="set OPENAI_API_KEY"):
            require_provider("openai", model="m")


class TestTheModelSOwnCompletionCeiling:
    """A caller's token budget is a budget, not a demand.

    ``ADVISOR_MAX_TOKENS`` is sized for models that spend output budget
    reasoning before the first token of JSON. Sent unchanged to a model
    whose own ceiling is lower, it made every call a 400 — the advisor
    then degraded to the rules, which is indistinguishable from a model
    with nothing to say.
    """

    def test_the_ceiling_is_read_out_of_the_refusal(self):
        message = (
            "Error code: 400 - max_tokens is too large: 32768. This model supports "
            "at most 16384 completion tokens, whereas you provided 32768."
        )
        assert _completion_ceiling(message) == 16384

    def test_an_unrelated_failure_names_no_ceiling(self):
        assert _completion_ceiling("rate limit exceeded") is None

    def test_the_call_is_retried_under_the_stated_ceiling(self, monkeypatch):
        sent = []

        class _Completions:
            def create(self, **payload):
                sent.append(payload)
                if payload["max_completion_tokens"] > 16384:
                    raise RuntimeError(
                        "max_tokens is too large: 32768. This model supports at most "
                        "16384 completion tokens, whereas you provided 32768."
                    )
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="{}", tool_calls=None),
                            finish_reason="stop",
                        )
                    ],
                    usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
                    model="test-model",
                )

        client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
        under_test = provider()
        monkeypatch.setattr(under_test, "_client", lambda: client)
        under_test.complete(request(max_tokens=32768))
        assert [p["max_completion_tokens"] for p in sent] == [32768, 16384]

    def test_a_failure_with_no_ceiling_is_not_retried(self, monkeypatch):
        calls = []

        class _Completions:
            def create(self, **payload):
                calls.append(payload)
                raise RuntimeError("connection reset")

        client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
        under_test = provider()
        monkeypatch.setattr(under_test, "_client", lambda: client)
        with pytest.raises(ProviderError):
            under_test.complete(request())
        assert len(calls) == 1
