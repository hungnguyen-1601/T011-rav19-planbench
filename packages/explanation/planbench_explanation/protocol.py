"""The wire between the platform and an external analyst — E5.

Everything an untrusted analyst can do to this system passes through the
three objects here: it is handed an :class:`AnalysisRequest`, it sends
:class:`ToolRequest` messages, and it receives :class:`ToolResult`
messages. It returns an :class:`AnalysisResponse` of hypotheses. There is
no fourth channel, and in particular there is no channel on which a
model can hand over a finding.

**The analyst cannot manufacture evidence, by shape.** A
:class:`HypothesisProposal` has no status, no confidence and no
measurement — E0 took those fields away. A :class:`ToolResult` has all
of them, and the only way one comes into existence is
:meth:`ToolSession.record` against a request the same session admitted.
An analyst that fabricates a result is holding an object nothing will
accept: the session has no admitted request with that id, so the result
never becomes a :class:`~planbench_explanation.ledger.CheckerResult` and
never reaches the promotion matrix.

That is the substance behind "only the tool host may sign a result".
A cryptographic signature would prove the same thing to a third party
across a trust boundary; within one process the binding to an admitted
request is what actually holds, so that is what is implemented rather
than a signature field an analyst could also fill in.

**Admission is where the catalog stops being documentation.** Every
request is checked against the card: does the tool exist at that
version, is it on the menu this analysis was opened with, is the run and
the packet and the bundle the one being analysed, does the evidence the
card requires actually exist for this run, and is the tool allowed to
execute at all. Research-proposal tools fail that last check by
construction — they write specifications, and a specification is not a
run.

**Two words that must never merge.** ``execution_status`` says how the
tool ran; ``proposition_verdict`` says whether the proposition stood.
A single ``pass`` covering both is how "the checker ran fine and refuted
the hypothesis" turns into "the check passed". They are separate fields
with separate vocabularies and a validator between them: a tool that did
not complete has no verdict at all.

**A top-level verdict belongs only to a single-proposition tool.** A
tool answering about three propositions and reporting one verdict is
reporting an aggregate nobody defined — so multi-proposition results
carry their verdicts inside the entries and leave the top level empty.

**The host stamps the over-readings.** ``unsupported_inferences`` is not
something a checker chooses per run; it is the card's
``forbidden_inference_types``, copied onto every result so the refusal
travels with the evidence. A result that dropped one would be a result
that quietly permits the reading its card forbids, and the drop would be
invisible at the far end.

**The shape of the data is closed too, not only the conclusions.**
Arguments are checked against the card's :class:`~planbench_explanation.tools.ToolIO`
at admission; measurements and references at recording. Without that,
the catalog locks which tool may say what while leaving every checker
free to invent its own argument names — and by the time four of them
exist, the contract is whatever the first one did.

Both halves of the output are closed, and for a while only one was.
Barring unknown measurement keys stops a checker inventing ``width``,
but a completed result carrying **no** measurements at all was still
well formed — a check that reports nothing is not a check that found
nothing. And a navigation tool reporting ``n_exemplars: 4`` had told the
caller how many episodes to open without saying which, because every
output was being squeezed through a mapping of floats. Pointers are now
:class:`EvidenceReference` values with a typed kind, and a card that
declares one requires it.

**A request is about a hypothesis the analyst actually declared, and
declaring is by content.** The session is told the proposals first; a
request naming a hypothesis id nobody proposed is refused. Otherwise
``hypothesis_id`` is a free-text field, the round cannot be
reconstructed as a line of reasoning, and evidence gathered "for" a
hypothesis that never existed still lands in the ledger.

Registering ids alone would leave the interesting half open: re-declare
``hyp-004`` mid-round with a different proposition and subject, and the
evidence gathered for the first hypothesis silently becomes evidence for
the second. So the session keeps a checksum per id — re-declaring the
same content is idempotent, re-declaring different content under one id
is refused, and an ``AnalysisResponse`` from another round or another
bundle is refused before any of it is registered. A refused declaration
registers **nothing**: the whole batch is checked before any of it is
written, so a caller that catches the rejection and a session that
raised it still agree on what was declared.

**Failure codes are a closed union.** Each card enumerates its own
failure modes; the host contributes the generic ones in
:data:`HOST_FAILURE_CODES`. A code outside the union is refused, because
a failure nobody enumerated is a failure nobody designed for — and the
downstream reader cannot tell it from a typo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.case_packet import CasePacket
from planbench_explanation.ledger import (
    CheckerResult,
    HypothesisProposal,
    PropositionOutcome,
)
from planbench_explanation.propositions import PropositionType
from planbench_explanation.provenance import (
    ExecutionStatus,
    InputProvenance,
    PropositionVerdict,
)
from planbench_explanation.tools import ToolCard, ToolCatalog, ToolNotInCatalog
from planbench_explanation.versioning import (
    CHECKSUM_PATTERN,
    CODE_REF_PATTERN,
    artifact_checksum,
)

#: Why a request or a result was turned away. A closed vocabulary so a
#: harness can count rejections by kind rather than by matching prose.
RejectionCode = Literal[
    "unknown_tool",
    "catalog_version_mismatch",
    "packet_mismatch",
    "analysis_run_mismatch",
    "bundle_mismatch",
    "duplicate_request_id",
    "sequence_out_of_order",
    "request_budget_exhausted",
    "missing_required_evidence",
    "execution_not_authorized",
    "unknown_hypothesis",
    "unknown_request",
    "duplicate_result",
    "tool_mismatch",
    "provenance_not_allowed",
    "proposition_not_supported",
    "inference_refusal_dropped",
    "arguments_rejected",
    "measurements_rejected",
    "references_rejected",
    "unknown_failure_code",
    "hypothesis_redefined",
]


#: Failures that belong to the host rather than to any tool. Kept
#: apart from a card's ``failure_modes`` because a card should not have
#: to enumerate the ways the platform itself can break, and because a
#: reader wants to know which side failed.
HOST_FAILURE_CODES: tuple[str, ...] = (
    "checker_not_implemented",
    "checker_timeout",
    "host_internal_error",
    "tool_unavailable",
)


class ProtocolRejection(ValueError):
    """A message the host refuses to process, with a machine-readable code."""

    def __init__(self, code: RejectionCode, message: str) -> None:
        self.code: RejectionCode = code
        super().__init__(f"{code}: {message}")


class AnalysisRequest(BaseModel):
    """What the platform opens an analysis round with.

    The packet is the analyst's whole view of the case (E4); the catalog
    is its whole vocabulary of actions. ``available_evidence`` is the
    third thing it needs and the one most easily forgotten: which kinds
    of evidence this particular run actually holds. A run recorded
    before the trace address changed has no per-episode trace, and an
    analyst that asks for one should be told so at admission rather than
    handed an empty result to interpret.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_run_id: str = Field(min_length=1)
    analyst_bundle_id: str = Field(min_length=1)
    packet: CasePacket
    catalog: ToolCatalog
    #: Evidence keys this run holds, matched against each card's
    #: ``required_evidence``. Declared by the platform, never by the
    #: analyst.
    available_evidence: frozenset[str] = frozenset()
    #: Ceiling on tool requests in one round. A round is a budget, and a
    #: budget nobody enforces is a suggestion.
    max_tool_requests: int = Field(default=64, ge=1, le=1024)

    @property
    def case_packet_checksum(self) -> str:
        return artifact_checksum(self.packet.model_dump(mode="json"))


class ToolRequest(BaseModel):
    """One action an analyst asks the host to take.

    Every identity field is here so a request can be placed later:
    which round, which packet, which menu, which analyst build, and
    where in the sequence. A request that names none of these is a
    request nobody can attribute after the fact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    analysis_run_id: str = Field(min_length=1)
    case_packet_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    tool_catalog_version: str = Field(min_length=1)
    analyst_bundle_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


class EvidenceReference(BaseModel):
    """A pointer a navigation tool returns: what kind, and which one.

    Separate from ``measurements`` because it is not a number, and a
    count of pointers is not a pointer. ``ref`` is opaque here — its
    grammar belongs to the kind — but it is the string a viewer resolves,
    so it may not be blank.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    label: str | None = None


class ToolResult(BaseModel):
    """What the host returns. Never constructed by an analyst.

    Well-formedness is enforced here; whether the result *belongs* to an
    admitted request is enforced by :meth:`ToolSession.record`, because
    that is a fact about the session and not about the message.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    request_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    execution_status: ExecutionStatus
    input_provenance: InputProvenance
    proposition_verdict: PropositionVerdict | None = None
    supported_propositions: tuple[PropositionOutcome, ...] = ()
    unsupported_inferences: tuple[PropositionType, ...] = ()
    measurements: dict[str, float] = Field(default_factory=dict)
    #: Typed pointers into the evidence. Empty for tools that compute
    #: rather than locate; required for the ones whose whole job is to
    #: say where to look.
    references: tuple[EvidenceReference, ...] = ()
    failure_code: str | None = None
    evidence_artifact_ref: str | None = None
    evidence_checksum: str | None = Field(default=None, pattern=CHECKSUM_PATTERN)
    implementation_ref: str | None = Field(default=None, pattern=CODE_REF_PATTERN)

    @model_validator(mode="after")
    def _check(self) -> ToolResult:
        if self.execution_status != "completed":
            if self.proposition_verdict is not None:
                raise ProtocolRejection(
                    "tool_mismatch",
                    f"execution_status={self.execution_status!r} carries "
                    f"proposition_verdict={self.proposition_verdict!r}. A tool that did "
                    "not complete has not adjudicated anything; how it ran and whether "
                    "the proposition stood are different questions.",
                )
            if self.supported_propositions:
                raise ProtocolRejection(
                    "tool_mismatch",
                    f"execution_status={self.execution_status!r} lists propositions; a "
                    "run that did not complete produced no outcomes",
                )
            if self.failure_code is None:
                raise ProtocolRejection(
                    "tool_mismatch",
                    f"execution_status={self.execution_status!r} with no failure_code; "
                    "the card enumerates its failure modes so a reader can tell "
                    "'no inputs' from 'the checker crashed'",
                )
            return self

        missing = [
            name
            for name, value in (
                ("evidence_artifact_ref", self.evidence_artifact_ref),
                ("evidence_checksum", self.evidence_checksum),
                ("implementation_ref", self.implementation_ref),
            )
            if value is None
        ]
        if missing:
            raise ProtocolRejection(
                "tool_mismatch",
                f"a completed result is missing {missing}; a verdict nobody can trace "
                "back to an artifact and a build is a verdict on trust",
            )
        if self.failure_code is not None:
            raise ProtocolRejection(
                "tool_mismatch",
                f"a completed result carries failure_code={self.failure_code!r}",
            )
        if not self.supported_propositions:
            if self.proposition_verdict is not None:
                raise ProtocolRejection(
                    "tool_mismatch",
                    "a top-level verdict with no proposition behind it says a "
                    "something stood without saying what",
                )
            return self
        if len(self.supported_propositions) == 1:
            if self.proposition_verdict is None:
                raise ProtocolRejection(
                    "tool_mismatch",
                    "a single-proposition result must state its verdict at the top "
                    "level, where the promotion matrix reads it",
                )
            if self.proposition_verdict != self.supported_propositions[0].result:
                raise ProtocolRejection(
                    "tool_mismatch",
                    f"top-level verdict {self.proposition_verdict!r} disagrees with the "
                    f"one proposition's {self.supported_propositions[0].result!r}",
                )
        elif self.proposition_verdict is not None:
            raise ProtocolRejection(
                "tool_mismatch",
                "a multi-proposition result has no single verdict; an aggregate over "
                "several propositions is a number nobody defined. Leave the top level "
                "empty and let each entry carry its own.",
            )
        return self

    def as_checker_result(self) -> CheckerResult:
        """The same facts in the ledger's vocabulary."""
        return CheckerResult(
            request_id=self.request_id,
            tool_id=self.tool_id,
            tool_version=self.tool_version,
            execution_status=self.execution_status,
            input_provenance=self.input_provenance,
            proposition_verdict=self.proposition_verdict,
            supported_propositions=self.supported_propositions,
            unsupported_inferences=self.unsupported_inferences,
            measurements=self.measurements,
            evidence_artifact_ref=self.evidence_artifact_ref,
            evidence_checksum=self.evidence_checksum,
            implementation_ref=self.implementation_ref,
        )


class AnalysisResponse(BaseModel):
    """What the analyst hands back at the end of a round.

    Abstention is a first-class answer with its own field rather than an
    empty proposal list, because "I found nothing worth proposing" and
    "I crashed" produce the same empty list and must not be scored the
    same way.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_run_id: str = Field(min_length=1)
    analyst_bundle_id: str = Field(min_length=1)
    proposals: tuple[HypothesisProposal, ...] = ()
    abstained: bool = False
    abstention_reason: str | None = None

    @model_validator(mode="after")
    def _check(self) -> AnalysisResponse:
        if self.abstained and self.proposals:
            raise ProtocolRejection(
                "tool_mismatch",
                "an abstention with proposals attached is not an abstention; say "
                "nothing or say something",
            )
        if self.abstained and not self.abstention_reason:
            raise ProtocolRejection(
                "tool_mismatch",
                "an abstention with no reason cannot be told from a silent failure",
            )
        ids = [proposal.hypothesis_id for proposal in self.proposals]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ProtocolRejection(
                "tool_mismatch", f"hypothesis id(s) {duplicates} proposed twice"
            )
        return self


class ToolSession:
    """The host side of one analysis round.

    Stateful on purpose. Admission needs to know what has already been
    asked — the sequence so far, which request ids are spent, how much of
    the budget is left — and a stateless check cannot see any of that.
    """

    def __init__(self, analysis: AnalysisRequest) -> None:
        self.analysis = analysis
        self._checksum = analysis.case_packet_checksum
        self._admitted: dict[str, tuple[ToolRequest, ToolCard]] = {}
        self._answered: set[str] = set()
        self._results: dict[str, ToolResult] = {}
        self._hypotheses: dict[str, str] = {}
        self._last_sequence = 0

    @property
    def declared_hypotheses(self) -> tuple[str, ...]:
        return tuple(sorted(self._hypotheses))

    def declare(self, proposals: Iterable[HypothesisProposal] | AnalysisResponse) -> None:
        """Register the hypotheses this round may gather evidence for.

        Callable more than once: a real analyst proposes, checks, and
        proposes again in light of what came back, and a contract that
        allowed only one declaration would force it to guess its whole
        line of reasoning before seeing any evidence.

        What it may not do is reuse an id. Each is bound to the checksum
        of the proposal it was declared with, so declaring the same
        proposal twice is a no-op and declaring a different one under
        the same id is refused — otherwise evidence gathered for one
        hypothesis becomes evidence for another by renaming.
        """
        if isinstance(proposals, AnalysisResponse):
            if proposals.analysis_run_id != self.analysis.analysis_run_id:
                raise ProtocolRejection(
                    "analysis_run_mismatch",
                    f"response is from round {proposals.analysis_run_id!r}, this "
                    f"session is {self.analysis.analysis_run_id!r}",
                )
            if proposals.analyst_bundle_id != self.analysis.analyst_bundle_id:
                raise ProtocolRejection(
                    "bundle_mismatch",
                    f"response is from bundle {proposals.analyst_bundle_id!r}, this "
                    f"round was opened for {self.analysis.analyst_bundle_id!r}",
                )
            proposals = proposals.proposals

        # Check the whole batch before writing any of it. Checking and
        # writing in one pass meant a batch refused on its third
        # proposal had already registered the first two: the caller sees
        # an exception, the session has changed, and neither of them
        # agrees with the other about what was declared.
        staged: dict[str, str] = {}
        for proposal in proposals:
            checksum = artifact_checksum(proposal.model_dump(mode="json"))
            known = self._hypotheses.get(proposal.hypothesis_id) or staged.get(
                proposal.hypothesis_id
            )
            if known is not None and known != checksum:
                raise ProtocolRejection(
                    "hypothesis_redefined",
                    f"{proposal.hypothesis_id!r} was already declared with different "
                    "content. Reusing an id would move the evidence already gathered "
                    "under it onto a different claim; give the new hypothesis its own id.",
                )
            staged[proposal.hypothesis_id] = checksum
        self._hypotheses.update(staged)

    def proposal_checksum(self, hypothesis_id: str) -> str:
        """What was declared under this id. For an auditor rebuilding a round."""
        try:
            return self._hypotheses[hypothesis_id]
        except KeyError as error:
            raise ProtocolRejection(
                "unknown_hypothesis", f"no proposal {hypothesis_id!r} in this round"
            ) from error

    @property
    def admitted(self) -> tuple[ToolRequest, ...]:
        return tuple(request for request, _ in self._admitted.values())

    @property
    def requested_tool_ids(self) -> tuple[str, ...]:
        """Which tools were asked for, in order. What golden scores."""
        return tuple(request.tool_id for request, _ in self._admitted.values())

    def admit(self, request: ToolRequest) -> ToolCard:
        """Accept a request, or refuse it with a coded reason."""
        analysis = self.analysis
        if request.analysis_run_id != analysis.analysis_run_id:
            raise ProtocolRejection(
                "analysis_run_mismatch",
                f"request names round {request.analysis_run_id!r}, this session is "
                f"{analysis.analysis_run_id!r}",
            )
        if request.analyst_bundle_id != analysis.analyst_bundle_id:
            raise ProtocolRejection(
                "bundle_mismatch",
                f"request names bundle {request.analyst_bundle_id!r}, this round was "
                f"opened for {analysis.analyst_bundle_id!r}. A round is attributable to "
                "one frozen analyst or to none.",
            )
        if request.case_packet_checksum != self._checksum:
            raise ProtocolRejection(
                "packet_mismatch",
                "request answers a different case packet than this round was opened with",
            )
        if request.tool_catalog_version != analysis.catalog.catalog_version:
            raise ProtocolRejection(
                "catalog_version_mismatch",
                f"request chose from menu {request.tool_catalog_version!r}, this round "
                f"serves {analysis.catalog.catalog_version!r}",
            )
        if request.request_id in self._admitted:
            raise ProtocolRejection(
                "duplicate_request_id",
                f"request id {request.request_id!r} was already admitted; ids are how "
                "results are matched to requests",
            )
        if request.sequence <= self._last_sequence:
            raise ProtocolRejection(
                "sequence_out_of_order",
                f"sequence {request.sequence} follows {self._last_sequence}; the order "
                "of a round is part of what a reviewer reconstructs",
            )
        if len(self._admitted) >= analysis.max_tool_requests:
            raise ProtocolRejection(
                "request_budget_exhausted",
                f"round budget of {analysis.max_tool_requests} tool requests is spent",
            )

        if request.hypothesis_id not in self._hypotheses:
            raise ProtocolRejection(
                "unknown_hypothesis",
                f"no proposal {request.hypothesis_id!r} was declared in this round; "
                "evidence is gathered for a stated hypothesis or it is gathered for "
                "nothing, and a round nobody can read as a line of reasoning is a "
                "round nobody can review",
            )

        try:
            card = analysis.catalog.card(request.tool_id, request.tool_version)
        except ToolNotInCatalog as error:
            raise ProtocolRejection("unknown_tool", str(error)) from error

        if not card.execution_authorized:
            raise ProtocolRejection(
                "execution_not_authorized",
                f"{card.tool_id} writes a specification for an experiment; running one "
                "is a decision a person makes in the research lane",
            )
        missing = sorted(set(card.required_evidence) - analysis.available_evidence)
        if missing:
            raise ProtocolRejection(
                "missing_required_evidence",
                f"{card.tool_id} needs {missing}, which this run does not hold. Being "
                "told so is the answer; an empty result would be read as a finding.",
            )
        problems = card.io.check_arguments(request.arguments)
        if problems:
            raise ProtocolRejection("arguments_rejected", f"{card.tool_id}: " + "; ".join(problems))

        self._admitted[request.request_id] = (request, card)
        self._last_sequence = request.sequence
        return card

    def record(self, result: ToolResult) -> ToolResult:
        """Bind a result to its admitted request, or refuse it.

        This is the narrow gate. A result whose request this session
        never admitted has nowhere to attach, which is what stops an
        analyst from writing its own evidence.

        Returns the result rather than a ledger row because **most tools
        do not produce ledger rows**. A fact query hands over the ΔU
        decomposition and a navigation tool hands over four episode ids;
        neither adjudicates a proposition, and a
        :class:`~planbench_explanation.ledger.CheckerResult` that
        adjudicates nothing is a row the promotion matrix would have to
        skip. Use :attr:`checker_results` for the ones that do.
        """
        found = self._admitted.get(result.request_id)
        if found is None:
            raise ProtocolRejection(
                "unknown_request",
                f"no admitted request {result.request_id!r} in this round; a result "
                "for a request the host never accepted is a result the host never "
                "produced",
            )
        request, card = found
        if result.request_id in self._answered:
            raise ProtocolRejection(
                "duplicate_result",
                f"request {result.request_id!r} already has a result; a second one "
                "would let the better of two answers be kept",
            )
        if (result.tool_id, result.tool_version) != (request.tool_id, request.tool_version):
            raise ProtocolRejection(
                "tool_mismatch",
                f"result claims {result.tool_id}@{result.tool_version} for a request "
                f"for {request.tool_id}@{request.tool_version}",
            )

        allowed = card.evidence_policy.allowed_input_provenance
        if result.input_provenance not in allowed:
            checkable = result.execution_status == "not_checkable"
            if not (checkable and result.input_provenance == "missing"):
                raise ProtocolRejection(
                    "provenance_not_allowed",
                    f"{card.tool_id} accepts {list(allowed)} but the result declares "
                    f"{result.input_provenance!r}",
                )

        supported = set(card.proposition_policy.supported_proposition_types)
        offered = {outcome.proposition_type for outcome in result.supported_propositions}
        beyond = sorted(offered - supported)
        if beyond:
            raise ProtocolRejection(
                "proposition_not_supported",
                f"{card.tool_id} reported on {beyond}, which its card does not support. "
                "The card is the menu of what this checker can establish, and a result "
                "outside it is a checker answering a question it was not built for.",
            )
        required_refusals = set(card.proposition_policy.forbidden_inference_types)
        if set(result.unsupported_inferences) != required_refusals:
            raise ProtocolRejection(
                "inference_refusal_dropped",
                f"{card.tool_id} forbids {sorted(required_refusals)} but the result "
                f"carries {sorted(result.unsupported_inferences)}. The refusals travel "
                "with the evidence; dropping one is how an over-reading becomes "
                "permitted downstream, silently.",
            )

        completed = result.execution_status == "completed"
        bad_measurements = card.io.check_measurements(result.measurements, completed=completed)
        if bad_measurements:
            raise ProtocolRejection("measurements_rejected", "; ".join(bad_measurements))
        bad_references = card.io.check_references(
            (reference.kind for reference in result.references), completed=completed
        )
        if bad_references:
            raise ProtocolRejection("references_rejected", "; ".join(bad_references))

        if result.failure_code is not None:
            allowed_codes = set(card.failure_modes) | set(HOST_FAILURE_CODES)
            if result.failure_code not in allowed_codes:
                raise ProtocolRejection(
                    "unknown_failure_code",
                    f"{result.failure_code!r} is neither one of {card.tool_id}'s "
                    f"declared failure modes {list(card.failure_modes)} nor a host "
                    f"code {list(HOST_FAILURE_CODES)}; an unenumerated failure cannot "
                    "be told from a typo",
                )

        self._answered.add(result.request_id)
        self._results[result.request_id] = result
        return result

    @property
    def results(self) -> tuple[ToolResult, ...]:
        """Every recorded result, in the order the requests were admitted."""
        return tuple(
            self._results[request_id]
            for request_id in self._admitted
            if request_id in self._results
        )

    @property
    def checker_results(self) -> tuple[CheckerResult, ...]:
        """The subset that adjudicated something, in the ledger's vocabulary.

        Filtered by the *card*, not by whether a particular result
        happened to come back empty: a mechanism check that failed to
        run is still a checker result, and the ledger needs it to tell
        "the check refuted this" from "nobody checked".
        """
        rows = []
        for request_id, (_, card) in self._admitted.items():
            if not card.proposition_policy.supported_proposition_types:
                continue
            result = self._results.get(request_id)
            if result is not None:
                rows.append(result.as_checker_result())
        return tuple(rows)


def stamped_result(
    card: ToolCard,
    request: ToolRequest,
    *,
    execution_status: ExecutionStatus,
    input_provenance: InputProvenance,
    proposition_verdict: PropositionVerdict | None = None,
    supported_propositions: Sequence[PropositionOutcome] = (),
    measurements: dict[str, float] | None = None,
    references: Sequence[EvidenceReference] = (),
    failure_code: str | None = None,
    evidence_artifact_ref: str | None = None,
    evidence_checksum: str | None = None,
    implementation_ref: str | None = None,
) -> ToolResult:
    """Build a result with the card's refusals already stamped on.

    A checker implementation should not be retyping
    ``forbidden_inference_types`` — that is how one of them goes missing.
    It comes off the card here, and :meth:`ToolSession.record` refuses
    the result if it does not.
    """
    return ToolResult(
        request_id=request.request_id,
        tool_id=card.tool_id,
        tool_version=card.tool_version,
        execution_status=execution_status,
        input_provenance=input_provenance,
        proposition_verdict=proposition_verdict,
        supported_propositions=tuple(supported_propositions),
        unsupported_inferences=card.proposition_policy.forbidden_inference_types,
        measurements=dict(measurements or {}),
        references=tuple(references),
        failure_code=failure_code,
        evidence_artifact_ref=evidence_artifact_ref,
        evidence_checksum=evidence_checksum,
        implementation_ref=implementation_ref,
    )


def missing_evidence_for(
    catalog: ToolCatalog, available: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    """Which tools this run cannot serve, and what each one is short of.

    Handed to an analyst alongside the packet so a round is not spent
    discovering the same absence four times.
    """
    have = set(available)
    shortfalls = {}
    for card in catalog.cards:
        missing = tuple(sorted(set(card.required_evidence) - have))
        if missing:
            shortfalls[card.tool_id] = missing
    return shortfalls
