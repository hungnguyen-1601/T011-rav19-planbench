"""The menu one round is actually shown, and who chooses from it — W3.

Two changes live here and they are **independent on purpose**, because
they answer different questions and bundling them would leave neither
answered:

``filter_tool_menu``
    Hide the cards this run could not serve anyway. A tool whose
    required evidence is absent will be refused at admission, and a
    refusal reads to a model as the platform being broken — so it spends
    the next turn working around a wall that was never there. Filtering
    is a **presentation** change: the same request would have failed
    either way.

``auto_route_checker``
    After the model has declared a hypothesis and the host has admitted
    it, the platform picks the checker deterministically instead of
    paying a model call for the choice. This is a **semantic** change,
    and the one thing in W3 that moves a metric's meaning:
    ``checker_selection`` stops being "did the model pick the right
    check" and becomes "did the code". The report separates the two, and
    the preregistration is re-read against that split rather than
    quietly reused.

Three constraints the plan is explicit about, each written down because
the obvious implementation breaks one:

**``menu_recall`` is measured before filtering is trusted.** If the
filter removes a tool the case actually needed, every downstream number
is measuring the filter. Recall is over the *acceptable* tools for a
case, and it has to be 1.0 before any experiment reads a filtered arm.

**``unknown`` falls back to the evidence-capable menu.** A round that
cannot name a mechanism is exactly the round that needs to go and look,
so filtering by mechanism must not leave it with nothing.

**Auto-routing happens after declare and admission, never before.** The
host binds evidence to the hypothesis it was gathered for; a request
that arrives first is refused as ``unknown_hypothesis``, and the refusal
would read as the platform being broken rather than as a router running
too early.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from planbench_explanation.case_packet import CasePacket
from planbench_explanation.ledger import HypothesisProposal
from planbench_explanation.tools import ToolCard, ToolCatalog

__all__ = [
    "ROUTING_FAILURES",
    "RouteRequest",
    "effective_menu",
    "menu_recall",
    "route_for",
]

#: The four ways a round can fail to get a check run, counted apart
#: because they call for different fixes: a menu that hid the tool, a run
#: that never recorded the evidence, an analyst that could not name the
#: arguments, and a repeat of a question already answered.
ROUTING_FAILURES: tuple[str, ...] = (
    "tool_not_in_menu",
    "missing_required_evidence",
    "missing_required_argument",
    "repeat_after_verdict",
)


@dataclass(frozen=True)
class RouteRequest:
    """A check the platform chose, and the arguments it could fill."""

    tool_id: str
    tool_version: str
    arguments: dict[str, object]
    hypothesis_id: str
    #: Recorded so a report can separate a code-routed call from a
    #: model-chosen one. Without it, ``checker_selection`` would silently
    #: change meaning the day auto-routing was switched on.
    chosen_by: str = "code_route"


def effective_menu(
    catalog: ToolCatalog,
    *,
    available_evidence: frozenset[str],
    mechanisms: Sequence[str] = (),
    already_called: Sequence[tuple[str, tuple[tuple[str, str], ...]]] = (),
) -> ToolCatalog:
    """The cards this round may usefully ask for.

    Filters on two things only: evidence this run holds, and — when
    mechanisms are named — the propositions those cards could support.
    Fact queries and evidence navigation always survive the mechanism
    filter: they are how an analyst finds out *which* mechanism, so
    filtering them by the mechanism it has not chosen yet is circular.

    ``already_called`` is a courtesy rather than a rule; the runner still
    refuses a repeat. A card is dropped only when every one of its
    argument shapes has already been answered, which is why the entry is
    a pair of tool id and arguments rather than a bare id.
    """
    wanted = {item for item in mechanisms if item and item != "unknown"}
    unknown_in_play = not wanted or any(item == "unknown" for item in mechanisms)
    exhausted = {tool for tool, _arguments in already_called}

    kept: list[ToolCard] = []
    for card in catalog.cards:
        if not set(card.required_evidence) <= set(available_evidence):
            continue
        if card.tool_class == "mechanism_check" and wanted and not unknown_in_play:
            supported = set(card.proposition_policy.supported_proposition_types)
            if not supported & wanted:
                continue
        if card.tool_class == "research_proposal" and card.tool_id in exhausted:
            continue
        kept.append(card)
    return ToolCatalog(catalog_version=catalog.catalog_version, cards=tuple(kept))


def menu_recall(
    filtered: ToolCatalog,
    *,
    acceptable_tools: Sequence[str],
) -> float:
    """Share of the tools a case could legitimately need that survived.

    Measured **before** any experiment reads a filtered arm. A filter
    that removed the tool the case needed would make every downstream
    number a measurement of the filter, and the failure is invisible
    afterwards: the round simply never asks.

    A case with no acceptable tools recorded returns 1.0 — there was
    nothing to lose — rather than dividing by zero and reporting a
    failure nobody could act on.
    """
    wanted = [item for item in acceptable_tools if item]
    if not wanted:
        return 1.0
    offered = {card.tool_id for card in filtered.cards}
    return sum(1 for item in wanted if item in offered) / len(wanted)


def route_for(
    proposal: HypothesisProposal,
    *,
    catalog: ToolCatalog,
    packet: CasePacket,
    available_evidence: frozenset[str],
    answered: Sequence[tuple[str, tuple[tuple[str, str], ...]]] = (),
) -> tuple[RouteRequest | None, str]:
    """The check this hypothesis needs, filled from the packet, or a reason.

    Returns the request and the empty string, or ``None`` and one of
    :data:`ROUTING_FAILURES`. The reason is the point: "no check was
    run" is four different facts, and a router that returned only
    ``None`` would collapse a menu bug, a missing recording, an
    unfillable argument and a repeat into one number.

    Only arguments whose card names a **packet** source are filled. An
    ``analyst`` argument — a budget multiplier, a window width — is left
    to the model: filling it with a default would be the platform
    choosing the experiment and then grading the answer.
    """
    mechanism = proposal.proposition_type
    candidates = [
        card
        for card in catalog.cards
        if card.tool_class == "mechanism_check"
        and mechanism in card.proposition_policy.supported_proposition_types
    ]
    if not candidates:
        return None, "tool_not_in_menu"

    servable = [
        card for card in candidates if set(card.required_evidence) <= set(available_evidence)
    ]
    if not servable:
        return None, "missing_required_evidence"

    already = {(tool, arguments) for tool, arguments in answered}
    for card in servable:
        arguments = _fill(card, proposal, packet)
        if arguments is None:
            continue
        key = (card.tool_id, tuple(sorted((name, str(value)) for name, value in arguments.items())))
        if key in already:
            continue
        return (
            RouteRequest(
                tool_id=card.tool_id,
                tool_version=card.tool_version,
                arguments=arguments,
                hypothesis_id=proposal.hypothesis_id,
            ),
            "",
        )

    # Every servable card was either unfillable or already answered. The
    # two are told apart by asking again whether any could be filled at
    # all — a repeat is a round that should stop, an unfillable argument
    # is a packet that never carried it.
    fillable = any(_fill(card, proposal, packet) is not None for card in servable)
    return None, "repeat_after_verdict" if fillable else "missing_required_argument"


def _fill(
    card: ToolCard, proposal: HypothesisProposal, packet: CasePacket
) -> dict[str, object] | None:
    """Arguments this card needs and the packet can supply, or ``None``.

    ``None`` when a required argument has no packet source or the packet
    does not carry it. Not a partial dictionary: a call missing an
    argument is refused at admission, and one filled with a plausible
    value is worse — it answers about the wrong thing and is stamped
    ``recorded`` like any other result.
    """
    arguments: dict[str, object] = {}
    for spec in card.io.arguments:
        value = _value_for(spec.source, proposal, packet)
        if value is None:
            if spec.required:
                return None
            continue
        arguments[spec.name] = value
    return arguments


def _value_for(source: str, proposal: HypothesisProposal, packet: CasePacket) -> object | None:
    if source == "packet_candidate":
        return _candidate_of(proposal, packet)
    if source == "packet_episode":
        for observation in packet.observations:
            if observation.worst_episode_context_id is not None:
                return observation.worst_episode_context_id
        return None
    if source == "packet_region":
        # The packet carries one measured route and no region names. The
        # host resolves that route under a known id; anything else would
        # be a name invented to make the call go through.
        return "route" if packet.task.route is not None else None
    if source == "packet_pair":
        return None if len(packet.candidates) < 2 else packet.candidates[0].candidate_id
    return None


def _candidate_of(proposal: HypothesisProposal, packet: CasePacket) -> str | None:
    """Which candidate this hypothesis is about, read from its own refs.

    The refs name a candidate in the packet or they do not; guessing the
    first one would send a checker at the other stack in a comparison
    where exactly one of them failed.
    """
    known = [candidate.candidate_id for candidate in packet.candidates]
    for reference in proposal.supports + proposal.contradicts:
        for candidate_id in known:
            if candidate_id in reference.ref:
                return candidate_id
    for observation in packet.observations:
        if observation.candidate_id in known:
            return observation.candidate_id
    return None


def failure_counts(reasons: Mapping[str, int]) -> dict[str, int]:
    """The four routing failures, always all four, zeros included.

    A table that omitted the zeros would let a reader mistake "this never
    happened" for "nobody measured it".
    """
    return {name: int(reasons.get(name, 0)) for name in ROUTING_FAILURES}
