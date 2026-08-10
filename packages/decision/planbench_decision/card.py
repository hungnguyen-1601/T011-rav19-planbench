"""Decision Card and reproducibility manifest (CONTRACTS HĐ-12, HĐ-13).

This is the convergence point. Gates decided who was eligible, objectives
scored them, the paired bootstrap decided whether the leader is actually
ahead — and all of it exists to produce one document a person can act on
and another person can rebuild.

**The card may only say what was established.** Three fields belong to
analyses that phase 3 does not run: ``pareto_label`` is
``UNCERTAIN_DOMINANCE`` (HĐ-10.1's own name for "not enough data to
conclude"), ``alternative`` is null because it may only ever be a
``PARETO_FRONTIER`` candidate, and the three stability figures in
``evidence`` are null. Null reads as *not measured*; a plausible default
would read as *measured and fine*, and nobody downstream could tell the
difference.

**The runner-up is not the alternative.** ``recommend`` returns the
second-ranked candidate because that is what the label is defined
against (HĐ-11.3). The card's ``alternative`` is a different claim — "you
could also ship this one" — and it needs the Pareto analysis to support
it. The two are deliberately not wired together.

**A recommendation must have cleared every gate.** Gates run before
scoring, so a candidate that failed one is not a worse choice, it is not
a choice. :func:`build_decision_card` refuses rather than trusting the
caller to have filtered — the whole point of G2 is that "fastest" must
never beat "did not collide".

**The manifest is the card's other half.** HĐ-13's acceptance test is
that somebody else rebuilds the same card from it. That is why the
bootstrap seed is in there (HĐ-13, added at 2.2.0): the confidence
interval is a random draw, and a manifest that cannot reproduce it fails
its own acceptance criterion.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from planbench_decision.anchors import ResolvedAnchors
from planbench_decision.candidate import ExperimentScope
from planbench_decision.gates import GateReport, assert_no_banned_language
from planbench_decision.objectives import DecisionSettings
from planbench_decision.stats import CandidateEvidence, Recommendation, RecommendationStatus
from planbench_schemas.contracts import CONTRACTS_VERSION
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.task_profile import ClaimLevel, TaskProfile

__all__ = [
    "CARD_SCHEMA_PATH",
    "MANIFEST_SCHEMA_PATH",
    "ApprovalBlock",
    "BenchmarkHost",
    "CardError",
    "DecisionCard",
    "EvidenceBlock",
    "Manifest",
    "ParetoLabel",
    "Provenance",
    "RecommendedBlock",
    "build_decision_card",
    "build_manifest",
    "resolve_git_sha",
]

#: Where the machine-checkable form of HĐ-12 and HĐ-13 lives (§16).
_CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
CARD_SCHEMA_PATH = _CONTRACTS_DIR / "schemas" / "decision_card.schema.json"
MANIFEST_SCHEMA_PATH = _CONTRACTS_DIR / "schemas" / "manifest.schema.json"

ParetoLabel = Literal["PARETO_FRONTIER", "LIKELY_DOMINATED", "UNCERTAIN_DOMINANCE"]
RecommendationScope = Literal["MISSION_LEVEL", "DEPLOYMENT_LEVEL", "ROBUST_DEPLOYMENT_LEVEL"]

#: HĐ-2.2's claim levels, in the card's vocabulary.
_SCOPE_OF_CLAIM: dict[ClaimLevel, RecommendationScope] = {
    "mission": "MISSION_LEVEL",
    "deployment": "DEPLOYMENT_LEVEL",
    "robust_deployment": "ROBUST_DEPLOYMENT_LEVEL",
}


class CardError(ValueError):
    """A card that would state something the run did not establish."""


class RecommendedBlock(BaseModel):
    """Which candidate, in the two forms a reader needs.

    ``candidate_id`` is the identity; ``stack`` is the human-readable
    label, which two candidates differing only in parameters share — that
    is exactly why it is never used as an identity (HĐ-1.3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    stack: str
    #: Where the parameters live, when they live somewhere. Null when the
    #: candidate record is the only copy: pointing at a second copy that
    #: could drift is worse than pointing at nothing.
    params_ref: str | None = None


class AlternativeBlock(BaseModel):
    """A second candidate a reader may legitimately ship instead."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    reason: str


class EvidenceBlock(BaseModel):
    """What backs the recommendation, and what has not been measured.

    The three ``None`` defaults are phase-5 analyses. They are optional
    in the schema and null here rather than absent, so a reader sees the
    question was asked and not answered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    delta_u_vs_second: float
    ci95: tuple[float, float]
    n_episodes: int = Field(ge=1)
    effect_size: float | None
    weight_stability_margin: float | None = None
    anchor_stability: str | None = None
    robustness_margin: float | None = None


class ApprovalBlock(BaseModel):
    """HĐ-14. A freshly built card is always ``PENDING``.

    Nothing in this module can set it otherwise: approval is a human act
    recorded through the approval flow, and a builder that could stamp
    ``APPROVED`` would be a path around the self-approval ban.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    by: str | None = None
    at: str | None = None
    comment: str | None = None


class BenchmarkHost(BaseModel):
    """The machine every candidate ran on (HĐ-7.4).

    Recorded because the comparison assumes one machine, one allocation,
    one thread count. Without it, even the relative ordering is a claim
    about two different computers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cpu: str = Field(min_length=1)
    cores_allocated: int = Field(ge=1)
    threads: int = Field(ge=1)


class Provenance(BaseModel):
    """Everything about the run that is not a number the engine computed.

    Passed in rather than discovered here. The decision layer is a pure
    function of its inputs (§16) — a module that shells out to ``git`` and
    reads the clock while building a card cannot be tested for
    reproducibility, which is the one property the manifest exists to
    provide. :func:`resolve_git_sha` is offered separately for the runner
    to call.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    git_sha: str = Field(min_length=7, pattern=r"^[0-9a-f]{7,40}$")
    benchmark_host: BenchmarkHost
    created_at: datetime
    docker_image_digest: str | None = None


class DecisionCard(BaseModel):
    """HĐ-12, as a validated object rather than a dict of hopes."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    contracts_version: str = CONTRACTS_VERSION
    recommendation_scope: RecommendationScope
    experiment_scope: ExperimentScope
    decision_mode: Literal["technical", "business_adjusted"]
    decision_mode_label: str = Field(min_length=1)
    status: RecommendationStatus
    recommended: RecommendedBlock
    alternative: AlternativeBlock | None
    gates: tuple[dict[str, Any], ...]
    objectives: dict[str, float]
    decision_utility: float = Field(ge=0.0, le=1.0)
    pareto_label: ParetoLabel
    evidence: EvidenceBlock
    declared_assumptions: dict[str, Any] | None
    manifest_ref: str = Field(min_length=1)
    approval: ApprovalBlock = ApprovalBlock()
    #: Populated only for NEAR_EQUIVALENT, where the declared ladder of
    #: HĐ-11.3 — not the raw utility — chose the winner. Outside HĐ-12's
    #: field list, kept off :meth:`to_json_dict` for that reason, and
    #: available to the UI, which has to explain the choice.
    tie_break_reason: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        """The card exactly as HĐ-12 writes it, ready for ``json.dump``.

        Hand-built rather than ``model_dump``: the contract's key names
        (``U_R``, ``G1``) are not Python field names, and the JSON is the
        artefact that has to match the document — the model is an
        implementation of it, not the other way round.

        Checked for banned language on the way out (§17 ban 10) for the
        same reason the gate card is: the rule has to hold on every path
        that produces text, not on the ones somebody remembered.
        """
        payload: dict[str, Any] = {
            "contracts_version": self.contracts_version,
            "recommendation_scope": self.recommendation_scope,
            "experiment_scope": self.experiment_scope,
            "decision_mode": self.decision_mode,
            "decision_mode_label": self.decision_mode_label,
            "status": self.status,
            "recommended": self.recommended.model_dump(),
            "alternative": None if self.alternative is None else self.alternative.model_dump(),
            "gates": [dict(row) for row in self.gates],
            "objectives": dict(self.objectives),
            "decision_utility": self.decision_utility,
            "pareto_label": self.pareto_label,
            "evidence": {
                "delta_u_vs_second": self.evidence.delta_u_vs_second,
                "ci95": list(self.evidence.ci95),
                "n_episodes": self.evidence.n_episodes,
                "effect_size": self.evidence.effect_size,
                "weight_stability_margin": self.evidence.weight_stability_margin,
                "anchor_stability": self.evidence.anchor_stability,
                "robustness_margin": self.evidence.robustness_margin,
            },
            "declared_assumptions": self.declared_assumptions,
            "manifest_ref": self.manifest_ref,
            "approval": self.approval.model_dump(),
        }
        assert_no_banned_language(payload, where="decision card")
        return payload


class Manifest(BaseModel):
    """HĐ-13. Enough to rebuild the card, and nothing that cannot be."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contracts_version: str = CONTRACTS_VERSION
    git_sha: str
    docker_image_digest: str | None
    task_profile_id: str
    anchor_config_version: str
    preference_profile: str
    decision_mode: str
    travel_time_accounting: str
    candidates: tuple[str, ...]
    episode_context_ids: dict[str, tuple[str, ...]]
    bootstrap: dict[str, int]
    benchmark_host: BenchmarkHost
    created_at: datetime

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "contracts_version": self.contracts_version,
            "git_sha": self.git_sha,
            "docker_image_digest": self.docker_image_digest,
            "task_profile_id": self.task_profile_id,
            "anchor_config_version": self.anchor_config_version,
            "preference_profile": self.preference_profile,
            "decision_mode": self.decision_mode,
            "travel_time_accounting": self.travel_time_accounting,
            "candidates": list(self.candidates),
            "episode_context_ids": {
                key: list(value) for key, value in self.episode_context_ids.items()
            },
            "bootstrap": dict(self.bootstrap),
            "benchmark_host": self.benchmark_host.model_dump(),
            "created_at": self.created_at.isoformat(),
        }


def build_decision_card(
    recommendation: Recommendation,
    evidence: Sequence[CandidateEvidence],
    gate_reports: Mapping[str, GateReport],
    profile: TaskProfile,
    settings: DecisionSettings,
    experiment_scope: ExperimentScope,
    manifest_ref: str,
    *,
    neighborhood_evaluated: bool = False,
) -> DecisionCard:
    """Assemble HĐ-12 from what the previous phases established.

    ``gate_reports`` covers **every** candidate that was evaluated, not
    only the survivors: HĐ-10.1 says nobody disappears from the report,
    and the most instructive row on the card is usually the fastest
    candidate being eliminated at G2.

    ``neighborhood_evaluated`` decides whether a robust-deployment claim
    is even available (HĐ-2.2). It defaults to false because that is the
    state of every run phase 3 can produce, and a claim level is not
    something to assume in the generous direction.
    """
    by_id = {item.candidate_id: item for item in evidence}
    winner = by_id.get(recommendation.recommended_id)
    if winner is None:
        raise CardError(
            f"recommended candidate {recommendation.recommended_id} has no evidence in the "
            "field being carded"
        )

    _require_gates_reported(evidence, gate_reports)
    _require_all_gates_passed(recommendation.recommended_id, gate_reports)

    comparison = recommendation.comparison
    return DecisionCard(
        recommendation_scope=_SCOPE_OF_CLAIM[
            profile.effective_claim_level(neighborhood_evaluated=neighborhood_evaluated)
        ],
        experiment_scope=experiment_scope,
        decision_mode=settings.decision_mode,
        decision_mode_label=settings.card_label,
        status=recommendation.status,
        recommended=RecommendedBlock(
            candidate_id=winner.candidate_id,
            stack=winner.candidate.stack_label,
        ),
        # HĐ-12: only ever a PARETO_FRONTIER candidate, and that label
        # does not exist until phase 5.2 runs. The statistical runner-up
        # is a different claim and is not promoted here.
        alternative=None,
        # Sorted by id rather than by rank: the gate table is the
        # eliminated candidates' row too, and a rebuild has to produce
        # the same file byte for byte (HĐ-13), which a rank-dependent
        # order would not when two candidates tie.
        gates=tuple(gate_reports[key].to_card() for key in sorted(gate_reports)),
        objectives=winner.set_objectives.to_card(),
        decision_utility=winner.set_objectives.decision_utility,
        # HĐ-10.1's own name for "not enough data to conclude". Printing
        # PARETO_FRONTIER without having run the analysis would assert
        # something unchecked.
        pareto_label="UNCERTAIN_DOMINANCE",
        evidence=EvidenceBlock(
            delta_u_vs_second=comparison.delta_median,
            ci95=comparison.ci95,
            n_episodes=comparison.n_episodes,
            effect_size=comparison.effect_size,
        ),
        declared_assumptions=None
        if settings.business_profile is None
        else settings.business_profile.model_dump(),
        manifest_ref=manifest_ref,
        tie_break_reason=recommendation.tie_break_reason,
    )


def build_manifest(
    recommendation: Recommendation,
    evidence: Sequence[CandidateEvidence],
    gate_reports: Mapping[str, GateReport],
    profile: TaskProfile,
    settings: DecisionSettings,
    anchors: ResolvedAnchors,
    provenance: Provenance,
    *,
    neighborhood_contexts: Sequence[EpisodeContext] = (),
) -> Manifest:
    """Assemble HĐ-13: everything needed to rebuild that card.

    ``candidates`` lists every candidate that was gated, not only the
    scored ones — a rebuild has to reproduce the gate table too, and a
    candidate eliminated at G2 is part of the result.

    The evaluation context ids come from the evidence rather than from a
    separate argument, so the manifest cannot claim a set the numbers
    were not computed over.
    """
    evaluation_ids = _shared_evaluation_ids(evidence)
    return Manifest(
        git_sha=provenance.git_sha,
        docker_image_digest=provenance.docker_image_digest,
        task_profile_id=profile.id,
        anchor_config_version=anchors.version,
        preference_profile=settings.preference_profile,
        decision_mode=settings.decision_mode,
        travel_time_accounting=settings.travel_time_accounting,
        candidates=tuple(sorted(gate_reports)),
        episode_context_ids={
            "evaluation": evaluation_ids,
            "neighborhood": tuple(
                sorted(context.episode_context_id for context in neighborhood_contexts)
            ),
        },
        bootstrap={
            "seed": recommendation.comparison.seed,
            "n_resamples": recommendation.comparison.n_resamples,
        },
        benchmark_host=provenance.benchmark_host,
        created_at=provenance.created_at,
    )


def resolve_git_sha(repo: Path | str | None = None) -> str:
    """Current commit, for the runner to put in :class:`Provenance`.

    Lives here so there is one answer to "which code produced this", but
    outside the builders so they stay pure. Raises rather than returning
    a placeholder: a manifest whose ``git_sha`` says ``unknown`` looks
    complete and rebuilds nothing.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo) if repo is not None else None,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CardError(
            "cannot read the current git commit, so no manifest can honestly say which code "
            f"produced this card ({exc})"
        ) from exc
    return completed.stdout.strip().lower()


def _require_gates_reported(
    evidence: Sequence[CandidateEvidence], gate_reports: Mapping[str, GateReport]
) -> None:
    missing = sorted(
        item.candidate_id for item in evidence if item.candidate_id not in gate_reports
    )
    if missing:
        raise CardError(
            f"candidate(s) {missing} were scored but have no gate report; gates run before "
            "scoring (HĐ-7), so a scored candidate with no gate row means the order was "
            "reversed somewhere"
        )


def _require_all_gates_passed(candidate_id: str, gate_reports: Mapping[str, GateReport]) -> None:
    report = gate_reports[candidate_id]
    if not report.passed:
        raise CardError(
            f"candidate {candidate_id} cannot be recommended: it failed "
            f"{list(report.blocking_gates)}. A gate is not a low score to be outweighed — a "
            "candidate that fails one is not a choice at all (HĐ-7)"
        )


def _shared_evaluation_ids(evidence: Sequence[CandidateEvidence]) -> tuple[str, ...]:
    """The one context set every scored candidate ran (HĐ-3.2).

    Re-checked here rather than assumed from the comparison: the manifest
    is what somebody else rebuilds from, and it must not record a set
    that only two of four candidates actually shared.
    """
    if not evidence:
        raise CardError("a manifest needs at least one scored candidate")
    reference = evidence[0].contexts
    for item in evidence[1:]:
        if item.contexts != reference:
            raise CardError(
                f"candidates {evidence[0].candidate_id} and {item.candidate_id} were scored "
                "over different context sets, so no single evaluation set can be recorded"
            )
    return reference
