"""Paired statistics and the recommendation label (CONTRACTS HĐ-11).

Everything upstream produced numbers. This module answers the only
question the platform exists to answer — *is the leader actually better,
or does it just have the higher number?* — and it answers it in the one
way the data supports.

**Paired, always.** Both candidates ran the same episode contexts (HĐ-3.2),
so the difference is taken *within* each context before anything is
averaged. Map layout, mission, traffic realisation and seed are then
identical on both sides of the subtraction and cancel; what is left is the
candidate. Comparing two independent means over the same runs would throw
that away and inflate the variance with between-episode noise that both
candidates saw equally.

**The refusal comes before the number.** If the context sets differ at
all, :func:`~planbench_decision.pairing.require_shared_contexts` raises
and no ΔU is produced. A ΔU over mismatched contexts is not a noisy
answer, it is an answer to a different question, and by the time it is on
a card the caveat has fallen off.

**"Overlapping CIs" is never how a tie is called.** §17 ban 5. Two
candidates' individual confidence intervals can overlap while the paired
difference is decisively non-zero — that is the normal case when both are
buffeted by the same episode-to-episode variance. The label reads the CI
of the *difference* and nothing else.

**A tie still returns one recommendation.** ``NEAR_EQUIVALENT`` does not
mean "pick either": HĐ-11.3 fixes four secondary criteria, declared in
advance and applied in order, so the tie-break cannot be reverse-
engineered after seeing which candidate it favours.

**No bare p-values.** HĐ-11.3 forbids reporting one without an effect
size; this module computes no p-value at all, and reports median, IQR,
CI95 and a paired effect size instead.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_decision.anchors import ResolvedAnchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import (
    DecisionSettings,
    ObjectiveBreakdown,
    episode_objectives,
    set_objectives,
)
from planbench_decision.pairing import require_shared_context_ids
from planbench_schemas.episode_context import EpisodeContext

if TYPE_CHECKING:  # pragma: no cover - import cycle, see gates.py
    from planbench_metrics.definitions import EpisodeMetricSet

__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "DEGENERATE_SPREAD",
    "TIE_BREAK_ORDER",
    "CandidateEvidence",
    "PairedComparison",
    "Recommendation",
    "RecommendationStatus",
    "StatisticsRefusal",
    "build_evidence",
    "compare_pair",
    "recommend",
]

RecommendationStatus = Literal["CLEAR_RECOMMENDATION", "NEAR_EQUIVALENT"]

#: Spread below which the differences count as identical. Utilities live
#: in [0, 1], so a standard deviation of 1e-12 is not measured
#: variability — it is what is left over from subtracting the same two
#: floats thirty times, which lands around 1e-17 rather than on zero.
#: Testing ``spread == 0.0`` would therefore never fire, and the effect
#: size would be reported as 2e+15: a number that looks like overwhelming
#: evidence and is actually a division by rounding error.
DEGENERATE_SPREAD = 1e-12

#: HĐ-11.2's resample count. Fixed rather than tuned: the CI is part of a
#: reproducible artefact (HĐ-13), so the number of resamples is one of the
#: things that has to be the same when somebody rebuilds the card.
BOOTSTRAP_RESAMPLES = 1000

#: HĐ-11.3, in order. Declared here as data so the card can print the
#: ladder it climbed, and so nobody can reorder it after seeing which
#: candidate each rung favours.
TIE_BREAK_ORDER: tuple[str, ...] = (
    "U_C cao hơn (rẻ hơn)",
    "IQR của decision_utility nhỏ hơn (ổn định hơn)",
    "n_tunable_params ít hơn (dễ bảo trì hơn)",
    "type = modular được ưu tiên hơn monolithic",
)


class StatisticsRefusal(ValueError):
    """The evidence on hand cannot support the statistic requested."""


class CandidateEvidence(BaseModel):
    """One candidate's scored episodes, ready to be compared.

    Holds both aggregation levels of HĐ-9.1 because they answer different
    questions and neither substitutes for the other: ``set_objectives``
    is what the card prints and what ranks the field,
    ``episode_utilities`` is what the paired bootstrap resamples.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate: Candidate
    set_objectives: ObjectiveBreakdown
    #: ``episode_context_id`` → ``decision_utility`` for that episode.
    episode_utilities: dict[str, float]

    @model_validator(mode="after")
    def _validate(self) -> CandidateEvidence:
        if not self.episode_utilities:
            raise StatisticsRefusal(
                f"candidate {self.candidate.candidate_id} has no scored episodes"
            )
        if self.set_objectives.candidate_id != self.candidate.candidate_id:
            raise StatisticsRefusal(
                f"set objectives belong to {self.set_objectives.candidate_id} but the "
                f"candidate is {self.candidate.candidate_id}"
            )
        if self.set_objectives.level != "set":
            raise StatisticsRefusal(
                "the ranking and the card need set-level objectives; episode-level U_R "
                "ignores the deployment's declared success floor (HĐ-9.1)"
            )
        return self

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    @property
    def contexts(self) -> tuple[str, ...]:
        return tuple(sorted(self.episode_utilities))

    @property
    def utility_iqr(self) -> float:
        """Spread of this candidate's per-episode utility — tie-break 2.

        A candidate whose utility swings wildly across episodes is a
        worse bet at equal average than one that does the same thing
        every time, and this is where that preference is stated.
        """
        values = np.asarray([self.episode_utilities[c] for c in self.contexts], dtype=float)
        return float(np.percentile(values, 75) - np.percentile(values, 25))


class PairedComparison(BaseModel):
    """``ΔU = U(A) − U(B)`` with its paired bootstrap CI (HĐ-11.2).

    Reports exactly what HĐ-11.3 requires as a minimum — median, IQR,
    CI95, effect size, n — and no p-value, which that section forbids
    reporting without an effect size anyway.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_a: str
    candidate_b: str
    n_episodes: int = Field(ge=1)
    delta_median: float
    delta_mean: float
    delta_iqr: float = Field(ge=0.0)
    ci95: tuple[float, float]
    #: Paired Cohen's d_z. ``None`` when every episode gave the identical
    #: difference: the standardised effect divides by a spread of zero and
    #: is undefined, and inventing ``inf`` would put a number where the
    #: data has none.
    effect_size: float | None
    n_resamples: int = Field(ge=1)
    seed: int

    @property
    def excludes_zero(self) -> bool:
        """Whether the CI of the difference is entirely on one side of 0."""
        low, high = self.ci95
        return low > 0.0 or high < 0.0

    @property
    def status(self) -> RecommendationStatus:
        return "CLEAR_RECOMMENDATION" if self.excludes_zero else "NEAR_EQUIVALENT"


class Recommendation(BaseModel):
    """One recommendation, its runner-up, and why it won (HĐ-11.3).

    ``tie_break_reason`` is populated only for ``NEAR_EQUIVALENT``, where
    the leader on raw utility is not automatically the recommendation:
    the declared ladder decides, and it may hand the decision to the
    other candidate. Saying which rung settled it is the difference
    between a recommendation and an assertion.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    status: RecommendationStatus
    recommended_id: str
    runner_up_id: str
    ranking: tuple[str, ...]
    comparison: PairedComparison
    tie_break_reason: str | None = None


def build_evidence(
    candidate: Candidate,
    metrics: Sequence[EpisodeMetricSet],
    contexts: Sequence[EpisodeContext],
    anchors: ResolvedAnchors,
    settings: DecisionSettings | None = None,
) -> CandidateEvidence:
    """Score one candidate's episodes at both aggregation levels.

    ``contexts`` is taken alongside the metrics so the sample-set rule of
    HĐ-11.4 is enforced by the same call that produces the numbers: a
    utility computed over neighborhood episodes would be resampled later
    as if those runs were independent draws, which they are not.
    """
    settings = settings or DecisionSettings()
    if not metrics:
        raise StatisticsRefusal(f"candidate {candidate.candidate_id} has no episodes")

    known = {context.episode_context_id for context in contexts}
    unknown = sorted({m.episode_context_id for m in metrics} - known)
    if unknown:
        raise StatisticsRefusal(
            f"episode(s) {unknown[:3]} of candidate {candidate.candidate_id} have no matching "
            "context; a paired comparison keys on the context, so an episode without one "
            "cannot take part"
        )

    utilities: dict[str, float] = {}
    for metric in metrics:
        if metric.episode_context_id in utilities:
            raise StatisticsRefusal(
                f"context {metric.episode_context_id} appears twice for candidate "
                f"{candidate.candidate_id}; the bootstrap resamples contexts, and a repeated "
                "condition would be drawn as two independent episodes"
            )
        utilities[metric.episode_context_id] = episode_objectives(
            metric, anchors, candidate, settings
        ).decision_utility

    return CandidateEvidence(
        candidate=candidate,
        set_objectives=set_objectives(metrics, anchors, candidate, settings),
        episode_utilities=utilities,
    )


def compare_pair(
    a: CandidateEvidence,
    b: CandidateEvidence,
    *,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
) -> PairedComparison:
    """Paired bootstrap of ``U(a) − U(b)`` over the shared contexts.

    Resampling is over **episode contexts**, not over individual metrics
    (HĐ-11.2): an episode is the unit that was drawn, and resampling
    metrics separately would break the pairing that makes the difference
    meaningful in the first place.

    Deterministic given ``seed``. HĐ-15.1 criterion 2 asks that rebuilding
    from a manifest reproduces the same card to six decimals, and a
    bootstrap seeded from the clock cannot do that — so the seed is an
    argument, defaulted, and recorded on the result.
    """
    if a.candidate_id == b.candidate_id:
        raise StatisticsRefusal(
            f"candidate {a.candidate_id} cannot be compared with itself; ΔU would be 0 by "
            "construction and the CI would claim it was measured"
        )
    if n_resamples < 1:
        raise StatisticsRefusal(f"n_resamples must be positive, got {n_resamples}")

    shared = require_shared_context_ids({a.candidate_id: a.contexts, b.candidate_id: b.contexts})
    deltas = np.asarray(
        [a.episode_utilities[c] - b.episode_utilities[c] for c in shared], dtype=float
    )

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(deltas), size=(n_resamples, len(deltas)))
    boot_means = deltas[indices].mean(axis=1)
    low, high = np.percentile(boot_means, [2.5, 97.5])

    return PairedComparison(
        candidate_a=a.candidate_id,
        candidate_b=b.candidate_id,
        n_episodes=len(deltas),
        delta_median=float(np.median(deltas)),
        delta_mean=float(deltas.mean()),
        delta_iqr=float(np.percentile(deltas, 75) - np.percentile(deltas, 25)),
        ci95=(float(low), float(high)),
        effect_size=_paired_effect_size(deltas),
        n_resamples=n_resamples,
        seed=seed,
    )


def recommend(
    evidence: Sequence[CandidateEvidence],
    *,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
) -> Recommendation:
    """Rank the field, test the top two, and name one winner (HĐ-11.3).

    The ranking is on set-level ``decision_utility`` — the card's number.
    The *label* comes from the paired CI against the runner-up, and only
    from that: a large gap in the ranking means nothing if the difference
    is inside the noise, and a small one can still be decisive when every
    episode agrees.

    Only the top two are compared. That is what HĐ-11.3 defines the label
    against, and it is also all that a single recommendation needs;
    ranking the rest of the field against each other is HĐ-10's job
    (Pareto, phase 5.2), which labels rather than eliminates.
    """
    if len(evidence) < 2:
        raise StatisticsRefusal(
            "a recommendation needs at least two candidates: the card's status is defined "
            "by the confidence interval of ΔU against the runner-up (HĐ-11.3), and with one "
            "candidate there is no evidence that it is better than anything"
        )

    ranking = _ranked_ids(evidence)
    by_id = {item.candidate_id: item for item in evidence}
    leader, runner_up = by_id[ranking[0]], by_id[ranking[1]]
    comparison = compare_pair(leader, runner_up, seed=seed, n_resamples=n_resamples)

    if comparison.status == "CLEAR_RECOMMENDATION":
        return Recommendation(
            status="CLEAR_RECOMMENDATION",
            recommended_id=leader.candidate_id,
            runner_up_id=runner_up.candidate_id,
            ranking=ranking,
            comparison=comparison,
        )

    winner, reason = _break_the_tie(leader, runner_up)
    loser = runner_up if winner is leader else leader
    return Recommendation(
        status="NEAR_EQUIVALENT",
        recommended_id=winner.candidate_id,
        runner_up_id=loser.candidate_id,
        ranking=ranking,
        comparison=comparison,
        tie_break_reason=reason,
    )


def _ranked_ids(evidence: Sequence[CandidateEvidence]) -> tuple[str, ...]:
    """Candidates by set-level utility, ties broken by id.

    The id tie-break is not a judgement — it is what keeps the ranking
    reproducible when two candidates score identically, so that rebuilding
    from a manifest cannot pick a different runner-up on a different day.
    """
    duplicates = sorted(
        {
            item.candidate_id
            for item in evidence
            if sum(1 for other in evidence if other.candidate_id == item.candidate_id) > 1
        }
    )
    if duplicates:
        raise StatisticsRefusal(
            f"candidate(s) {duplicates} appear more than once in the field; the same "
            "configuration cannot be its own rival"
        )
    ordered = sorted(
        evidence,
        key=lambda item: (-item.set_objectives.decision_utility, item.candidate_id),
    )
    return tuple(item.candidate_id for item in ordered)


def _break_the_tie(
    leader: CandidateEvidence, runner_up: CandidateEvidence
) -> tuple[CandidateEvidence, str]:
    """HĐ-11.3's four criteria, in the declared order.

    Applied only when the paired CI contains zero. The order is fixed in
    :data:`TIE_BREAK_ORDER` and never re-derived from the data: a ladder
    chosen after seeing who it favours is not a tie-break, it is a
    justification.

    All four exhausted means the two are indistinguishable on every
    declared axis; the raw ranking then stands, which keeps the outcome
    reproducible rather than arbitrary.
    """
    for index, (value_a, value_b) in enumerate(
        (
            (leader.set_objectives.u_c, runner_up.set_objectives.u_c),
            (-leader.utility_iqr, -runner_up.utility_iqr),
            (
                -_tunable_params(leader),
                -_tunable_params(runner_up),
            ),
            (_modular_rank(leader), _modular_rank(runner_up)),
        )
    ):
        if value_a > value_b:
            return leader, TIE_BREAK_ORDER[index]
        if value_b > value_a:
            return runner_up, TIE_BREAK_ORDER[index]
    return leader, "hòa trên cả bốn tiêu chí phụ; giữ thứ hạng theo decision_utility"


def _tunable_params(item: CandidateEvidence) -> float:
    """Declared parameter count, or +∞ when it was never declared.

    Undeclared sorts *worst* on this rung rather than best. The rung
    rewards "fewer knobs to maintain", and a candidate that did not say
    how many it has has not earned that credit (HĐ-1.6).
    """
    tuning = item.candidate.tuning
    return math.inf if tuning is None else float(tuning.n_tunable_params)


def _modular_rank(item: CandidateEvidence) -> int:
    """HĐ-11.3 rung 4: modular over monolithic, for explainability."""
    return 1 if item.candidate.type == "modular" else 0


def _paired_effect_size(deltas: np.ndarray) -> float | None:
    """Paired Cohen's ``d_z``: mean difference over its own spread.

    The paired form is the right one here for the same reason the test
    is paired: the spread that matters is the spread *of the differences*,
    not the spread of either candidate's utility, most of which is the
    episode and cancels.

    Undefined — reported as ``None`` — when every episode gave exactly the
    same difference. That happens with deterministic planners on a static
    map, and it means the sample says nothing about variability rather
    than that the effect is infinite.
    """
    if len(deltas) < 2:
        return None
    spread = float(deltas.std(ddof=1))
    if spread <= DEGENERATE_SPREAD:
        return None
    return float(deltas.mean() / spread)
