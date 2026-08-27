"""One episode, two candidates: who won, what happened, what differed.

The case packet answers *why did this stack win the run*. This answers a
narrower question a reader asks with a replay open: **in this episode,
which of the two won, and which difference between them plausibly bears
on that**.

Three outputs, deliberately not one (plan 2026-08-27 §0):

``EpisodeVerdict``
    Who won. Deterministic, from the utility the scoring pass already
    stored per episode. No model is involved and none may contradict it.

``EpisodeDiagnosis``
    What happened to **each** candidate, separately: outcome, detections
    with their windows, planning attempts. An observation about one side
    is not an account of the difference, and keeping the two apart is
    what stops "C1 had a near miss" from being read as "that is why C1
    lost" — especially when C1 won.

``EpisodeContrast``
    A difference between the two with evidence behind it, and a
    ``strength`` saying how much that evidence can carry. Only findings
    that pass the contract in :mod:`planbench_analyst.guard` may be
    presented as bearing on the verdict.

**A verdict with no direction has no loser.** ``tie``,
``not_comparable`` and ``undecidable`` all leave ``winner`` unset, and
every contrast that needs a losing side is withheld with
``verdict_has_no_direction`` rather than picking one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.case_packet import (
    STANDING_UNKNOWNS,
    EpisodeTimeline,
    MeasuredValue,
    RobotFacts,
)
from planbench_explanation.contrast import CandidateComponents
from planbench_explanation.detectors import (
    SEVERITY,
    Detection,
    severity_of,
)
from planbench_explanation.ledger import KnownUnknown
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.propositions import (
    PropositionType,
    effect_direction,
)
from planbench_explanation.subjects import Subject
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_schemas.identity import canonical_json

EPISODE_PACKET_SCHEMA_VERSION = "0.1.0"

#: The one sentence a verdict is allowed to carry about its own weight.
#:
#: A field with a single legal value, for the reason
#: ``PROGRESS_SYNC_WARNING`` is one: a caveat a caller may reword is a
#: caveat a caller may dilute, and this one guards the reading that costs
#: the most — one episode read as the run's answer.
EPISODE_VERDICT_CAVEAT = (
    "One episode. There is no confidence interval on a single sample, and this "
    "is not the run's verdict: the decision card ranks candidates over every "
    "episode that was run."
)

VerdictBasis = Literal[
    "episode_decision_utility",
    "outcome_only",
    "not_comparable",
    "undecidable",
]

ContrastKind = Literal[
    "outcome_differs",
    "component_differs",
    "divergence_precedes_outcome",
    "detection_only_on_loser",
    "detection_worse_on_loser",
]

#: What a kind of difference is allowed to carry on its own.
#:
#: ``context`` restates the verdict or narrows the space; it never
#: supports a mechanism by itself. ``support`` can carry a mechanism to
#: ``associated`` **when** episode-scoped occurrence evidence and the
#: polarity agree — the rest of that contract lives in the guard, which
#: is where a model's citations are read.
CONTRAST_STRENGTH: dict[ContrastKind, Literal["context", "support"]] = {
    "outcome_differs": "context",
    "component_differs": "context",
    "divergence_precedes_outcome": "context",
    "detection_only_on_loser": "support",
    "detection_worse_on_loser": "support",
}

#: Withheld because the verdict names no losing side.
VERDICT_HAS_NO_DIRECTION = "verdict_has_no_direction"

#: Withheld because both candidates showed it to a comparable degree.
PRESENT_ON_BOTH = "present_on_both"

#: Withheld because it appears only on the side that won, and the
#: mechanism it points at is one that harms whoever has it.
ONLY_ON_WINNER = "only_on_winner"


class EpisodePacketRefusal(ValueError):
    """This episode cannot be assembled into a packet, and why."""


class CandidateOutcome(BaseModel):
    """One candidate's end of one episode, exactly as the run scored it.

    Read from ``report["candidates"][i]["episodes"]`` and never
    recomputed. A second arithmetic for "how long did it take" is a
    second answer, and the two drift where nobody is looking.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_id: str = Field(min_length=1)
    success: bool
    failure_reason: str | None = None
    collision_count: int = Field(ge=0)
    min_clearance: float | None = None
    travel_time_s: float | None = Field(default=None, ge=0)
    p99_latency_ms: float | None = Field(default=None, ge=0)
    replan_count: int = Field(default=0, ge=0)
    #: ``None`` when this candidate was never scored on utility — it was
    #: eliminated at a gate, or stopped early. Absent is not zero: zero
    #: reads as "scored, and scored badly".
    decision_utility: float | None = None


class EpisodeVerdict(BaseModel):
    """Which candidate won this episode, and on what basis.

    ``winner`` is unset for every basis but the two that can name one.
    The caller does not get to fill it in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    episode_context_id: str = Field(min_length=1)
    candidate_a: str = Field(min_length=1)
    candidate_b: str = Field(min_length=1)
    basis: VerdictBasis
    winner: str | None = None
    loser: str | None = None
    tie: bool = False
    #: Both are ``None`` unless the basis is utility. Denominator one,
    #: stated: a rate over one episode that does not say so is the claim
    #: this layer exists to refuse.
    utility_a: MeasuredValue | None = None
    utility_b: MeasuredValue | None = None
    delta_utility: MeasuredValue | None = None
    #: Why there is no winner, when there is none.
    undecided_reason: str = ""
    caveat: Literal[EPISODE_VERDICT_CAVEAT] = EPISODE_VERDICT_CAVEAT  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _check(self) -> EpisodeVerdict:
        if self.candidate_a == self.candidate_b:
            raise EpisodePacketRefusal(
                f"a verdict compares two candidates, and both sides name {self.candidate_a!r}"
            )
        named = {self.candidate_a, self.candidate_b}
        if self.winner is not None and self.winner not in named:
            raise EpisodePacketRefusal(f"winner {self.winner!r} is not one of {sorted(named)}")
        if self.loser is not None and self.loser not in named:
            raise EpisodePacketRefusal(f"loser {self.loser!r} is not one of {sorted(named)}")
        if (self.winner is None) != (self.loser is None):
            raise EpisodePacketRefusal(
                "a winner and a loser arrive together or not at all; one without "
                "the other is a comparison half-made"
            )
        if self.winner is not None and self.winner == self.loser:
            raise EpisodePacketRefusal("the winner cannot also be the loser")
        if self.winner is not None and self.tie:
            raise EpisodePacketRefusal("a tie has no winner")
        if self.winner is None and not self.undecided_reason:
            raise EpisodePacketRefusal(
                "a verdict with no winner has to say why; silence there reads as "
                "'the two were equal', which is one of four different answers"
            )
        if self.basis in ("not_comparable", "undecidable") and self.winner is not None:
            raise EpisodePacketRefusal(f"basis {self.basis!r} cannot name a winner")
        return self

    @property
    def has_direction(self) -> bool:
        """Whether anything may be attached to a losing side."""
        return self.winner is not None and self.loser is not None


class EpisodeDiagnosis(BaseModel):
    """What happened to one candidate in this episode. Not a comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_id: str = Field(min_length=1)
    outcome: CandidateOutcome | None = None
    detections: tuple[Detection, ...] = ()
    #: Planning attempts read from the sidecar, when this run recorded
    #: one. ``None`` means nobody wrote it down, which is different from
    #: "the planner never tried".
    planning_attempts: int | None = Field(default=None, ge=0)
    no_path_attempts: int | None = Field(default=None, ge=0)
    first_no_path_tick: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self) -> EpisodeDiagnosis:
        for detection in self.detections:
            if detection.candidate_id != self.candidate_id:
                raise EpisodePacketRefusal(
                    f"diagnosis for {self.candidate_id!r} carries a detection about "
                    f"{detection.candidate_id!r}"
                )
        if self.outcome is not None and self.outcome.candidate_id != self.candidate_id:
            raise EpisodePacketRefusal(
                f"diagnosis for {self.candidate_id!r} carries the outcome of "
                f"{self.outcome.candidate_id!r}"
            )
        return self


class EpisodeContrast(BaseModel):
    """A difference between the two candidates, and what it can carry."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: ContrastKind
    #: Which candidate the difference is *against*. Always the loser for
    #: the detection kinds; the field exists so a renderer never has to
    #: infer it from the verdict a second time.
    against_candidate_id: str = Field(min_length=1)
    #: The component the difference is about, when it is about one.
    subject: Subject | None = None
    #: The mechanism this difference would point at, when the kind
    #: implies one. Carried so the guard can read the polarity from the
    #: registry rather than from a sentence.
    proposition_type: PropositionType | None = None
    detail: str = Field(min_length=1)
    #: Refs into the packet's own fact index — filled by the view, not
    #: by whoever proposes a hypothesis.
    evidence_refs: tuple[str, ...] = ()
    measurements: dict[str, float] = Field(default_factory=dict)

    @property
    def strength(self) -> Literal["context", "support"]:
        return CONTRAST_STRENGTH[self.kind]

    @model_validator(mode="after")
    def _check(self) -> EpisodeContrast:
        if self.proposition_type is not None:
            direction = effect_direction(self.proposition_type)
            if direction == "benefits_subject":
                raise EpisodePacketRefusal(
                    f"{self.kind} is stated against {self.against_candidate_id!r}, but "
                    f"{self.proposition_type!r} is a mechanism that helps whoever has it"
                )
        return self


class RuledOut(BaseModel):
    """A difference that was looked for and deliberately not offered.

    Written down rather than dropped. "Both stacks stalled in the same
    doorway" is a finding about the pairing, and a contrast list that
    simply omits it reads as though nobody checked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ContrastKind
    reason: Literal[VERDICT_HAS_NO_DIRECTION, PRESENT_ON_BOTH, ONLY_ON_WINNER]  # type: ignore[valid-type]
    detail: str = Field(min_length=1)


def outcome_from_row(row: Mapping[str, Any], *, candidate_id: str) -> CandidateOutcome:
    """One scored episode row, in this module's shape.

    Every number is copied. ``episode_decision_utility`` is the run's own
    per-episode utility and clips differently from the card's figure, so
    it is read and never averaged into something that looks like one.
    """
    return CandidateOutcome(
        candidate_id=candidate_id,
        success=bool(row.get("success")),
        failure_reason=(str(row["failure_reason"]) if row.get("failure_reason") else None),
        collision_count=int(row.get("collision_count") or 0),
        min_clearance=_optional_float(row.get("min_clearance")),
        travel_time_s=_optional_float(row.get("travel_time_s")),
        p99_latency_ms=_optional_float(row.get("p99_latency_ms")),
        replan_count=int(row.get("replan_count") or 0),
        decision_utility=_optional_float(row.get("episode_decision_utility")),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return number


def _utility(value: float) -> MeasuredValue:
    """One episode's utility, carrying the denominator that says so."""
    return MeasuredValue(value=value, unit="utility", denominator=1)


def build_verdict(
    *,
    episode_context_id: str,
    candidate_a: str,
    candidate_b: str,
    outcome_a: CandidateOutcome | None,
    outcome_b: CandidateOutcome | None,
    tie_epsilon: float,
) -> EpisodeVerdict:
    """Who won this episode, on the strongest basis the data supports.

    ``tie_epsilon`` is preregistered and passed in. A margin chosen after
    seeing the distribution is a margin chosen to produce an answer.

    Four bases, and the difference between two of them is the one that
    matters most: **a candidate with no row did not lose**. It may never
    have run this episode, it may have been eliminated before the
    episode began, or the recording may be missing. Reading absence as
    defeat is the single most tempting mistake here.
    """
    if tie_epsilon < 0:
        raise EpisodePacketRefusal("tie_epsilon is a margin, and a negative margin is not one")
    common = {
        "episode_context_id": episode_context_id,
        "candidate_a": candidate_a,
        "candidate_b": candidate_b,
    }

    if outcome_a is None or outcome_b is None:
        missing = candidate_a if outcome_a is None else candidate_b
        return EpisodeVerdict(
            **common,
            basis="not_comparable",
            undecided_reason=(
                f"{missing} has no row for this episode. That can mean it never ran the "
                "episode, that a gate eliminated it first, or that the recording is "
                "incomplete — none of which is losing."
            ),
        )

    if outcome_a.decision_utility is not None and outcome_b.decision_utility is not None:
        delta = outcome_a.decision_utility - outcome_b.decision_utility
        if abs(delta) < tie_epsilon:
            return EpisodeVerdict(
                **common,
                basis="episode_decision_utility",
                tie=True,
                utility_a=_utility(outcome_a.decision_utility),
                utility_b=_utility(outcome_b.decision_utility),
                delta_utility=_utility(delta),
                undecided_reason=(
                    f"the two are within the preregistered margin of {tie_epsilon} utility"
                ),
            )
        winner, loser = (candidate_a, candidate_b) if delta > 0 else (candidate_b, candidate_a)
        return EpisodeVerdict(
            **common,
            basis="episode_decision_utility",
            winner=winner,
            loser=loser,
            utility_a=_utility(outcome_a.decision_utility),
            utility_b=_utility(outcome_b.decision_utility),
            delta_utility=_utility(delta),
        )

    if outcome_a.success != outcome_b.success:
        winner = candidate_a if outcome_a.success else candidate_b
        loser = candidate_b if outcome_a.success else candidate_a
        return EpisodeVerdict(
            **common,
            basis="outcome_only",
            winner=winner,
            loser=loser,
        )

    # Both reached the goal, or neither did, and no utility was scored.
    # Two different failure reasons do **not** rank: this repository has
    # no canonical ordering over them, and inventing one here would put a
    # policy nobody agreed to underneath every episode verdict.
    both = "reached the goal" if outcome_a.success else "did not reach the goal"
    return EpisodeVerdict(
        **common,
        basis="undecidable",
        undecided_reason=(
            f"neither candidate was scored on utility for this episode, and both {both}. "
            "Two unlike failures do not rank: no ordering over failure reasons is "
            "declared anywhere in this platform, and one invented here would decide "
            "episodes by a rule nobody wrote down."
        ),
    )


def build_diagnoses(
    *,
    verdict: EpisodeVerdict,
    outcomes: Mapping[str, CandidateOutcome | None],
    detections: Sequence[Detection],
    planning: Mapping[str, Mapping[str, int | None]] | None = None,
) -> tuple[EpisodeDiagnosis, ...]:
    """One diagnosis per candidate, in the verdict's own order."""
    attempts = planning or {}
    built: list[EpisodeDiagnosis] = []
    for candidate_id in (verdict.candidate_a, verdict.candidate_b):
        mine = tuple(item for item in detections if item.candidate_id == candidate_id)
        record = attempts.get(candidate_id) or {}
        built.append(
            EpisodeDiagnosis(
                candidate_id=candidate_id,
                outcome=outcomes.get(candidate_id),
                detections=mine,
                planning_attempts=record.get("attempts"),
                no_path_attempts=record.get("no_path"),
                first_no_path_tick=record.get("first_no_path_tick"),
            )
        )
    return tuple(built)


#: Which mechanism a detection type points at, and whose component it is
#: about. The same pairs ``integration.DETECTION_HYPOTHESES`` uses for
#: the model-free floor — imported rather than restated would be better
#: still, but that module builds proposals and importing it here would
#: make a data table depend on a round runner.
DETECTION_MECHANISM: dict[str, tuple[PropositionType, Subject]] = {
    "narrow_gap_refusal": ("geometric_infeasibility", "costmap_inflation"),
    "stuck_cluster": ("local_minimum_entrapment", "local_controller"),
    "oscillation": ("local_minimum_entrapment", "local_controller"),
    "detour": ("sampling_budget_insufficiency", "global_planner"),
    "latency_spike": ("expansion_latency_association", "global_planner"),
    "replan_storm": ("replan_instability", "global_planner"),
}

#: How much worse a shared detection has to be on the losing side before
#: the difference is a difference rather than the same thing twice.
#: Relative, because the measurements span seconds, metres and
#: milliseconds and one absolute threshold cannot mean anything in all
#: three.
WORSE_ON_LOSER_RATIO = 1.5

#: Fields of an outcome that rank on their own, and which way is better.
#: ``travel_time_s`` is here and ``replan_count`` is not: replanning is
#: already paid for in time and latency, and counting it again would
#: charge twice under a rule nobody wrote.
_OUTCOME_FIELDS: tuple[tuple[str, Literal["higher", "lower"], str], ...] = (
    ("success", "higher", "reached the goal"),
    ("collision_count", "lower", "collisions"),
    ("min_clearance", "higher", "worst clearance"),
    ("travel_time_s", "lower", "travel time"),
)


def _outcome_contrasts(
    verdict: EpisodeVerdict,
    outcomes: Mapping[str, CandidateOutcome | None],
) -> tuple[EpisodeContrast | None, RuledOut | None]:
    """The cheapest difference there is: the two ends of the episode.

    Computed before any detector runs, because it needs nothing but the
    rows the run already scored — and because a reader asking "why did
    this one win" is owed the plain answer first.
    """
    if not verdict.has_direction:
        return None, RuledOut(
            kind="outcome_differs",
            reason=VERDICT_HAS_NO_DIRECTION,
            detail="no side is the loser, so no outcome can be stated against one",
        )
    winner = outcomes.get(str(verdict.winner))
    loser = outcomes.get(str(verdict.loser))
    if winner is None or loser is None:  # pragma: no cover - verdict guards this
        return None, None

    differences: list[str] = []
    measurements: dict[str, float] = {}
    for field, better, label in _OUTCOME_FIELDS:
        mine, theirs = getattr(winner, field), getattr(loser, field)
        if mine is None or theirs is None or mine == theirs:
            continue
        winner_ahead = mine > theirs if better == "higher" else mine < theirs
        if not winner_ahead:
            continue
        differences.append(label)
        measurements[f"{field}_winner"] = float(mine)
        measurements[f"{field}_loser"] = float(theirs)
    if not differences:
        return None, None
    return (
        EpisodeContrast(
            kind="outcome_differs",
            against_candidate_id=str(verdict.loser),
            detail=(
                f"{verdict.winner} ended this episode ahead of {verdict.loser} on "
                + ", ".join(differences)
            ),
            measurements=measurements,
        ),
        None,
    )


def _component_contrast(
    verdict: EpisodeVerdict,
    components: Mapping[str, CandidateComponents],
) -> tuple[EpisodeContrast | None, RuledOut | None]:
    """Which parts of the two stacks are not the same part.

    Context, never support. That two stacks run different controllers
    narrows where a mechanism could live; it says nothing about whether
    any mechanism fired. Read as support it licenses exactly the move
    this layer exists to refuse — pick any known weakness of the losing
    component and call it the reason.
    """
    if not verdict.has_direction:
        return None, RuledOut(
            kind="component_differs",
            reason=VERDICT_HAS_NO_DIRECTION,
            detail="a component difference is stated against a losing side, and there is none",
        )
    winner = components.get(str(verdict.winner))
    loser = components.get(str(verdict.loser))
    if winner is None or loser is None:
        return None, None
    fields = winner.differs_in(loser)
    if not fields:
        return None, RuledOut(
            kind="component_differs",
            reason=PRESENT_ON_BOTH,
            detail="the two candidates declare the same stack in every component",
        )
    return (
        EpisodeContrast(
            kind="component_differs",
            against_candidate_id=str(verdict.loser),
            detail=(
                "the two stacks differ in " + ", ".join(fields) + "; a mechanism that "
                "explains the difference has to live in one of those"
            ),
        ),
        None,
    )


def _detection_contrasts(
    verdict: EpisodeVerdict,
    detections: Sequence[Detection],
) -> tuple[tuple[EpisodeContrast, ...], tuple[RuledOut, ...]]:
    """Detections read as a difference, with the three ways they are not.

    A detection is a difference when it fired on the losing side and not
    on the winning one, or fired on both and was materially worse on the
    loser. Anything else is written to ``ruled_out``:

    * both sides, comparable severity — the pattern belongs to the
      pairing, not to either candidate. Same reading
      ``contrast.rules_out_component_specific_attribution`` makes at run
      level;
    * only the winner, for a mechanism that harms whoever has it — that
      is a diagnosis, and offering it as a contrast would explain a loss
      with the winner's problem;
    * no direction in the verdict at all.
    """
    if not verdict.has_direction:
        kinds: tuple[ContrastKind, ...] = ("detection_only_on_loser", "detection_worse_on_loser")
        return (), tuple(
            RuledOut(
                kind=kind,
                reason=VERDICT_HAS_NO_DIRECTION,
                detail="a detection is offered against a losing side, and there is none",
            )
            for kind in kinds
        )

    winner_id, loser_id = str(verdict.winner), str(verdict.loser)
    by_side: dict[str, dict[str, Detection]] = {winner_id: {}, loser_id: {}}
    for item in detections:
        side = by_side.get(item.candidate_id)
        if side is None:
            continue
        seen = side.get(item.type)
        if seen is None or (severity_of(item) or -1e30) > (severity_of(seen) or -1e30):
            side[item.type] = item

    found: list[EpisodeContrast] = []
    withheld: list[RuledOut] = []
    for detection_type in sorted(set(by_side[winner_id]) | set(by_side[loser_id])):
        on_loser = by_side[loser_id].get(detection_type)
        on_winner = by_side[winner_id].get(detection_type)
        mechanism = DETECTION_MECHANISM.get(detection_type)
        proposition = mechanism[0] if mechanism else None
        subject = mechanism[1] if mechanism else None

        if on_loser is None:
            if on_winner is not None:
                withheld.append(
                    RuledOut(
                        kind="detection_only_on_loser",
                        reason=ONLY_ON_WINNER,
                        detail=(
                            f"{detection_type} fired on {winner_id}, which won this "
                            "episode; whatever it says about that run, it does not "
                            "account for the other side's loss"
                        ),
                    )
                )
            continue

        if on_winner is None:
            found.append(
                EpisodeContrast(
                    kind="detection_only_on_loser",
                    against_candidate_id=loser_id,
                    subject=subject,
                    proposition_type=proposition,
                    detail=f"{detection_type} fired on {loser_id} and not on {winner_id}",
                    measurements=dict(on_loser.measurements),
                )
            )
            continue

        worse, ratio = _is_worse(on_loser, on_winner, detection_type)
        if not worse:
            withheld.append(
                RuledOut(
                    kind="detection_worse_on_loser",
                    reason=PRESENT_ON_BOTH,
                    detail=(
                        f"{detection_type} fired on both candidates to a comparable "
                        "degree, so it describes the pairing rather than either side"
                    ),
                )
            )
            continue
        measurements = dict(on_loser.measurements)
        if ratio is not None:
            measurements["severity_ratio"] = ratio
        found.append(
            EpisodeContrast(
                kind="detection_worse_on_loser",
                against_candidate_id=loser_id,
                subject=subject,
                proposition_type=proposition,
                detail=(f"{detection_type} fired on both, and materially worse on {loser_id}"),
                measurements=measurements,
            )
        )
    return tuple(found), tuple(withheld)


def _is_worse(
    on_loser: Detection,
    on_winner: Detection,
    detection_type: str,
) -> tuple[bool, float | None]:
    """Whether the loser's instance is materially the worse one.

    Compared through :func:`severity_of`, which already normalises
    direction — a clearance of 0.01 m outranks one of 0.14 m. The ratio
    is taken on the raw measurement rather than the normalised severity,
    because a normalised value can be negative and a ratio of two
    negatives reads backwards.
    """
    key, direction = SEVERITY[detection_type]
    loser_value = on_loser.measurements.get(key)
    winner_value = on_winner.measurements.get(key)
    if loser_value is None or winner_value is None:
        # No measurement on one side: severity cannot be compared, and a
        # missing number is not evidence of a difference.
        return False, None
    if direction == "higher":
        if winner_value <= 0:
            return loser_value > 0, None
        ratio = loser_value / winner_value
    else:
        if loser_value <= 0:
            return winner_value > 0, None
        ratio = winner_value / loser_value
    return ratio >= WORSE_ON_LOSER_RATIO, ratio


def build_contrasts(
    *,
    verdict: EpisodeVerdict,
    outcomes: Mapping[str, CandidateOutcome | None],
    components: Mapping[str, CandidateComponents],
    detections: Sequence[Detection],
    divergence_precedes: bool = False,
    divergence_detail: str = "",
) -> tuple[tuple[EpisodeContrast, ...], tuple[RuledOut, ...]]:
    """Every difference this episode supports, and every one it does not.

    Ordered by what the evidence can carry: the ``support`` kinds first,
    then context. A reader — and a budgeter — takes the top of the list
    when it can only take part of it.
    """
    found: list[EpisodeContrast] = []
    withheld: list[RuledOut] = []

    detection_found, detection_withheld = _detection_contrasts(verdict, detections)
    found.extend(detection_found)
    withheld.extend(detection_withheld)

    if divergence_precedes:
        if verdict.has_direction:
            found.append(
                EpisodeContrast(
                    kind="divergence_precedes_outcome",
                    against_candidate_id=str(verdict.loser),
                    detail=divergence_detail or "the two runs parted before the outcomes differed",
                )
            )
        else:
            withheld.append(
                RuledOut(
                    kind="divergence_precedes_outcome",
                    reason=VERDICT_HAS_NO_DIRECTION,
                    detail="there is no losing side for the parting to be stated against",
                )
            )

    outcome_contrast, outcome_ruled = _outcome_contrasts(verdict, outcomes)
    if outcome_contrast is not None:
        found.append(outcome_contrast)
    if outcome_ruled is not None:
        withheld.append(outcome_ruled)

    component_contrast, component_ruled = _component_contrast(verdict, components)
    if component_contrast is not None:
        found.append(component_contrast)
    if component_ruled is not None:
        withheld.append(component_ruled)

    found.sort(key=lambda item: (0 if item.strength == "support" else 1, item.kind))
    return tuple(found), tuple(withheld)


# --------------------------------------------------------------------------
# What blocks a claim here, which is not what blocks one for the run
# --------------------------------------------------------------------------

#: Gaps that hold whatever scope is being asked about.
#:
#: Both members are properties of the platform, not of a run: H4's
#: accounting is not finished, and the PPO golden runtime is not
#: recorded. Neither becomes true for one episode because that episode
#: happened to go well.
GLOBAL_UNKNOWN_IDS: frozenset[str] = frozenset(unknown.id for unknown in STANDING_UNKNOWNS)

UnknownScope = Literal["global", "run_statistical", "episode"]


class ScopedUnknown(BaseModel):
    """A known unknown, and whether it has any force at episode scope.

    **A run-level gap does not automatically block an episode claim.**
    The run may lack the prevalence to call a pattern a property of the
    pairing while this episode has a sidecar and a checker that
    reproduced the refusal. Carrying the run's blocks across unchanged
    would drop exactly the claims this layer was built to allow, and it
    would do it silently — the guard's rule 3 reports "the packet blocks
    that claim type" either way.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    unknown: KnownUnknown
    scope: UnknownScope

    @property
    def blocks(self) -> bool:
        """Whether this one may remove a claim type at episode scope."""
        return self.scope in ("global", "episode")


def classify_unknown(unknown: KnownUnknown) -> ScopedUnknown:
    """Which of the three scopes a gap belongs to.

    A table rather than a field on :class:`KnownUnknown`, because that
    model is the wire contract between the platform and an external
    analyst: widening it would bump the explanation schema and rebuild
    every fixture, to record something only this layer asks about.
    """
    if unknown.id in GLOBAL_UNKNOWN_IDS:
        return ScopedUnknown(unknown=unknown, scope="global")
    return ScopedUnknown(unknown=unknown, scope="run_statistical")


def episode_unknowns(
    *,
    sidecar_present: bool,
    route: RouteFeatures | None,
    robot: RobotFacts | None,
    has_clearance: bool,
    has_latency: bool,
) -> tuple[KnownUnknown, ...]:
    """The gaps **this episode** has, recomputed from what it recorded.

    Each one is a fact about the recording, checked here rather than
    inherited: no sidecar means no replay can be reproduced, no route
    geometry means a passage width cannot be compared to a footprint,
    and a trace missing a column means the detector reading it never
    ran and so never found anything.
    """
    gaps: list[KnownUnknown] = []
    if not sidecar_present:
        gaps.append(
            KnownUnknown(
                id="episode_planning_inputs_unavailable",
                blocks_claim_types=("sampling_budget_insufficiency",),
                source="no planning-input sidecar was recorded for this episode",
            )
        )
    width = None
    if robot is not None:
        # Declared if the packet builder wrote one, derived from radius
        # and margin otherwise. Deriving here rather than refusing keeps
        # the gap honest: the parts are on the packet, and a claim that
        # the passage was too narrow is checkable from them.
        width = robot.required_passage_width_m or robot.derived_passage_width_m
    if route is None or route.narrowest_passage_m is None or width is None:
        gaps.append(
            KnownUnknown(
                id="episode_route_geometry_unavailable",
                blocks_claim_types=("geometric_infeasibility",),
                source=(
                    "this episode records no measured passage width or no inflated "
                    "footprint, so no passage can be compared against one"
                ),
            )
        )
    if not has_clearance:
        gaps.append(
            KnownUnknown(
                id="episode_clearance_unrecorded",
                blocks_claim_types=("clearance_refusal",),
                source="the trace for this episode carries no clearance column",
            )
        )
    if not has_latency:
        gaps.append(
            KnownUnknown(
                id="episode_latency_unrecorded",
                blocks_claim_types=("expansion_latency_association",),
                source="the trace for this episode carries no planner latency column",
            )
        )
    return tuple(gaps)


# --------------------------------------------------------------------------
# The packet
# --------------------------------------------------------------------------


class EpisodePacket(BaseModel):
    """Everything an analyst may read about one episode, and no more.

    Deliberately **not** a :class:`CasePacket` with a narrower scope. The
    case packet's validators require a waterfall for exemplars and at
    least two candidates for a comparison, and its facts are set-level:
    ΔU over thirty episodes, an observation seen in nine of them. None of
    that is available here and none of it should be — a packet about one
    episode that carried the run's aggregates would let a statement about
    this episode rest on a number from the other twenty-nine.

    What does travel from the run is identity only: the header, the task,
    the components. Those name things; they assert nothing about this
    episode. Measurements over the whole run are reachable through a tool
    when a round asks for them, and arrive labelled with run scope.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    header: ExplanationArtifactHeader
    episode_packet_schema_version: str = EPISODE_PACKET_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    #: The run's own case packet, by checksum. Pins what "the run" meant
    #: without copying any of it: a tool that serves run-level facts must
    #: be reading the same artifact this was built beside.
    run_packet_checksum: str = ""
    episode_context_id: str = Field(min_length=1)

    verdict: EpisodeVerdict
    diagnoses: tuple[EpisodeDiagnosis, ...]
    contrasts: tuple[EpisodeContrast, ...] = ()
    ruled_out: tuple[RuledOut, ...] = ()

    candidates: tuple[CandidateComponents, ...]
    robot: RobotFacts | None = None
    route: RouteFeatures | None = None
    timelines: tuple[EpisodeTimeline, ...] = ()
    known_unknowns: tuple[KnownUnknown, ...] = ()
    #: Run-level gaps, carried for the reader and stripped of force.
    run_context_unknowns: tuple[KnownUnknown, ...] = ()
    #: What the budgeter dropped, and why. Never silent.
    omissions: tuple[str, ...] = ()
    evidence_class: str = "production"

    @model_validator(mode="after")
    def _check(self) -> EpisodePacket:
        if len(self.candidates) != 2:
            raise EpisodePacketRefusal(
                "an episode packet explains a comparison, and a comparison needs "
                f"two candidates; this one has {len(self.candidates)}"
            )
        named = {item.candidate_id for item in self.candidates}
        if named != {self.verdict.candidate_a, self.verdict.candidate_b}:
            raise EpisodePacketRefusal(
                f"the packet carries components for {sorted(named)} and a verdict about "
                f"{sorted({self.verdict.candidate_a, self.verdict.candidate_b})}"
            )
        if self.verdict.episode_context_id != self.episode_context_id:
            raise EpisodePacketRefusal(
                f"the packet is about {self.episode_context_id!r} and the verdict about "
                f"{self.verdict.episode_context_id!r}"
            )
        for timeline in self.timelines:
            if timeline.episode_context_id != self.episode_context_id:
                raise EpisodePacketRefusal(
                    f"a timeline for {timeline.episode_context_id!r} is in the packet "
                    f"for {self.episode_context_id!r}"
                )
            if timeline.candidate_id not in named:
                raise EpisodePacketRefusal(
                    f"a timeline names {timeline.candidate_id!r}, which is not one of "
                    f"{sorted(named)}"
                )
        for contrast in self.contrasts:
            if contrast.against_candidate_id not in named:
                raise EpisodePacketRefusal(
                    f"a contrast is stated against {contrast.against_candidate_id!r}, "
                    f"which is not one of {sorted(named)}"
                )
        return self

    @property
    def blocked_claim_types(self) -> tuple[PropositionType, ...]:
        """What may not be claimed **here**.

        Global gaps and this episode's own. Run-statistical gaps are in
        :attr:`run_context_unknowns` and carry no force: they describe
        what thirty episodes could not settle, and this is one episode
        with its own recording.
        """
        blocked: set[PropositionType] = set()
        for unknown in self.known_unknowns:
            blocked.update(unknown.blocks_claim_types)
        return tuple(sorted(blocked))  # type: ignore[return-value]


#: What the budgeter keeps, best first. It drops from the **other** end.
#:
#: Verdict and caveat are absent because they are never dropped. The rest
#: is ranked by what a reader could not reconstruct without it: a
#: detection is an observation nothing else in the packet records, while
#: ``outcome_differs`` and ``component_differs`` restate rows and
#: identifiers that are in the packet anyway — which is why the weak
#: contrasts go before the diagnoses and not after.
BUDGET_KEEP_ORDER: tuple[str, ...] = (
    "supported_contrast",
    "diagnosis",
    "weak_contrast",
    "divergence",
    "timeline",
)


class BudgetedPacket(BaseModel):
    """A packet that fits, and an account of what it cost to make it fit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    packet: EpisodePacket
    dropped: tuple[str, ...] = ()


def packet_bytes(packet: EpisodePacket) -> int:
    """The packet's size, measured the way it will be serialised."""
    return len(canonical_json(packet.model_dump(mode="json")).encode("utf-8"))


def fit_to_budget(
    packet: EpisodePacket,
    *,
    max_bytes: int,
    measure: Callable[[EpisodePacket], int] = packet_bytes,
) -> BudgetedPacket:
    """Drop whole findings until the packet fits, and say which.

    Drops from the **cheap end** of :data:`BUDGET_KEEP_ORDER`: timelines
    first, supported contrasts last and only when nothing else is left
    to give.

    **Atomic groups.** Dropping the diagnoses removes the detections a
    supported contrast rests on, so it happens only after the weak
    contrasts have gone and never while a supported contrast is still
    the thing being kept — a packet that states a difference and carries
    nothing that shows it is worse than one that says less.

    The checksum a caller pins is taken **after** this runs, for the
    obvious reason: what a round was given is what was left.
    """
    if max_bytes <= 0:
        raise EpisodePacketRefusal("a byte budget of zero leaves no room for the verdict")

    current = packet
    dropped: list[str] = []
    for stage in reversed(BUDGET_KEEP_ORDER):
        if measure(current) <= max_bytes:
            break
        trimmed = _drop_stage(current, stage)
        if trimmed is None:
            continue
        current = trimmed
        dropped.append(stage)

    return BudgetedPacket(
        packet=current.model_copy(
            update={"omissions": (*current.omissions, *(f"dropped:{name}" for name in dropped))}
        ),
        dropped=tuple(dropped),
    )


def _drop_stage(packet: EpisodePacket, stage: str) -> EpisodePacket | None:
    """One stage of the budget, or ``None`` when there was nothing there."""
    if stage == "timeline":
        if not packet.timelines:
            return None
        return packet.model_copy(update={"timelines": ()})

    if stage == "weak_contrast":
        weak = tuple(item for item in packet.contrasts if item.strength == "context")
        if not weak:
            return None
        kept = tuple(item for item in packet.contrasts if item.strength != "context")
        return packet.model_copy(update={"contrasts": kept})

    if stage == "diagnosis":
        if not any(item.detections for item in packet.diagnoses):
            return None
        # The outcome rows stay: they are what the verdict rests on, and
        # they cost a fraction of what the detections do.
        stripped = tuple(item.model_copy(update={"detections": ()}) for item in packet.diagnoses)
        return packet.model_copy(update={"diagnoses": stripped})

    if stage == "supported_contrast":
        supported = tuple(item for item in packet.contrasts if item.strength == "support")
        if not supported:
            return None
        kept = tuple(item for item in packet.contrasts if item.strength != "support")
        return packet.model_copy(update={"contrasts": kept})

    return None
