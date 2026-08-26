"""Provider-agnostic LLM interface.

Nothing below names a vendor. Domain code (mission parsing, tool
calling, report writing) depends only on :class:`LLMProvider`, so the
backing model can be swapped — or replaced by the deterministic mock —
without touching a single line of agent logic.

Design notes:

- One request object rather than a long keyword list. Adding a
  capability later (say, a cache hint) means one optional field, not a
  signature change in every provider.
- Tool calls and tool results are first-class message parts. Providers
  translate them to their own wire format; the agent loop in
  :mod:`planbench_agent.workflow` never sees provider-specific shapes.
- ``structured`` carries a parsed object when ``output_schema`` was
  requested. Callers still validate it with Pydantic — a provider
  claiming schema conformance is not proof of it.

Safety boundary (spec section 25): a provider can only return text,
tool calls, or a structured object. It cannot execute anything. Every
side effect goes through the tool registry, which enforces its own
policy — the LLM never reaches the simulator, ``/cmd_vel``, or the
approval state machine directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProviderError(Exception):
    """The provider failed to produce a usable response."""


class ProviderUnavailable(ProviderError):
    """The provider is not configured or its SDK is not installed."""


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class StopReason(StrEnum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    REFUSAL = "refusal"


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model. ``input_schema`` is JSON Schema."""

    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """The model asking for a tool to run. ``id`` correlates the result."""

    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """The outcome of a tool call, fed back on the next turn."""

    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class ProviderTurn:
    """A provider's own serialisation of an assistant turn, kept intact.

    ``text`` and ``tool_calls`` are the parts the agent understands, and
    for a long time they were all this layer kept. That loses whatever
    else the vendor attached — and some vendors *require* it back on the
    next request:

    * Gemini signs each function call with a ``thought_signature`` and
      rejects the follow-up turn without it ("Function call is missing a
      thought_signature");
    * Anthropic requires thinking blocks echoed back unchanged while a
      turn is still in progress.

    Rebuilding the assistant message from the parsed fields drops both.
    So the provider stores its raw payload here and replays it verbatim
    instead of reconstructing it.

    ``format`` names the wire format, not the vendor: every
    OpenAI-compatible provider shares one. A provider must ignore a turn
    whose format it does not recognise — that is what makes a transcript
    safe to carry across a provider switch.
    """

    format: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class LLMMessage:
    """One conversation turn.

    A user turn carries either free text or tool results; an assistant
    turn carries text and/or tool calls. Keeping both on one type means
    the transcript is a plain list, which is trivial to persist.
    """

    role: MessageRole
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    #: Set on assistant turns that came back from a provider. Replayed
    #: verbatim so vendor metadata survives the round trip.
    provider_turn: ProviderTurn | None = None

    @staticmethod
    def user(text: str) -> LLMMessage:
        return LLMMessage(role=MessageRole.USER, text=text)

    @staticmethod
    def assistant(
        text: str = "",
        tool_calls: Sequence[ToolCall] = (),
        provider_turn: ProviderTurn | None = None,
    ) -> LLMMessage:
        return LLMMessage(
            role=MessageRole.ASSISTANT,
            text=text,
            tool_calls=tuple(tool_calls),
            provider_turn=provider_turn,
        )

    @staticmethod
    def results(results: Sequence[ToolResult]) -> LLMMessage:
        return LLMMessage(role=MessageRole.USER, tool_results=tuple(results))


@dataclass(frozen=True)
class LLMRequest:
    """Everything a provider needs for one completion."""

    system: str
    messages: tuple[LLMMessage, ...]
    tools: tuple[ToolSpec, ...] = ()
    output_schema: Mapping[str, Any] | None = None
    max_tokens: int = 8192


@dataclass(frozen=True)
class LLMResponse:
    """What a provider returned. ``structured`` is unvalidated by design."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    structured: Mapping[str, Any] | None = None
    stop_reason: StopReason = StopReason.END_TURN
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    #: The provider's untouched assistant turn, for replay on the next
    #: request. See :class:`ProviderTurn`.
    provider_turn: ProviderTurn | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """The only surface domain code may use to reach a language model."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier recorded in transcripts and reports."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier, or a sentinel for non-model providers."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one completion. Must not raise for ordinary refusals."""

    @property
    def deterministic(self) -> bool:
        """True when identical requests always produce identical output.

        Reports record this: a conclusion drawn with a non-deterministic
        provider is not reproducible from the transcript alone.
        """
        return False


Responder = Callable[[LLMRequest], LLMResponse]


class MockProvider(LLMProvider):
    """Deterministic stand-in used by tests and by key-less deployments.

    Three modes, in priority order:

    1. ``script`` — replay a fixed list of responses, one per call. Used
       by tests that need an exact model output (including malformed
       ones, to prove the validators reject them).
    2. ``responder`` — a caller-supplied pure function of the request.
    3. default — :class:`planbench_agent.deterministic.DeterministicResponder`,
       a rule-based responder that keeps the whole M8 pipeline runnable
       without any API key.

    It is never a substitute for a real model: it does keyword matching,
    not language understanding. What it *does* guarantee is that every
    surrounding guarantee — schema validation, the approval gate,
    citation checking — is exercised for real.
    """

    def __init__(
        self,
        *,
        script: Sequence[LLMResponse] | None = None,
        responder: Responder | None = None,
        name: str = "mock",
    ) -> None:
        self._name = name
        self._script = list(script) if script is not None else None
        self._calls: list[LLMRequest] = []
        if responder is not None:
            self._responder: Responder | None = responder
        elif script is not None:
            self._responder = None
        else:
            from planbench_agent.deterministic import DeterministicResponder

            self._responder = DeterministicResponder()

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return "deterministic-mock"

    @property
    def deterministic(self) -> bool:
        return True

    @property
    def calls(self) -> tuple[LLMRequest, ...]:
        """Every request seen, for assertions about prompt construction."""
        return tuple(self._calls)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._calls.append(request)
        if self._script is not None:
            if not self._script:
                raise ProviderError("mock provider script exhausted")
            return self._script.pop(0)
        assert self._responder is not None  # set in every non-script branch
        return self._responder(request)


@dataclass
class RecordingProvider(LLMProvider):
    """Wraps another provider and records the exchange for auditing.

    Every agent conclusion has to be re-checkable by a human, which
    means the exact prompt and the exact answer must be recoverable.
    """

    inner: LLMProvider
    exchanges: list[tuple[LLMRequest, LLMResponse]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"recording:{self.inner.name}"

    @property
    def model(self) -> str:
        return self.inner.model

    @property
    def deterministic(self) -> bool:
        return self.inner.deterministic

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self.inner.complete(request)
        self.exchanges.append((request, response))
        return response


__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MessageRole",
    "MockProvider",
    "ProviderError",
    "ProviderTurn",
    "ProviderUnavailable",
    "RecordingProvider",
    "Responder",
    "StopReason",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
]
