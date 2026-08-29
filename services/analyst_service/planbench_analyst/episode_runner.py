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
    catalog_text,
    propose,
)
from planbench_analyst.episode_guard import (
    CONTRAST,
    DIAGNOSIS,
    EpisodeRoundResult,
    episode_guard,
)
from planbench_analyst.episode_prompts import (
    CONTRAST_CITATION_RULE,
    EPISODE_SYSTEM,
    build_episode_user_turn,
    episode_prompt_checksum,
    episode_schema,
)
from planbench_analyst.episode_view import EpisodeView, run_context_block
from planbench_analyst.features import RoundFeatures
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
        system=EPISODE_SYSTEM + (CONTRAST_CITATION_RULE if flags.contrast_citation_rule else ""),
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
    return replace(result, cost=report.cost)


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
