"""A rule-based responder that stands in for a language model.

Why this exists: the project must be testable and demonstrable with no
API key, and every guarantee around the model — schema validation, the
approval gate, citation checking — has to be exercised for real rather
than mocked away. So the mock is not a stub returning canned strings; it
walks the same paths a real provider would, using keyword rules instead
of language understanding.

What it is not: an LLM. It cannot paraphrase, infer intent, or handle a
sentence whose vocabulary it does not recognise. When it cannot parse a
mission it says so, and the surrounding code refuses — which is exactly
what should happen when a model returns something unusable.

Everything here is a pure function of the request: the same request
always yields the same response, so an agent transcript recorded against
this provider replays byte-for-byte.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from planbench_agent.provider import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    MessageRole,
    StopReason,
    ToolCall,
)

_CRITIQUE_KEYS = {"summary", "findings", "ranked_rule_codes"}
_ID = re.compile(r"\b[0-9a-f]{8,32}\b")

MODEL_NAME = "deterministic-mock"


class DeterministicResponder:
    """Callable responder used as :class:`MockProvider`'s default."""

    def __call__(self, request: LLMRequest) -> LLMResponse:
        if request.output_schema is not None:
            return self._structured(request)
        if request.tools:
            return self._tool_turn(request)
        return _text(_last_user_text(request.messages) or "no input")

    # -- structured output ---------------------------------------------

    def _structured(self, request: LLMRequest) -> LLMResponse:
        """The only schema this responder fills is the critique one.

        It answers with *no findings*, and that is the honest answer: an
        offline keyword matcher has no judgement to add beyond what the
        deterministic rules already found. Inventing an objection here
        would put noise in the one place the system is trying to keep
        clean, and a reader could not tell it apart from a model's.
        """
        schema = request.output_schema or {}
        properties = set((schema.get("properties") or {}).keys())
        if not properties >= _CRITIQUE_KEYS:
            return _text(
                "This deterministic provider does not fill that schema.",
                stop_reason=StopReason.REFUSAL,
            )
        return LLMResponse(
            structured={"summary": "", "findings": [], "ranked_rule_codes": []},
            text="",
            model=MODEL_NAME,
        )

    def _tool_turn(self, request: LLMRequest) -> LLMResponse:
        available = {tool.name for tool in request.tools}
        already = _called_tools(request.messages)
        text = _last_user_text(request.messages) or _first_user_text(request.messages)

        for name, arguments in _plan(text, _first_user_text(request.messages)):
            if name in available and name not in already:
                return LLMResponse(
                    tool_calls=(
                        ToolCall(id=f"call_{len(already) + 1}", name=name, arguments=arguments),
                    ),
                    stop_reason=StopReason.TOOL_USE,
                    model=MODEL_NAME,
                )
        return _text(_summarise(request.messages))


def _plan(text: str, first: str) -> list[tuple[str, dict[str, Any]]]:
    """Which read-only tools the request plausibly needs, in order.

    Keyword matching, deliberately shallow. Its job is to make the
    offline path *do* something recognisable — retrieve the run the
    question is about, then the documentation — not to imitate
    judgement. Every tool it can reach only reads.
    """
    lowered = f"{first}\n{text}".lower()
    plan: list[tuple[str, dict[str, Any]]] = []
    identifiers = _ID.findall(lowered)

    if identifiers:
        run_id = identifiers[0]
        plan.append(("get_decision_run", {"run_id": run_id}))
        plan.append(("get_gate_table", {"run_id": run_id}))
        if any(word in lowered for word in ("recommend", "winner", "card", "choose", "chose")):
            plan.append(("get_decision_card", {"run_id": run_id}))
        if any(word in lowered for word in ("wrong", "doubt", "object", "critique", "trust")):
            plan.append(("get_critique", {"run_id": run_id}))
    if any(word in lowered for word in ("run", "comparison", "compare", "decision")):
        plan.append(("list_decision_runs", {}))
    if any(word in lowered for word in ("deployment", "profile", "world", "robot")):
        plan.append(("list_deployments", {}))
    if any(word in lowered for word in ("candidate", "stack", "planner", "algorithm")):
        plan.append(("list_candidates", {}))
    if "scenario" in lowered:
        plan.append(("list_scenarios", {}))
    plan.append(("search_knowledge", {"query": first or text}))
    return plan


def _summarise(messages: Sequence[LLMMessage]) -> str:
    results = [result for message in messages for result in message.tool_results]
    if not results:
        return (
            "No tool returned data for this request. Nothing is asserted, because "
            "there is no recorded evidence to assert it from."
        )
    lines = ["Recorded data retrieved for this request:"]
    for result in results:
        marker = "error" if result.is_error else "ok"
        lines.append(f"- {result.name} ({marker}): {_clip(result.content)}")
    lines.append(
        "These are raw stored values. Any conclusion drawn from them is for a "
        "human reviewer to make."
    )
    return "\n".join(lines)


def _clip(text: str, limit: int = 400) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _called_tools(messages: Sequence[LLMMessage]) -> set[str]:
    return {result.name for message in messages for result in message.tool_results}


def _last_user_text(messages: Sequence[LLMMessage]) -> str:
    for message in reversed(messages):
        if message.role is MessageRole.USER and message.text:
            return message.text
    return ""


def _first_user_text(messages: Sequence[LLMMessage]) -> str:
    for message in messages:
        if message.role is MessageRole.USER and message.text:
            return message.text
    return ""


def _text(body: str, stop_reason: StopReason = StopReason.END_TURN) -> LLMResponse:
    return LLMResponse(text=body, stop_reason=stop_reason, model=MODEL_NAME)


def scripted_tool_call(name: str, arguments: Mapping[str, Any], call_id: str = "call_1"):
    """Helper for tests that need one specific tool call."""
    return LLMResponse(
        tool_calls=(ToolCall(id=call_id, name=name, arguments=dict(arguments)),),
        stop_reason=StopReason.TOOL_USE,
        model=MODEL_NAME,
    )


__all__ = ["MODEL_NAME", "DeterministicResponder", "scripted_tool_call"]
