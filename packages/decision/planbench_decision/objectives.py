"""Four objectives and the Decision Utility (CONTRACTS HĐ-9).

Gates decided who may be considered. This module decides how good the
survivors are, by folding normalised metrics into four numbers —
reliability, safety, efficiency, cost — and then into one:

    decision_utility = w_R·U_R + w_S·U_S + w_E·U_E + w_C·U_C

The name is ``decision_utility`` everywhere, never ``score`` (HĐ-9.2).
Not a style preference: "score" invites the reading that the number is a
property of the planner, and it is not. It is a property of *this
planner under this deployment's weights* — change the preference profile
and the ranking legitimately changes, which is the whole thesis.

**Two aggregation levels, and they do not agree on U_R.** HĐ-9.1 needs
objectives per episode (a paired ΔU cannot exist otherwise, HĐ-11.1) and
HĐ-12 prints objectives for the whole evaluation set. Because ``u`` is
affine *with clipping*, the two coincide wherever no episode hits a clip
boundary — and diverge at U_R, where every episode hits one: ``success``
is 0 or 1, so the per-episode mean is just the success rate (0.967),
while the set level scores the success rate itself against the
customer's declared floor (``u(0.967) = 0.34`` at ``success_rate_min =
0.95``). 0.34 is the card's number, and the one the topic document works
out by hand in §6.2. Hence two functions with two names:
:func:`episode_objectives` feeds the statistics,
:func:`set_objectives` feeds the card.

**Anchors are exogenous and thresholds come from the profile.** Nothing
here chooses a scale; every ``u`` call goes through
:class:`~planbench_decision.anchors.ResolvedAnchors`, which was bound to
one deployment. The only numbers written in this module are the contract's
own weights, and those are data (a profile the user picks), not thresholds.

**Double counting is blocked structurally, not by convention.**
``travel_time_accounting`` picks exactly one home for travel time:
``efficiency`` keeps it in O3 as ``time_efficiency``; ``monetized_cost``
moves it to O4 and *removes* it from O3 (HĐ-9.3). Two settings, one
place, validated — never both, which §17 ban 9 forbids.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_decision.anchors import ResolvedAnchors
from planbench_decision.candidate import Candidate

if TYPE_CHECKING:  # pragma: no cover - import cycle, see gates.py
    from planbench_metrics.definitions import EpisodeMetricSet

__all__ = [
    "DEFAULT_BETA",
    "PREFERENCE_PROFILES",
    "WEIGHT_SUM_TOLERANCE",
    "AggregationLevel",
    "BusinessProfile",
    "DecisionMode",
    "DecisionSettings",
    "ObjectiveBreakdown",
    "ObjectiveError",
    "PreferenceWeights",
    "TravelTimeAccounting",
    "episode_objectives",
    "set_objectives",
]

DecisionMode = Literal["technical", "business_adjusted"]
TravelTimeAccounting = Literal["efficiency", "monetized_cost"]
AggregationLevel = Literal["episode", "set"]

#: Weights are user input written as decimals; 0.30 + 0.10 + 0.25 + 0.35
#: does not sum to exactly 1.0 in binary floating point.
WEIGHT_SUM_TOLERANCE = 1e-9

#: HĐ-9.1 default split of U_C over latency, memory, CPU and engineering
#: cost. Engineering cost carries as much weight as latency because it is
#: the axis the whole topic exists to make visible — a stack that needs
#: three person-days of tuning is not free just because the tuning
#: happened before the benchmark.
DEFAULT_BETA: tuple[float, float, float, float] = (0.30, 0.20, 0.20, 0.30)


class ObjectiveError(ValueError):
    """A utility that would be computed under rules other than stated."""


class BusinessProfile(BaseModel):
    """Declared money assumptions (HĐ-9.3, ``business_adjusted`` only).

    Every field here is *declared*, never measured, which is why the
    whole object is copied onto the card as ``declared_assumptions``: a
    reader has to be able to see which numbers came from the platform
    and which came from whoever filled in the form. The contract's own
    warning applies — this is a cost model with declared assumptions,
    and calling it "the real TCO" is banned language (§17 ban 10).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    engineer_cost_per_hour: float = Field(gt=0)
    deployment_horizon_missions: int = Field(gt=0)
    hardware_upgrade_cost: float = Field(ge=0)
    #: The unit the three figures above are in, and the unit
    #: ``constraints.cost_per_mission_max`` had better be in too. The
    #: platform never converts between currencies and never assumes one:
    #: it carries the string onto the card so the ceiling and the cost
    #: cannot be silently compared across units.
    currency: str = Field(min_length=1)

    def engineering_cost_per_mission(self, tuning_wall_clock_h: float) -> float:
        """One-off engineering effort amortised over the horizon (N3).

        The point of the whole mode, in one line: a one-off cost divided
        by the number of missions that will pay for it. Three
        person-days of tuning is 0.5 seconds per mission over 50,000
        missions and 432 seconds per mission over a 200-mission pilot,
        so the same candidates under the same weights can rank
        differently at different horizons. Adding hours to milliseconds
        without this division is the modelling error N3 exists to name.

        ``hardware_upgrade_cost`` rides along because it is the same kind
        of number: the one-off price of the subsystem a candidate needed
        at G6, paid once and used by every mission after.
        """
        one_off = tuning_wall_clock_h * self.engineer_cost_per_hour + self.hardware_upgrade_cost
        return one_off / self.deployment_horizon_missions


class PreferenceWeights(BaseModel):
    """One deployment's trade-off, as the four weights plus U_C's split.

    Weights are *not* thresholds and are not read from the task profile:
    the profile says what the site needs, the preference profile says
    what it values. Two sites with identical constraints can rank the
    same candidates differently, and that has to stay expressible —
    it is the argument that "the best planner" does not exist.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    w_r: float = Field(ge=0, le=1)
    w_s: float = Field(ge=0, le=1)
    w_e: float = Field(ge=0, le=1)
    w_c: float = Field(ge=0, le=1)
    beta: tuple[float, float, float, float] = DEFAULT_BETA

    @model_validator(mode="after")
    def _validate_sums(self) -> PreferenceWeights:
        total = self.w_r + self.w_s + self.w_e + self.w_c
        if not math.isclose(total, 1.0, abs_tol=WEIGHT_SUM_TOLERANCE):
            raise ObjectiveError(
                f"objective weights must sum to 1.0, got {total}; a utility built on "
                "weights that do not sum to one is not on the [0, 1] scale its anchors "
                "put every component on, and two candidates scored under different "
                "totals cannot be compared"
            )
        beta_total = sum(self.beta)
        if not math.isclose(beta_total, 1.0, abs_tol=WEIGHT_SUM_TOLERANCE):
            raise ObjectiveError(f"U_C weights (beta) must sum to 1.0, got {beta_total}")
        if any(value < 0 for value in self.beta):
            raise ObjectiveError(f"U_C weights (beta) must be non-negative, got {self.beta}")
        return self

    @property
    def uses_engineering_cost(self) -> bool:
        """Whether β4 gives engineering cost any weight at all."""
        return self.beta[3] > 0.0


def _renormalised_beta_without_engineering_cost() -> tuple[float, float, float, float]:
    """β with β4 dropped and the rest rescaled to sum to 1 (HĐ-9.1).

    Rescaling rather than leaving the total at 0.70 keeps U_C on the same
    [0, 1] scale as the other three objectives; without it a profile that
    ignores engineering cost would silently down-weight cost as a whole
    relative to every other profile.
    """
    b1, b2, b3, _ = DEFAULT_BETA
    total = b1 + b2 + b3
    return (b1 / total, b2 / total, b3 / total, 0.0)


#: HĐ-9.2's four defaults. ``measured_only`` is the profile for a report
#: that refuses to price anything the platform did not measure, so β4 = 0
#: and the remaining three are renormalised (HĐ-9.1).
PREFERENCE_PROFILES: dict[str, PreferenceWeights] = {
    "kho_ban_dem": PreferenceWeights(w_r=0.30, w_s=0.10, w_e=0.25, w_c=0.35),
    "benh_vien_gio_cao_diem": PreferenceWeights(w_r=0.25, w_s=0.50, w_e=0.10, w_c=0.15),
    "pilot_demo": PreferenceWeights(w_r=0.35, w_s=0.20, w_e=0.30, w_c=0.15),
    "measured_only": PreferenceWeights(
        w_r=0.30,
        w_s=0.25,
        w_e=0.25,
        w_c=0.20,
        beta=_renormalised_beta_without_engineering_cost(),
    ),
}


class DecisionSettings(BaseModel):
    """Everything about *how* to score, fixed before any number is made.

    Kept as one validated object rather than four arguments because the
    combinations are what is legal or not: ``monetized_cost`` outside
    business mode, or business mode with no declared assumptions, are
    both refusals — and refusing at construction means a run cannot get
    halfway through 300 episodes before finding out.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    preference_profile: str = "kho_ban_dem"
    decision_mode: DecisionMode = "technical"
    travel_time_accounting: TravelTimeAccounting = "efficiency"
    business_profile: BusinessProfile | None = None
    #: Weights that replace the named profile's, for the HĐ-11.5 stability
    #: sweep and nothing else. The named profile stays on the object so
    #: :attr:`profile_label` can say what was perturbed and from where —
    #: the same discipline :meth:`ResolvedAnchors.scaled` follows, and for
    #: the same reason: a result computed under moved weights must not be
    #: storable as a result under the declared ones.
    weights_override: PreferenceWeights | None = None

    @model_validator(mode="after")
    def _validate_combination(self) -> DecisionSettings:
        if self.preference_profile not in PREFERENCE_PROFILES:
            raise ObjectiveError(
                f"unknown preference profile {self.preference_profile!r}; known profiles are "
                f"{sorted(PREFERENCE_PROFILES)} (HĐ-9.2)"
            )
        if self.travel_time_accounting == "monetized_cost" and self.decision_mode != (
            "business_adjusted"
        ):
            raise ObjectiveError(
                "travel_time_accounting='monetized_cost' is only valid in "
                "decision_mode='business_adjusted': pricing travel time needs the declared "
                "money assumptions, and in technical mode there are none. Leaving it on "
                "would count travel time in O3 and O4 at once (§17 ban 9)"
            )
        if self.decision_mode == "business_adjusted" and self.business_profile is None:
            raise ObjectiveError(
                "decision_mode='business_adjusted' requires a business_profile; a card in "
                "this mode must list every assumption it was adjusted by (HĐ-9.3)"
            )
        if self.decision_mode == "technical" and self.business_profile is not None:
            raise ObjectiveError(
                "decision_mode='technical' means measured figures only, so a business_profile "
                "here would be carried but never used — and a reader would reasonably assume "
                "it was"
            )
        return self

    @property
    def weights(self) -> PreferenceWeights:
        return self.weights_override or PREFERENCE_PROFILES[self.preference_profile]

    @property
    def profile_label(self) -> str:
        """What to record as the preference profile of a run.

        A sweep run is not a run under the named profile, and storing it
        as one would let a card computed at ``w_S = 0.03`` be filed under
        ``benh_vien_gio_cao_diem``. Marked here rather than left to each
        caller to remember.
        """
        if self.weights_override is None:
            return self.preference_profile
        return f"{self.preference_profile} (perturbed)"

    def with_weights(self, weights: PreferenceWeights) -> DecisionSettings:
        """This deployment scored under different weights (HĐ-11.5)."""
        return self.model_copy(update={"weights_override": weights})

    @property
    def card_label(self) -> str:
        """The sentence HĐ-9.3 requires on the card for this mode."""
        if self.decision_mode == "technical":
            return "Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được"
        return "Đã hiệu chỉnh theo giả định kinh doanh do người dùng khai"


class ObjectiveBreakdown(BaseModel):
    """The four objectives and the utility they add up to.

    ``level`` travels with the numbers because the two levels are not
    interchangeable and differ at U_R (see the module docstring). A card
    that printed the episode level would be quoting a reliability figure
    that ignores the customer's declared floor.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    level: AggregationLevel
    candidate_id: str
    n_episodes: int = Field(ge=1)
    u_r: float = Field(ge=0.0, le=1.0)
    u_s: float = Field(ge=0.0, le=1.0)
    u_e: float = Field(ge=0.0, le=1.0)
    u_c: float = Field(ge=0.0, le=1.0)
    decision_utility: float = Field(ge=0.0, le=1.0)
    preference_profile: str
    decision_mode: DecisionMode

    def to_card(self) -> dict[str, float]:
        """The ``objectives`` block of a Decision Card (HĐ-12)."""
        return {"U_R": self.u_r, "U_S": self.u_s, "U_E": self.u_e, "U_C": self.u_c}


def episode_objectives(
    metric: EpisodeMetricSet,
    anchors: ResolvedAnchors,
    candidate: Candidate,
    settings: DecisionSettings | None = None,
) -> ObjectiveBreakdown:
    """Objectives for one episode — the input to a paired ΔU (HĐ-11.1).

    ``U_R`` here is 0 or 1: a single episode either reached the goal or
    did not, and ``u`` of a binary variable clips to the ends. That is
    correct at this level and wrong at the card's level, which is why
    :func:`set_objectives` exists separately.

    The candidate-constant part of ``U_C`` (engineering cost) contributes
    the same amount to every episode of a candidate. HĐ-11.1 allows this
    explicitly: in a paired difference it is a translation, so it moves
    the level of ΔU without touching its variance.
    """
    settings = settings or DecisionSettings()
    _refuse_monetized_travel_time(settings)
    engineering_cost_h = _engineering_cost_hours(candidate, settings)

    u_r = anchors.u("success_rate", 1.0 if metric.success else 0.0)
    u_s = _safety(anchors, metric.near_miss_rate, metric.min_clearance)
    u_e = _efficiency(anchors, settings, metric.path_efficiency, metric.time_efficiency)
    u_c = _cost(
        anchors,
        settings,
        p99_latency_ms=metric.p99_latency_ms,
        memory_estimate_mb=_require_memory(metric.memory_estimate_mb, candidate),
        cpu_time_per_mission_s=metric.cpu_time_per_mission_s,
        engineering_cost_h=engineering_cost_h,
    )
    return _breakdown("episode", candidate, 1, settings, u_r, u_s, u_e, u_c)


def set_objectives(
    metrics: Sequence[EpisodeMetricSet],
    anchors: ResolvedAnchors,
    candidate: Candidate,
    settings: DecisionSettings | None = None,
) -> ObjectiveBreakdown:
    """Objectives over the whole evaluation set — the card's numbers.

    ``U_R`` scores the *success rate* against the deployment's declared
    floor, so 96.7% against a 95% floor is 0.34, not 0.967: the credit is
    for the margin over what the customer asked for, which is the reading
    the topic document's worked example (§6.2) uses.

    Every other component is the mean over episodes. Mean rather than
    worst case on purpose — the worst case is what the gates already
    ruled on, and repeating it here would charge a candidate twice for
    the same bad episode while saying nothing about typical behaviour.
    """
    settings = settings or DecisionSettings()
    _refuse_monetized_travel_time(settings)
    if not metrics:
        raise ObjectiveError(
            f"candidate {candidate.candidate_id} has no episodes to score; an objective over "
            "an empty set is not zero, it is undefined"
        )
    _require_one_candidate(metrics, candidate)
    engineering_cost_h = _engineering_cost_hours(candidate, settings)

    u_r = anchors.u("success_rate", _mean(1.0 if m.success else 0.0 for m in metrics))
    u_s = _safety(
        anchors,
        _mean(m.near_miss_rate for m in metrics),
        _mean(m.min_clearance for m in metrics),
    )
    u_e = _efficiency(
        anchors,
        settings,
        _mean(m.path_efficiency for m in metrics),
        _mean(m.time_efficiency for m in metrics),
    )
    u_c = _cost(
        anchors,
        settings,
        p99_latency_ms=_mean(m.p99_latency_ms for m in metrics),
        memory_estimate_mb=_mean(_require_memory(m.memory_estimate_mb, candidate) for m in metrics),
        cpu_time_per_mission_s=_mean(m.cpu_time_per_mission_s for m in metrics),
        engineering_cost_h=engineering_cost_h,
    )
    return _breakdown("set", candidate, len(metrics), settings, u_r, u_s, u_e, u_c)


def _breakdown(
    level: AggregationLevel,
    candidate: Candidate,
    n_episodes: int,
    settings: DecisionSettings,
    u_r: float,
    u_s: float,
    u_e: float,
    u_c: float,
) -> ObjectiveBreakdown:
    weights = settings.weights
    utility = weights.w_r * u_r + weights.w_s * u_s + weights.w_e * u_e + weights.w_c * u_c
    return ObjectiveBreakdown(
        level=level,
        candidate_id=candidate.candidate_id,
        n_episodes=n_episodes,
        # Every value here is already a convex combination of numbers
        # ``u`` clipped to [0, 1], so the clamp only absorbs floating-point
        # drift: renormalised β sums to 1.0000000000000002, which is
        # enough to fail a ``le=1`` bound on an otherwise perfect score.
        u_r=_clamp(u_r),
        u_s=_clamp(u_s),
        u_e=_clamp(u_e),
        u_c=_clamp(u_c),
        decision_utility=_clamp(utility),
        preference_profile=settings.profile_label,
        decision_mode=settings.decision_mode,
    )


def _safety(anchors: ResolvedAnchors, near_miss_rate: float, min_clearance: float) -> float:
    """``U_S`` (HĐ-9.1). ``collision_count`` is absent on purpose.

    Collisions live at gate G2 and nowhere else (HĐ-6): a candidate that
    collided is not in this computation at all, and letting collisions
    also lower a score would imply they can be traded against speed.
    """
    return 0.5 * anchors.u("near_miss_rate", near_miss_rate) + 0.5 * anchors.u(
        "min_clearance", min_clearance
    )


def _efficiency(
    anchors: ResolvedAnchors,
    settings: DecisionSettings,
    path_efficiency: float,
    time_efficiency: float,
) -> float:
    """``U_E`` (HĐ-9.1), minus travel time when O4 has taken it.

    Under ``monetized_cost`` travel time is priced in O4, so it *leaves*
    O3 entirely and U_E is path efficiency alone. Halving it and leaving
    a hole would quietly cap U_E at 0.5 for every candidate.
    """
    if settings.travel_time_accounting == "monetized_cost":
        return anchors.u("path_efficiency", path_efficiency)
    return 0.5 * anchors.u("path_efficiency", path_efficiency) + 0.5 * anchors.u(
        "time_efficiency", time_efficiency
    )


def _cost(
    anchors: ResolvedAnchors,
    settings: DecisionSettings,
    *,
    p99_latency_ms: float,
    memory_estimate_mb: float,
    cpu_time_per_mission_s: float,
    engineering_cost_h: float | None,
) -> float:
    """``U_C`` (HĐ-9.1): compute cost plus the cost of owning the thing."""
    weights = settings.weights
    b1, b2, b3, b4 = weights.beta
    total = (
        b1 * anchors.u("p99_latency_ms", p99_latency_ms)
        + b2 * anchors.u("memory_estimate_mb", memory_estimate_mb)
        + b3 * anchors.u("cpu_time_per_mission_s", cpu_time_per_mission_s)
    )
    if b4 > 0.0:
        assert engineering_cost_h is not None  # guaranteed by _engineering_cost_hours
        total += b4 * _engineering_term(anchors, settings, engineering_cost_h)
    return total


def _engineering_term(
    anchors: ResolvedAnchors, settings: DecisionSettings, engineering_cost_h: float
) -> float:
    """β4's contribution: the same effort on one of two scales.

    Technical mode scores the raw hours against the contract's hours
    anchor — a number the platform measured, on a scale it can defend
    from nothing but convention (good 0 h, bad 40 h).

    Business mode divides that effort by the declared horizon and scores
    the currency-per-mission figure against the customer's own declared
    ceiling. Same effort, different question: not "is 24 hours of tuning
    a lot" but "does 24 hours of tuning matter across the missions that
    will pay for it".

    Never both. The two are alternative scales for one quantity, so
    adding them would double-weight engineering effort inside U_C the
    way §17 ban 9 forbids across objectives.
    """
    if settings.decision_mode == "technical":
        return anchors.u("tuning_wall_clock_h", engineering_cost_h)

    business = settings.business_profile
    assert business is not None  # guaranteed by DecisionSettings validation
    return anchors.u(
        "engineering_cost_per_mission",
        business.engineering_cost_per_mission(engineering_cost_h),
    )


def _engineering_cost_hours(candidate: Candidate, settings: DecisionSettings) -> float | None:
    """``engineering_cost`` in technical mode: declared tuning hours.

    ``None`` when the active profile gives it no weight (``measured_only``,
    β4 = 0) — that profile exists precisely so a candidate with no tuning
    declaration can still be scored, and demanding the declaration anyway
    would defeat it.

    Otherwise the declaration is required. Substituting 0 would score
    "did not say" as "cost nothing", handing the best O4 to whoever
    skipped the paperwork (HĐ-1.6).
    """
    if not settings.weights.uses_engineering_cost:
        return None
    if candidate.tuning is None:
        raise ObjectiveError(
            f"candidate {candidate.candidate_id} has no tuning declaration, but preference "
            f"profile {settings.preference_profile!r} weights engineering cost at "
            f"β4 = {settings.weights.beta[3]}. Declare it (HĐ-1.6) or score under the "
            "'measured_only' profile, which prices nothing the platform did not measure. "
            "It is not treated as zero: that would reward not declaring"
        )
    return candidate.tuning.tuning_wall_clock_h


def _require_memory(value: float | None, candidate: Candidate) -> float:
    if value is None:
        raise ObjectiveError(
            f"an episode of candidate {candidate.candidate_id} carries no "
            "memory_estimate_mb, so U_C cannot be computed; recompute the metrics with the "
            "candidate's resource_profile (peak_rss_mb is not a substitute, §17 ban 13)"
        )
    return value


def _require_one_candidate(metrics: Sequence[EpisodeMetricSet], candidate: Candidate) -> None:
    foreign = sorted({m.candidate_id for m in metrics if m.candidate_id != candidate.candidate_id})
    if foreign:
        raise ObjectiveError(
            f"metrics for candidate(s) {foreign} were passed alongside "
            f"{candidate.candidate_id}; a utility averaged across candidates describes none "
            "of them"
        )


def _refuse_monetized_travel_time(settings: DecisionSettings) -> None:
    """``travel_time_accounting='monetized_cost'`` is still not computable.

    ``business_adjusted`` prices *engineering effort*, which needs one
    declared rate (currency per hour) and one declared horizon, both of
    which :class:`BusinessProfile` now carries. Pricing *travel time*
    needs a different declaration the platform does not have: what one
    mission of throughput is worth. Without it, moving travel time out
    of O3 would leave it priced by nothing at all — strictly worse than
    leaving it as an efficiency, where at least the scale is physical.

    Refused rather than approximated, for the reason that governs this
    whole mode: the card carries the label "adjusted by the assumptions
    the user declared", and that sentence must not stand over a figure
    computed under a scale nobody declared.
    """
    if settings.travel_time_accounting == "monetized_cost":
        raise ObjectiveError(
            "travel_time_accounting='monetized_cost' is not implemented: pricing travel time "
            "needs a declared value per mission of throughput, which no profile carries. "
            "business_adjusted prices engineering effort and leaves travel time in U_E, where "
            "its scale is physical (HĐ-9.3)"
        )


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _mean(values: Iterable[float]) -> float:
    collected = list(values)
    return float(sum(collected) / len(collected))
