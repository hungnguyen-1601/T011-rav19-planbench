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
from planbench_agent.specs import parse_mission_text

_MISSION_KEYS = {"scenario", "algorithms", "seeds"}
_ID = re.compile(r"\b[0-9a-f]{8,32}\b")
_EVIDENCE_LINE = re.compile(r"^\[([a-z_]+:[A-Za-z0-9_.\-+#]+)\]\s*(.+)$")

MODEL_NAME = "deterministic-mock"


class DeterministicResponder:
    """Callable responder used as :class:`MockProvider`'s default."""

    def __call__(self, request: LLMRequest) -> LLMResponse:
        if request.output_schema is not None:
            return self._structured(request)
        if "INSUFFICIENT EVIDENCE" in request.system:
            return self._report(request)
        if request.tools:
            return self._tool_turn(request)
        return _text(_last_user_text(request.messages) or "no input")

    # -- structured output ---------------------------------------------

    def _structured(self, request: LLMRequest) -> LLMResponse:
        schema = request.output_schema or {}
        properties = set((schema.get("properties") or {}).keys())
        text = _last_user_text(request.messages)
        if not properties >= _MISSION_KEYS:
            # Unknown schema: refuse rather than emit something shaped
            # roughly right. A wrong object would be validated and
            # rejected downstream anyway, but slower and less clearly.
            return _text(
                "This deterministic provider only produces benchmark mission objects.",
                stop_reason=StopReason.REFUSAL,
            )
        draft = parse_mission_text(text)
        if draft is None:
            return _text(
                "Could not identify a scenario from the built-in library in that request.",
            )
        return LLMResponse(
            structured=draft.model_dump(mode="json"),
            text="",
            model=MODEL_NAME,
        )

    # -- report writing --------------------------------------------------

    def _report(self, request: LLMRequest) -> LLMResponse:
        """Compose a cited summary strictly from the evidence block.

        Citations are copied out of the prompt, so this responder cannot
        fabricate one — which also means the citation validator's
        rejection path needs a scripted provider to test, not this one.
        """
        prompt = _last_user_text(request.messages)
        evidence = _parse_evidence(prompt)
        if not evidence:
            return _text("INSUFFICIENT EVIDENCE — no evidence block was supplied.")

        question = ""
        for line in prompt.splitlines():
            if line.startswith("Question:"):
                question = line.removeprefix("Question:").strip()
                break

        lines: list[str] = []
        if question:
            lines.append(f"Question: {question}")
        lines.append(
            f"Summary of {len(evidence)} recorded evidence items, reported without interpretation:"
        )
        for citation_id, statement in evidence:
            lines.append(f"- {statement} [{citation_id}]")
        lines.append(
            "Limitations: these are simulation results only, and comparisons hold "
            "solely within one conditions_checksum."
        )
        return LLMResponse(text="\n".join(lines), model=MODEL_NAME)

    # -- tool calling ----------------------------------------------------

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

    Only read-only tools: this responder never proposes or runs a
    benchmark on its own initiative. Mutating steps are driven
    explicitly by :mod:`planbench_agent.workflow`, where the human gate
    is visible in the code path.
    """
    lowered = f"{first}\n{text}".lower()
    plan: list[tuple[str, dict[str, Any]]] = []
    identifiers = _ID.findall(lowered)

    if identifiers:
        benchmark_id = identifiers[0]
        plan.append(("get_benchmark", {"benchmark_id": benchmark_id}))
        plan.append(("get_benchmark_report", {"benchmark_id": benchmark_id}))
        if any(word in lowered for word in ("episode", "fail", "collision", "why")):
            plan.append(("list_episodes", {"benchmark_id": benchmark_id}))
    if "leaderboard" in lowered or "rank" in lowered or "best" in lowered:
        plan.append(("get_leaderboard", {}))
    if "scenario" in lowered:
        plan.append(("list_scenarios", {}))
    if "algorithm" in lowered or "stack" in lowered or "planner" in lowered:
        plan.append(("list_algorithms", {}))
    if not plan:
        plan.append(("search_knowledge", {"query": first or text}))
    else:
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


def _parse_evidence(prompt: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for line in prompt.splitlines():
        match = _EVIDENCE_LINE.match(line.strip())
        if match:
            found.append((match.group(1), match.group(2).strip()))
    return found


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
