"""Scoring one round against the labels — the scorer's side of B1.

Everything here reads the label file, and nothing here ever reaches the
analyst: that separation is W0's, and it is the reason the labels live
in ``fixtures/golden/labels/`` rather than in the packet. What this
module adds is the arithmetic — how a round becomes the endpoints the
preregistration named, and what each of them refuses to count.

The rules that decide whether a number means anything:

**The primary endpoint is case-level and takes the worst repeat.** A
case is correct when *every* repeat got the mechanism right. Averaging
over repeats would let a model that is right two times in three report
0.67 on a case a reader would call unreliable, and reliability is a
different endpoint with its own number.

**A claim about the wrong component is not a correct mechanism.** They
are two secondary endpoints and one primary; a mechanism scored without
its subject would credit "something in the stack is starved" as an
answer.

**Abstention is scored against what the label expected**, not against
whether an answer would have been right. A round that declines a case
the labels say is answerable is wrong in a way that looks safe, and one
that answers a case the labels say has no answer is wrong in a way that
looks useful.

**Nothing is scored on a draft.** A ``CheckPlan`` statement exists only
because the host binds evidence to a declared hypothesis; scoring it
would score a sentence written before its evidence arrived.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from planbench_analyst.eval_spec import CaseLabels, refs_satisfy
from planbench_analyst.packet_view import PacketView
from planbench_analyst.runner import RoundOutcome

__all__ = ["CaseScore", "RepeatScore", "score_case", "score_repeat"]


@dataclass(frozen=True)
class RepeatScore:
    """One run of one case, against that case's labels."""

    case_id: str
    mechanism_correct: bool
    subject_correct: bool
    evidence_relevant: bool
    tool_acceptable: bool
    abstention_correct: bool
    structural_violations: int
    #: Whether a checker actually returned a verdict on this round. The
    #: verified rate is a separate endpoint: an analyst can be right and
    #: unverified, and the two must not be added together.
    verified: bool
    stopped_because: str
    input_tokens: int
    output_tokens: int
    model_calls: int

    @property
    def cost_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class CaseScore:
    """One case across its repeats, as the endpoints are read."""

    case_id: str
    repeats: tuple[RepeatScore, ...]

    @property
    def mechanism_correct(self) -> bool:
        """Every repeat, not most of them. The worst repeat is the case."""
        return bool(self.repeats) and all(item.mechanism_correct for item in self.repeats)

    @property
    def subject_correct(self) -> bool:
        return bool(self.repeats) and all(item.subject_correct for item in self.repeats)

    @property
    def abstention_correct(self) -> bool:
        return bool(self.repeats) and all(item.abstention_correct for item in self.repeats)

    @property
    def stable(self) -> bool:
        """Whether the repeats agreed with each other at all.

        Reported beside correctness because "wrong every time" and
        "right once out of three" are different problems, and only the
        second one is a reliability problem.
        """
        return len({item.mechanism_correct for item in self.repeats}) == 1

    @property
    def structural_violations(self) -> int:
        return sum(item.structural_violations for item in self.repeats)

    @property
    def median_tokens(self) -> float:
        values = sorted(item.cost_tokens for item in self.repeats)
        if not values:
            return 0.0
        middle = len(values) // 2
        if len(values) % 2:
            return float(values[middle])
        return (values[middle - 1] + values[middle]) / 2.0


def score_repeat(
    case_id: str,
    outcome: RoundOutcome,
    label: CaseLabels | None,
    view: PacketView,
) -> RepeatScore:
    """One round, scored. A case with no label is scored as unanswerable.

    A missing label is **not** treated as "anything passes": the round
    is recorded with every correctness field false, so a suite that
    quietly lost its labels reports zero rather than a perfect score.
    """
    response = outcome.response
    # Only final proposals are scored. A draft is a sentence written
    # before its evidence arrived, and the round's own transcript is
    # what says which is which.
    finals = [proposal for proposal in response.proposals if not proposal.requested_checks]
    blocked = len(outcome.guard.blocked)

    if label is None:
        return RepeatScore(
            case_id=case_id,
            mechanism_correct=False,
            subject_correct=False,
            evidence_relevant=False,
            tool_acceptable=False,
            abstention_correct=False,
            structural_violations=blocked,
            verified=False,
            stopped_because=outcome.stopped_because,
            input_tokens=outcome.cost.input_tokens,
            output_tokens=outcome.cost.output_tokens,
            model_calls=outcome.cost.model_calls,
        )

    abstained = response.abstained or not finals
    abstention_correct = abstained == label.expect_abstention

    mechanism_correct = False
    subject_correct = False
    evidence_relevant = False
    if not abstained and not label.expect_abstention:
        for proposal in finals:
            if proposal.proposition_type != label.expected_mechanism:
                continue
            mechanism_correct = True
            if label.expected_subject in ("", None) or (
                proposal.proposed_subject == label.expected_subject
            ):
                subject_correct = True
            if refs_satisfy(proposal.supports, label, view):
                evidence_relevant = True
            break

    # Tool acceptability is read over the whole round rather than over
    # the surviving proposal: a check that was asked for and refused is
    # still the analyst having chosen a tool, and the refusal is counted
    # elsewhere as a routing failure.
    asked = {
        check.tool_id
        for proposal in response.proposals
        for check in proposal.requested_checks
    }
    tool_acceptable = (
        not label.acceptable_tools
        or not asked
        or bool(asked & set(label.acceptable_tools))
    )

    verified = any(
        result.execution_status == "completed" and result.proposition_verdict is not None
        for result in outcome.results
    )

    return RepeatScore(
        case_id=case_id,
        mechanism_correct=mechanism_correct,
        subject_correct=subject_correct,
        evidence_relevant=evidence_relevant,
        tool_acceptable=tool_acceptable,
        abstention_correct=abstention_correct,
        structural_violations=blocked,
        verified=verified,
        stopped_because=outcome.stopped_because,
        input_tokens=outcome.cost.input_tokens,
        output_tokens=outcome.cost.output_tokens,
        model_calls=outcome.cost.model_calls,
    )


def score_case(case_id: str, repeats: Sequence[RepeatScore]) -> CaseScore:
    return CaseScore(case_id=case_id, repeats=tuple(repeats))
