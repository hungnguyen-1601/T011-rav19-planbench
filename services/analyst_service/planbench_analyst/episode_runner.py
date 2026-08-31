"""Asking the model about one episode, and keeping the register it answered in.

Thin on purpose. The engine that talks to a provider, the eight rules
that read a proposal, the deduplication by content hash, the cost
accounting — all of it works the same whatever scope the round is about,
and none of it is copied here.

What this module owns is the two things that are only true at this
scope:

* the round is **refused** when the packet and the flag disagree about
  which question was asked. The two packet shapes are similar enough
  that a mismatch would otherwise run to completion and answer
  confidently about the wrong thing;
* the ``bearing`` the model declared is lifted out of the raw answer
  before the proposal is built, because
  :class:`~planbench_explanation.ledger.HypothesisProposal` forbids
  extra fields, and it is carried beside the response from there on.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from planbench_agent.provider import LLMMessage, LLMProvider, LLMRequest
from planbench_analyst.analyst import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_S,
    AnalystRefusal,
    RoundCost,
    catalog_text,
    propose,
)
from planbench_analyst.episode_guard import (
    CONTRAST,
    DIAGNOSIS,
    EpisodeAnnotation,
    EpisodeRoundResult,
    episode_guard,
)
from planbench_analyst.episode_prompts import (
    CONTRAST_CITATION_RULE,
    EPISODE_REVISION_PREFACE,
    EPISODE_SYSTEM,
    MAGNITUDE_PLACEHOLDER_RULE,
    build_episode_user_turn,
    episode_prompt_checksum,
    episode_schema,
)
from planbench_analyst.episode_view import EpisodeView, run_context_block
from planbench_analyst.features import RoundFeatures
from planbench_explanation.episode_floor import episode_floor
from planbench_explanation.protocol import AnalysisResponse
from planbench_explanation.tools import ToolCatalog


class EpisodeScopeRefusal(AnalystRefusal):
    """The packet and the arm vector disagree about the question asked."""


def check_scope(features: RoundFeatures, *, episode: bool) -> None:
    """Refuse a round whose packet is not the shape its flags declare.

    Both directions matter. An episode packet run under a run-scope
    vector would be indexed by a builder that expects aggregates it does
    not have; a run packet under an episode vector would be scored
    against a verdict nobody computed. Neither raises anywhere else —
    they produce an answer, and the answer is about the wrong thing.
    """
    if episode and not features.episode_scope:
        raise EpisodeScopeRefusal(
            "this round was given one episode and an arm vector that says the "
            "whole run; the checksum would record a system that was never run"
        )
    if not episode and features.episode_scope:
        raise EpisodeScopeRefusal(
            "this round was given the whole run and an arm vector that says one "
            "episode; there is no verdict to hold the answer against"
        )


def declared_bearings(payload: Mapping[str, Any]) -> dict[int, str]:
    """The register the model asked for, per hypothesis, by position.

    By position because the id is derived from content **after** the
    proposal is built, and the raw answer has no id in it — deliberately,
    so a model cannot dodge deduplication by renaming.
    """
    found: dict[int, str] = {}
    for index, item in enumerate(payload.get("hypotheses") or ()):
        if not isinstance(item, Mapping):
            continue
        bearing = item.get("bearing")
        if bearing in (DIAGNOSIS, CONTRAST):
            found[index] = str(bearing)
    return found


def _payload_of(answer: Any) -> Mapping[str, Any]:
    """The structured answer, however this provider chose to return it.

    Read here as well as inside the engine because the register the
    model declared is the one field the engine cannot keep: it builds a
    :class:`~planbench_explanation.ledger.HypothesisProposal`, which
    forbids extras, so ``bearing`` has to be taken off the raw answer
    before that happens.
    """
    structured = getattr(answer, "structured", None)
    if isinstance(structured, Mapping):
        return structured
    text = getattr(answer, "text", "") or ""
    try:
        loaded = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, Mapping) else {}


@dataclass(frozen=True)
class EpisodeRound:
    """What names this round, without the packet a run-scope request carries.

    ``AnalysisRequest`` cannot be used here: its ``packet`` field is a
    ``CasePacket`` and this round is about an episode. Rather than widen
    that contract - which would bump the explanation schema and rebuild
    every fixture in the repository to admit a shape only this scope
    uses - the engine asks for the three things it actually reads, and
    both kinds of round satisfy that.
    """

    analysis_run_id: str
    analyst_bundle_id: str
    catalog: ToolCatalog


def run_episode_round(
    analysis: EpisodeRound,
    view: EpisodeView,
    provider: LLMProvider,
    *,
    features: RoundFeatures | None = None,
    catalog: ToolCatalog | None = None,
    run_measurements: Mapping[str, object] = {},
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> EpisodeRoundResult:
    """Ask once, then apply the ten rules. One turn, no revision yet.

    The revision loop, the no-progress guard and the tool calls live in
    :mod:`planbench_analyst.runner` and are not duplicated here; wiring
    this scope through that loop is the next step and needs a host that
    serves an episode packet.
    """
    flags = features or RoundFeatures(episode_scope=True)
    check_scope(flags, episode=True)
    cards = catalog or analysis.catalog

    turn = build_episode_user_turn(
        view.serialize(),
        catalog_text(cards),
        run_context_text=(
            run_context_block(view.packet, run_measurements) if flags.run_context else ""
        ),
    )
    request = LLMRequest(
        system=(
            EPISODE_SYSTEM
            + (CONTRAST_CITATION_RULE if flags.contrast_citation_rule else "")
            + (MAGNITUDE_PLACEHOLDER_RULE if flags.magnitude_placeholders else "")
        ),
        messages=(LLMMessage.user(turn),),
        output_schema=episode_schema(discriminated_union=flags.discriminated_union),
        max_tokens=max_tokens,
    )
    answer = provider.complete(request)
    payload = _payload_of(answer)
    positions = declared_bearings(payload)

    report = propose(
        analysis,
        view,  # type: ignore[arg-type]
        _Replayed(answer, provider),
        discriminated_union=flags.discriminated_union,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        menu=cards,
    )

    # Positions to ids. The engine builds proposals in the order the
    # model wrote them and drops some along the way, so the mapping is
    # by remaining order rather than by index into the raw answer.
    bearings: dict[str, str] = {}
    kept = list(report.response.proposals)
    for position, proposal in enumerate(kept):
        bearings[proposal.hypothesis_id] = positions.get(position, DIAGNOSIS)

    result = episode_guard(
        report.response,
        view,
        catalog=cards,
        bearings=bearings,
        critic=flags.critic,
    )
    # The guard reads proposals and knows nothing about what the round
    # spent getting them. Attached here, where both are in hand.
    result = replace(result, cost=report.cost)

    if flags.reword_once and _lost_everything_to_wording(result):
        result = _reworded(
            analysis,
            view,
            provider,
            flags,
            cards,
            first=result,
            turn=turn,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
    if flags.floor_when_silent and not result.response.proposals:
        result = _floor_after_silence(analysis, view, result)
    return result


def _floor_after_silence(
    analysis: EpisodeRound, view: EpisodeView, silent: EpisodeRoundResult
) -> EpisodeRoundResult:
    """What the platform can say when nothing the model said survived.

    **Sixty per cent of hold-out rounds ended with a blank screen**, and
    every one of them for the same reason: the model wrote a number into
    a sentence and rule 2 removed the sentence. It knew what happened
    and said it in a form the platform cannot check. Meanwhile the floor
    — what fired, and a difference only where one was found — was
    computable the whole time, from the packet, for nothing.
    So the reader gets that rather than nothing.

    **It is labelled, not passed off.** The flag says the floor answered
    and the guard's own reasons stay on the result, because the one
    thing worse than a blank panel is a panel that reads as the
    analyst's when the analyst's words were all refused. Whoever renders
    this owes the reader that distinction; what this function owes them
    is not to blur it here.

    Deliberately not an abstention either: an abstention is the analyst
    deciding there was nothing worth proposing, and the analyst decided
    the opposite — loudly, several times, in sentences nobody could
    check.
    """
    answer = episode_floor(view.packet)
    if not answer.proposals:
        # Nothing fired and nothing differed. The silence was the honest
        # answer after all, and dressing it up would be inventing one.
        return silent
    response = AnalysisResponse(
        analysis_run_id=analysis.analysis_run_id,
        analyst_bundle_id=analysis.analyst_bundle_id,
        proposals=tuple(answer.proposals),
        abstained=False,
    )
    return replace(
        silent,
        response=response,
        annotations={
            proposal.hypothesis_id: EpisodeAnnotation(
                bearing=answer.bearings[proposal.hypothesis_id]
            )
            for proposal in answer.proposals
        },
        flags=(*silent.flags, ("answered_by_floor", silent.response.abstention_reason or "")),
    )


#: Rules a rewrite can satisfy, because they are about how a sentence is
#: written rather than about whether it is true.
#:
#: ``quantity_in_statement`` is the whole reason this exists: on the
#: episodes the analyst is *best* at — one side reached the goal, the
#: other did not, where a blind scoring pass marked it right 43 times
#: out of 44 — nine of its eleven silences were "every proposal was
#: refused (quantity_in_statement)". It knew the answer and wrote the
#: number instead of citing it, and the round was lost over punctuation.
#:
#: ``magnitude_not_in_packet`` joins them for the same reason one step
#: on. The placeholder is the legal way to state a figure, and this rule
#: fires when the ref inside the braces resolves to nothing — the model
#: asked the packet for a number the packet does not hold. That is a
#: citation chosen wrongly, not a claim held wrongly: the finding may be
#: exactly right and reachable by naming a ref that does resolve, or by
#: dropping the figure. A hold-out episode with a supported contrast
#: went silent on this alone.
#:
#: **Added by reasoning rather than by measurement**, unlike the two
#: above, which were counted on recorded arms before they were written.
#: What bounds the risk is that a rewrite is re-guarded like any other
#: round: a retry that cites a second ref nothing backs is refused
#: again, and the cost of being wrong is one extra call.
#:
#: ``contradicts_verdict`` is deliberately absent. A statement handing
#: the episode to the side the platform did not name is not badly
#: worded, it is wrong, and inviting a rewrite would be inviting the
#: same claim in safer words. ``claim_blocked_by_packet`` is absent for
#: the same reason: the packet has withdrawn the right to make that kind
#: of claim here, and no wording restores it.
REWORDABLE_RULES: frozenset[str] = frozenset(
    {"quantity_in_statement", "wording_above_associated", "magnitude_not_in_packet"}
)


def _lost_everything_to_wording(result: EpisodeRoundResult) -> bool:
    """Every proposal removed, and every removal one a rewrite could fix."""
    if result.response.proposals or not result.blocked:
        return False
    return all(item.rule in REWORDABLE_RULES for item in result.blocked)


def _reworded(
    analysis: EpisodeRound,
    view: EpisodeView,
    provider: LLMProvider,
    flags: RoundFeatures,
    cards: ToolCatalog,
    *,
    first: EpisodeRoundResult,
    turn: str,
    max_tokens: int,
    timeout_s: float,
) -> EpisodeRoundResult:
    """One more turn, told exactly what was removed and why.

    **One, not a loop.** A round that cannot say it in two turns is a
    round whose problem is not the wording, and a loop would spend a
    caller's money discovering that one turn at a time.

    The first answer is kept if the second is empty too: a second
    silence is still the honest answer, and it costs the reader nothing
    to be told the first reason rather than a later one.
    """
    complaints = "\n".join(
        f"- removed by rule `{item.rule}`: {item.detail}" for item in first.blocked
    )
    revision = (
        turn
        + EPISODE_REVISION_PREFACE
        + "Every hypothesis you offered was removed before it reached the reader:\n"
        + complaints
        + "\nSay the same things again without what was refused. Cite the ref for "
        "any number rather than writing the number.\n"
    )
    request = LLMRequest(
        system=(
            EPISODE_SYSTEM
            + (CONTRAST_CITATION_RULE if flags.contrast_citation_rule else "")
            + (MAGNITUDE_PLACEHOLDER_RULE if flags.magnitude_placeholders else "")
        ),
        messages=(LLMMessage.user(revision),),
        output_schema=episode_schema(discriminated_union=flags.discriminated_union),
        max_tokens=max_tokens,
    )
    answer = provider.complete(request)
    positions = declared_bearings(_payload_of(answer))
    report = propose(
        analysis,
        view,  # type: ignore[arg-type]
        _Replayed(answer, provider),
        discriminated_union=flags.discriminated_union,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        menu=cards,
    )
    bearings = {
        proposal.hypothesis_id: positions.get(position, DIAGNOSIS)
        for position, proposal in enumerate(report.response.proposals)
    }
    second = episode_guard(
        report.response,
        view,
        catalog=cards,
        bearings=bearings,
        critic=flags.critic,
    )
    # Both turns were paid for whichever answer is kept, so both are
    # counted. A retry billed as one turn is a cap on nothing.
    spent = RoundCost(
        input_tokens=first.cost.input_tokens + report.cost.input_tokens,
        output_tokens=first.cost.output_tokens + report.cost.output_tokens,
    )
    kept = second if second.response.proposals else first
    return replace(
        kept,
        cost=spent,
        blocked=(*first.blocked, *second.blocked),
        flags=(
            *kept.flags,
            ("reworded_once", "kept_second" if second.response.proposals else "kept_first"),
            # **Which turn each refusal belongs to.** `blocked` above is
            # both turns concatenated, which is right for a spend count
            # and useless for the question that matters: of the rounds
            # offered a rewrite, the ones that fell silent anyway are
            # where the wording rules are costing answers, and a merged
            # list cannot say whether the second turn repeated the first
            # mistake or made a new one. Recorded as a flag rather than
            # a new field so nothing downstream has to change to ignore
            # it.
            ("blocked_first_turn", str(len(first.blocked))),
            ("blocked_second_turn", str(len(second.blocked))),
        ),
    )


class _Replayed:
    """A provider that answers once, with an answer already in hand."""

    def __init__(self, answer: Any, inner: LLMProvider) -> None:
        self._answer = answer
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def deterministic(self) -> bool:
        return self._inner.deterministic

    def complete(self, request: LLMRequest):  # type: ignore[no-untyped-def]
        return self._answer


def episode_runtime_config(
    features: RoundFeatures,
    *,
    source_manifest_hash: str,
    catalog_version: str,
) -> dict[str, object]:
    """What identifies an episode round, as the checksum carries it.

    The episode prompt's own digest is in here, and the run scope's is
    not: a bundle graded on one and replayed on the other would
    otherwise share an identity while having been asked two different
    questions.
    """
    return {
        "scope": "episode",
        "prompt": episode_prompt_checksum(),
        "features": features.as_config,
        "source_manifest_hash": source_manifest_hash,
        "catalog_version": catalog_version,
    }
