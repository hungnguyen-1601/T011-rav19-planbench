"""Pareto labelling by non-inferiority (CONTRACTS HĐ-10).

If A is no worse than B on every objective and better on at least one,
then no non-negative weighting can put B ahead. Saying so is worth doing
for two reasons: scoring B is wasted, and — the one that matters — if the
weights are ever nudged, B can climb back up on a technicality.

**Label, never delete (HĐ-10.1).** Nobody disappears from the report. A
dominated candidate keeps its row, its score and its gate table; what it
loses is the right to be offered as the alternative.

**The rule is non-inferiority, and the two obvious alternatives are both
wrong.** The topic document records getting this wrong twice, in
opposite directions:

- *"A must beat B by ≥ ε on every objective"* is too strict. A single tie
  (``ΔU = 0``) switches the rule off even when A leads by 0.10 everywhere
  else, so the filter never fires.
- *"for every j, CI₉₅(ΔU_j) is not entirely below 0"* is too loose, and
  wrong in kind. It confuses **no evidence that A is worse** with
  **evidence that A is not worse**. With few episodes ``CI = [−0.30,
  +0.35]`` satisfies it while A may well be far worse on that objective.
  Less data would then mean *more* dominance claims, which is the most
  dangerous direction an elimination rule can fail in.

What is implemented is HĐ-10.2's form, on the lower bound of the paired
bootstrap CI:

    A dominates B  ⟺  ∀j: LCB₉₅(ΔU_j) ≥ −ε_j
                    ∧  ∃k: LCB₉₅(ΔU_k) >  +ε_k

Thin data widens every interval, drives every ``LCB`` down, and the rule
declines to conclude — which is the behaviour the contract asks every
elimination rule in this project to have: *if there were no data, what
would the rule do?* The answer must be "nothing".

**Three labels need two tests, not one.** "Not dominated" is not the same
claim as "on the frontier". A candidate nobody has been *shown* to
dominate might simply not have been measured enough. So
``PARETO_FRONTIER`` requires positive evidence that no rival dominates
it, established from the upper bound the same way dominance is
established from the lower one, and everything left over is
``UNCERTAIN_DOMINANCE``. With no data at all, every candidate lands
there — the contract's own acceptance test.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from planbench_decision.pairing import require_shared_context_ids
from planbench_decision.stats import (
    BOOTSTRAP_RESAMPLES,
    OBJECTIVE_NAMES,
    CandidateEvidence,
    paired_bootstrap_ci,
)

__all__ = [
    "DEFAULT_EPSILON",
    "MIN_EPISODES_FOR_DOMINANCE",
    "DominanceVerdict",
    "ObjectiveInterval",
    "ParetoError",
    "ParetoLabel",
    "ParetoReport",
    "choose_alternative",
    "compare_objectives",
    "dominance",
    "label_field",
    "require_labelled",
]

ParetoLabel = Literal["PARETO_FRONTIER", "LIKELY_DOMINATED", "UNCERTAIN_DOMINANCE"]

#: HĐ-10.2's tolerance, the same on all four objectives. It is a
#: *practical* indifference band, not a statistical one: a candidate 0.01
#: of utility behind on safety is not meaningfully worse, and treating it
#: as worse would keep obviously dominated candidates alive forever.
DEFAULT_EPSILON = 0.02

#: Paired episodes below which no dominance verdict is issued at all.
#:
#: Found by the contract's own acceptance test rather than reasoned to in
#: advance. A percentile bootstrap over ``n`` points can only produce
#: ``n`` distinct values, so its 2.5th percentile is not an estimate of a
#: tail — at ``n = 1`` every resample is the same point and the "95% CI"
#: is a zero-width interval around it. The rule then concludes dominance
#: from a single episode *with maximum confidence*, which is precisely
#: the direction HĐ-10.2 forbids: less data must never conclude more.
#:
#: The interval machinery cannot express this on its own, because "no
#: spread" and "no data" look identical to it — the same blind spot
#: :data:`~planbench_decision.stats.DEGENERATE_SPREAD` guards against in
#: the effect size. So the floor is declared instead of inferred, and
#: below it a verdict is neither dominance nor its refutation: it is
#: ``UNCERTAIN_DOMINANCE``, the label that means "not enough data".
MIN_EPISODES_FOR_DOMINANCE = 10


class ParetoError(ValueError):
    """A dominance claim the evidence cannot support."""


class ObjectiveInterval(BaseModel):
    """One objective's paired ΔU and where its 95% CI sits.

    Both bounds are kept. Dominance reads the lower one; establishing
    that a rival does *not* dominate reads the upper one, and a report
    that stored only ``lcb`` could do the first but never the second.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    objective: str
    delta_mean: float
    lcb: float
    ucb: float

    def non_inferior(self, epsilon: float) -> bool:
        """Evidence that A is not worse than B here by more than ε."""
        return self.lcb >= -epsilon

    def clearly_better(self, epsilon: float) -> bool:
        """Evidence that A is better than B here by more than ε."""
        return self.lcb > epsilon

    def clearly_worse(self, epsilon: float) -> bool:
        """Evidence that A is *worse* than B here by more than ε."""
        return self.ucb < -epsilon

    def not_clearly_better(self, epsilon: float) -> bool:
        """Evidence that A does not beat B here by more than ε.

        The upper-bound mirror of :meth:`clearly_better`, and what makes
        "no rival dominates this one" a claim rather than an absence.
        """
        return self.ucb <= epsilon


class DominanceVerdict(BaseModel):
    """Whether A dominates B, and the four intervals behind the answer."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_a: str
    candidate_b: str
    n_episodes: int = Field(ge=1)
    epsilon: float = Field(gt=0.0)
    intervals: tuple[ObjectiveInterval, ...]

    @property
    def underpowered(self) -> bool:
        """Too few paired episodes for either verdict to mean anything.

        See :data:`MIN_EPISODES_FOR_DOMINANCE`. Both :attr:`dominates`
        and :attr:`cannot_dominate` are false here, which is not a
        contradiction — it is the third label.
        """
        return self.n_episodes < MIN_EPISODES_FOR_DOMINANCE

    @property
    def dominates(self) -> bool:
        """HĐ-10.2, verbatim, once there is enough data to read it."""
        if self.underpowered:
            return False
        return all(item.non_inferior(self.epsilon) for item in self.intervals) and any(
            item.clearly_better(self.epsilon) for item in self.intervals
        )

    @property
    def cannot_dominate(self) -> bool:
        """Positive evidence that A does **not** dominate B.

        Dominance needs two things at once, so it is refuted by
        establishing that either fails:

        - B is clearly better somewhere, so the "no worse anywhere" half
          cannot hold; or
        - A is nowhere clearly better, so the "better somewhere" half
          cannot hold.

        The second clause is what lets two genuinely equivalent
        candidates, measured well, both reach the frontier: their
        intervals hug zero, neither beats the other by ε, and that is a
        finding rather than a shortage of data.

        Underpowered runs establish neither, which is what keeps that
        last sentence true: without the floor, a one-episode run would
        satisfy this clause trivially and put everybody on the frontier.
        """
        if self.underpowered:
            return False
        return any(item.clearly_worse(self.epsilon) for item in self.intervals) or all(
            item.not_clearly_better(self.epsilon) for item in self.intervals
        )

    @property
    def evidence_line(self) -> str:
        """One line naming the objectives that carried the verdict."""
        better = [i.objective for i in self.intervals if i.clearly_better(self.epsilon)]
        worse = [i.objective for i in self.intervals if i.clearly_worse(self.epsilon)]
        return (
            f"{self.candidate_a} vs {self.candidate_b} over {self.n_episodes} paired episodes: "
            f"better at {better or '—'}, worse at {worse or '—'} (ε = {self.epsilon})"
        )


class ParetoReport(BaseModel):
    """Every candidate's label, plus the comparisons that produced them."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    labels: dict[str, ParetoLabel]
    #: ``(a, b)`` → verdict, for every ordered pair that was compared.
    verdicts: dict[str, DominanceVerdict]
    epsilon: float = Field(gt=0.0)

    def label_of(self, candidate_id: str) -> ParetoLabel:
        if candidate_id not in self.labels:
            raise ParetoError(
                f"candidate {candidate_id} was not part of this Pareto analysis; labelling it "
                "from a different field would assert something unchecked"
            )
        return self.labels[candidate_id]

    @property
    def frontier(self) -> tuple[str, ...]:
        """The only candidates HĐ-12 lets the card offer as alternatives."""
        return tuple(
            sorted(cid for cid, label in self.labels.items() if label == "PARETO_FRONTIER")
        )

    def dominated_by(self, candidate_id: str) -> tuple[str, ...]:
        """Who has been shown to dominate this candidate, if anyone."""
        return tuple(
            sorted(
                verdict.candidate_a
                for verdict in self.verdicts.values()
                if verdict.candidate_b == candidate_id and verdict.dominates
            )
        )


def compare_objectives(
    a: CandidateEvidence,
    b: CandidateEvidence,
    *,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    epsilon: float = DEFAULT_EPSILON,
) -> DominanceVerdict:
    """Paired ΔU and its CI, objective by objective (HĐ-10.2).

    Paired on the episode context exactly as the head-to-head comparison
    is, and refusing on mismatched context sets for the same reason: a
    difference taken across different episodes answers a question nobody
    asked.

    Each objective gets its own bootstrap, seeded from ``seed`` plus the
    objective's position, so the four are not resampled identically —
    reusing one index matrix would correlate the four intervals in a way
    the data does not.
    """
    if a.candidate_id == b.candidate_id:
        raise ParetoError(
            f"candidate {a.candidate_id} cannot dominate itself; every ΔU would be 0 by "
            "construction and the intervals would claim it was measured"
        )
    if epsilon <= 0:
        raise ParetoError(
            f"epsilon must be positive, got {epsilon}; a zero tolerance makes every tie a "
            "difference and no two candidates would ever be non-inferior"
        )

    shared = require_shared_context_ids({a.candidate_id: a.contexts, b.candidate_id: b.contexts})

    intervals: list[ObjectiveInterval] = []
    for index, objective in enumerate(OBJECTIVE_NAMES):
        left, right = a.objective_series(objective), b.objective_series(objective)
        deltas = np.asarray([left[c] - right[c] for c in shared], dtype=float)
        lcb, ucb = paired_bootstrap_ci(deltas, seed=seed + index, n_resamples=n_resamples)
        intervals.append(
            ObjectiveInterval(
                objective=objective,
                delta_mean=float(deltas.mean()),
                lcb=lcb,
                ucb=ucb,
            )
        )

    return DominanceVerdict(
        candidate_a=a.candidate_id,
        candidate_b=b.candidate_id,
        n_episodes=len(shared),
        epsilon=epsilon,
        intervals=tuple(intervals),
    )


def dominance(
    a: CandidateEvidence,
    b: CandidateEvidence,
    *,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    epsilon: float = DEFAULT_EPSILON,
) -> bool:
    """Does A dominate B (HĐ-10.2)? Convenience over :func:`compare_objectives`."""
    return compare_objectives(a, b, seed=seed, n_resamples=n_resamples, epsilon=epsilon).dominates


def label_field(
    evidence: Sequence[CandidateEvidence],
    *,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    epsilon: float = DEFAULT_EPSILON,
) -> ParetoReport:
    """Label every candidate ``PARETO_FRONTIER`` / ``LIKELY_DOMINATED`` /
    ``UNCERTAIN_DOMINANCE`` (HĐ-10.1).

    Ordered pairs, both ways: dominance is not symmetric, and a report
    that only compared each unordered pair once would have to pick a
    direction, which is the direction of whoever sorted the list.

    A single candidate is labelled ``UNCERTAIN_DOMINANCE`` rather than
    ``PARETO_FRONTIER``. "Nobody dominates it" is trivially true with no
    rivals and would read on the card as an established finding.
    """
    verdicts: dict[str, DominanceVerdict] = {}
    for left in evidence:
        for right in evidence:
            if left.candidate_id == right.candidate_id:
                continue
            verdicts[_key(left.candidate_id, right.candidate_id)] = compare_objectives(
                left, right, seed=seed, n_resamples=n_resamples, epsilon=epsilon
            )

    labels: dict[str, ParetoLabel] = {}
    for item in evidence:
        rivals = [other for other in evidence if other.candidate_id != item.candidate_id]
        against = [verdicts[_key(rival.candidate_id, item.candidate_id)] for rival in rivals]
        if not against:
            labels[item.candidate_id] = "UNCERTAIN_DOMINANCE"
        elif any(verdict.dominates for verdict in against):
            labels[item.candidate_id] = "LIKELY_DOMINATED"
        elif all(verdict.cannot_dominate for verdict in against):
            labels[item.candidate_id] = "PARETO_FRONTIER"
        else:
            labels[item.candidate_id] = "UNCERTAIN_DOMINANCE"

    return ParetoReport(labels=labels, verdicts=verdicts, epsilon=epsilon)


def choose_alternative(
    report: ParetoReport,
    recommended_id: str,
    ranking: Sequence[str],
) -> str | None:
    """The card's ``alternative``: best frontier candidate that is not the
    recommendation (HĐ-12).

    Only ever a ``PARETO_FRONTIER`` candidate. The statistical runner-up
    is a different claim — it is whoever came second on one weighted sum,
    which may be a candidate that is worse on every objective at once.
    Offering that as "near-equivalent alternative" would invite a reader
    to switch to something the analysis can show is worse.

    ``None`` when the frontier holds nobody else, which is a real answer:
    there is no second option worth naming.
    """
    frontier = set(report.frontier) - {recommended_id}
    for candidate_id in ranking:
        if candidate_id in frontier:
            return candidate_id
    return None


def _key(a: str, b: str) -> str:
    return f"{a}->{b}"


def require_labelled(report: ParetoReport, candidate_ids: Mapping[str, object]) -> None:
    """Every scored candidate carries a label (HĐ-10.1: nobody vanishes)."""
    missing = sorted(set(candidate_ids) - set(report.labels))
    if missing:
        raise ParetoError(
            f"candidate(s) {missing} were scored but carry no Pareto label; HĐ-10.1 says "
            "nobody disappears from the report"
        )
