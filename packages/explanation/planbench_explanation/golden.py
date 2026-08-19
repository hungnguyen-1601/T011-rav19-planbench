"""The acceptance contract for an external analyst — E5.

The platform does not build the analyst and does not tune it. What it
owes the AI team is a **stated bar**: a set of cases where the answer is
known because it was planted, a definition of every metric, and a
threshold agreed before the numbers exist. What the AI team owes back is
an :class:`~planbench_explanation.bundle.AnalystBundle` — not a report.

**Three things are graded and only one of them is a rate.** The
structural invariants are counts that must be zero: a claim promoted
from evidence that does not support it, an assertion rendered that no
claim licenses, a claim about a proposition the packet's known unknowns
block. None of those trade off against accuracy. An analyst that finds
every mechanism and leaks one blocked claim has failed, because the
leak is the failure this whole layer exists to prevent.

The rates come second, and precision and abstention are weighted above
recall on purpose. A missed mechanism costs an engineer an afternoon; a
confident wrong one costs the credibility of every explanation the
system will ever print.

**Abstention is a scored answer, not an absence.** Every family carries
cases where the right response is "the evidence here does not support a
mechanism". They are scored on their own axis, because an analyst that
proposes something for every case can score well on precision over the
cases it happened to get right while being useless on exactly the cases
where a human most needs to be told to stop.

**Macro before micro.** Six families of unequal size averaged together
lets the largest family carry the score. Both are reported; the macro
average is the one the thresholds are set against.

**No official golden before the writer.** Half these families need
planted runs whose planning inputs were recorded as they happened —
which is the E4.5 sidecar, which is not built. A suite can be marked
``calibration`` today; ``preregistered`` is refused while
:data:`OFFICIAL_GOLDEN_READY` is false. Grading an analyst on
reconstructed inputs and calling the result a gate would bake the
reconstruction's errors into the threshold.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.bundle import CALIBRATION_TARGETS, MetricTargets
from planbench_explanation.propositions import PropositionType
from planbench_explanation.protocol import AnalysisResponse
from planbench_explanation.subjects import Subject

#: Whether the planning-input sidecar (E4.5) exists. A platform
#: constant, in this module, for the same reason ``H4_ACCOUNTING_COMPLETE``
#: is one: it decides what the platform may certify, and the party being
#: certified must not be able to pass it as an argument.
OFFICIAL_GOLDEN_READY = False

#: The six mechanism families the suite covers (design section 6).
CaseFamily = Literal[
    "inflation_gap_closure",
    "dwa_local_minimum",
    "rrt_sample_starvation",
    "expansion_latency",
    "negative_control",
    "insufficient_evidence",
]

CASE_FAMILIES: tuple[CaseFamily, ...] = (
    "inflation_gap_closure",
    "dwa_local_minimum",
    "rrt_sample_starvation",
    "expansion_latency",
    "negative_control",
    "insufficient_evidence",
)

#: What a variant is testing. ``near_boundary`` is the interesting one:
#: a case sitting just inside or just outside the mechanism, where an
#: analyst that pattern-matches on surface features gets it wrong.
VariantKind = Literal["positive", "negative", "must_abstain", "near_boundary"]

#: How many variants a family needs before its macro score means
#: anything. Enforced only on a preregistered suite — a calibration
#: suite is allowed to be a skeleton.
MIN_VARIANTS_PER_FAMILY = 12
MAX_VARIANTS_PER_FAMILY = 20


class GoldenRefusal(ValueError):
    """A suite or a case that cannot be used to grade anything."""


class ExpectedFinding(BaseModel):
    """What was planted: a proposition about a subject.

    Not a sentence. Scoring on wording would grade the analyst's prose
    style, and the ledger already gates wording separately.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    proposition_type: PropositionType
    subject: Subject

    @property
    def key(self) -> tuple[str, str]:
        return (self.proposition_type, self.subject)


class PlantedCase(BaseModel):
    """One case with a known answer."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(min_length=1)
    family: CaseFamily
    variant: VariantKind
    #: Path to the packet fixture. A reference rather than an embedded
    #: packet: a packet is large, and a suite that carries copies is a
    #: suite whose cases drift from the runs they describe.
    packet_ref: str = Field(min_length=1)
    expected_findings: tuple[ExpectedFinding, ...] = ()
    #: The right answer is silence. Scored on its own axis.
    expect_abstention: bool = False
    #: Which checkers a competent analyst would ask for. Scored
    #: separately from the findings: asking the right question and
    #: reaching the right conclusion are different skills, and an
    #: analyst that reaches the conclusion without checking got lucky.
    expected_checker_requests: tuple[str, ...] = ()
    #: Propositions that must never be proposed here. A leak is a
    #: structural failure, not a precision penalty.
    forbidden_claims: tuple[PropositionType, ...] = ()
    #: Why this case is in the suite, for whoever reads a failure.
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> PlantedCase:
        if self.expect_abstention and self.expected_findings:
            raise GoldenRefusal(
                f"{self.case_id}: a case that expects abstention cannot also expect "
                "findings; one of the two is what the case is for"
            )
        if self.variant == "must_abstain" and not self.expect_abstention:
            raise GoldenRefusal(f"{self.case_id}: variant must_abstain without expect_abstention")
        if self.variant in ("positive", "near_boundary") and not (
            self.expected_findings or self.expect_abstention
        ):
            raise GoldenRefusal(
                f"{self.case_id}: a {self.variant} case with neither findings nor an "
                "abstention has no answer to grade against"
            )
        overlap = {finding.proposition_type for finding in self.expected_findings} & set(
            self.forbidden_claims
        )
        if overlap:
            raise GoldenRefusal(f"{self.case_id}: {sorted(overlap)} is both planted and forbidden")
        return self


class GoldenSuite(BaseModel):
    """A versioned set of planted cases, visible or hidden."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    suite_version: str = Field(min_length=1)
    #: ``visible`` suites go to the AI team for calibration. ``hidden``
    #: ones stay with the platform and are opened once.
    visibility: Literal["visible", "hidden"]
    #: ``calibration`` is a working set. ``preregistered`` is a suite
    #: thresholds were agreed against, and it is what a gate runs.
    status: Literal["calibration", "preregistered"]
    cases: tuple[PlantedCase, ...]
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> GoldenSuite:
        ids = [case.case_id for case in self.cases]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise GoldenRefusal(f"case id(s) {duplicates} appear twice in one suite")
        if self.status != "preregistered":
            return self

        if not OFFICIAL_GOLDEN_READY:
            raise GoldenRefusal(
                "no suite may be preregistered until the planning-input sidecar "
                "(E4.5) records attempts as they happen. Half these families are "
                "replayed, and a threshold agreed against reconstructed inputs bakes "
                "the reconstruction's errors into the bar."
            )
        missing = sorted(set(CASE_FAMILIES) - {case.family for case in self.cases})
        if missing:
            raise GoldenRefusal(
                f"preregistered suite is missing {missing}; the macro average is over "
                "the six families and a missing one is a family nobody is graded on"
            )
        for family in CASE_FAMILIES:
            count = sum(1 for case in self.cases if case.family == family)
            if not MIN_VARIANTS_PER_FAMILY <= count <= MAX_VARIANTS_PER_FAMILY:
                raise GoldenRefusal(
                    f"family {family!r} has {count} variants; a preregistered suite "
                    f"needs {MIN_VARIANTS_PER_FAMILY}–{MAX_VARIANTS_PER_FAMILY} so a "
                    "family score is not one lucky case"
                )
            variants = {case.variant for case in self.cases if case.family == family}
            if "must_abstain" not in variants:
                raise GoldenRefusal(
                    f"family {family!r} has no must_abstain variant; an analyst is "
                    "then never asked to stop, in a family where it should"
                )
        return self

    def family(self, name: CaseFamily) -> tuple[PlantedCase, ...]:
        return tuple(case for case in self.cases if case.family == name)


class CaseSubmission(BaseModel):
    """What an analyst produced for one case, and what it asked for."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(min_length=1)
    response: AnalysisResponse
    #: Tool ids the host admitted this round, in order. Taken from the
    #: session rather than from the analyst's own account of itself.
    requested_tool_ids: tuple[str, ...] = ()
    #: Structural violations the platform observed while running the
    #: case. Counted, never averaged.
    contamination: tuple[str, ...] = ()
    unsupported_rendered_assertions: tuple[str, ...] = ()
    blocked_claim_leaks: tuple[str, ...] = ()


class CaseScore(BaseModel):
    """One case, scored. Counts rather than rates, so they can be summed."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str
    family: CaseFamily
    proposed: int = Field(ge=0)
    correct: int = Field(ge=0)
    expected: int = Field(ge=0)
    #: Expected findings whose proposition appeared within the first
    #: three proposals. Three because a panel shows a handful and an
    #: analyst that buries the answer at rank nine has not found it.
    recalled_at_3: int = Field(ge=0)
    #: Of the proposals matching an expected proposition, how many named
    #: the right subject. Attribution is the part that misleads a reader,
    #: so it is scored apart from finding the mechanism at all.
    attribution_considered: int = Field(ge=0)
    attribution_correct: int = Field(ge=0)
    checkers_expected: int = Field(ge=0)
    checkers_requested: int = Field(ge=0)
    abstention_expected: bool = False
    abstention_given: bool = False
    structural_violations: int = Field(ge=0)


def score_case(case: PlantedCase, submission: CaseSubmission) -> CaseScore:
    """Grade one case against what was planted in it.

    Matching is on ``(proposition_type, subject)`` for attribution and on
    ``proposition_type`` alone for finding the mechanism, because those
    are two different questions and collapsing them hides which one an
    analyst is failing.
    """
    if submission.case_id != case.case_id:
        raise GoldenRefusal(
            f"submission for {submission.case_id!r} scored against case {case.case_id!r}"
        )

    proposals = submission.response.proposals
    expected_types = [finding.proposition_type for finding in case.expected_findings]
    expected_keys = {finding.key for finding in case.expected_findings}

    correct = sum(
        1
        for proposal in proposals
        if (proposal.proposition_type, proposal.proposed_subject) in expected_keys
    )
    top_three = {proposal.proposition_type for proposal in proposals[:3]}
    recalled = sum(1 for kind in set(expected_types) if kind in top_three)

    considered = [
        proposal for proposal in proposals if proposal.proposition_type in set(expected_types)
    ]
    attribution_correct = sum(
        1
        for proposal in considered
        if (proposal.proposition_type, proposal.proposed_subject) in expected_keys
    )

    asked = set(submission.requested_tool_ids)
    checkers_requested = sum(
        1 for tool_id in set(case.expected_checker_requests) if tool_id in asked
    )

    leaks = {
        proposal.proposition_type
        for proposal in proposals
        if proposal.proposition_type in set(case.forbidden_claims)
    }
    violations = (
        len(submission.contamination)
        + len(submission.unsupported_rendered_assertions)
        + len(submission.blocked_claim_leaks)
        + len(leaks)
    )

    return CaseScore(
        case_id=case.case_id,
        family=case.family,
        proposed=len(proposals),
        correct=correct,
        expected=len(expected_keys),
        recalled_at_3=recalled,
        attribution_considered=len(considered),
        attribution_correct=attribution_correct,
        checkers_expected=len(set(case.expected_checker_requests)),
        checkers_requested=checkers_requested,
        abstention_expected=case.expect_abstention,
        abstention_given=submission.response.abstained,
        structural_violations=violations,
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    """A rate, or ``None`` when nothing was asked.

    ``None`` rather than ``0.0`` or ``1.0``: a family with no abstention
    cases has no abstention rate, and inventing one either flatters or
    punishes an analyst for a question nobody put to it.
    """
    if denominator == 0:
        return None
    return numerator / denominator


class ScoreBoard(BaseModel):
    """Rates over a set of case scores, with the counts kept."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    n_cases: int = Field(ge=0)
    precision: float | None = None
    recall_at_3: float | None = None
    abstention: float | None = None
    component_attribution: float | None = None
    checker_selection: float | None = None
    structural_violations: int = Field(ge=0)

    @property
    def clean(self) -> bool:
        """No structural violation anywhere. The precondition for a pass."""
        return self.structural_violations == 0

    @property
    def measurements(self) -> dict[str, float | None]:
        """What a gate reads. ``None`` where the metric did not apply.

        Handed to :meth:`~planbench_explanation.bundle.MetricTargets.evaluate`,
        which turns ``None`` into a failing ``0.0``. The distinction is
        kept until that point because "no abstention case was put to it"
        and "it scored zero on abstention" are different facts, and only
        the scorer knows which one happened.
        """
        return {
            "structural_violations": float(self.structural_violations),
            "precision": self.precision,
            "recall_at_3": self.recall_at_3,
            "abstention": self.abstention,
            "component_attribution": self.component_attribution,
            "checker_selection": self.checker_selection,
        }


def _board(scores: Sequence[CaseScore]) -> ScoreBoard:
    return ScoreBoard(
        n_cases=len(scores),
        precision=_ratio(
            sum(score.correct for score in scores), sum(score.proposed for score in scores)
        ),
        recall_at_3=_ratio(
            sum(score.recalled_at_3 for score in scores),
            sum(score.expected for score in scores),
        ),
        abstention=_ratio(
            sum(1 for score in scores if score.abstention_expected and score.abstention_given),
            sum(1 for score in scores if score.abstention_expected),
        ),
        component_attribution=_ratio(
            sum(score.attribution_correct for score in scores),
            sum(score.attribution_considered for score in scores),
        ),
        checker_selection=_ratio(
            sum(score.checkers_requested for score in scores),
            sum(score.checkers_expected for score in scores),
        ),
        structural_violations=sum(score.structural_violations for score in scores),
    )


class SuiteScore(BaseModel):
    """A whole suite, micro and macro."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    suite_version: str
    #: Every case pooled. Dominated by the largest family, which is why
    #: it is not what thresholds are set against.
    micro: ScoreBoard
    #: Each family scored, then the families averaged. The reported one.
    macro: ScoreBoard
    by_family: dict[str, ScoreBoard]

    @property
    def clean(self) -> bool:
        return self.micro.clean


def _macro(boards: Sequence[ScoreBoard], *, n_cases: int, violations: int) -> ScoreBoard:
    """Average the family rates, skipping families a metric did not apply to."""

    def mean(name: str) -> float | None:
        values = [value for board in boards if (value := getattr(board, name)) is not None]
        if not values:
            return None
        return sum(values) / len(values)

    return ScoreBoard(
        n_cases=n_cases,
        precision=mean("precision"),
        recall_at_3=mean("recall_at_3"),
        abstention=mean("abstention"),
        component_attribution=mean("component_attribution"),
        checker_selection=mean("checker_selection"),
        structural_violations=violations,
    )


def score_suite(suite: GoldenSuite, submissions: Sequence[CaseSubmission]) -> SuiteScore:
    """Score every case in the suite. A missing submission is a failure.

    Not an omission: an analyst that returned nothing for a case is
    scored as having proposed nothing there, which costs it recall and
    abstention alike. Silently dropping the case would let a crash on
    the hard cases improve the score.
    """
    by_id = {submission.case_id: submission for submission in submissions}
    unknown = sorted(set(by_id) - {case.case_id for case in suite.cases})
    if unknown:
        raise GoldenRefusal(
            f"submission(s) for {unknown}, which are not in suite {suite.suite_version}"
        )

    scores = [
        score_case(
            case,
            by_id.get(
                case.case_id,
                CaseSubmission(
                    case_id=case.case_id,
                    response=AnalysisResponse(
                        analysis_run_id=f"missing-{case.case_id}",
                        analyst_bundle_id="missing",
                    ),
                ),
            ),
        )
        for case in suite.cases
    ]
    families = sorted({score.family for score in scores})
    by_family = {
        family: _board([score for score in scores if score.family == family]) for family in families
    }
    micro = _board(scores)
    macro = _macro(
        list(by_family.values()),
        n_cases=len(scores),
        violations=micro.structural_violations,
    )
    return SuiteScore(
        suite_version=suite.suite_version,
        micro=micro,
        macro=macro,
        by_family=by_family,
    )


#: The bar lives in :mod:`planbench_explanation.bundle`, beside the gate
#: decision it judges, and is re-exported here because the scorer is
#: where most callers meet it. One definition: a second copy would let a
#: suite be scored against thresholds a decision was never checked
#: against.
__all__ = [
    "CALIBRATION_TARGETS",
    "CASE_FAMILIES",
    "MAX_VARIANTS_PER_FAMILY",
    "MIN_VARIANTS_PER_FAMILY",
    "OFFICIAL_GOLDEN_READY",
    "CaseFamily",
    "CaseScore",
    "CaseSubmission",
    "ExpectedFinding",
    "GoldenRefusal",
    "GoldenSuite",
    "MetricTargets",
    "PlantedCase",
    "ScoreBoard",
    "SuiteScore",
    "VariantKind",
    "score_case",
    "score_suite",
]
