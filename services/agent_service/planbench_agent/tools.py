"""The tool surface exposed to the model, and the policy around it.

Two rules shape this module.

**Least authority.** A tool exists only if the agent genuinely needs it.
There is no tool for driving the robot, editing a map, approving a run,
or accepting a result — the omissions are the enforcement.
:data:`FORBIDDEN_CAPABILITIES` records them so a future contributor who
adds one has to delete a line that says not to.

**Read-only, by having nothing else.** Every tool here reads. The
previous version could draft and submit benchmarks, which mattered when
a benchmark had a page; after P6 it created records nothing could
display, so the model was spending turns producing invisible work. What
replaced it is not a smaller version of the same idea — the agent now
reads the decision layer a person is already looking at, and argues with
it.

Tool failures are returned to the model as error results, not raised.
A model that asked for a nonexistent run should see "not found" and
correct itself; crashing the loop teaches it nothing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from planbench_agent.gateway import AgentGateway, GatewayError
from planbench_agent.provider import ToolCall, ToolResult, ToolSpec

logger = logging.getLogger("planbench.agent.tools")

# Capabilities the agent must never have. Listed rather than merely
# absent so the constraint is greppable and testable (spec section 25).
FORBIDDEN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "drive_robot",  # /cmd_vel and any other actuation
        "write_map",  # maps come from the library or a human
        "write_scenario",
        "write_metrics",  # metrics are computed, never authored
        "approve_run",  # human gate 1 (HĐ-14)
        "accept_result",  # human gate 2
        "reject_result",
        "declare_safe",  # the safety verdict belongs to a reviewer
        "run_comparison",  # launching a sweep is a person's decision
        "write_task_profile",  # a deployment is a claim about the world
    }
)


class Effect(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class ToolPolicy:
    """What this session's agent is permitted to do."""

    #: Kept even though every tool is currently READ. The class is the
    #: place a future write tool would have to declare itself, and
    #: deleting it would remove the seam that makes that declaration
    #: unavoidable.
    allow_write: bool = False

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
    policy: ToolPolicy | None = None,
) -> ToolRegistry:
    """Assemble the tool set over the gateway.

    Ordered the way a reader would work: what worlds exist, what could
    run in them, what did run, and what the rules already said about it.

    Every tool reads stored data. There is no documentation search: the
    corpus this used to carry was the team's own Markdown — design
    diaries, plans, course notes — and a document that disagrees with the
    code makes the agent confidently wrong rather than merely ignorant.
    One of those documents claimed seven stacks and a `dwa_predictive`
    that does not exist. What a run actually did is in the database, and
    that is what these tools return.
    """
    policy = policy or ToolPolicy()
    tools: list[Tool] = [
        Tool(
            name="list_deployments",
            description=(
                "List declared deployments (task profiles): the worlds the platform "
                "has been asked to measure something in. Every comparison runs "
                "inside exactly one of these."
            ),
            input_schema=_NO_ARGS,
            effect=Effect.READ,
            handler=lambda _: gateway.list_deployments(),
        ),
        Tool(
            name="get_deployment",
            description=(
                "The full deployment profile: robot, missions, constraints, "
                "hardware budget, sensor noise, replanning rule. Read this before "
                "judging whether a comparison answered the question it claims to."
            ),
            input_schema=_one_id("task_profile_id", "Deployment id from list_deployments."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_deployment(str(args["task_profile_id"])),
        ),
        Tool(
            name="list_candidates",
            description=(
                "Registered candidates: complete navigation configurations a "
                "comparison may choose between. candidate_id is a hash of the "
                "configuration, so the same id always means the same thing."
            ),
            input_schema=_NO_ARGS,
            effect=Effect.READ,
            handler=lambda _: gateway.list_candidates(),
        ),
        Tool(
            name="list_scenarios",
            description=(
                "List the built-in scenario library in curriculum order "
                "(easiest first). These are the only scenarios that exist."
            ),
            input_schema=_NO_ARGS,
            effect=Effect.READ,
            handler=lambda _: gateway.list_scenarios(),
        ),
        Tool(
            name="list_decision_runs",
            description=(
                "Comparisons that have been run. ranked=false means the run "
                "eliminated candidates without recommending one — that is a "
                "result, not a failure, and its gate table is the deliverable."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "task_profile_id": {
                        "type": "string",
                        "description": "Optional: only runs in this deployment.",
                    }
                },
                "additionalProperties": False,
            },
            effect=Effect.READ,
            handler=lambda args: gateway.list_decision_runs(
                str(args["task_profile_id"]) if args.get("task_profile_id") else None
            ),
        ),
        Tool(
            name="get_decision_run",
            description=(
                "The whole stored comparison report: sample, per-candidate gates, "
                "statistics, provenance. Cite fields from it by path, for example "
                "sample.n_episodes or candidates[0].gates.G4.status."
            ),
            input_schema=_one_id("run_id", "Run id from list_decision_runs."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_decision_run(str(args["run_id"])),
        ),
        Tool(
            name="get_decision_card",
            description=(
                "The recommendation for a run: which candidate, on what evidence, "
                "with the interval around the difference. Returns null when the "
                "run ranked nobody."
            ),
            input_schema=_one_id("run_id", "Run id."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_decision_card(str(args["run_id"])),
        ),
        Tool(
            name="get_gate_table",
            description=(
                "Per-candidate G1-G6 verdicts with the numbers behind them: who "
                "was eliminated, at which gate, after how many episodes. Gates are "
                "conditions of entry, never scores — a candidate that failed one "
                "is not a runner-up."
            ),
            input_schema=_one_id("run_id", "Run id."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_gate_table(str(args["run_id"])),
        ),
        Tool(
            name="get_critique",
            description=(
                "What the deterministic rules already object to in this run. Read "
                "it before answering so you add something rather than repeat it."
            ),
            input_schema=_one_id("run_id", "Run id."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_critique(str(args["run_id"])),
        ),
        Tool(
            name="get_outcome",
            description=(
                "Why a run ended the way it did: which metric separated the "
                "candidates, who was eliminated at a gate rather than beaten, and "
                "which algorithm traits the numbers confirm or contradict. Read "
                "this before explaining a win or a loss — your narrative starts "
                "from these grounded findings, not from memory of what A* is."
            ),
            input_schema=_one_id("run_id", "Run id."),
            effect=Effect.READ,
            handler=lambda args: gateway.get_outcome(str(args["run_id"])),
        ),
        Tool(
            name="get_episode_verdict",
            description=(
                "Which of the two stacks took one episode of a run, what happened "
                "on each side of it, and which differences between them carry "
                "evidence. Deterministic, and the only grounded answer about a "
                "single episode: read it before saying anything about one, because "
                "a decision card ranks candidates over every episode and cannot "
                "say which side any one of them went to."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Run id."},
                    "episode_context_id": {
                        "type": "string",
                        "description": "Which episode of that run.",
                    },
                },
                "required": ["run_id", "episode_context_id"],
                "additionalProperties": False,
            },
            effect=Effect.READ,
            handler=lambda args: gateway.get_episode_verdict(
                str(args["run_id"]), str(args["episode_context_id"])
            ),
        ),
        Tool(
            name="get_recommendation",
            description=(
                "Which algorithm a deployment should use, argued from its stored "
                "runs by deterministic rules: feasibility on that profile first, "
                "then the cards, then the per-mission split of ΔU. Answer 'which "
                "should I pick' from this — never from your own weighing of the "
                "evidence. evidence_tier 3 means nothing comparable was measured "
                "and the honest advice is which comparison to run. Omit "
                "task_profile_id only when a single deployment exists."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "task_profile_id": {
                        "type": "string",
                        "description": (
                            "Deployment id from list_deployments. Optional when "
                            "exactly one deployment exists."
                        ),
                    }
                },
                "additionalProperties": False,
            },
            effect=Effect.READ,
            handler=lambda args: gateway.get_recommendation(
                str(args["task_profile_id"]) if args.get("task_profile_id") else None
            ),
        ),
    ]

    return ToolRegistry(tools, policy)


__all__ = [
    "FORBIDDEN_CAPABILITIES",
    "Effect",
    "Tool",
    "ToolPolicy",
    "ToolRegistry",
    "build_registry",
]
