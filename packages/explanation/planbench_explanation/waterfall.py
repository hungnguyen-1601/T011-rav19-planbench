"""Where ΔU came from, objective by objective — E1.

The Decision Card prints one number: ``ΔU`` between the recommendation
and its runner-up. The waterfall takes that exact number apart, so a
reader can see that the winner won on efficiency and gave back a little
on safety, rather than being told a total and asked to trust it.

**The bars decompose the number ``recommend()`` used, not a near
relative of it.** ``decision_utility = Σ w_j·u_j`` per episode, so the
mean paired difference decomposes exactly:

    mean(ΔU) = Σ_j w_j · mean(Δu_j)

and :class:`Waterfall` refuses to exist if its bars do not add up. That
check is the whole point of the module: a decomposition that does not
reconstitute its total is a picture of something else.

Two arithmetic traps sit either side of that identity, and both are
here as code rather than as advice.

**Mean, not median.** The identity above holds through the *mean* and
only through the mean — ``Σ w_j·median(Δu_j)`` is not ``median(ΔU)``,
because a median is not linear. HĐ-11.3 reports median and IQR, so the
median travels on the waterfall as a descriptive companion, in its own
field, never as a bar. Somebody who builds bars from medians gets a
picture whose parts do not sum to its total and no error to tell them.

**Two utility levels that disagree at U_R.** The card's utility is the
*set-level* one, and it is not the mean of the per-episode utilities:
``u`` is affine with clipping, and at U_R every episode hits a clip
boundary — ``success`` is 0 or 1, so the per-episode mean is just the
success rate, while the set level scores that rate against the
deployment's declared floor. The bars are built at the episode level,
because a paired difference cannot exist at the set level. So a reader
adding the bars will not land on the card's number, and
:class:`UtilityDrillDown` says so with both figures side by side rather
than leaving them to discover it.

**The intervals are marginal.** Each bar carries a paired bootstrap CI
of its own contribution. They are per-objective statements, not a
simultaneous band: adding them does not give the total's interval, and
the total's interval is computed from the total differences (the same
one HĐ-11.3 puts on the card). All bootstraps share one seed on
purpose — identical resample indices mean that within every resample the
bars still sum to the total, so the parts and the whole stay coherent.

The profile is named on the object. The decomposition is a function of
the deployment's weights: change the profile and the bars legitimately
change shape, and a waterfall that does not say which weights drew it is
presenting a preference as a measurement.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_decision.objectives import (
    PREFERENCE_PROFILES,
    WEIGHT_SUM_TOLERANCE,
    DecisionSettings,
    PreferenceWeights,
)
from planbench_decision.pairing import require_shared_context_ids
from planbench_decision.stats import (
    OBJECTIVE_NAMES,
    CandidateEvidence,
    StatisticsRefusal,
    paired_bootstrap_ci,
)

Objective = Literal["U_R", "U_S", "U_E", "U_C"]

#: How far the bars may miss their total before the waterfall refuses.
#: The identity is exact in real arithmetic; what is left is float drift
#: from summing four weighted means, which lands around 1e-16.
SUM_TOLERANCE = 1e-9

#: Float slack for the bound checks. Bounds are structural, so this
#: only absorbs the drift of arithmetic that already happened.
_EPS = 1e-12

#: Weight attribute on :class:`PreferenceWeights` for each objective.
_WEIGHT_FIELDS: dict[str, str] = {"U_R": "w_r", "U_S": "w_s", "U_E": "w_e", "U_C": "w_c"}

#: Objective field on :class:`ObjectiveBreakdown`.
_OBJECTIVE_FIELDS: dict[str, str] = {"U_R": "u_r", "U_S": "u_s", "U_E": "u_e", "U_C": "u_c"}


class WaterfallRefusal(ValueError):
    """The evidence on hand cannot support a decomposition."""


def _check_interval(interval: tuple[float, float], *, field: str) -> tuple[float, float]:
    """An interval with its ends the right way round.

    ``(2.0, -2.0)`` reads as "contains everything" to a straddles-zero
    test and draws inside-out on a chart, and neither failure announces
    itself. One guard, used by every interval in the module.
    """
    low, high = interval
    if low > high:
        raise WaterfallRefusal(
            f"{field}={interval!r} has its bounds reversed; an interval whose lower "
            "bound exceeds its upper one silently contains nothing and tests as "
            "containing everything"
        )
    return interval


def _within(value: float, *, limit: float, field: str) -> None:
    """A number inside the range its own definition allows.

    Every objective utility is on [0, 1] by construction (anchors clip
    it there), so a paired difference lives on [-1, 1] and a weighted
    contribution on [-w, w]. Numbers outside those ranges are not
    extreme measurements — they are impossible ones, and a set of them
    can be chosen to cancel so that every sum still balances. Bounds are
    what stops a balanced artifact from being an arbitrary one.
    """
    if not -limit - _EPS <= value <= limit + _EPS:
        raise WaterfallRefusal(
            f"{field}={value!r} is outside [{-limit}, {limit}]; utilities are on "
            "[0, 1] by construction, so this number cannot have been measured — and "
            "impossible numbers can be chosen to cancel out and pass every sum check"
        )


def _one_of_each(objectives: Sequence[str], *, field: str) -> None:
    """Exactly the four objectives, exactly once each.

    Counting is not enough and neither is set membership: ``U_R, U_S,
    U_E, U_E`` is four entries whose contributions can still sum to the
    right total, while U_C has vanished and the explanation now credits
    the win to the wrong objective. The multiset is the check.
    """
    if Counter(objectives) != Counter(OBJECTIVE_NAMES):
        raise WaterfallRefusal(
            f"{field} must name each of {list(OBJECTIVE_NAMES)} exactly once, "
            f"got {list(objectives)}; a duplicated objective hides a missing one "
            "and the totals still add up"
        )


#: Whether the weights are a declared profile or a deliberate move away
#: from one (the HĐ-11.5 stability sweep).
ProfileKind = Literal["canonical", "perturbed"]


def _same_weights(left: PreferenceWeights, right: PreferenceWeights) -> bool:
    """Whether two preference profiles are the same preference.

    **Including ``beta``.** The first cut compared only the four
    top-level weights, which let an artifact keep ``w_C`` at the table's
    value while splitting U_C as ``(1, 0, 0, 0)`` — a different
    preference about what "cost" means, certified as canonical. Worse,
    the artifact could not even be filed honestly as perturbed, because
    the same check declared it a match.
    """
    pairs = [
        (float(getattr(left, field)), float(getattr(right, field)))
        for field in _WEIGHT_FIELDS.values()
    ]
    if len(left.beta) != len(right.beta):
        return False
    pairs += list(zip((float(v) for v in left.beta), (float(v) for v in right.beta), strict=True))
    return all(math.isclose(a, b, rel_tol=1e-9, abs_tol=_EPS) for a, b in pairs)


class WaterfallProfile(BaseModel):
    """Which preference the bars were drawn under, as data rather than a name.

    A free-text label is checkable against nothing. With the weights
    snapshotted but the label loose, an artifact can be re-filed from
    ``kho_ban_dem`` to ``pilot_demo`` without touching a single number
    and still validate — the arithmetic stays right while the panel
    tells a reader it describes a preference it does not describe, and a
    sensitivity sweep can be laundered into a headline result.

    So the label is **derived, never accepted**: the artifact declares
    which named profile it starts from and whether the weights were
    moved, and :attr:`label` is computed from those two. The wording
    matches ``DecisionSettings.profile_label`` because the evidence on
    both sides was filed under that string.

    ``canonical`` additionally means *these are the table's weights*, and
    that is checked. The consequence is deliberate: if
    ``PREFERENCE_PROFILES`` is ever edited, artifacts filed as canonical
    under the edited name stop validating, because their bars were drawn
    under weights that name no longer denotes. Re-filing them as
    ``perturbed`` with the same snapshot keeps every number readable and
    says what they actually are.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: ProfileKind
    #: A key of ``PREFERENCE_PROFILES``. A perturbed profile still names
    #: the profile it was perturbed *from*; weights with no origin are
    #: not a sweep, they are an unexplained preference.
    base_profile: str
    weights: PreferenceWeights
    #: Derived from the two above. ``None`` only on the way in.
    label: str | None = None

    @model_validator(mode="after")
    def _check(self) -> WaterfallProfile:
        declared = PREFERENCE_PROFILES.get(self.base_profile)
        if declared is None:
            raise WaterfallRefusal(
                f"unknown base profile {self.base_profile!r}; known profiles are "
                f"{sorted(PREFERENCE_PROFILES)} (HĐ-9.2). A sweep still names the "
                "profile it moved away from"
            )
        matches_table = _same_weights(self.weights, declared)
        if self.kind == "canonical" and not matches_table:
            raise WaterfallRefusal(
                f"profile {self.base_profile!r} is declared canonical but its weights "
                f"are {self.weights!r}, not the declared "
                f"{declared!r}; weights moved away from a named profile are a sweep, "
                "and filing one under the plain name is how a perturbed result gets "
                "read as the deployment's own preference"
            )
        if self.kind == "perturbed" and matches_table:
            raise WaterfallRefusal(
                f"profile {self.base_profile!r} is declared perturbed but its weights "
                "are exactly the declared ones; marking an unmoved profile as a sweep "
                "hides a headline result behind a caveat"
            )

        derived = (
            self.base_profile if self.kind == "canonical" else f"{self.base_profile} (perturbed)"
        )
        if self.label is None:
            object.__setattr__(self, "label", derived)
            return self
        if self.label != derived:
            raise WaterfallRefusal(
                f"profile label {self.label!r} does not follow from base_profile "
                f"{self.base_profile!r} and kind {self.kind!r}, which give {derived!r}"
            )
        return self


class WaterfallBar(BaseModel):
    """One objective's share of ΔU, with its own interval."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    objective: Objective
    #: The deployment's weight for this objective. On the bar because
    #: the bar is ``weight × difference`` and a reader comparing two
    #: profiles needs to see which half moved.
    weight: float = Field(ge=0.0, le=1.0)
    #: Mean paired difference of the objective itself, before weighting.
    #: Utilities are on [0, 1], so their paired difference is on [-1, 1].
    delta_objective_mean: float = Field(ge=-1.0, le=1.0)
    #: ``weight × delta_objective_mean`` — the height of the bar, and
    #: the term that participates in the sum.
    contribution: float = Field(ge=-1.0, le=1.0)
    #: Marginal 95% CI of *this contribution*. Not simultaneous with the
    #: other bars, and not summable into the total's interval.
    ci95: tuple[float, float]
    #: Whether the interval contains 0 — the UI renders such a bar
    #: dimmed. A **stored** field rather than a property: E4 writes this
    #: object to an artifact and serves it as JSON, and a property does
    #: not survive ``model_dump()``. It would have been the flag that
    #: tells a reader "this bar settles nothing", missing from exactly
    #: the place a reader looks.
    #:
    #: ``None`` only ever appears on the way in: the validator below
    #: fills it from the interval, or refuses if a supplied value
    #: disagrees. Deriving it *after* parsing rather than before means a
    #: malformed ``ci95`` is a structured validation error rather than a
    #: ``TypeError`` from comparing a string to a float — which, through
    #: an API, is the difference between a 422 and a 500.
    crosses_zero: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> WaterfallBar:
        low, high = _check_interval(self.ci95, field=f"{self.objective} ci95")

        expected_product = self.weight * self.delta_objective_mean
        if not math.isclose(self.contribution, expected_product, rel_tol=1e-9, abs_tol=1e-12):
            raise WaterfallRefusal(
                f"{self.objective} bar claims a contribution of {self.contribution!r} "
                f"but weight × difference is {expected_product!r}; the bar's height and "
                "the numbers printed beside it would tell a reader two different stories"
            )

        # A weighted share of a [0, 1] objective cannot leave [-w, w],
        # and neither can an interval around it.
        _within(self.contribution, limit=self.weight, field=f"{self.objective} contribution")
        _within(low, limit=self.weight, field=f"{self.objective} ci95 lower bound")
        _within(high, limit=self.weight, field=f"{self.objective} ci95 upper bound")

        derived = low <= 0.0 <= high
        if self.crosses_zero is None:
            # Frozen model, so the assignment goes through ``object`` —
            # returning a copy from a validator is not supported when
            # the model is built by ``__init__``.
            object.__setattr__(self, "crosses_zero", derived)
            return self
        if self.crosses_zero != derived:
            raise WaterfallRefusal(
                f"{self.objective} bar says crosses_zero={self.crosses_zero} but its "
                f"interval is {self.ci95!r}; the flag the UI dims by must not be able "
                "to disagree with the interval it describes"
            )
        return self


class ObjectiveLevels(BaseModel):
    """One objective at both aggregation levels, for one candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    objective: Objective
    #: What the card prints (HĐ-9.1 set level). An objective utility, so
    #: on [0, 1] by construction.
    set_level: float = Field(ge=0.0, le=1.0)
    #: Mean of the per-episode values — what the bars are built from.
    episode_mean: float = Field(ge=0.0, le=1.0)

    @property
    def diverges(self) -> bool:
        """Whether the two levels disagree beyond float drift."""
        return not math.isclose(self.set_level, self.episode_mean, abs_tol=1e-9)


class UtilityDrillDown(BaseModel):
    """Both utility levels, side by side, with the divergence named.

    This exists because of one predictable complaint: *"I added the bars
    and did not get the number on the card."* That is correct behaviour
    and it needs somewhere to be explained. The card is set level; the
    bars are episode level; they part company at U_R, where clipping is
    not incidental but universal.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_a: str
    candidate_b: str
    #: Set-level ``decision_utility`` — the card's numbers. A utility,
    #: so on [0, 1].
    set_utility_a: float = Field(ge=0.0, le=1.0)
    set_utility_b: float = Field(ge=0.0, le=1.0)
    #: Mean over episodes of ``decision_utility`` — what the bars sum to.
    episode_mean_utility_a: float = Field(ge=0.0, le=1.0)
    episode_mean_utility_b: float = Field(ge=0.0, le=1.0)
    levels_a: tuple[ObjectiveLevels, ...]
    levels_b: tuple[ObjectiveLevels, ...]
    #: Objectives whose two levels disagree, for either candidate. In
    #: practice U_R, always: it is the one where every episode is
    #: clipped. Stored rather than derived on access for the reason
    #: ``crosses_zero`` is — E4 serves this as JSON, and the list of
    #: objectives a reader must not add up cannot be the part that does
    #: not survive serialisation. ``None`` only on the way in: derived
    #: below from parsed levels, checked when supplied.
    diverging_objectives: tuple[Objective, ...] | None = None

    @model_validator(mode="after")
    def _check(self) -> UtilityDrillDown:
        if self.candidate_a == self.candidate_b:
            raise WaterfallRefusal(
                f"drill-down compares {self.candidate_a} with itself; every level would "
                "match by construction and the panel would report it as a finding"
            )
        _one_of_each([level.objective for level in self.levels_a], field="levels_a")
        _one_of_each([level.objective for level in self.levels_b], field="levels_b")

        derived = tuple(
            name
            for name in OBJECTIVE_NAMES
            if any(level.diverges and level.objective == name for level in self.levels_a)
            or any(level.diverges and level.objective == name for level in self.levels_b)
        )
        if self.diverging_objectives is None:
            object.__setattr__(self, "diverging_objectives", derived)
            return self
        if tuple(self.diverging_objectives) != derived:
            raise WaterfallRefusal(
                f"drill-down claims {list(self.diverging_objectives)} diverge but the "
                f"levels say {list(derived)}; this list is what warns a reader that the "
                "card and the bars are not the same aggregation, and it may not drift "
                "from the numbers it describes"
            )
        return self

    @property
    def set_delta(self) -> float:
        """ΔU between the card's two numbers. Not what the bars sum to."""
        return self.set_utility_a - self.set_utility_b

    @property
    def episode_mean_delta(self) -> float:
        """ΔU the bars reconstitute."""
        return self.episode_mean_utility_a - self.episode_mean_utility_b


class Waterfall(BaseModel):
    """The decomposition of one paired ΔU, and the proof it adds up."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_a: str
    candidate_b: str
    #: Which preference drew this, as typed data: the named profile it
    #: starts from, whether the weights were moved, and the weights
    #: themselves. A waterfall without this presents a preference as a
    #: measurement; with only a free-text name, it can present one
    #: preference as another.
    profile: WaterfallProfile
    n_episodes: int = Field(ge=1)
    #: What the bars sum to: mean paired ΔU at the episode level. A
    #: difference of two [0, 1] utilities, so on [-1, 1].
    delta_utility_mean: float = Field(ge=-1.0, le=1.0)
    #: Descriptive companion (HĐ-11.3). Deliberately not a bar — the
    #: decomposition identity does not hold through a median.
    delta_utility_median: float = Field(ge=-1.0, le=1.0)
    #: Interval of the total, computed from the total differences. Not
    #: derived from the bars' intervals and not comparable term by term.
    total_ci95: tuple[float, float]
    bars: tuple[WaterfallBar, ...]
    drill_down: UtilityDrillDown
    seed: int
    n_resamples: int = Field(ge=1)

    @property
    def bar_sum(self) -> float:
        return float(sum(bar.contribution for bar in self.bars))

    @model_validator(mode="after")
    def _bars_reconstitute_the_total(self) -> Waterfall:
        if self.candidate_a == self.candidate_b:
            raise WaterfallRefusal(
                f"waterfall decomposes {self.candidate_a} against itself; every bar is "
                "zero by construction while the intervals claim it was measured. Checked "
                "here as well as in the builder, because an artifact is read back by code "
                "that never called the builder"
            )
        _one_of_each([bar.objective for bar in self.bars], field="bars")
        low, high = _check_interval(self.total_ci95, field="total_ci95")
        _within(low, limit=1.0, field="total_ci95 lower bound")
        _within(high, limit=1.0, field="total_ci95 upper bound")

        # The four weights are one deployment's preference profile, and
        # a set that does not sum to 1 puts the utility on a different
        # scale than the anchors placed every component on (HĐ-9.1).
        weight_total = sum(bar.weight for bar in self.bars)
        if not math.isclose(weight_total, 1.0, abs_tol=WEIGHT_SUM_TOLERANCE):
            raise WaterfallRefusal(
                f"the bars' weights sum to {weight_total!r}, not 1.0; these are supposed "
                "to be one deployment's profile, and a set that does not sum to one is "
                "not one profile"
            )

        # ...and they must be *this* profile's weights, not any four
        # numbers that happen to sum to one.
        for bar in self.bars:
            declared = float(getattr(self.profile.weights, _WEIGHT_FIELDS[bar.objective]))
            if not math.isclose(bar.weight, declared, rel_tol=1e-9, abs_tol=_EPS):
                raise WaterfallRefusal(
                    f"the {bar.objective} bar is weighted {bar.weight!r} but the profile "
                    f"snapshot says {declared!r}; the bars would be a decomposition "
                    "under weights no deployment declared, filed under a profile name "
                    "that means something else"
                )

        # Each bar's difference must be the difference the drill-down
        # measured for that objective. Without this the two halves can
        # disagree per objective and still agree in total: bars saying
        # (+0.1, −0.1) against levels saying (+0.2, −0.2) sums to the
        # same ΔU and credits the win differently.
        by_objective_a = {level.objective: level.episode_mean for level in self.drill_down.levels_a}
        by_objective_b = {level.objective: level.episode_mean for level in self.drill_down.levels_b}
        for bar in self.bars:
            measured = by_objective_a[bar.objective] - by_objective_b[bar.objective]
            if abs(bar.delta_objective_mean - measured) > SUM_TOLERANCE:
                raise WaterfallRefusal(
                    f"the {bar.objective} bar decomposes a difference of "
                    f"{bar.delta_objective_mean!r} but the drill-down measured "
                    f"{measured!r} for that objective; per-objective errors that cancel "
                    "leave the total right and every attribution wrong"
                )

        drift = abs(self.bar_sum - self.delta_utility_mean)
        if drift > SUM_TOLERANCE:
            raise WaterfallRefusal(
                f"bars sum to {self.bar_sum!r} but ΔU is {self.delta_utility_mean!r} "
                f"(off by {drift:.3e}); a decomposition that does not reconstitute its "
                "total is a picture of a different quantity"
            )

        # The drill-down is the panel that explains why the bars and the
        # card differ. Pointing at another pair of candidates, or at
        # another ΔU, makes it an explanation of a different comparison
        # printed under this one's heading.
        if (self.drill_down.candidate_a, self.drill_down.candidate_b) != (
            self.candidate_a,
            self.candidate_b,
        ):
            raise WaterfallRefusal(
                f"drill-down compares {self.drill_down.candidate_a} with "
                f"{self.drill_down.candidate_b} but the waterfall compares "
                f"{self.candidate_a} with {self.candidate_b}"
            )
        level_drift = abs(self.drill_down.episode_mean_delta - self.delta_utility_mean)
        if level_drift > SUM_TOLERANCE:
            raise WaterfallRefusal(
                f"drill-down reports an episode-level ΔU of "
                f"{self.drill_down.episode_mean_delta!r} but the bars decompose "
                f"{self.delta_utility_mean!r} (off by {level_drift:.3e}); the two halves "
                "of the same panel would disagree about what was measured"
            )

        # And each side's own utility must be the weighted sum of its own
        # objectives — the same identity as the bars, one level down.
        self._check_side("a")
        self._check_side("b")
        return self

    def _check_side(self, side: Literal["a", "b"]) -> None:
        """``U = Σ w_j·u_j`` for **one** candidate, at both aggregation levels.

        Nothing global belongs here: the helper runs once per candidate,
        so a whole-object invariant placed in it runs twice and reads as
        if it were per-candidate.
        """
        levels = self.drill_down.levels_a if side == "a" else self.drill_down.levels_b
        for level_name, stated in (
            ("set_level", getattr(self.drill_down, f"set_utility_{side}")),
            ("episode_mean", getattr(self.drill_down, f"episode_mean_utility_{side}")),
        ):
            folded = sum(
                float(getattr(self.profile.weights, _WEIGHT_FIELDS[level.objective]))
                * float(getattr(level, level_name))
                for level in levels
            )
            if abs(folded - stated) > SUM_TOLERANCE:
                raise WaterfallRefusal(
                    f"candidate {side}'s {level_name} objectives fold to {folded!r} under "
                    f"this profile but the drill-down states a utility of {stated!r}; "
                    "an objective can be moved and the total left standing"
                )


def build_waterfall(
    a: CandidateEvidence,
    b: CandidateEvidence,
    *,
    settings: DecisionSettings,
    seed: int = 0,
    n_resamples: int = 1000,
) -> Waterfall:
    """Decompose ``ΔU = U(a) − U(b)`` over the shared episode contexts.

    ``settings`` supplies the weights, and it must be the settings the
    evidence was scored under — the decomposition multiplies by ``w_j``
    and a mismatched profile produces bars that sum to somebody else's
    total. Checked against the profile label recorded on both sides.

    Every bootstrap here uses ``seed`` and the same paired differences
    per context, so the resample indices are identical across bars: the
    bars stay coherent with the total inside each resample rather than
    being four unrelated intervals that happen to be drawn together.
    """
    if a.candidate_id == b.candidate_id:
        raise WaterfallRefusal(
            f"candidate {a.candidate_id} cannot be decomposed against itself; every "
            "bar would be zero by construction and the intervals would claim it was measured"
        )

    profile = settings.profile_label
    for side in (a, b):
        if side.set_objectives.preference_profile != profile:
            raise WaterfallRefusal(
                f"candidate {side.candidate_id} was scored under profile "
                f"{side.set_objectives.preference_profile!r} but the waterfall was asked "
                f"for {profile!r}; weights that did not produce the utilities cannot "
                "decompose them"
            )

    shared = require_shared_context_ids({a.candidate_id: a.contexts, b.candidate_id: b.contexts})
    utility_deltas = np.asarray(
        [a.episode_utilities[c] - b.episode_utilities[c] for c in shared], dtype=float
    )

    weights = settings.weights
    bars: list[WaterfallBar] = []
    for objective in OBJECTIVE_NAMES:
        weight = float(getattr(weights, _WEIGHT_FIELDS[objective]))
        series_a = a.objective_series(objective)
        series_b = b.objective_series(objective)
        deltas = np.asarray([series_a[c] - series_b[c] for c in shared], dtype=float)
        contributions = deltas * weight
        low, high = paired_bootstrap_ci(contributions, seed=seed, n_resamples=n_resamples)
        bars.append(
            WaterfallBar(
                objective=objective,  # type: ignore[arg-type]
                weight=weight,
                delta_objective_mean=float(deltas.mean()),
                contribution=float(contributions.mean()),
                ci95=(low, high),
            )
        )

    total_low, total_high = paired_bootstrap_ci(utility_deltas, seed=seed, n_resamples=n_resamples)

    return Waterfall(
        candidate_a=a.candidate_id,
        candidate_b=b.candidate_id,
        profile=WaterfallProfile(
            kind="perturbed" if settings.weights_override is not None else "canonical",
            base_profile=settings.preference_profile,
            weights=weights,
        ),
        n_episodes=len(shared),
        delta_utility_mean=float(utility_deltas.mean()),
        delta_utility_median=float(np.median(utility_deltas)),
        total_ci95=(total_low, total_high),
        bars=tuple(bars),
        drill_down=_drill_down(a, b),
        seed=seed,
        n_resamples=n_resamples,
    )


def _drill_down(a: CandidateEvidence, b: CandidateEvidence) -> UtilityDrillDown:
    return UtilityDrillDown(
        candidate_a=a.candidate_id,
        candidate_b=b.candidate_id,
        set_utility_a=a.set_objectives.decision_utility,
        set_utility_b=b.set_objectives.decision_utility,
        episode_mean_utility_a=_mean_utility(a),
        episode_mean_utility_b=_mean_utility(b),
        levels_a=_levels(a),
        levels_b=_levels(b),
    )


def _levels(evidence: CandidateEvidence) -> tuple[ObjectiveLevels, ...]:
    return tuple(
        ObjectiveLevels(
            objective=objective,  # type: ignore[arg-type]
            set_level=float(getattr(evidence.set_objectives, _OBJECTIVE_FIELDS[objective])),
            episode_mean=float(np.mean(list(evidence.objective_series(objective).values()))),
        )
        for objective in OBJECTIVE_NAMES
    )


def _mean_utility(evidence: CandidateEvidence) -> float:
    values = list(evidence.episode_utilities.values())
    if not values:  # pragma: no cover - CandidateEvidence refuses this first
        raise StatisticsRefusal(f"candidate {evidence.candidate_id} has no scored episodes")
    return float(np.mean(values))
