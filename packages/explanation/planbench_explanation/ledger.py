"""The five ledger objects, and the powers each one deliberately lacks.

The explanation layer's central risk is not a wrong sentence — it is a
sentence that *sounds* better supported than the data behind it. The
defence is ownership, expressed in schemas rather than in validation
rules applied after the fact:

``HypothesisProposal``
    everything an analyst — human or model — is allowed to return.
    There is **no** status, confidence, level, or impact number in it.
    Not "rejected if present": absent from the schema, so a proposal
    carrying one fails to parse. Leaving a ``{delta, method}`` field in
    the analyst's object and validating the number afterwards still
    lets a model invent a number of exactly the right shape, and a
    reviewer reading the artifact cannot tell invented from computed.
``CheckerResult``
    what a tool host produced. Only the host writes these, and each one
    carries a resolvable implementation reference and an evidence
    checksum, so a result can be traced back to the build that made it.
``ImpactRef``
    a pointer to a tool-produced artifact, plus the **kind** of impact
    it describes. The two kinds are not interchangeable and the
    distinction is the difference between an honest sentence and a
    causal one — see :class:`ImpactRef`.
``InvestigationRecord``
    the orchestrator's view: which proposal, adjudicated how, with
    which results attached.
``Claim``
    what the UI may render. Produced only by the deterministic
    promotion matrix (:mod:`planbench_explanation.promotion`), never
    written by hand and never by an analyst.

``KnownUnknown`` sits alongside them. It is structured, not prose,
because the orchestrator *enforces* it: a gap that blocks a claim type
blocks it in code, rather than being a paragraph the analyst is trusted
to have read.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.levels import ClaimLevel, Qualifier, canonical_qualifiers
from planbench_explanation.propositions import (
    PropositionType,
    canonical_propositions,
    require_assertable,
)
from planbench_explanation.provenance import (
    ExecutionStatus,
    InputProvenance,
    PropositionVerdict,
)
from planbench_explanation.subjects import Subject
from planbench_explanation.versioning import CHECKSUM_PATTERN, validate_code_ref

#: What an evidence reference points at.
#:
#: ``knowledge_entry`` is the one with a shape rule: a KB citation must
#: pin an entry version (``kb:inflation_gap_closure@2``). An unversioned
#: citation would let a curated entry be edited under a claim that was
#: promoted before the edit.
EvidenceKind = Literal[
    "fact",
    "observation",
    "trace_window",
    "artifact",
    "knowledge_entry",
    "plan_attempt",
    "contrast",
]


class EvidenceRef(BaseModel):
    """One pointer into data the platform holds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str = Field(min_length=1)
    kind: EvidenceKind
    provenance: InputProvenance = "recorded"
    checksum: str | None = None

    @model_validator(mode="after")
    def _check(self) -> EvidenceRef:
        if self.kind == "knowledge_entry" and "@" not in self.ref:
            raise ValueError(
                f"knowledge entry reference {self.ref!r} does not pin a version; "
                "write kb:<entry_id>@<entry_version> so an edit to the entry "
                "cannot silently change what an already-promoted claim cited"
            )
        if self.provenance == "missing" and self.checksum is not None:
            raise ValueError("evidence that is missing cannot carry a checksum")
        return self


class KnownUnknown(BaseModel):
    """A gap in the data, and the claim types it forbids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    blocks_claim_types: tuple[PropositionType, ...]
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> KnownUnknown:
        if not self.blocks_claim_types:
            raise ValueError(
                f"known unknown {self.id!r} blocks nothing; a gap that blocks no "
                "claim type is a note, and notes do not belong in the packet's "
                "enforced section"
            )
        canonical_propositions(self.blocks_claim_types, field="blocks_claim_types")
        return self


class RequestedCheck(BaseModel):
    """A tool the analyst asks the host to run. A request, not a result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class HypothesisProposal(BaseModel):
    """Everything the analyst may return, and nothing else.

    ``extra="forbid"`` is load-bearing here, not hygiene: it is what
    turns "the analyst must not report a confidence" from a policy into
    a parse error.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    hypothesis_statement: str = Field(min_length=1)
    proposition_type: PropositionType
    proposed_subject: Subject
    supports: tuple[EvidenceRef, ...] = ()
    contradicts: tuple[EvidenceRef, ...] = ()
    #: Evidence the analyst says is needed and absent. Structured
    #: incompleteness beats a confident story built around a hole.
    missing_evidence: tuple[str, ...] = ()
    requested_checks: tuple[RequestedCheck, ...] = ()
    #: Prose only, and always routed to the research lane for human
    #: approval. No tool executes an experiment.
    recommended_experiments: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> HypothesisProposal:
        require_assertable(self.proposition_type, field="proposition_type")
        return self


class PropositionOutcome(BaseModel):
    """One proposition a tool result speaks to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposition_id: str = Field(min_length=1)
    proposition_type: PropositionType
    result: PropositionVerdict


class CheckerResult(BaseModel):
    """A tool host's answer — the ledger's copy of a ToolResult.

    Three rules the schema enforces, each from a way the single word
    ``pass`` used to hide a distinction:

    1. ``execution_status`` says how the run went; ``proposition_verdict``
       says whether the proposition stood. A completed run that refutes
       the hypothesis is a success and a dead claim.
    2. A top-level ``proposition_verdict`` is only meaningful for a tool
       speaking to exactly one proposition. Multi-proposition results
       omit it and carry a verdict per entry.
    3. A run that did not complete carries no verdict at all. Otherwise
       ``not_checkable`` acquires an opinion it has no basis for.

    And one rule about traceability. A completed result must carry all
    three of ``evidence_artifact_ref``, ``evidence_checksum`` and
    ``implementation_ref``, and the last two must be **well formed** —
    a 64-hex digest and a resolvable code reference (``git:<40 hex>`` or
    ``sha256:<64 hex>``). They were optional in the first cut, and then
    briefly required-but-unvalidated, which let ``"x"`` satisfy the
    rule; a checksum that hashes nothing traces no better than a blank.
    Non-completed results may omit them — a run that did not happen
    produced no evidence to reference.

    **What this does and does not prove.** The schema makes a result
    *traceable*: every field an auditor needs to go and look is present
    and resolvable. It does **not** prove the tool host wrote it —
    nothing verifies a signature here, and a caller with a plausible
    digest can construct one. Authorship is enforced upstream, by the
    host being the only writer of results into the ledger (E5/E6). Both
    halves are needed and neither substitutes for the other, so neither
    is described as if it were the other.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    execution_status: ExecutionStatus
    input_provenance: InputProvenance
    proposition_verdict: PropositionVerdict | None = None
    supported_propositions: tuple[PropositionOutcome, ...] = ()
    unsupported_inferences: tuple[PropositionType, ...] = ()
    measurements: dict[str, float] = Field(default_factory=dict)
    evidence_artifact_ref: str | None = None
    evidence_checksum: str | None = Field(default=None, pattern=CHECKSUM_PATTERN)
    #: ``git:<40 hex>`` or ``sha256:<64 hex>`` of the checker build.
    implementation_ref: str | None = None

    @model_validator(mode="after")
    def _check(self) -> CheckerResult:
        canonical_propositions(self.unsupported_inferences, field="unsupported_inferences")
        if self.execution_status != "completed":
            if self.proposition_verdict is not None or self.supported_propositions:
                raise ValueError(
                    f"execution_status={self.execution_status!r} carries a verdict; "
                    "a run that did not complete has no opinion about the proposition"
                )
            return self
        if not self.supported_propositions:
            raise ValueError(
                "a completed checker result must name at least one proposition it "
                "spoke to; a bare verdict cannot be matched to a hypothesis"
            )
        if len(self.supported_propositions) > 1 and self.proposition_verdict is not None:
            raise ValueError(
                "a top-level proposition_verdict is only valid for a tool declaring "
                "exactly one proposition; multi-proposition results carry a verdict "
                "per entry"
            )
        if (
            len(self.supported_propositions) == 1
            and self.proposition_verdict is not None
            and self.proposition_verdict != self.supported_propositions[0].result
        ):
            raise ValueError(
                "top-level proposition_verdict disagrees with the single "
                "proposition entry; one result cannot answer two ways"
            )
        if self.input_provenance == "missing":
            raise ValueError(
                "a completed check cannot have missing inputs; report "
                "execution_status 'not_checkable' instead"
            )
        unsigned = [
            name
            for name, value in (
                ("evidence_artifact_ref", self.evidence_artifact_ref),
                ("evidence_checksum", self.evidence_checksum),
                ("implementation_ref", self.implementation_ref),
            )
            if not value
        ]
        if unsigned:
            raise ValueError(
                f"completed checker result is missing {unsigned}; a result without "
                "an artifact, a checksum and the identity of the code that produced "
                "it cannot be traced back to anything, and it would still be enough "
                "to promote a claim"
            )
        validate_code_ref(str(self.implementation_ref), field="implementation_ref")
        return self

    def verdict_for(self, proposition_type: PropositionType) -> PropositionVerdict | None:
        """This result's verdict about ``proposition_type``, if it has one."""
        for outcome in self.supported_propositions:
            if outcome.proposition_type == proposition_type:
                return outcome.result
        return None


#: What an impact artifact describes.
#:
#: ``observed_contribution``
#:     how much an objective contributed to the utility gap, over the
#:     episodes where the mechanism appears. It does **not** say the
#:     mechanism produced that much. Template: "the mechanism appears in
#:     the episodes where time efficiency is down 0.074."
#: ``attributable_effect_estimate``
#:     an estimate of the part *due to* the mechanism. Requires a named
#:     method, its assumptions and an uncertainty, and renders with the
#:     ``estimated`` qualifier.
ImpactKind = Literal["observed_contribution", "attributable_effect_estimate"]


class ImpactRef(BaseModel):
    """A pointer to a tool-produced impact artifact, and its kind.

    No number lives here. The moment the ledger holds a float, some
    render path will print it without the artifact's caveats, and the
    difference between the two impact kinds — which is entirely a
    difference in what the number means — stops travelling with it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_ref: str = Field(min_length=1)
    impact_kind: ImpactKind
    objective: str = Field(min_length=1)
    method: str = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    uncertainty: str | None = None
    #: True when the decomposition depends on the preference profile, in
    #: which case the profile must be named wherever this is rendered.
    profile_weighted: bool = False

    @model_validator(mode="after")
    def _check(self) -> ImpactRef:
        if self.impact_kind == "attributable_effect_estimate":
            if not self.assumptions:
                raise ValueError(
                    "an attributable effect estimate must state its assumptions; "
                    "without them the estimate reads as a measurement"
                )
            if not self.uncertainty:
                raise ValueError("an attributable effect estimate must state an uncertainty")
        return self


class InterventionEvidence(BaseModel):
    """A preregistered intervention run in the research lane.

    The only route to ``intervention_supported``. Preregistration is
    required rather than encouraged: sweeping several axes at several
    doses and keeping the axis that explained something is a garden of
    forking paths, and a per-seed interval does not repair multiplicity.

    **It has to say what it tested and how it came out.** The first cut
    of this object recorded only a preregistration, some axes and a
    scope — so an intervention that varied an unrelated axis, and one
    that varied the right axis and found nothing, were the same object
    to the matrix, and both promoted a claim to the top rung. An
    intervention now names the proposition it moved, the subject it
    acted on, its verdict, the direction of the effect and the
    statistical result behind it. A ``refuted`` or ``inconclusive``
    verdict is recorded rather than dropped: the matrix reads it and
    refuses.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    preregistration_ref: str = Field(min_length=1)
    axes: tuple[str, ...]
    artifact_ref: str = Field(min_length=1)
    #: Which proposition the intervention was designed to move. Matched
    #: against the proposal by the promotion matrix.
    proposition_type: PropositionType
    #: Which component the axes acted on. Varying an inflation radius
    #: says nothing about a global planner, and the matrix checks.
    subject: Subject
    verdict: PropositionVerdict
    #: What happened to the mechanism when the axis moved.
    effect_direction: Literal["removed", "reduced", "unchanged", "increased"]
    #: Where the ΔΔU, the per-seed intervals and the disappearance rate
    #: live. An intervention without a statistical result is an anecdote
    #: with a preregistration attached.
    statistical_result_ref: str = Field(min_length=1)
    #: The bounds the claim must always be spoken inside, e.g.
    #: "simulator, declared Task Neighborhood".
    scope: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> InterventionEvidence:
        if not self.axes:
            raise ValueError("an intervention must name the axes it varied")
        require_assertable(self.proposition_type, field="proposition_type")
        if self.verdict == "supported" and self.effect_direction in ("unchanged", "increased"):
            raise ValueError(
                f"verdict 'supported' with effect_direction {self.effect_direction!r}: "
                "an intervention that did not reduce the mechanism has not supported "
                "the proposition, whatever the run was hoping for"
            )
        return self


#: How far the orchestrator got with one proposal.
#:
#: ``checked`` with no results is legitimate and means *adjudicated on
#: observations alone* — the catalog held no applicable check. That path
#: cannot exceed ``associated``; see the promotion matrix.
RecordStatus = Literal["proposed", "checked", "check_failed", "not_checkable"]

#: Which sample the record's evidence came from. Research-lane evidence
#: never enters the evaluation distribution and always renders with the
#: ``research_lane`` qualifier.
EvidenceLane = Literal["evaluation", "research"]


class InvestigationRecord(BaseModel):
    """The orchestrator's adjudication of one proposal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    proposal_ref: str = Field(min_length=1)
    status: RecordStatus
    evidence_lane: EvidenceLane = "evaluation"
    checker_results: tuple[CheckerResult, ...] = ()
    impact_ref: ImpactRef | None = None
    intervention: InterventionEvidence | None = None

    @model_validator(mode="after")
    def _check(self) -> InvestigationRecord:
        if self.status == "proposed" and self.checker_results:
            raise ValueError("a record still 'proposed' cannot hold checker results")
        if self.intervention is not None and self.evidence_lane != "research":
            raise ValueError(
                "an intervention is a new run and belongs to the research lane; "
                "recording one under 'evaluation' would put a diagnostic run into "
                "the evaluation distribution"
            )
        return self


class Claim(BaseModel):
    """What the UI may render — produced by the promotion matrix only.

    ``scope`` is mandatory at every level, not just for interventions.
    A claim without a stated scope is read as a property of the
    algorithm ("A beats B in narrow gaps"), which is the one
    generalisation the platform never earns.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str = Field(min_length=1)
    level: ClaimLevel
    proposition_type: PropositionType
    subject: Subject
    statement: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    supports: tuple[EvidenceRef, ...]
    record_ref: str = Field(min_length=1)
    qualifiers: tuple[Qualifier, ...] = ()
    impact_ref: ImpactRef | None = None
    #: Which version of the rules promoted this. Two artifacts with the
    #: same evidence and different levels are explained by this field.
    promotion_matrix_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Claim:
        require_assertable(self.proposition_type, field="proposition_type")
        canonical_qualifiers(self.qualifiers)
        if not self.supports:
            raise ValueError("a claim with no supporting evidence is not a claim")
        return self
