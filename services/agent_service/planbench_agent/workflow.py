"""Agent workflow: session state, the tool loop, and the human gates.

The workflow is deliberately a small state machine rather than "let the
model decide what to do next". A benchmark platform has a mandatory
order — draft, human approval, run, analyse, report — and encoding it in
code means the order holds regardless of what the model says.

Where the model *is* in charge (choosing which read-only tools to call
while answering a question) it runs inside :meth:`AgentService.converse`,
which bounds the number of iterations and returns the full transcript.

Human gates, restated because they are the point of this module:

* the agent may draft and submit a benchmark, and it may run one that is
  already approved. It has no path to approving anything;
* after a run, results sit in PENDING_REVIEW until a human accepts them.
  Any report the agent writes before that is marked provisional.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from planbench_agent.evidence import EvidenceBundle, collect_benchmark_evidence
from planbench_agent.gateway import AgentGateway, ApprovalRequired, BenchmarkSummary
from planbench_agent.provider import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    StopReason,
)
from planbench_agent.rag import KnowledgeBase
from planbench_agent.report import GeneratedReport, generate_report
from planbench_agent.specs import (
    MissionDraft,
    MissionRefusal,
    mission_schema,
    parse_structured,
    validate_draft,
)
from planbench_agent.tools import RUNNABLE_STATE, ToolPolicy, ToolRegistry, build_registry

logger = logging.getLogger("planbench.agent.workflow")

MAX_TOOL_ITERATIONS = 6

MISSION_SYSTEM = """You translate a robotics benchmark request into a \
benchmark specification.

Rules:
- Choose a scenario ONLY from the built-in library enum. Never invent a \
scenario, a map, or an algorithm.
- Compare complete navigation stacks (global planner + local planner). Never \
compare a global planner against a local planner.
- If the request does not name seeds, pick a small deterministic list.
- If no library scenario matches the request, do not guess: return nothing \
usable and explain what is missing."""

CHAT_SYSTEM = """You are an analyst for a robotics planning benchmark platform \
that runs in simulation only.

Rules:
- Answer from tool results and retrieved documents. If the tools return \
nothing relevant, say so; never answer from memory about this project.
- Never claim a planner is safe, production-ready, or approved. That verdict \
belongs to a human reviewer.
- Never claim a benchmark ran, or report a metric, unless a tool returned it.
- You cannot drive the robot, edit maps or scenarios, or approve anything. \
Say so plainly if asked.
- Results are only comparable within one conditions_checksum."""


class AgentState(StrEnum):
    IDLE = "idle"
    MISSION_PARSED = "mission_parsed"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    REPORTED = "reported"
    REFUSED = "refused"
    FAILED = "failed"


class AgentEvent(BaseModel):
    """One auditable step. The transcript is the audit trail."""

    model_config = ConfigDict(frozen=True)

    timestamp: str
    state: AgentState
    action: str
    detail: str = ""


class AgentSession(BaseModel):
    """Mutable session state, safe to serialise and hand to the API."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    provider: str
    model: str
    deterministic: bool = False
    state: AgentState = AgentState.IDLE
    mission: str = ""
    draft: MissionDraft | None = None
    refusal: MissionRefusal | None = None
    benchmark_id: str | None = None
    report: GeneratedReport | None = None
    events: list[AgentEvent] = Field(default_factory=list)

    def record(self, state: AgentState, action: str, detail: str = "") -> AgentEvent:
        self.state = state
        event = AgentEvent(
            timestamp=datetime.now(UTC).isoformat(),
            state=state,
            action=action,
            detail=detail,
        )
        self.events.append(event)
        return event


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
        self._registry: ToolRegistry = build_registry(gateway, knowledge, policy)

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def knowledge(self) -> KnowledgeBase | None:
        return self._knowledge

    def new_session(self, session_id: str) -> AgentSession:
        return AgentSession(
            id=session_id,
            provider=self._provider.name,
            model=self._provider.model,
            deterministic=self._provider.deterministic,
        )

    # -- 1. mission -> draft ------------------------------------------

    def parse_mission(self, session: AgentSession, mission: str) -> AgentSession:
        """Ask the provider for a spec, then validate it hard.

        Two independent checks stand between a model answer and a stored
        benchmark: Pydantic parsing with ``extra="forbid"``, and a
        registry lookup for every name. Failing either is a refusal —
        the session goes to REFUSED and no benchmark is created.
        """
        session.mission = mission
        response = self._provider.complete(
            LLMRequest(
                system=MISSION_SYSTEM,
                messages=(LLMMessage.user(mission),),
                output_schema=mission_schema(),
                max_tokens=2048,
            )
        )
        if response.stop_reason is StopReason.REFUSAL:
            return self._refuse(session, "the provider declined this request", ())
        if response.structured is None:
            return self._refuse(
                session,
                "the provider did not return a benchmark specification",
                (response.text.strip(),) if response.text.strip() else (),
            )

        draft, errors = parse_structured(response.structured)
        if draft is None:
            return self._refuse(session, "the specification did not match the schema", errors)
        errors = validate_draft(draft)
        if errors:
            return self._refuse(session, "the specification is not valid for this platform", errors)

        session.draft = draft
        session.refusal = None
        session.record(
            AgentState.MISSION_PARSED,
            "parse_mission",
            f"scenario={draft.scenario} algorithms={list(draft.algorithms)} "
            f"seeds={list(draft.seeds)}",
        )
        return session

    def _refuse(self, session: AgentSession, reason: str, errors: Sequence[str]) -> AgentSession:
        session.draft = None
        session.refusal = MissionRefusal(reason=reason, errors=tuple(errors))
        session.record(AgentState.REFUSED, "refuse", f"{reason}: {'; '.join(errors)}".strip(": "))
        logger.info(
            "agent refused a mission",
            extra={"context": {"session": session.id, "reason": reason}},
        )
        return session

    # -- 2. draft -> pending human approval ----------------------------

    def submit_for_approval(self, session: AgentSession) -> BenchmarkSummary:
        """Create the benchmark and hand it to a human. Nothing executes."""
        if session.draft is None:
            raise ValueError("no validated draft in this session")
        created = self._gateway.create_benchmark(session.draft)
        submitted = self._gateway.submit_benchmark(created.id)
        session.benchmark_id = submitted.id
        session.record(
            AgentState.AWAITING_HUMAN_APPROVAL,
            "submit_for_approval",
            f"benchmark {submitted.id} is {submitted.state}; a reviewer must approve it",
        )
        return submitted

    # -- 3. run, only when a human already approved --------------------

    def run_approved(self, session: AgentSession, benchmark_id: str | None = None):
        """Execute an approved benchmark, or refuse in every other state."""
        target = benchmark_id or session.benchmark_id
        if target is None:
            raise ValueError("no benchmark associated with this session")
        stored = self._gateway.get_benchmark(target)
        if stored.state != RUNNABLE_STATE:
            session.record(
                AgentState.AWAITING_HUMAN_APPROVAL,
                "run_refused",
                f"benchmark {target} is {stored.state!r}, not {RUNNABLE_STATE!r}",
            )
            raise ApprovalRequired(
                f"benchmark {target!r} is in state {stored.state!r}; a human reviewer "
                f"must approve it before the agent may run it"
            )
        session.record(AgentState.RUNNING, "run_benchmark", f"benchmark {target}")
        finished = self._gateway.run_benchmark(target)
        session.benchmark_id = finished.id
        session.record(
            AgentState.COMPLETED,
            "run_finished",
            f"benchmark {finished.id} is {finished.state}",
        )
        return finished

    # -- 4. evidence + report ------------------------------------------

    def collect_evidence(
        self,
        benchmark_id: str,
        question: str = "",
        *,
        analyse_failures: bool = True,
        max_analyses: int = 8,
    ) -> EvidenceBundle:
        """Gather citable facts from storage. No model involved."""
        benchmark = self._gateway.get_benchmark(benchmark_id)
        report = self._gateway.get_report(benchmark_id)
        episodes = tuple(self._gateway.list_episodes(benchmark_id))
        analyses: list[tuple[str, object]] = []
        if analyse_failures:
            failed = [episode for episode in episodes if episode.status != "success"]
            for episode in failed[:max_analyses]:
                analyses.append((episode.id, self._gateway.analyse_episode(episode.id)))
        return collect_benchmark_evidence(
            benchmark,
            report,
            episodes,
            tuple(analyses),  # type: ignore[arg-type]
            question=question,
        )

    def write_report(
        self, session: AgentSession, benchmark_id: str | None = None, question: str = ""
    ) -> GeneratedReport:
        """Generate a cited report; refusals are returned, not raised."""
        target = benchmark_id or session.benchmark_id
        if target is None:
            raise ValueError("no benchmark associated with this session")
        benchmark = self._gateway.get_benchmark(target)
        question = question or f"Summarise the results of benchmark {benchmark.name!r}."
        bundle = self.collect_evidence(target, question)
        report = generate_report(self._provider, bundle, question, benchmark_state=benchmark.state)
        session.report = report
        session.record(
            AgentState.REFUSED if report.refused else AgentState.REPORTED,
            "write_report",
            report.refusal_reason
            or f"{len(report.citations)} citations over {report.evidence_count} evidence items",
        )
        return report

    # -- conversational tool loop --------------------------------------

    def converse(
        self,
        message: str,
        history: Sequence[LLMMessage] = (),
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> tuple[ChatTurn, tuple[LLMMessage, ...]]:
        """Run the model with tools until it answers or the budget runs out.

        The iteration cap is not decoration: a model that keeps calling
        tools would otherwise run indefinitely against live services.
        Hitting it is reported as ``truncated`` rather than hidden.
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
            messages.append(LLMMessage.assistant(response.text, response.tool_calls))
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
    "MISSION_SYSTEM",
    "AgentEvent",
    "AgentService",
    "AgentSession",
    "AgentState",
    "ChatTurn",
]
