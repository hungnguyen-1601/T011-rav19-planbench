"""The tool surface exposed to the model, and the policy around it.

Two rules shape this module.

**Least authority.** A tool exists only if the agent genuinely needs it.
There is no tool for driving the robot, editing a map, approving a
benchmark, or accepting a result — the omissions are the enforcement.
:data:`FORBIDDEN_CAPABILITIES` records them so a future contributor who
adds one has to delete a line that says not to.

**Explicit effect class.** Every tool declares whether it mutates state.
:class:`ToolPolicy` can disable mutating tools wholesale (read-only
sessions), and ``run_benchmark`` additionally re-checks the approval
state before it calls the gateway, so the refusal appears in the
transcript rather than as an opaque 409 from a lower layer.

Tool failures are returned to the model as error results, not raised.
A model that asked for a nonexistent benchmark should see "not found"
and correct itself; crashing the loop teaches it nothing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from planbench_agent.gateway import AgentGateway, ApprovalRequired, GatewayError
from planbench_agent.provider import ToolCall, ToolResult, ToolSpec
from planbench_agent.rag import KnowledgeBase
from planbench_agent.specs import MissionDraft, parse_structured, validate_draft

logger = logging.getLogger("planbench.agent.tools")

# Capabilities the agent must never have. Listed rather than merely
# absent so the constraint is greppable and testable (spec section 25).
FORBIDDEN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "drive_robot",  # /cmd_vel and any other actuation
        "write_map",  # maps come from the library or a human
        "write_scenario",
        "write_metrics",  # metrics are computed, never authored
        "approve_benchmark",  # human gate 1
        "accept_result",  # human gate 2
        "reject_result",
        "declare_safe",  # the safety verdict belongs to a reviewer
    }
)

# The approval state a benchmark must be in before the agent may run it.
RUNNABLE_STATE = "approved"


class Effect(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class ToolPolicy:
    """What this session's agent is permitted to do."""

    allow_write: bool = True
    #: Hard ceiling on episodes the agent may launch in one benchmark.
    #: An LLM that miscounts seeds should waste seconds, not an hour.
    max_episodes: int = 60

    def permits(self, effect: Effect) -> bool:
        return effect is Effect.READ or self.allow_write


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    effect: Effect
    handler: Callable[[Mapping[str, Any]], Any]

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, input_schema=self.input_schema
        )


class ToolRegistry:
    """Holds the tools, enforces the policy, renders results as JSON."""

    def __init__(self, tools: list[Tool], policy: ToolPolicy | None = None) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._policy = policy or ToolPolicy()

    @property
    def policy(self) -> ToolPolicy:
        return self._policy

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def available(self) -> tuple[Tool, ...]:
        """Tools the policy currently allows, in a stable order.

        Stable because the tool list is part of the prompt prefix: a
        reordering would change the prompt for no reason.
        """
        return tuple(
            tool
            for name in sorted(self._tools)
            if self._policy.permits((tool := self._tools[name]).effect)
        )

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(tool.spec() for tool in self.available())

    def execute(self, call: ToolCall) -> ToolResult:
        """Run one tool call. Every failure comes back as an error result."""
        tool = self._tools.get(call.name)
        if tool is None:
            return self._error(call, f"unknown tool {call.name!r}; available: {self.names()}")
        if not self._policy.permits(tool.effect):
            return self._error(
                call,
                f"tool {call.name!r} changes state and this session is read-only",
            )
        try:
            payload = tool.handler(call.arguments or {})
        except ApprovalRequired as exc:
            logger.info("agent tool refused: %s", exc, extra={"context": {"tool": call.name}})
            return self._error(call, f"refused: {exc}")
        except (GatewayError, ValueError, KeyError, TypeError) as exc:
            return self._error(call, f"{type(exc).__name__}: {exc}")
        return ToolResult(call_id=call.id, name=call.name, content=_render(payload))

    @staticmethod
    def _error(call: ToolCall, message: str) -> ToolResult:
        return ToolResult(call_id=call.id, name=call.name, content=message, is_error=True)


def _render(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    elif isinstance(payload, list | tuple):
        payload = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in payload
        ]
    return json.dumps(payload, sort_keys=True, default=str)


_NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def _one_id(field: str, description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {field: {"type": "string", "description": description}},
        "required": [field],
        "additionalProperties": False,
    }


def build_registry(
    gateway: AgentGateway,
    knowledge: KnowledgeBase | None = None,
    policy: ToolPolicy | None = None,
) -> ToolRegistry:
    """Assemble the tool set over a gateway (and optionally a corpus)."""
    policy = policy or ToolPolicy()
    tools: list[Tool] = [
        Tool(
            name="list_scenarios",
            description=(
                "List the built-in benchmark scenarios in curriculum order "
                "(easiest first). These are the only scenarios that exist."
            ),
            input_schema=_NO_ARGS,
            effect=Effect.READ,
            handler=lambda _: gateway.list_scenarios(),
        ),
        Tool(
            name="list_algorithms",
            description=(
                "List registered navigation stacks. Only entries with "
                "benchmarkable=true may be compared; a stack always pairs a "
                "global planner with a local planner."
            ),
            input_schema=_NO_ARGS,
            effect=Effect.READ,
            handler=lambda _: gateway.list_algorithms(),
        ),
        Tool(
            name="list_benchmarks",
            description="List benchmarks with their approval state.",
            input_schema=_NO_ARGS,
            effect=Effect.READ,
            handler=lambda _: gateway.list_benchmarks(),
        ),
        Tool(
            name="get_benchmark",
            description="Fetch one benchmark: spec, approval state, fairness checksum.",
            input_schema=_one_id("benchmark_id", "Benchmark identifier."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_benchmark(str(args["benchmark_id"])),
        ),
        Tool(
            name="get_benchmark_report",
            description=(
                "Fetch the recorded report: per-algorithm aggregates and the "
                "fairness record. Returns null when the benchmark has not run."
            ),
            input_schema=_one_id("benchmark_id", "Benchmark identifier."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_report(str(args["benchmark_id"])),
        ),
        Tool(
            name="list_episodes",
            description="List the episodes of a benchmark with outcome and artifact URI.",
            input_schema=_one_id("benchmark_id", "Benchmark identifier."),
            effect=Effect.READ,
            handler=lambda args: gateway.list_episodes(str(args["benchmark_id"])),
        ),
        Tool(
            name="analyse_episode",
            description=(
                "Run evidence-based failure analysis on one recorded episode. "
                "Returns a primary finding plus the evidence behind it."
            ),
            input_schema=_one_id("episode_id", "Episode identifier."),
            effect=Effect.READ,
            handler=lambda args: gateway.analyse_episode(str(args["episode_id"])),
        ),
        Tool(
            name="get_leaderboard",
            description=(
                "Ranked stacks grouped by identical conditions. Rows in "
                "different groups are not comparable."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "scenario_name": {"type": "string", "description": "Optional filter."}
                },
                "additionalProperties": False,
            },
            effect=Effect.READ,
            handler=lambda args: gateway.leaderboard(args.get("scenario_name") or None),
        ),
        Tool(
            name="propose_benchmark",
            description=(
                "Create a DRAFT benchmark from a scenario, a list of stacks and "
                "a list of seeds, then submit it for human approval. Drafting "
                "does not execute anything."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "scenario": {"type": "string"},
                    "algorithms": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "seeds": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                },
                "required": ["name", "scenario", "algorithms", "seeds"],
                "additionalProperties": False,
            },
            effect=Effect.WRITE,
            handler=lambda args: _propose(gateway, policy, args),
        ),
        Tool(
            name="run_benchmark",
            description=(
                "Execute a benchmark that a human reviewer has ALREADY "
                "approved. Refuses in any other state — you cannot approve a "
                "benchmark yourself."
            ),
            input_schema=_one_id("benchmark_id", "Benchmark identifier."),
            effect=Effect.WRITE,
            handler=lambda args: _run(gateway, str(args["benchmark_id"])),
        ),
    ]

    if knowledge is not None:
        tools.append(
            Tool(
                name="search_knowledge",
                description=(
                    "Search project documentation and indexed results. Each hit "
                    "carries a chunk id to cite as [document:<chunk id>]."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                effect=Effect.READ,
                handler=lambda args: _search(knowledge, args),
            )
        )
    return ToolRegistry(tools, policy)


def _search(knowledge: KnowledgeBase, args: Mapping[str, Any]) -> Any:
    hits = knowledge.search(str(args["query"]), limit=int(args.get("limit", 5)))
    if not hits:
        return "no matching documentation; do not answer from memory"
    return [
        {
            "citation_id": f"document:{hit.chunk.id}",
            "title": hit.chunk.title,
            "score": round(hit.score, 4),
            "text": hit.chunk.text,
        }
        for hit in hits
    ]


def _propose(gateway: AgentGateway, policy: ToolPolicy, args: Mapping[str, Any]) -> Any:
    draft, errors = parse_structured(
        {
            "name": args.get("name", ""),
            "description": args.get("description", ""),
            "scenario": args.get("scenario", ""),
            "algorithms": tuple(args.get("algorithms", ())),
            "seeds": tuple(args.get("seeds", ())),
        }
    )
    if draft is None:
        raise ValueError(f"invalid benchmark proposal: {'; '.join(errors)}")
    errors = validate_draft(draft)
    if errors:
        raise ValueError(f"invalid benchmark proposal: {'; '.join(errors)}")
    _check_size(draft, policy)
    created = gateway.create_benchmark(draft)
    submitted = gateway.submit_benchmark(created.id)
    return {
        "benchmark": submitted.model_dump(mode="json"),
        "next_step": (
            "A human reviewer must approve this benchmark before it can run. You cannot approve it."
        ),
    }


def _check_size(draft: MissionDraft, policy: ToolPolicy) -> None:
    if draft.episode_count > policy.max_episodes:
        raise ValueError(
            f"{draft.episode_count} episodes exceeds the per-benchmark limit of "
            f"{policy.max_episodes}; reduce the seeds or the algorithm list"
        )


def _run(gateway: AgentGateway, benchmark_id: str) -> Any:
    stored = gateway.get_benchmark(benchmark_id)
    if stored.state != RUNNABLE_STATE:
        raise ApprovalRequired(
            f"benchmark {benchmark_id!r} is in state {stored.state!r}; "
            f"it must be {RUNNABLE_STATE!r} (approved by a human reviewer) before it can run"
        )
    return gateway.run_benchmark(benchmark_id)


__all__ = [
    "FORBIDDEN_CAPABILITIES",
    "RUNNABLE_STATE",
    "Effect",
    "Tool",
    "ToolPolicy",
    "ToolRegistry",
    "build_registry",
]
