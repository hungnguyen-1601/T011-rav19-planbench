"""Adapter for every provider that speaks the OpenAI Chat Completions API.

One wire format, many vendors. OpenAI defines it; Google exposes Gemini
through an OpenAI-compatible endpoint; OpenRouter, Groq, DeepSeek, xAI,
vLLM and Ollama all implement it too. Writing one careful adapter
against that format buys support for all of them and keeps a single code
path under test — better than a per-vendor adapter written from a
half-remembered SDK signature.

A vendor with features outside this format (Gemini's native grounding,
say) can still get its own adapter later: that is what
:class:`~planbench_agent.provider.LLMProvider` is for. Nothing in the
domain changes.

Two differences from the Anthropic wire format the translation has to
get right:

- tool results are **one message each** (``role: "tool"``), not grouped
  into a single user turn;
- tool arguments arrive as a **JSON string**, not a parsed object.

Credentials come from the environment only. No key is read from a file
in the repository, and no key is ever written into a prompt.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MessageRole,
    ProviderError,
    ProviderUnavailable,
    StopReason,
    ToolCall,
)

logger = logging.getLogger("planbench.agent.openai_compatible")

_STOP_REASONS = {
    "stop": StopReason.END_TURN,
    "tool_calls": StopReason.TOOL_USE,
    "function_call": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
    "content_filter": StopReason.REFUSAL,
}


@dataclass(frozen=True)
class Preset:
    """Everything that differs between OpenAI-compatible vendors."""

    name: str
    #: ``None`` means the SDK's own default (api.openai.com).
    base_url: str | None
    #: Environment variable holding the key. Empty = no key needed.
    api_key_env: str
    #: Newer OpenAI models require ``max_completion_tokens``; most other
    #: implementations of the format only accept ``max_tokens``.
    max_tokens_field: str = "max_tokens"
    #: Where to look up valid model ids, quoted in the error message when
    #: no model is configured.
    models_hint: str = ""
    #: Key that is deliberately not required (local servers).
    requires_key: bool = True


PRESETS: dict[str, Preset] = {
    "openai": Preset(
        name="openai",
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        max_tokens_field="max_completion_tokens",
        models_hint="https://platform.openai.com/docs/models",
    ),
    "gemini": Preset(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        models_hint="https://ai.google.dev/gemini-api/docs/models",
    ),
    "openrouter": Preset(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        models_hint="https://openrouter.ai/models",
    ),
    "groq": Preset(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        models_hint="https://console.groq.com/docs/models",
    ),
    "deepseek": Preset(
        name="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        models_hint="https://api-docs.deepseek.com",
    ),
    "xai": Preset(
        name="xai",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
        models_hint="https://docs.x.ai/docs/models",
    ),
    "local": Preset(
        name="local",
        # Ollama's and vLLM's OpenAI-compatible servers both default here.
        base_url="http://localhost:11434/v1",
        api_key_env="",
        models_hint="whatever your local server serves (`ollama list`)",
        requires_key=False,
    ),
}


@dataclass
class OpenAICompatibleProvider(LLMProvider):
    """Chat Completions client for any vendor implementing that API."""

    preset: Preset
    model_id: str = ""
    api_key: str | None = None
    base_url: str | None = None
    timeout: float = 120.0
    max_retries: int = 2
    #: Vendor-specific extras merged into every request body, for knobs
    #: this adapter does not model (``reasoning_effort``, ``top_p``, …).
    extra_options: Mapping[str, Any] = field(default_factory=dict)
    _cached_client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.api_key is None and self.preset.api_key_env:
            self.api_key = os.environ.get(self.preset.api_key_env) or None
        if self.base_url is None:
            self.base_url = self.preset.base_url

    @property
    def name(self) -> str:
        return self.preset.name

    @property
    def model(self) -> str:
        return self.model_id

    @property
    def deterministic(self) -> bool:
        return False

    @classmethod
    def for_provider(cls, kind: str, **kwargs: Any) -> OpenAICompatibleProvider:
        try:
            preset = PRESETS[kind]
        except KeyError:
            raise ValueError(
                f"unknown OpenAI-compatible provider {kind!r}; expected one of {sorted(PRESETS)}"
            ) from None
        return cls(preset=preset, **kwargs)

    @staticmethod
    def sdk_installed() -> bool:
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def available(cls, kind: str) -> bool:
        """True when the SDK is importable and the key (if any) is set."""
        preset = PRESETS.get(kind)
        if preset is None:
            return False
        if preset.requires_key and not os.environ.get(preset.api_key_env):
            return False
        return cls.sdk_installed()

    def _client(self) -> Any:
        if self._cached_client is not None:
            return self._cached_client
        # Key first: a missing key is the common misconfiguration, and
        # reporting an import error instead sends the reader after the
        # wrong problem.
        if self.preset.requires_key and not self.api_key:
            raise ProviderUnavailable(
                f"no API key for {self.preset.name!r}: set "
                f"{self.preset.api_key_env} in the environment "
                "(never commit a key to the repository)"
            )
        if not self.model_id:
            raise ProviderUnavailable(
                f"no model configured for {self.preset.name!r}: set "
                f"PLANBENCH_AGENT_MODEL to a model this provider serves "
                f"({self.preset.models_hint})"
            )
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on the env
            raise ProviderUnavailable(
                "the 'openai' package is not installed; install it "
                "(`pip install openai`) or use the deterministic mock provider"
            ) from exc
        self._cached_client = openai.OpenAI(
            api_key=self.api_key or "not-needed",
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        return self._cached_client

    # -- request translation ---------------------------------------------

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for message in request.messages:
            messages.extend(_to_wire(message))

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            self.preset.max_tokens_field: request.max_tokens,
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": _function_spec(
                        tool.name, tool.description, dict(tool.input_schema)
                    ),
                }
                for tool in request.tools
            ]
        if request.output_schema is not None:
            schema = dict(request.output_schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "planbench_structured_output",
                    "schema": schema,
                    "strict": _schema_is_strict(schema),
                },
            }
        payload.update(self.extra_options)
        return payload

    def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._client()
        try:
            completion = client.chat.completions.create(**self._payload(request))
        except ProviderUnavailable:
            raise
        except Exception as exc:  # the SDK's hierarchy is vendor-specific
            raise ProviderError(
                f"{self.preset.name} request failed: {type(exc).__name__}: {exc}"
            ) from exc
        return _from_wire(completion, expect_structured=request.output_schema is not None)


def _function_spec(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
    """One tool as an OpenAI function definition.

    ``strict`` is only claimed when the schema actually satisfies the
    strict-mode rules (closed object, every property required).
    Declaring it otherwise is rejected by the API, and several of our
    tools legitimately have optional arguments.
    """
    spec: dict[str, Any] = {"name": name, "description": description, "parameters": schema}
    if _schema_is_strict(schema):
        spec["strict"] = True
    return spec


def _schema_is_strict(schema: Mapping[str, Any]) -> bool:
    if schema.get("additionalProperties") is not False:
        return False
    properties = set((schema.get("properties") or {}).keys())
    return properties == set(schema.get("required") or ())


def _to_wire(message: LLMMessage) -> list[dict[str, Any]]:
    """One domain message as one *or more* Chat Completions messages."""
    if message.role is MessageRole.ASSISTANT:
        wire: dict[str, Any] = {"role": "assistant", "content": message.text or None}
        if message.tool_calls:
            wire["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(dict(call.arguments), sort_keys=True),
                    },
                }
                for call in message.tool_calls
            ]
        return [wire]

    # Unlike Anthropic, each tool result is its own message with
    # role "tool"; there is no is_error flag, so the error is carried in
    # the text where the model can still read it.
    if message.tool_results:
        messages = [
            {
                "role": "tool",
                "tool_call_id": result.call_id,
                "content": f"ERROR: {result.content}" if result.is_error else result.content,
            }
            for result in message.tool_results
        ]
        if message.text:
            messages.append({"role": "user", "content": message.text})
        return messages
    return [{"role": "user", "content": message.text}]


def _from_wire(completion: Any, expect_structured: bool) -> LLMResponse:
    choices = getattr(completion, "choices", None) or ()
    if not choices:
        raise ProviderError("the provider returned no choices")
    choice = choices[0]
    message = choice.message

    text = getattr(message, "content", None) or ""
    calls: list[ToolCall] = []
    for call in getattr(message, "tool_calls", None) or ():
        function = getattr(call, "function", None)
        if function is None:
            continue
        calls.append(
            ToolCall(
                id=getattr(call, "id", "") or "",
                name=getattr(function, "name", "") or "",
                arguments=_parse_arguments(getattr(function, "arguments", "")),
            )
        )

    structured = None
    if expect_structured and text:
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            # Leave it unset: the caller validates with Pydantic and will
            # refuse, which is the right outcome for a malformed answer.
            logger.warning("structured output was requested but the response was not JSON")

    usage = getattr(completion, "usage", None)
    return LLMResponse(
        text=text,
        tool_calls=tuple(calls),
        structured=structured,
        stop_reason=_STOP_REASONS.get(
            getattr(choice, "finish_reason", "") or "", StopReason.END_TURN
        ),
        model=getattr(completion, "model", "") or "",
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )


def _parse_arguments(raw: Any) -> Mapping[str, Any]:
    """Tool arguments arrive as a JSON string on this API.

    A model that emits malformed JSON produces an empty argument map
    rather than an exception: the tool then reports a missing-argument
    error the model can see and correct, which beats killing the loop.
    """
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("tool arguments were not valid JSON: %r", raw[:200])
            return {}
        if isinstance(parsed, Mapping):
            return dict(parsed)
        if isinstance(parsed, Sequence) and not isinstance(parsed, str | bytes):
            return {"items": list(parsed)}
        return {"value": parsed}
    return {}


__all__ = ["PRESETS", "OpenAICompatibleProvider", "Preset"]
