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
from pydantic import BaseModel, ConfigDict, Field

from planbench_agent import AgentService, ChatTurn
from planbench_agent.factory import provider_status
from planbench_agent.gateway import GatewayError
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
    providers: tuple[ProviderInfo, ...] = ()


class ChatContext(BaseModel):
    """The record the reader had open when they asked.

    **Identifiers only, never prose.** The caller says *which* record is
    on screen; the server looks it up itself. A context that carried a
    description would be text from the page arriving in the position
    where instructions live, and a deployment can be named anything its
    owner types.

    Resolution goes through the same gateway the tools use, so a run the
    caller may not read is a context they cannot attach either.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default="", max_length=64)
    task_profile_id: str = Field(default="", max_length=120)
    #: Which episode of that run is on screen, when one is. An
    #: identifier like the two above: the server checks the run
    #: actually ran it, and a reader who has chosen none sends none —
    #: the replay opens on the first episode so its canvases are not
    #: blank, and answering about that one would be answering a
    #: question nobody asked.
    episode_context_id: str = Field(default="", max_length=64)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    #: What the reader is looking at. Optional: the ``/agent`` page is
    #: attached to no record and sends none.
    context: ChatContext | None = None


class ChatResponse(BaseModel):
    provider: str
    model: str
    deterministic: bool
    turn: ChatTurn
    #: Whether the record the caller said was on screen resolved and was
    #: passed on. False when none was sent, and when one was sent and did
    #: not resolve — the dock says so rather than leaving the reader to
    #: assume their question was attached to the page.
    context_used: bool = False


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
    return CapabilitiesResponse(
        provider=agent.provider.name,
        model=agent.provider.model,
        deterministic=agent.provider.deterministic,
        tools=agent.registry.names(),
        forbidden=tuple(sorted(FORBIDDEN_CAPABILITIES)),
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


def _resolve_context(agent: AgentService, context: ChatContext | None) -> str:
    """The ids the reader has on screen, once the platform has confirmed them.

    Confirming matters twice over. It keeps the model from being told a
    record exists when it does not — an id the caller made up would
    otherwise reach the turn as fact. And because the lookup runs through
    the caller's own gateway, a run they may not read cannot be attached
    to their question either.

    What comes back is **identity, not content**: the model still calls
    the tools. Pasting the run in here would answer from a snapshot this
    endpoint chose, while the honesty rules in the system prompt are
    written against tool results.
    """
    if context is None:
        return ""
    known: list[str] = []
    report: dict[str, object] = {}
    if context.run_id:
        try:
            report = agent.gateway.get_decision_run(context.run_id)
        except GatewayError:
            pass
        else:
            # The id comes from the caller, not from the record: this
            # gateway hands back the stored *report*, which is keyed by
            # what the run measured rather than by the run. The lookup
            # returning at all is what makes the id worth repeating.
            known.append(f"decision run {context.run_id}")
            profile = (report.get("identity") or {}).get("task_profile_id")
            if not context.task_profile_id and profile:
                context = context.model_copy(update={"task_profile_id": str(profile)})
    if context.task_profile_id:
        try:
            agent.gateway.get_deployment(context.task_profile_id)
        except GatewayError:
            pass
        else:
            known.append(f"deployment {context.task_profile_id}")
    if context.episode_context_id:
        # Checked against this run's own sample rather than taken on
        # trust: an episode id the run never ran would put the model in
        # front of a record that does not exist, and it would talk about
        # it — which is the failure the whole context mechanism was
        # built to avoid.
        episodes = ((report or {}).get("sample") or {}).get("episode_context_ids") or ()
        if context.episode_context_id in episodes:
            known.insert(0, f"episode {context.episode_context_id}")
    if not known:
        return ""
    return (
        "The reader is looking at " + " of ".join(known) + " in the app. "
        "Read that record with the tools before anything else, and answer about "
        "it unless the question names a different one. These identifiers were "
        "resolved by the platform; the words below are the reader's."
    )


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, agent: Agent, _: ActiveUser) -> ChatResponse:
    """One conversational turn with read-only tools available.

    Stateless on the server. The transcript belongs to the client, which
    keeps a refresh honest — there is no hidden context making the second
    answer depend on a first the reader cannot see.

    ``context`` is the one thing the client may add, and it is held to
    the same standard: identifiers the platform re-checks, shown in the
    dock so the reader can see what their question was attached to. An
    unresolvable one is dropped rather than passed on, because a model
    told about a run that does not exist will talk about it.
    """
    preamble = _resolve_context(agent, payload.context)
    turn, _messages = agent.converse(payload.message, preamble=preamble)
    return ChatResponse(
        provider=agent.provider.name,
        model=agent.provider.model,
        deterministic=agent.provider.deterministic,
        turn=turn,
        context_used=bool(preamble),
    )
