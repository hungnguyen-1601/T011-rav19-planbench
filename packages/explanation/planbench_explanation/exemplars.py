"""Which episodes the comparison page opens with — E2.

Thirty paired episodes, one two-panel viewer, and somebody has to decide
which pair loads first. Left to a human that decision is invisible and
looks like evidence: showing the two episodes where the winner won
hardest is a true statement about two episodes and a misleading picture
of thirty. Left to "top |ΔU|" it is the same picture with a formula
behind it.

So the set is **preregistered**: a fixed recipe, written before any
particular run, that always returns the same four roles.

``typical``
    ΔU closest to the median. The episode a reader should calibrate on.
``strongest_for_winner`` / ``strongest_for_runnerup``
    the extremes, both of them. Showing one without the other is the
    cherry-pick this recipe exists to prevent, so they are one unit.
``safety_critical``
    the worst safety outcome across both candidates, whatever ΔU says.
    Utility folds safety in with everything else; a collision that cost
    little utility is still the episode a person needs to watch.

**Ties are resolved by episode id, always.** Not by "first seen": a
recipe whose output depends on the order episodes came back from a
database is not preregistered, it is reproducible-looking.

Prevalence — *"the detour appears in 27 of 30 pairs; ep 017 is typical
of it"* — is deliberately not here. It needs the E3 detectors, and a
weaker stand-in written now would be a second definition of detour that
somebody later has to reconcile.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_decision.pairing import require_shared_context_ids
from planbench_decision.stats import CandidateEvidence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from planbench_metrics.definitions import EpisodeMetricSet

ExemplarRole = Literal[
    "typical",
    "strongest_for_winner",
    "strongest_for_runnerup",
    "safety_critical",
]

#: In the order the panel should offer them.
EXEMPLAR_ROLES: tuple[ExemplarRole, ...] = (
    "typical",
    "strongest_for_winner",
    "strongest_for_runnerup",
    "safety_critical",
)


class EpisodeSafety(BaseModel):
    """What the safety role is chosen from, for one episode and one side."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    collision_count: int = Field(ge=0)
    min_clearance: float


class ExemplarRefusal(ValueError):
    """The evidence on hand cannot support a preregistered selection."""


class Exemplar(BaseModel):
    """One chosen episode, its role, and the number that chose it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    role: ExemplarRole
    episode_context_id: str = Field(min_length=1)
    #: Paired ΔU for this episode — the quantity three of the four roles
    #: are defined on, carried even for ``safety_critical`` so a reader
    #: can see that the worst-safety episode was not the worst on utility.
    delta_utility: float
    #: The criterion value that selected it, in its own units: metres of
    #: clearance for ``safety_critical``, ΔU for the rest.
    criterion: float
    #: Present when the choice came down to the id tie-break, so a
    #: reader can tell "clearly the worst" from "one of four equals".
    tie_break_over: tuple[str, ...] = ()


class ExemplarSet(BaseModel):
    """The four roles, always all four, always in order."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_a: str
    candidate_b: str
    n_episodes: int = Field(ge=1)
    exemplars: tuple[Exemplar, ...]

    @model_validator(mode="after")
    def _check(self) -> ExemplarSet:
        roles = tuple(item.role for item in self.exemplars)
        if roles != EXEMPLAR_ROLES:
            raise ExemplarRefusal(
                f"an exemplar set is exactly {list(EXEMPLAR_ROLES)} in that order, "
                f"got {list(roles)}. Dropping a role is how the pair of extremes "
                "becomes a single flattering one"
            )
        if self.candidate_a == self.candidate_b:
            raise ExemplarRefusal("exemplars compare a candidate with itself")
        return self

    def by_role(self, role: ExemplarRole) -> Exemplar:
        (found,) = [item for item in self.exemplars if item.role == role]
        return found

    @property
    def episode_ids(self) -> tuple[str, ...]:
        return tuple(item.episode_context_id for item in self.exemplars)


def select_exemplars(
    a: CandidateEvidence,
    b: CandidateEvidence,
    *,
    metrics_a: Mapping[str, EpisodeMetricSet],
    metrics_b: Mapping[str, EpisodeMetricSet],
) -> ExemplarSet:
    """The preregistered four for scored evidence still in memory.

    An adapter. The recipe itself works on plain series
    (:func:`select_exemplars_from_series`) so that the same four roles
    can be chosen from a stored report months later, by code that has no
    ``CandidateEvidence`` and cannot rebuild one.
    """
    require_shared_context_ids({a.candidate_id: a.contexts, b.candidate_id: b.contexts})
    missing = [
        context for context in a.contexts if context not in metrics_a or context not in metrics_b
    ]
    if missing:
        raise ExemplarRefusal(
            f"no metrics for episode(s) {sorted(missing)[:3]}; the safety role is "
            "chosen from collisions and clearance, and an episode with neither "
            "recorded cannot be ruled in or out of it"
        )
    return select_exemplars_from_series(
        candidate_a=a.candidate_id,
        candidate_b=b.candidate_id,
        utilities_a=a.episode_utilities,
        utilities_b=b.episode_utilities,
        safety_a={
            context: EpisodeSafety(
                collision_count=metric.collision_count, min_clearance=metric.min_clearance
            )
            for context, metric in metrics_a.items()
        },
        safety_b={
            context: EpisodeSafety(
                collision_count=metric.collision_count, min_clearance=metric.min_clearance
            )
            for context, metric in metrics_b.items()
        },
    )


def select_exemplars_from_series(
    *,
    candidate_a: str,
    candidate_b: str,
    utilities_a: Mapping[str, float],
    utilities_b: Mapping[str, float],
    safety_a: Mapping[str, EpisodeSafety],
    safety_b: Mapping[str, EpisodeSafety],
) -> ExemplarSet:
    """The preregistered four, from per-episode utility and safety alone.

    ``candidate_a`` is the recommended candidate: ΔU is ``U(a) − U(b)``,
    so ``strongest_for_winner`` is its best episode. Passing them the
    other way round produces a valid set with the roles mirrored, which
    is why the candidate ids travel on the result.
    """
    if candidate_a == candidate_b:
        raise ExemplarRefusal(
            f"candidate {candidate_a} cannot be its own runner-up; every ΔU is zero "
            "and all four roles would land on the id that sorts first"
        )
    shared = require_shared_context_ids(
        {candidate_a: tuple(sorted(utilities_a)), candidate_b: tuple(sorted(utilities_b))}
    )
    missing = [context for context in shared if context not in safety_a or context not in safety_b]
    if missing:
        raise ExemplarRefusal(
            f"no safety data for episode(s) {sorted(missing)[:3]}; the safety role is "
            "chosen from collisions and clearance, and an episode with neither "
            "recorded cannot be ruled in or out of it"
        )

    deltas = {context: utilities_a[context] - utilities_b[context] for context in shared}
    median = statistics.median(deltas.values())
    typical = _pick(deltas, key=lambda context: abs(deltas[context] - median))
    strongest_winner = _pick(deltas, key=lambda context: -deltas[context])
    strongest_runnerup = _pick(deltas, key=lambda context: deltas[context])
    safety = _pick(deltas, key=lambda context: _safety_key(context, safety_a, safety_b))

    return ExemplarSet(
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        n_episodes=len(shared),
        exemplars=(
            Exemplar(
                role="typical",
                episode_context_id=typical.context,
                delta_utility=deltas[typical.context],
                criterion=deltas[typical.context],
                tie_break_over=typical.tied_with,
            ),
            Exemplar(
                role="strongest_for_winner",
                episode_context_id=strongest_winner.context,
                delta_utility=deltas[strongest_winner.context],
                criterion=deltas[strongest_winner.context],
                tie_break_over=strongest_winner.tied_with,
            ),
            Exemplar(
                role="strongest_for_runnerup",
                episode_context_id=strongest_runnerup.context,
                delta_utility=deltas[strongest_runnerup.context],
                criterion=deltas[strongest_runnerup.context],
                tie_break_over=strongest_runnerup.tied_with,
            ),
            Exemplar(
                role="safety_critical",
                episode_context_id=safety.context,
                delta_utility=deltas[safety.context],
                criterion=_worst_clearance(safety.context, safety_a, safety_b),
                tie_break_over=safety.tied_with,
            ),
        ),
    )


class _Choice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    context: str
    tied_with: tuple[str, ...]


def _pick(deltas: Mapping[str, float], *, key) -> _Choice:  # type: ignore[no-untyped-def]
    """Smallest key wins; equal keys go to the smallest episode id.

    The tie is *reported*, not just resolved. "Worst by a wide margin"
    and "worst by a coin flip the recipe made for you" are different
    pieces of evidence, and only one of them supports a story.
    """
    scored = sorted((key(context), context) for context in deltas)
    best_score = scored[0][0]
    tied = tuple(sorted(context for score, context in scored if score == best_score))
    return _Choice(context=tied[0], tied_with=tied[1:])


def _safety_key(
    context: str,
    safety_a: Mapping[str, EpisodeSafety],
    safety_b: Mapping[str, EpisodeSafety],
) -> tuple[int, float]:
    """Sort key for the safety role: collisions first, then clearance.

    A collision outranks any amount of clearance — the two are not on a
    scale with each other, and a near miss at 2 cm is still not a crash.
    Both are read across the pair, because the episode worth watching is
    worth watching whichever side had the problem.
    """
    collisions = max(safety_a[context].collision_count, safety_b[context].collision_count)
    return (-collisions, _worst_clearance(context, safety_a, safety_b))


def _worst_clearance(
    context: str,
    safety_a: Mapping[str, EpisodeSafety],
    safety_b: Mapping[str, EpisodeSafety],
) -> float:
    return min(safety_a[context].min_clearance, safety_b[context].min_clearance)


def index_metrics(metrics: Sequence[EpisodeMetricSet]) -> dict[str, EpisodeMetricSet]:
    """``episode_context_id`` → metrics, refusing a repeated episode.

    A duplicate here means two scored runs of one episode, and silently
    keeping the last one would let the exemplar recipe depend on which
    order they were loaded in.
    """
    indexed: dict[str, EpisodeMetricSet] = {}
    for metric in metrics:
        if metric.episode_context_id in indexed:
            raise ExemplarRefusal(
                f"episode {metric.episode_context_id} appears twice in one candidate's "
                "metrics; which of the two the recipe sees would depend on load order"
            )
        indexed[metric.episode_context_id] = metric
    return indexed


class ReportExemplarRefusal(ExemplarRefusal):
    """A stored report cannot support the preregistered selection."""


class CardlessPairRefusal(ValueError):
    """A run with no card that still may not be read as a pair."""


def cardless_pair(report: Mapping[str, Any]) -> tuple[str, str]:
    """The two candidates a run with no card compared, or a refusal.

    A card is refused when fewer than two candidates clear the six
    gates, and that refusal is about a **deployment** claim: nobody may
    be told which stack to ship. It says nothing about whether one stack
    reached the goal in a given episode and the other did not, which is
    a different claim, settled without any utility at all, and the one a
    reader with a replay open is actually asking.

    So the pair is looked up rather than refused — but only where there
    is nothing to look up wrongly.

    **Refuses on three or more.** With a card the pair is recorded and
    the statistics chose it; without one, picking two out of three is a
    choice made after the numbers are visible, which is the move a
    preregistration exists to stop. Two candidates leave nothing to
    choose.

    Ordered by id rather than by outcome, for the same reason: ordering
    by who won would let the reading of a run decide how the run is
    read.
    """
    ids = [
        candidate_id
        for candidate_id in sorted(
            str(candidate.get("candidate_id") or "") for candidate in report.get("candidates", ())
        )
        if candidate_id
    ]
    if len(ids) != 2:
        raise CardlessPairRefusal(
            f"a run with no card is read as a pair only when it compared exactly two "
            f"candidates; this one has {len(ids)}, and choosing two of them is a choice "
            f"nobody has made"
        )
    return ids[0], ids[1]


def compared_pair(report: Mapping[str, Any]) -> tuple[str, str] | None:
    """Which two candidates the paired comparison was about.

    Read from ``comparison_pair``, which the scoring run writes from the
    recommendation itself.

    **Not from the card, and this is the whole point of the field.** The
    card carries ``recommended`` and ``alternative``, and the second of
    those is *not* the runner-up: HĐ-12 lets ``alternative`` name only a
    PARETO_FRONTIER candidate, so it is ``None`` on every run without a
    Pareto analysis and can name a different candidate when it is set.
    An earlier version of this function read it anyway. That was wrong
    twice over — it returned ``None`` for ordinary ranked runs, sending
    a page that had a perfectly good winner and runner-up back to
    "whatever registered first", and where it did return something it
    could name a candidate ΔU was never computed against.

    ``None`` when the run recorded no pair: a run that ranked nobody has
    no winner, and three of the four exemplar roles are defined against
    one. Older runs also land here, and the honest consequence is no
    exemplar set rather than a pair chosen from list order.
    """
    pair = report.get("comparison_pair")
    if not isinstance(pair, Mapping):
        return None
    winner = str(pair.get("recommended_candidate_id") or "")
    runner_up = str(pair.get("runner_up_candidate_id") or "")
    if not winner or not runner_up or winner == runner_up:
        return None
    return winner, runner_up


def select_exemplars_from_report(
    report: Mapping[str, Any],
    *,
    candidate_a: str | None = None,
    candidate_b: str | None = None,
) -> ExemplarSet:
    """The four roles, from a report read back off the database.

    The pair comes from the card (:func:`compared_pair`) unless a caller
    names one, because ``strongest_for_winner`` means nothing until
    "winner" is settled by something other than list order.

    **Refuses rather than approximates.** A run recorded before
    ``episode_decision_utility`` was stored has no per-episode utility
    anywhere — the metric set it was derived from is not in the report,
    and the number cannot be recovered from the seven columns that are.
    Three of the four roles are defined on ΔU, so the honest answer is
    no exemplar set at all. Substituting travel time, or ranking by the
    one role that survives, would put a differently-chosen pair of
    episodes under a label that says they were chosen by the recipe.
    """
    if candidate_a is None or candidate_b is None:
        pair = compared_pair(report)
        if pair is None:
            raise ReportExemplarRefusal(
                "this run records no comparison pair, so it names no winner and no "
                "runner-up; three of the four roles are defined against a winner, "
                "and choosing one from list order would label whichever candidate "
                "sorts first as the one that won. A run that ranked nobody never "
                "had a pair; one scored before the field existed must be scored again"
            )
        candidate_a = candidate_a or pair[0]
        candidate_b = candidate_b or pair[1]

    by_id = {str(entry.get("candidate_id")): entry for entry in (report.get("candidates") or [])}
    entries = []
    for candidate_id in (candidate_a, candidate_b):
        entry = by_id.get(candidate_id)
        if entry is None:
            raise ReportExemplarRefusal(f"candidate {candidate_id} is not in this run")
        entries.append(entry)

    utilities = [_utilities(entry) for entry in entries]
    for candidate_id, series in zip((candidate_a, candidate_b), utilities, strict=True):
        if not series:
            raise ReportExemplarRefusal(
                f"candidate {candidate_id} has no per-episode utility in this report. "
                "Runs scored before that column existed cannot be re-derived from the "
                "rows that were kept, and three of the four roles are defined on ΔU — "
                "so this run has no exemplar set until it is scored again"
            )

    return select_exemplars_from_series(
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        utilities_a=utilities[0],
        utilities_b=utilities[1],
        safety_a=_safety(entries[0]),
        safety_b=_safety(entries[1]),
    )


def _utilities(entry: Mapping[str, Any]) -> dict[str, float]:
    """Per-episode utility from a report row, skipping episodes without one."""
    out: dict[str, float] = {}
    for row in entry.get("episodes") or []:
        value = row.get("episode_decision_utility")
        if value is None:
            continue
        out[str(row["episode_context_id"])] = float(value)
    return out


def _safety(entry: Mapping[str, Any]) -> dict[str, EpisodeSafety]:
    return {
        str(row["episode_context_id"]): EpisodeSafety(
            collision_count=int(row.get("collision_count", 0)),
            min_clearance=float(row.get("min_clearance", 0.0)),
        )
        for row in entry.get("episodes") or []
    }
