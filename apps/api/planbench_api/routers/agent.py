"""Agent endpoints: what the model can be asked, and what it may reach.

Two routes, both read-only, and the shortness is the design. The four
that used to sit here — parse a mission, run an approved benchmark,
collect evidence, write a report — all served a benchmark flow that was
retired in P6. Keeping them would have left the published API describing
a system that no longer exists, which is worse than an API that does
less: a caller cannot tell a stale route from a working one until it
fails.

What the agent may do now is read the decision layer and answer from it.
Running a comparison, editing a deployment and approving a result stay
where they were: with a person, on the decisions page.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from planbench_agent import AgentService, ChatTurn
from planbench_agent.factory import provider_status
from planbench_agent.tools import FORBIDDEN_CAPABILITIES
from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_agent_service

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


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(agent: Agent, _: ActiveUser) -> CapabilitiesResponse:
    """What this agent can and cannot do, including the provider in use.

    Surfacing ``deterministic`` matters: an answer from the fallback
    provider is keyword-matched, not model-generated, and a reader should
    not have to guess which one produced it.

    ``providers`` lists every configurable backend with what is still
    missing, so "why is it still on the mock?" is answerable without
    reading server logs — most often the answer is an unset model id,
    which `auto` treats as a reason to skip a provider that has a key.
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
    """One conversational turn with read-only tools available.

    Stateless on the server. The transcript belongs to the client, which
    keeps a refresh honest — there is no hidden context making the second
    answer depend on a first the reader cannot see.
    """
    turn, _messages = agent.converse(payload.message)
    return ChatResponse(
        provider=agent.provider.name,
        model=agent.provider.model,
        deterministic=agent.provider.deterministic,
        turn=turn,
    )
