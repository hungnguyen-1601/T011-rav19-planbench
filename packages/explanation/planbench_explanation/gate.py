"""Running a frozen analyst against a hidden suite, and deciding — E6b.

E5 defined what is submitted (an :class:`~planbench_explanation.bundle.AnalystBundle`),
what it is graded on (a :class:`~planbench_explanation.golden.GoldenSuite`),
how the grading works (:func:`~planbench_explanation.golden.score_suite`)
and what a verdict looks like
(:class:`~planbench_explanation.bundle.GateDecision`). Every piece
existed and nothing put them in a line. This is the line.

**The platform runs the bundle; the AI team does not run the gate.** That
is the whole reason the unit of submission is a frozen configuration
rather than an endpoint — an endpoint can log the hidden packets, change
its prompt between cases, or notice it is being graded. So the analyst
arrives here as a callable this harness invokes, once per case, inside
an environment the platform controls.

**The hidden suite is opened once.** :class:`GateRun` records the suite
version it consumed, and :func:`run_gate` refuses a suite whose
visibility is ``visible``: grading against the set the AI team
calibrated on measures how well it fitted that set.

**Nothing here decides thresholds.** The bar arrives as
:class:`~planbench_explanation.bundle.MetricTargets` and the decision is
built through it, so the thresholds on the decision are the
preregistered ones by construction rather than by care. A gate that
could choose its own bar while running is not a gate.

**A case that raises is a case scored, not a case skipped.** An analyst
that crashes on the six hardest packets and returns cleanly on the rest
would otherwise be graded on the rest. The exception is recorded, the
case is submitted as an abstention it never made, and the score reflects
what happened.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.budget import PLATFORM_BUDGET_CAP, AnalysisBudget
from planbench_explanation.bundle import (
    AnalystBundle,
    BundleRefusal,
    GateDecision,
    MetricTargets,
)
from planbench_explanation.case_packet import CasePacket
from planbench_explanation.golden import (
    CaseSubmission,
    GoldenSuite,
    PlantedCase,
    SuiteScore,
    score_suite,
)
from planbench_explanation.packet_artifact import PacketArtifact
from planbench_explanation.protocol import (
    AnalysisRequest,
    AnalysisResponse,
    ToolSession,
)
from planbench_explanation.tools import ToolCatalog

#: What the platform invokes per case: it is handed the round and hands
#: back the analyst's proposals. Whatever runs behind it — a container,
#: an API call, a stub — is the submitter's business and is frozen by
#: the bundle, not by this signature.
Analyst = Callable[[AnalysisRequest], AnalysisResponse]

#: How the platform gets a packet for a hidden case. A callable rather
#: than a directory of files because the hidden set is not in this
#: repository and must not become discoverable by being addressable
#: here.
PacketSource = Callable[[PlantedCase], CasePacket | PacketArtifact]

#: How the platform gets a host session for a case, so tool requests are
#: admitted and answered the way they will be in production. Returns the
#: session the round used, which is where ``requested_tool_ids`` comes
#: from — scoring reads the host's account of the round, never the
#: analyst's.
SessionSource = Callable[[AnalysisRequest], ToolSession]


class GateRefusal(ValueError):
    """A gate run that must not proceed as asked."""


class CaseOutcome(BaseModel):
    """What happened on one case, before scoring reads it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(min_length=1)
    submission: CaseSubmission
    #: Present when the analyst raised. Recorded rather than retried: a
    #: gate that retries is measuring the best of several attempts,
    #: which is not what a deployment gets.
    error: str | None = None


class DryGateRun(BaseModel):
    """A rehearsal: a score, and deliberately no decision.

    The first version of this returned an ordinary :class:`GateRun` with
    ``allow_visible_suite=True``, which meant a dry run produced a
    perfectly valid :class:`GateDecision` — and
    :func:`~planbench_explanation.bundle.analyst_visible` takes one of
    those. A rehearsal on the calibration set could therefore turn the
    feature on. Splitting the types closes that by construction: there
    is no object here for ``verify_gate_decision`` to accept, because
    there is no decision.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    is_dry_run: Literal[True] = True
    bundle_id: str = Field(min_length=1)
    bundle_identity_checksum: str = Field(min_length=64, max_length=64)
    suite_version: str = Field(min_length=1)
    outcomes: tuple[CaseOutcome, ...]
    score: SuiteScore

    @property
    def failed_cases(self) -> tuple[str, ...]:
        return tuple(item.case_id for item in self.outcomes if item.error is not None)


class GateRun(BaseModel):
    """One bundle, one suite, one pass. The record of the grading itself."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    is_dry_run: Literal[False] = False
    bundle_id: str = Field(min_length=1)
    bundle_identity_checksum: str = Field(min_length=64, max_length=64)
    suite_version: str = Field(min_length=1)
    #: What the bundle asked for, and what it actually ran under. Both,
    #: because "the platform capped you" is a fact about the run that a
    #: submitter reading a failed gate needs and cannot derive.
    requested_budget_checksum: str = Field(min_length=64, max_length=64)
    effective_budget_checksum: str = Field(min_length=64, max_length=64)
    outcomes: tuple[CaseOutcome, ...]
    score: SuiteScore
    decision: GateDecision

    @model_validator(mode="after")
    def _check(self) -> GateRun:
        if self.decision.bundle_identity_checksum != self.bundle_identity_checksum:
            raise GateRefusal(
                "the decision names a different bundle identity than the run that produced it"
            )
        if self.decision.hidden_suite_version != self.suite_version:
            raise GateRefusal("the decision names a different suite than the one that was run")
        if self.decision.effective_budget_checksum != self.effective_budget_checksum:
            raise GateRefusal(
                "the decision names a different effective budget than the run that "
                "produced it"
            )
        return self

    @property
    def failed_cases(self) -> tuple[str, ...]:
        """Cases where the analyst raised. Zero is the normal number."""
        return tuple(item.case_id for item in self.outcomes if item.error is not None)


def _abstained_for(case: PlantedCase, analysis: AnalysisRequest, reason: str) -> CaseSubmission:
    """A submission standing in for a case the analyst could not answer.

    Scored as an abstention it did not make, which costs it on every
    case where something *was* there to find and credits it on the
    must-abstain ones. That asymmetry is deliberate: crashing is not a
    strategy, and it should not become one on the cases where silence is
    the right answer either — the structural count below records the
    failure separately so a clean sheet cannot be crashed into.
    """
    return CaseSubmission(
        case_id=case.case_id,
        response=AnalysisResponse(
            analysis_run_id=analysis.analysis_run_id,
            analyst_bundle_id=analysis.analyst_bundle_id,
            abstained=True,
            abstention_reason=f"the analyst raised: {reason}",
        ),
        contamination=(f"analyst_error:{case.case_id}",),
    )


#: Said in one place so the refusal is one line at the call site: a
#: multi-line ``raise`` reads as scenery, and this one is load-bearing.
_BARE_PACKET_REFUSAL = (
    "case {case_id} arrived as a bare packet; a graded run needs the artifact so the "
    "platform can derive where it came from rather than take the submitter's word for it"
)


def _packet_for(case: PlantedCase, source: PacketSource, *, dry_run: bool) -> CasePacket:
    """The packet for one case, and what a graded run demands of it.

    A dry run may be handed a bare :class:`CasePacket` — it is a
    rehearsal, and asking somebody to write a provenance file to
    rehearse is how rehearsals stop happening. A graded run may not:
    without a :class:`PacketArtifact` there is nothing to derive
    ``fixture_kind`` from, and "was this packet recorded or written by
    hand" is exactly the question a threshold rests on.
    """
    supplied = source(case)
    if isinstance(supplied, PacketArtifact):
        if not dry_run and supplied.fixture_kind != "recorded":
            raise GateRefusal(
                f"case {case.case_id} is a {supplied.fixture_kind} fixture; a gate "
                "grades against runs that were recorded as they happened, and a "
                "threshold agreed against a hand-written packet is a threshold about "
                "a run nobody made"
            )
        return supplied.packet
    if not dry_run:
        raise GateRefusal(_BARE_PACKET_REFUSAL.format(case_id=case.case_id))
    return supplied


def run_gate(
    bundle: AnalystBundle,
    suite: GoldenSuite,
    *,
    analyst: Analyst,
    packets: PacketSource,
    sessions: SessionSource,
    catalog: ToolCatalog,
    targets: MetricTargets,
    preregistration_ref: str,
    decided_at: str,
    budget_cap: AnalysisBudget = PLATFORM_BUDGET_CAP,
    dry_run: bool = False,
) -> GateRun | DryGateRun:
    """Run one frozen analyst over one suite and record what it earned.

    ``dry_run`` is a rehearsal and returns a :class:`DryGateRun`, which
    carries no decision at all — see that class for why the flag alone
    was not enough. It was called ``allow_visible_suite``; the name
    described one of the three things it turns off.

    **The graded path is fail-closed on three conditions**, and all
    three are the same mistake wearing different clothes — grading
    against something other than the preregistered hidden set:

    * the suite is ``hidden``: a score on the calibration set measures
      how well the submitter fitted the set they were given;
    * the suite is ``preregistered``: a working set is a set somebody
      may still be editing, and a threshold agreed after the numbers
      were seen is not a threshold;
    * every packet is a ``recorded`` artifact: see :func:`_packet_for`.
    """
    if not dry_run:
        if suite.visibility != "hidden":
            raise GateRefusal(
                f"suite {suite.suite_version} is {suite.visibility}; grading against the "
                "set the AI team calibrated on measures how well it fitted that set. "
                "Pass dry_run=True for a rehearsal, and do not call the result a gate."
            )
        if suite.status != "preregistered":
            raise GateRefusal(
                f"suite {suite.suite_version} is {suite.status!r}, not 'preregistered'; "
                "a working set is one somebody may still be editing, and a bar agreed "
                "against a moving set is not a bar. Preregister it or pass dry_run=True."
            )
    if not bundle.runs_catalog(catalog.catalog_version):
        raise GateRefusal(
            f"the bundle was frozen against tool catalog {bundle.tool_catalog_version!r} "
            f"and this gate serves {catalog.catalog_version!r}; a wire contract that "
            "moved is a different system under the same name"
        )

    effective_budget = bundle.requested_budget.capped_by(budget_cap)
    outcomes: list[CaseOutcome] = []
    for case in suite.cases:
        packet = _packet_for(case, packets, dry_run=dry_run)
        analysis = AnalysisRequest(
            analysis_run_id=f"{bundle.bundle_id}:{case.case_id}",
            analyst_bundle_id=bundle.bundle_id,
            packet=packet,
            catalog=catalog,
        )
        session = sessions(analysis)
        try:
            response = analyst(analysis)
            session.declare(response)
            submission = CaseSubmission(
                case_id=case.case_id,
                response=response,
                requested_tool_ids=session.requested_tool_ids,
                blocked_claim_leaks=_blocked_leaks(case, response, packet),
            )
            error: str | None = None
        except Exception as raised:  # noqa: BLE001 - this is the boundary
            submission = _abstained_for(case, analysis, repr(raised))
            error = repr(raised)
        outcomes.append(CaseOutcome(case_id=case.case_id, submission=submission, error=error))

    score = score_suite(suite, [item.submission for item in outcomes])
    if dry_run:
        return DryGateRun(
            bundle_id=bundle.bundle_id,
            bundle_identity_checksum=bundle.identity_checksum,
            suite_version=suite.suite_version,
            outcomes=tuple(outcomes),
            score=score,
        )
    decision = GateDecision(
        bundle_id=bundle.bundle_id,
        bundle_identity_checksum=bundle.identity_checksum,
        hidden_suite_version=suite.suite_version,
        preregistration_ref=preregistration_ref,
        decided_at=decided_at,
        targets_checksum=targets.checksum,
        effective_budget_checksum=effective_budget.checksum,
        metrics=targets.evaluate(score.macro.measurements),
        notes=tuple(
            f"analyst raised on {case_id}"
            for case_id in sorted(item.case_id for item in outcomes if item.error is not None)
        ),
    )
    return GateRun(
        bundle_id=bundle.bundle_id,
        bundle_identity_checksum=bundle.identity_checksum,
        suite_version=suite.suite_version,
        requested_budget_checksum=bundle.requested_budget.checksum,
        effective_budget_checksum=effective_budget.checksum,
        outcomes=tuple(outcomes),
        score=score,
        decision=decision,
    )


def _blocked_leaks(
    case: PlantedCase, response: AnalysisResponse, packet: CasePacket
) -> tuple[str, ...]:
    """Proposals the packet's own declared gaps forbade.

    Read off the **packet**, not off the case: the packet is what the
    analyst was shown, and a gap it declared is a gap the analyst was
    told about. Scoring a leak against a gap nobody was shown would
    grade it on a rule it could not have known.
    """
    blocked = {kind for unknown in packet.known_unknowns for kind in unknown.blocks_claim_types}
    return tuple(
        sorted(
            f"{proposal.hypothesis_id}:{proposal.proposition_type}"
            for proposal in response.proposals
            if proposal.proposition_type in blocked
        )
    )


def gate_summary(run: GateRun, targets: MetricTargets) -> Mapping[str, object]:
    """What a person reads. Every required metric, met or not.

    Built from the decision rather than from the score so it reports the
    numbers the decision was actually made on — a summary computed a
    second way is a second answer waiting to disagree.
    """
    return {
        "bundle_id": run.bundle_id,
        "suite": run.suite_version,
        "passed": run.decision.passes(targets),
        "failed_metrics": list(run.decision.failed_metrics),
        "analyst_errors": list(run.failed_cases),
        "metrics": {
            row.metric: {
                "value": row.value,
                "threshold": row.threshold,
                "direction": row.direction,
                "met": row.met,
            }
            for row in run.decision.metrics
        },
    }


def verify_gate_run(run: GateRun, *, bundle: AnalystBundle, targets: MetricTargets) -> None:
    """Re-check a recorded run against the bundle and bar it claims.

    The same lesson as the claim ledger and the gate decision: an
    artifact's own account of what it graded is the part under
    suspicion, so the identity and the thresholds are compared against
    arguments the caller supplies.
    """
    if run.bundle_identity_checksum != bundle.identity_checksum:
        raise BundleRefusal(
            "this gate run graded a different configuration than the bundle supplied"
        )
    if run.decision.targets_checksum != targets.checksum:
        raise BundleRefusal(
            "this gate run was judged against a different bar than the one supplied"
        )
    rebuilt = targets.evaluate(run.score.macro.measurements)
    stored = {row.metric: row for row in run.decision.metrics}
    for row in rebuilt:
        if stored[row.metric].value != row.value:
            raise BundleRefusal(
                f"{row.metric}: the decision records {stored[row.metric].value} and the "
                f"suite score gives {row.value}"
            )


def cases_by_family(suite: GoldenSuite) -> Mapping[str, Sequence[PlantedCase]]:
    """Grouped, for a reader checking coverage before a gate is run."""
    grouped: dict[str, list[PlantedCase]] = {}
    for case in suite.cases:
        grouped.setdefault(case.family, []).append(case)
    return grouped
