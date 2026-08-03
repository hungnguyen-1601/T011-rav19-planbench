"""Agentic AI endpoints (M8).

Every route is authenticated and runs the agent *as the calling user*,
so an agent-created benchmark is attributed to a real person and cannot
be approved by that same person (separation of duties, spec section 21).

What these endpoints deliberately do not offer: approving a benchmark,
accepting a result, editing a map or scenario, or any form of robot
control. Those are human actions and live on their own routers.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from planbench_agent import (
    AgentService,
    AgentSession,
    ApprovalRequired,
    BenchmarkSummary,
    ChatTurn,
    GatewayError,
    GeneratedReport,
    MissionDraft,
    MissionRefusal,
)
from planbench_agent.evidence import EvidenceBundle
from planbench_agent.factory import provider_status
from planbench_agent.report import FabricatedCitation
from planbench_agent.tools import FORBIDDEN_CAPABILITIES
from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_agent_service
from planbench_api.errors import DomainValidationError, InvalidStateError, NotFoundError

router = APIRouter(prefix="/agent", tags=["agent"])

Agent = Annotated[AgentService, Depends(get_agent_service)]


class ProviderInfo(BaseModel):
    """Readiness of one configurable provider."""

    name: str
    ready: bool
    api_key_env: str
    missing: str = ""


class CapabilitiesResponse(BaseModel):
    provider: str
    model: str
    deterministic: bool
    tools: tuple[str, ...]
    forbidden: tuple[str, ...]
    knowledge_documents: int
    providers: tuple[ProviderInfo, ...] = ()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    provider: str
    model: str
    deterministic: bool
    turn: ChatTurn


class MissionRequest(BaseModel):
    mission: str = Field(min_length=1, max_length=4000)
    #: Create and submit the benchmark when the draft validates. Even
    #: with this on, execution still waits for a human approval.
    submit: bool = False


class MissionResponse(BaseModel):
    session: AgentSession
    draft: MissionDraft | None = None
    refusal: MissionRefusal | None = None
    benchmark: BenchmarkSummary | None = None
    next_step: str


class ReportRequest(BaseModel):
    question: str = ""


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(agent: Agent, _: ActiveUser) -> CapabilitiesResponse:
    """What this agent can and cannot do, including the provider in use.

    Surfacing ``deterministic`` matters: an answer from the fallback
    provider is keyword-matched, not model-generated, and a reader
    should not have to guess which one produced a report.

    ``providers`` lists every configurable backend with what is still
    missing, so "why is it still on the mock?" is answerable without
    reading server logs.
    """
    knowledge = agent.knowledge
    return CapabilitiesResponse(
        provider=agent.provider.name,
        model=agent.provider.model,
        deterministic=agent.provider.deterministic,
        tools=agent.registry.names(),
        forbidden=tuple(sorted(FORBIDDEN_CAPABILITIES)),
        knowledge_documents=len(knowledge.document_ids) if knowledge is not None else 0,
        providers=tuple(
            ProviderInfo(
                name=status.name,
                ready=status.ready,
                api_key_env=status.api_key_env,
                missing=status.missing,
            )
            for status in provider_status()
        ),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, agent: Agent, _: ActiveUser) -> ChatResponse:
    """One conversational turn with read/write tools available."""
    turn, _messages = agent.converse(payload.message)
    return ChatResponse(
        provider=agent.provider.name,
        model=agent.provider.model,
        deterministic=agent.provider.deterministic,
        turn=turn,
    )


@router.post("/missions", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission(payload: MissionRequest, agent: Agent, user: ActiveUser) -> MissionResponse:
    """Parse a mission into a validated spec; optionally submit it.

    A refusal is a 201 with ``refusal`` populated, not an error: "I could
    not turn that into a benchmark, here is why" is a successful
    outcome of asking.
    """
    session = agent.new_session(uuid.uuid4().hex[:12])
    agent.parse_mission(session, payload.mission)

    if session.draft is None:
        return MissionResponse(
            session=session,
            refusal=session.refusal,
            next_step="Rephrase the mission naming a library scenario and stacks to compare.",
        )

    benchmark: BenchmarkSummary | None = None
    next_step = "Draft validated. POST it with submit=true, or create the benchmark yourself."
    if payload.submit:
        try:
            benchmark = agent.submit_for_approval(session)
        except (GatewayError, ValueError) as exc:
            raise DomainValidationError(str(exc)) from exc
        next_step = (
            f"Benchmark {benchmark.id} is ready. Run it yourself, or send it to "
            f"another member for a spec review first."
        )
    return MissionResponse(
        session=session, draft=session.draft, benchmark=benchmark, next_step=next_step
    )


@router.post("/benchmarks/{benchmark_id}/run", response_model=BenchmarkSummary)
def run_benchmark(benchmark_id: str, agent: Agent, _: ActiveUser) -> BenchmarkSummary:
    """Run an already-approved benchmark. 409 in any other state."""
    session = agent.new_session(uuid.uuid4().hex[:12])
    try:
        return agent.run_approved(session, benchmark_id)
    except ApprovalRequired as exc:
        raise InvalidStateError(str(exc)) from exc
    except GatewayError as exc:
        raise NotFoundError("benchmark", benchmark_id) from exc


@router.get("/benchmarks/{benchmark_id}/evidence", response_model=EvidenceBundle)
def evidence(
    benchmark_id: str,
    agent: Agent,
    _: ActiveUser,
    question: str = Query(default=""),
) -> EvidenceBundle:
    """The citable facts behind any answer about this benchmark.

    Exposed on its own so a reviewer can audit the inputs to a report
    without reading the report.
    """
    try:
        return agent.collect_evidence(benchmark_id, question)
    except GatewayError as exc:
        raise NotFoundError("benchmark", benchmark_id) from exc


@router.post("/benchmarks/{benchmark_id}/report", response_model=GeneratedReport)
def report(
    benchmark_id: str, payload: ReportRequest, agent: Agent, _: ActiveUser
) -> GeneratedReport:
    """Generate a cited report. Unverifiable output is refused, not returned."""
    session = agent.new_session(uuid.uuid4().hex[:12])
    try:
        return agent.write_report(session, benchmark_id, payload.question)
    except GatewayError as exc:
        raise NotFoundError("benchmark", benchmark_id) from exc
    except FabricatedCitation as exc:
        raise DomainValidationError(
            "the generated report cited evidence that does not exist and was discarded",
            list(exc.unknown),
        ) from exc


__all__ = ["router"]
