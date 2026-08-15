"""How far the recommendation can be pushed before it changes (HĐ-11.5).

Every number upstream of here answers "which candidate is best". This
module answers the question a reader should ask next, and usually cannot:
*how much of that answer came from the data, and how much from the two
sets of assumptions we typed in?*

**Why this is the project's answer to N1, not a nice-to-have.** Ask an
engineer "how much more does safety matter than travel time" and the
reply is a number invented in five seconds — which then decides who
wins. The escape is to stop asking. Instead of demanding the right
weight, report how far the wrong one can be from the truth without
changing the recommendation: *"A wins, and for B to overtake it the
safety weight would have to fall from 0.10 to below 0.03 — you would
have to care about safety three times less than you said."* A reader can
act on that without ever naming their own weights.

**Two assumptions, two sweeps, and they are not the same question.**

- ``weight_stability`` moves the *preferences* — what this deployment
  values. A margin here is about the user's own uncertainty.
- ``anchor_stability`` moves the *scales* — what counts as a good
  clearance or a bad latency. A margin here is about ours. HĐ-8.3 law 3
  demands it of every decision, because anchors are an assumption like
  any other and one that the user never sees.

**Nothing is recomputed by hand.** Both sweeps re-run the real scoring
pipeline (``build_evidence`` then ``recommend``) with one input changed.
A second implementation of the utility that "just" applied new weights to
stored objectives would be a copy of the formula, and the two copies
would drift — the failure this codebase has already had to fix once, in
the pairing rule. The cost of doing it properly is small: the sweep never
touches the simulator, only arithmetic over metrics already on disk.

**The flip criterion is the recommended candidate, not the label.** A
run that stays on the same candidate but crosses from
``CLEAR_RECOMMENDATION`` to ``NEAR_EQUIVALENT`` has not changed its
advice, and reporting that as instability would make every margin look
worse than it is. Status changes are reported separately, on the side.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from planbench_decision.anchors import AnchorError, ResolvedAnchors
from planbench_decision.candidate import Candidate
from planbench_decision.objectives import DecisionSettings, PreferenceWeights
from planbench_decision.stats import Recommendation, build_evidence, recommend
from planbench_schemas.episode_context import EpisodeContext

if TYPE_CHECKING:  # pragma: no cover - import cycle, see gates.py
    from planbench_metrics.definitions import EpisodeMetricSet

__all__ = [
    "ANCHOR_SWEEP",
    "SENSITIVE_MARGIN",
    "WEIGHT_NAMES",
    "WEIGHT_SCAN_STEPS",
    "AnchorStability",
    "ScoredField",
    "SensitivityError",
    "WeightFlip",
    "WeightStability",
    "anchor_stability",
    "weight_stability",
]

#: The four objective weights, in the order HĐ-9.1 writes them.
WEIGHT_NAMES: tuple[str, ...] = ("w_r", "w_s", "w_e", "w_c")

#: HĐ-11.5: a recommendation that flips under a shift smaller than this
#: is labelled ``SENSITIVE_TO_PREFERENCES``.
SENSITIVE_MARGIN = 0.10

#: HĐ-8.3 law 3's shift, both directions.
ANCHOR_SWEEP = 0.10

#: Grid resolution of the weight scan before bisection refines it. The
#: scan exists because the recommendation is not guaranteed monotonic in
#: the shift — bisecting from the start could jump over a flip and report
#: stability that is not there. 40 steps puts the grid at 0.025, well
#: under the 0.10 threshold that matters, so a flip that would change the
#: label cannot hide between two samples.
WEIGHT_SCAN_STEPS = 40

#: Bisection stops here. Finer than the reader can act on; coarser than
#: the float noise that would make the bisection loop forever.
_BISECTION_TOLERANCE = 1e-4


class SensitivityError(ValueError):
    """A sweep that could not be run, or could not mean what it claims."""


@dataclass(frozen=True)
class ScoredField:
    """The candidates of one run, re-scorable under changed assumptions.

    Holds metrics and contexts rather than scores, because that is the
    point: a sweep needs to run the scoring again, and anything already
    reduced to a utility has the old weights baked into it.

    Only gate survivors belong here. A candidate eliminated at a gate
    does not come back when the weights move — gates run before scoring
    and are not a matter of preference (HĐ-7) — so including one would
    let a sweep report a "flip" to a candidate that was never eligible.
    :meth:`from_survivors` is the constructor that enforces that, and the
    one callers should use.

    A dataclass rather than a model: every field is an already-validated
    object from an earlier phase, and re-validating an ``EpisodeMetricSet``
    once per sweep step would cost more than the sweep.
    """

    candidates: tuple[Candidate, ...]
    metrics: Mapping[str, Sequence[EpisodeMetricSet]]
    contexts: tuple[EpisodeContext, ...]

    @classmethod
    def from_survivors(
        cls,
        candidates: Sequence[Candidate],
        metrics: Mapping[str, Sequence[EpisodeMetricSet]],
        contexts: Sequence[EpisodeContext],
        passed: Mapping[str, bool],
    ) -> ScoredField:
        """Keep only the candidates that cleared every gate (HĐ-7)."""
        survivors = tuple(c for c in candidates if passed.get(c.candidate_id, False))
        if len(survivors) < 2:
            raise SensitivityError(
                f"a stability sweep needs at least two candidates that cleared the gates, got "
                f"{len(survivors)}; with one there is nothing the recommendation could flip to"
            )
        missing = sorted(c.candidate_id for c in survivors if c.candidate_id not in metrics)
        if missing:
            raise SensitivityError(f"no metrics for candidate(s) {missing}")
        return cls(
            candidates=survivors,
            metrics={c.candidate_id: tuple(metrics[c.candidate_id]) for c in survivors},
            contexts=tuple(contexts),
        )

    def recommend_under(
        self, anchors: ResolvedAnchors, settings: DecisionSettings, *, seed: int
    ) -> Recommendation:
        """Re-run the real pipeline with these assumptions."""
        evidence = [
            build_evidence(
                candidate,
                self.metrics[candidate.candidate_id],
                self.contexts,
                anchors,
                settings,
            )
            for candidate in self.candidates
        ]
        return recommend(evidence, seed=seed)


class WeightFlip(BaseModel):
    """The nearest point at which the advice changes, in the user's terms.

    Reported as the weight's *value* at the flip rather than only as a
    distance, because the sentence a reader can act on is "safety would
    have to fall below 0.03", not "the margin is 0.7".
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    weight: str
    direction: str
    original_value: float
    flip_value: float
    #: Fraction of the way from the declared weights to the extreme.
    shift: float = Field(ge=0.0, le=1.0)
    new_recommended_id: str

    @property
    def sentence(self) -> str:
        """The N1 sentence, ready to print."""
        verb = "giảm" if self.direction == "down" else "tăng"
        return (
            f"Để {self.new_recommended_id} lật ngược khuyến nghị, trọng số {self.weight} phải "
            f"{verb} từ {self.original_value:.2f} tới {self.flip_value:.2f}"
        )


class WeightStability(BaseModel):
    """HĐ-11.5's ``weight_stability_margin`` and what produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    recommended_id: str
    #: Smallest shift that flips the advice; 1.0 when nothing does, which
    #: is a real statement: even zeroing or maximising a single weight
    #: leaves the same recommendation.
    margin: float = Field(ge=0.0, le=1.0)
    nearest_flip: WeightFlip | None
    #: Every direction that flipped, for a UI that wants to show the
    #: whole picture rather than only the closest edge.
    flips: tuple[WeightFlip, ...] = ()

    @property
    def is_sensitive(self) -> bool:
        return self.margin < SENSITIVE_MARGIN

    @property
    def label(self) -> str | None:
        """HĐ-11.5's warning label, or ``None`` when it does not apply."""
        return "SENSITIVE_TO_PREFERENCES" if self.is_sensitive else None


class AnchorStability(BaseModel):
    """HĐ-8.3 law 3 / HĐ-11.5: does our own scale choice decide this?"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommended_id: str
    changed_at: tuple[str, ...]
    #: The shift actually applied. Carried rather than assumed so the
    #: verdict string cannot say ``±10%`` about a sweep that was not 10%
    #: — a card field that misreports its own experiment is worse than
    #: one that is absent.
    sweep: float = Field(gt=0.0)

    @property
    def verdict(self) -> str:
        """The string HĐ-12 prints in ``evidence.anchor_stability``.

        At the contract's own ±10% this reads exactly as HĐ-12's example
        writes it, ``unchanged_at_±10%``.
        """
        if self.changed_at:
            return f"changed_at_{'_and_'.join(self.changed_at)}"
        return f"unchanged_at_±{self.sweep:.0%}"


def weight_stability(
    field: ScoredField,
    anchors: ResolvedAnchors,
    settings: DecisionSettings | None = None,
    *,
    seed: int = 0,
) -> WeightStability:
    """How far the weights can move before the advice does (HĐ-11.5).

    Each of the four weights is walked toward both of its extremes — 0,
    and 1 with the others driven to 0 — with the remaining three kept in
    their declared proportions so the vector always sums to 1. Anything
    else would change two assumptions at once and make the answer
    unattributable.

    ``shift`` is the fraction of that walk, so 0 is the declared weights
    and 1 is the extreme. The margin is the smallest shift over all eight
    directions that changes the recommended candidate, and 1.0 when none
    of them does.
    """
    settings = settings or DecisionSettings()
    baseline = field.recommend_under(anchors, settings, seed=seed).recommended_id

    flips: list[WeightFlip] = []
    for name in WEIGHT_NAMES:
        for direction in ("down", "up"):
            flip = _scan_one_direction(
                field, anchors, settings, name, direction, baseline, seed=seed
            )
            if flip is not None:
                flips.append(flip)

    flips.sort(key=lambda item: (item.shift, item.weight, item.direction))
    nearest = flips[0] if flips else None
    return WeightStability(
        recommended_id=baseline,
        margin=nearest.shift if nearest is not None else 1.0,
        nearest_flip=nearest,
        flips=tuple(flips),
    )


def anchor_stability(
    field: ScoredField,
    anchors: ResolvedAnchors,
    settings: DecisionSettings | None = None,
    *,
    seed: int = 0,
    sweep: float = ANCHOR_SWEEP,
) -> AnchorStability:
    """Does our own choice of scale decide this (HĐ-8.3 law 3)?

    **One metric at a time, not all at once.** The law is written as
    "shift every anchor ±10%", and taken literally that check cannot
    fail. With ``bad' = good + (bad - good)·f`` every ``u`` maps by the
    same affine function ``u ↦ 1 - (1-u)/f``; the decision utility is a
    convex combination of ``u`` values so it maps identically; and a
    strictly increasing map applied to every candidate alike leaves the
    order untouched. A uniform sweep returns "unchanged" on any input
    whatsoever, which is not evidence — it is arithmetic.

    So each anchored metric is swept on its own, which is the same shape
    as the weight sweep and for the same reason: one assumption moves at
    a time, so a flip can be attributed to it. What comes back is not
    just *whether* our scales decided the outcome but *which one* did,
    and that is the actionable form — "the recommendation turns on where
    we drew the line for latency" is something a reader can argue with.

    The shift itself is a change of *width*: ``good`` holds still and
    ``bad`` moves. Scaling both ends instead translates the scale off the
    domain of any metric bounded at 1.0 — ``success_rate`` at
    ``{1.00, 0.95}`` became ``{1.10, 1.045}``, every real rate clipped to
    0, and ``U_R`` went dead for the whole field while the sweep happily
    reported "unchanged".
    """
    settings = settings or DecisionSettings()
    baseline = field.recommend_under(anchors, settings, seed=seed).recommended_id

    changed: list[str] = []
    for metric in sorted(anchors.anchors):
        for factor, sign in ((1.0 + sweep, "+"), (1.0 - sweep, "-")):
            shifted = anchors.scaled(factor, only=metric)
            try:
                moved = field.recommend_under(shifted, settings, seed=seed).recommended_id
            except AnchorError as exc:  # pragma: no cover - defensive
                raise SensitivityError(
                    f"anchors with {metric} shifted by {sign}{sweep:.0%} could not score the "
                    f"field: {exc}"
                ) from exc
            if moved != baseline:
                changed.append(f"{metric}{sign}{sweep:.0%}")

    return AnchorStability(
        recommended_id=baseline,
        changed_at=tuple(changed),
        sweep=sweep,
    )


def _scan_one_direction(
    field: ScoredField,
    anchors: ResolvedAnchors,
    settings: DecisionSettings,
    name: str,
    direction: str,
    baseline: str,
    *,
    seed: int,
) -> WeightFlip | None:
    """Grid-scan one weight toward one extreme, then bisect the crossing.

    Scan first, bisect second, and not the other way round: the
    recommendation is a step function of the shift with no guarantee of a
    single crossing, so bisecting from the start could step over a flip
    and report stability that does not exist. The grid bounds what can be
    missed; the bisection only sharpens a crossing the grid already
    found.
    """
    declared = settings.weights
    original_value = getattr(declared, name)

    def recommended_at(shift: float) -> str:
        moved = _shifted_weights(declared, name, direction, shift)
        swept = settings.with_weights(moved)
        return field.recommend_under(anchors, swept, seed=seed).recommended_id

    previous = 0.0
    for step in range(1, WEIGHT_SCAN_STEPS + 1):
        shift = step / WEIGHT_SCAN_STEPS
        if recommended_at(shift) == baseline:
            previous = shift
            continue

        low, high = previous, shift
        while high - low > _BISECTION_TOLERANCE:
            middle = (low + high) / 2.0
            if recommended_at(middle) == baseline:
                low = middle
            else:
                high = middle
        flipped = _shifted_weights(declared, name, direction, high)
        return WeightFlip(
            weight=name,
            direction=direction,
            original_value=original_value,
            flip_value=getattr(flipped, name),
            shift=high,
            new_recommended_id=recommended_at(high),
        )
    return None


def _shifted_weights(
    declared: PreferenceWeights, name: str, direction: str, shift: float
) -> PreferenceWeights:
    """Move one weight ``shift`` of the way to its extreme, renormalised.

    The other three keep their proportions to each other, so the sweep
    varies exactly one thing. When they sum to zero — the declared vector
    put everything on this one weight — they are spread evenly instead,
    which is the only choice that does not invent a preference ordering
    the user never expressed.
    """
    if not 0.0 <= shift <= 1.0:
        raise SensitivityError(f"weight shift must be in [0, 1], got {shift}")

    current = getattr(declared, name)
    target = 0.0 if direction == "down" else 1.0
    moved = current + (target - current) * shift

    others = [other for other in WEIGHT_NAMES if other != name]
    rest = 1.0 - moved
    total_others = sum(getattr(declared, other) for other in others)
    if total_others > 0.0:
        values = {other: getattr(declared, other) / total_others * rest for other in others}
    else:
        values = {other: rest / len(others) for other in others}
    values[name] = moved

    # The four now sum to 1 up to float noise; PreferenceWeights checks
    # that to 1e-9 and the arithmetic above lands well inside it.
    return PreferenceWeights(beta=declared.beta, **values)
