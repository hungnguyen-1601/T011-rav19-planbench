"""Anthropic adapter for :class:`~planbench_agent.provider.LLMProvider`.

This is the only module in the repository that knows a vendor exists.
Domain code imports :mod:`planbench_agent.provider`; swapping in another
vendor means adding a sibling of this file, not editing anything else.

The SDK is imported lazily inside :meth:`AnthropicProvider._client` so
that `pip install anthropic` stays optional: a checkout without it still
runs every test and every offline workflow through the deterministic
mock. Credentials come from the environment only — no key is ever read
from a config file in the repository or written into a prompt.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
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

logger = logging.getLogger("planbench.agent.anthropic")

DEFAULT_MODEL = "claude-opus-5"
API_KEY_ENV = "ANTHROPIC_API_KEY"

# Above this, a non-streaming request risks an HTTP timeout, so the
# adapter switches to the streaming helper and collects the final
# message. Callers do not need to know which path ran.
STREAMING_THRESHOLD = 16_000

_STOP_REASONS = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "refusal": StopReason.REFUSAL,
}


class AnthropicProvider(LLMProvider):
    """Calls the Claude Messages API.

    ``effort`` and adaptive thinking are set explicitly rather than left
    to defaults: a benchmark platform should record exactly how the
    model was configured when a report was produced.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        effort: str = "high",
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get(API_KEY_ENV) or None
        self._effort = effort
        self._timeout = timeout
        self._max_retries = max_retries
        self._cached_client: Any | None = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    @property
    def deterministic(self) -> bool:
        return False

    @staticmethod
    def available() -> bool:
        """True when the SDK is importable and a key is in the environment."""
        if not os.environ.get(API_KEY_ENV):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _client(self) -> Any:
        if self._cached_client is not None:
            return self._cached_client
        # Key first: a missing key is the common misconfiguration, and
        # reporting the import error instead would send the reader after
        # the wrong problem.
        if not self._api_key:
            raise ProviderUnavailable(
                f"no API key: set {API_KEY_ENV} in the environment "
                "(never commit a key to the repository)"
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on the env
            raise ProviderUnavailable(
                "the 'anthropic' package is not installed; install it or use the "
                "deterministic mock provider"
            ) from exc
        self._cached_client = anthropic.Anthropic(
            api_key=self._api_key, timeout=self._timeout, max_retries=self._max_retries
        )
        return self._cached_client

    # -- request translation ---------------------------------------------

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [_to_wire(message) for message in request.messages],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._effort},
        }
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": dict(tool.input_schema),
                    "strict": True,
                }
                for tool in request.tools
            ]
        if request.output_schema is not None:
            payload["output_config"]["format"] = {
                "type": "json_schema",
                "schema": dict(request.output_schema),
            }
        return payload

    def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._client()
        payload = self._payload(request)
        try:
            if request.max_tokens > STREAMING_THRESHOLD:
                with client.messages.stream(**payload) as stream:
                    message = stream.get_final_message()
            else:
                message = client.messages.create(**payload)
        except ProviderUnavailable:
            raise
        except Exception as exc:  # SDK exception hierarchy is vendor-specific
            raise ProviderError(f"Anthropic request failed: {type(exc).__name__}: {exc}") from exc
        return _from_wire(message, expect_structured=request.output_schema is not None)


def _to_wire(message: LLMMessage) -> dict[str, Any]:
    """One domain message as an Anthropic message dict."""
    if message.role is MessageRole.ASSISTANT:
        content: list[dict[str, Any]] = []
        if message.text:
            content.append({"type": "text", "text": message.text})
        for call in message.tool_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": dict(call.arguments),
                }
            )
        return {"role": "assistant", "content": content or [{"type": "text", "text": ""}]}

    # Tool results and free text both arrive on a user turn. All results
    # for one assistant turn must travel together in a single message,
    # which is why LLMMessage groups them.
    if message.tool_results:
        blocks = [
            {
                "type": "tool_result",
                "tool_use_id": result.call_id,
                "content": result.content,
                **({"is_error": True} if result.is_error else {}),
            }
            for result in message.tool_results
        ]
        if message.text:
            blocks.append({"type": "text", "text": message.text})
        return {"role": "user", "content": blocks}
    return {"role": "user", "content": message.text}


def _from_wire(message: Any, expect_structured: bool) -> LLMResponse:
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for block in getattr(message, "content", ()) or ():
        kind = getattr(block, "type", "")
        if kind == "text":
            text_parts.append(block.text)
        elif kind == "tool_use":
            calls.append(ToolCall(id=block.id, name=block.name, arguments=_as_mapping(block.input)))

    text = "".join(text_parts)
    structured = None
    if expect_structured and text:
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            # Leave it unset: the caller validates with Pydantic and will
            # refuse, which is the correct outcome for a malformed answer.
            logger.warning("structured output was requested but the response was not JSON")

    usage = getattr(message, "usage", None)
    return LLMResponse(
        text=text,
        tool_calls=tuple(calls),
        structured=structured,
        stop_reason=_STOP_REASONS.get(
            getattr(message, "stop_reason", "") or "", StopReason.END_TURN
        ),
        model=getattr(message, "model", "") or "",
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return {"items": list(value)}
    return {"value": value}


__all__ = ["API_KEY_ENV", "DEFAULT_MODEL", "AnthropicProvider"]
