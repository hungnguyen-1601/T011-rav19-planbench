"""The tool loop: a model answering questions about stored runs.

What this module used to be was a state machine over drafting, approval,
execution and reporting — the order a benchmark had to happen in, encoded
so the model could not reorder it. That order still exists, but it now
lives on the decisions page where a person walks it, and the parts of it
the agent could touch created records nothing displayed. They are gone.

What remains is the half that was always the model's job and is now its
only job: read what the platform recorded, and answer from it.

Two bounds hold that in place. The **iteration cap** stops a model that
keeps calling tools instead of answering. The **tool registry** is
read-only, so the worst outcome of a confused loop is a wasted minute
rather than a changed record.

The system prompt is where the honesty rules live, and they are not
decoration: a model that answers about this project from memory will be
fluent and wrong, and the reader has no way to tell.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_agent.gateway import AgentGateway
from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    StopReason,
)
from planbench_agent.rag import KnowledgeBase
from planbench_agent.tools import ToolPolicy, ToolRegistry, build_registry

logger = logging.getLogger("planbench.agent.workflow")

#: How many times the model may call tools before it has to answer.
#: Not decoration: without it, a model that keeps reaching for one more
#: tool runs indefinitely against live services.
MAX_TOOL_ITERATIONS = 6

CHAT_SYSTEM = """You are an analyst for a robotics planning benchmark platform \
that runs in simulation only.

Rules:
- Answer from tool results and retrieved documents. If the tools return \
nothing relevant, say so; never answer from memory about this project.
- Never claim a planner is safe, production-ready, or approved. That verdict \
belongs to a human reviewer.
- Never report a metric unless a tool returned it. Do not estimate, \
interpolate, or round beyond what you were given.
- Gates are conditions of entry, not scores. A candidate that failed one is \
eliminated, never a runner-up.
- A run that ranked nobody is a result, not a failure: its gate table says \
who was eliminated where.
- You cannot run a comparison, edit a deployment, or approve anything. Say so \
plainly if asked."""


class ChatTurn(BaseModel):
    """Result of one conversational exchange, tool calls included."""

    model_config = ConfigDict(frozen=True)

    text: str
    tools_used: tuple[str, ...] = ()
    tool_errors: tuple[str, ...] = ()
    iterations: int = 0
    truncated: bool = False


class AgentService:
    """Orchestrates the provider, the tools and the gateway."""

    def __init__(
        self,
        provider: LLMProvider,
        gateway: AgentGateway,
        knowledge: KnowledgeBase | None = None,
        policy: ToolPolicy | None = None,
    ) -> None:
        self._provider = provider
        self._gateway = gateway
        self._knowledge = knowledge
        self._registry = build_registry(gateway, knowledge, policy)

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def knowledge(self) -> KnowledgeBase | None:
        return self._knowledge

    def converse(
        self,
        message: str,
        history: Sequence[LLMMessage] = (),
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> tuple[ChatTurn, tuple[LLMMessage, ...]]:
        """Run the model with tools until it answers or the budget runs out.

        Hitting the cap is reported as ``truncated`` rather than hidden,
        and the text says nothing is asserted — a truncated loop has an
        answer shaped like a conclusion and none of the work behind it.
        """
        messages: list[LLMMessage] = [*history, LLMMessage.user(message)]
        specs = self._registry.specs()
        used: list[str] = []
        errors: list[str] = []

        for iteration in range(1, max_iterations + 1):
            response = self._provider.complete(
                LLMRequest(system=CHAT_SYSTEM, messages=tuple(messages), tools=specs)
            )
            if response.stop_reason is StopReason.REFUSAL:
                messages.append(LLMMessage.assistant(response.text))
                return (
                    ChatTurn(
                        text=response.text or "The model declined to answer.",
                        tools_used=tuple(used),
                        tool_errors=tuple(errors),
                        iterations=iteration,
                    ),
                    tuple(messages),
                )
            # Carry the provider's own payload forward, not just the parts
            # this layer parsed. Some vendors sign their tool calls and
            # reject the follow-up turn if the signature is missing — see
            # ProviderTurn.
            messages.append(
                LLMMessage.assistant(
                    response.text, response.tool_calls, provider_turn=response.provider_turn
                )
            )
            if not response.wants_tools:
                return (
                    ChatTurn(
                        text=response.text,
                        tools_used=tuple(used),
                        tool_errors=tuple(errors),
                        iterations=iteration,
                    ),
                    tuple(messages),
                )
            results = []
            for call in response.tool_calls:
                result = self._registry.execute(call)
                used.append(call.name)
                if result.is_error:
                    errors.append(f"{call.name}: {result.content}")
                results.append(result)
            messages.append(LLMMessage.results(results))

        return (
            ChatTurn(
                text=(
                    "Stopped after the tool-call budget was exhausted without a final "
                    "answer. Nothing is asserted."
                ),
                tools_used=tuple(used),
                tool_errors=tuple(errors),
                iterations=max_iterations,
                truncated=True,
            ),
            tuple(messages),
        )


__all__ = [
    "CHAT_SYSTEM",
    "MAX_TOOL_ITERATIONS",
    "AgentService",
    "ChatTurn",
]
