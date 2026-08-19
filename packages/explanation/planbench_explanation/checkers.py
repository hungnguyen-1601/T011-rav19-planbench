"""The mechanism checks the platform can actually run — E6a.

E5 wrote the cards; this runs two of them. The other two,
``replay_global_plan`` and ``rrt_convergence``, need planning inputs
recorded as the run happened — the E4.5 sidecar, which does not exist —
and they stay ``not_checkable`` rather than being approximated. A replay
from reconstructed inputs is a different measurement wearing the same
name.

**A checker is a pure function of its evidence.** Nothing here reads a
file, opens a run directory or knows what a session is: the host fetches
the evidence and passes it in, so a check can be re-run on the same
inputs by anybody with the inputs and no access to the platform. It is
also what makes the results testable without a run.

**Each returns a verdict, not a conclusion.** ``supported`` /
``refuted`` / ``inconclusive`` about one named proposition, plus the
measurements the card declares. Whether that verdict becomes a claim is
the promotion matrix's business, and what level it reaches depends on
the card ceiling, the provenance and the packet's gaps — none of which a
checker knows or should.

One correction to the catalog belongs in this module's history, because
it is the kind of thing that reads as an implementation detail and is
not. ``latency_vs_expanded_nodes`` was written to relate **per-replan**
expansions to the latency of the tick that carried them. HĐ-5's trace
schema has ``planner_latency_ms`` per row and **no expanded-node
column**, and that schema is one of the three frozen contracts. So the
per-replan version cannot be computed from what runs record, and
pretending otherwise would mean inventing the number. What can be
computed is the association **across episodes** of one candidate:
episodes whose search expanded more nodes recorded higher planner
latency. Weaker, real, and still capped at ``associated``. The card now
says that instead.

The same paragraph explains why the check is **within one candidate**:
the benchmark already separates a grid search's expanded nodes from a
sampling planner's tree size, because they count different things.
Correlating one against the other across candidates would be a number
about the units, not about the run.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.propositions import PropositionType
from planbench_explanation.provenance import PropositionVerdict

#: Below this many episodes an association is a shape two points make.
MINIMUM_EPISODES_FOR_ASSOCIATION = 8

#: |rho| at or above this is reported as an association; below it the
#: verdict is ``refuted`` rather than ``inconclusive``, because the
#: question asked was "do these move together" and "no" is an answer.
ASSOCIATION_RHO = 0.4


class CheckerRefusal(ValueError):
    """A check that cannot be run on the evidence it was given."""


class CheckOutcome(BaseModel):
    """What a checker produces: one verdict, and the numbers behind it.

    Deliberately not a :class:`~planbench_explanation.protocol.ToolResult`.
    A checker does not know its request id, its card's forbidden
    inferences or the provenance of what it was handed; the host adds
    those. Keeping the two apart is what stops a checker stamping its
    own result.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    proposition_type: PropositionType
    verdict: PropositionVerdict
    measurements: dict[str, float]
    #: The checker's own words about what it found. For an auditor
    #: reading the ledger, never rendered to a user — rendering is
    #: template-gated by claim level.
    note: str = Field(min_length=1)


class GapEvidence(BaseModel):
    """Everything ``gap_vs_footprint`` needs, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    region_id: str = Field(min_length=1)
    #: Geometry of the region, measured across the route rather than
    #: around a point — see :mod:`planbench_explanation.map_features`.
    features: RouteFeatures
    robot_radius_m: float = Field(gt=0)
    #: The configured inflation margin. Kept apart from the radius
    #: because the mechanism under test is the *configuration*, not the
    #: robot: a passage the footprint clears and the inflation does not
    #: is exactly the finding.
    inflation_radius_m: float = Field(ge=0)


def check_gap_vs_footprint(evidence: GapEvidence) -> CheckOutcome:
    """Does the configured clearance exceed the measured passage width.

    Uses ``narrowest_passage_m`` — the narrowest cross-section closed by
    obstacles on **both** sides — and nothing else. The lower bound is
    not consulted: "at least 0.3 m" cannot establish "narrower than
    0.74 m", and an earlier version of the detector that reached for it
    was reaching for the one conclusion it cannot support.

    A route the map never bounded on both sides therefore yields no
    verdict at all, which is the honest outcome and is why this raises
    rather than returning ``inconclusive`` with an invented number.
    """
    width = evidence.features.narrowest_passage_m
    if width is None:
        raise CheckerRefusal(
            f"region {evidence.region_id!r} was never measured between two mapped "
            "obstacles, so the only figure available is a lower bound — and a lower "
            "bound cannot show a passage is too narrow"
        )

    required = evidence.robot_radius_m + evidence.inflation_radius_m
    margin = width - required
    measurements = {
        "passage_width_m": width,
        "required_clearance_m": required,
        "margin_m": margin,
        "inflation_radius_m": evidence.inflation_radius_m,
    }
    if margin < 0.0:
        return CheckOutcome(
            proposition_type="geometric_infeasibility",
            verdict="supported",
            measurements=measurements,
            note=(
                f"the narrowest cross-section of {evidence.region_id} is {width:.3f} m "
                f"and the configured inflation requires {required:.3f} m, leaving "
                f"{margin:.3f} m"
            ),
        )
    return CheckOutcome(
        proposition_type="geometric_infeasibility",
        verdict="refuted",
        measurements=measurements,
        note=(
            f"the narrowest cross-section of {evidence.region_id} is {width:.3f} m "
            f"against a requirement of {required:.3f} m, so the passage is open to "
            "this configuration and the refusal has another cause"
        ),
    )


class EpisodeSearchCost(BaseModel):
    """One episode's search size and the latency recorded beside it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    episode_context_id: str = Field(min_length=1)
    expanded_nodes: int = Field(ge=0)
    planner_latency_ms: float = Field(ge=0.0)


class LatencyEvidence(BaseModel):
    """Episodes of **one** candidate, paired expansions and latency."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidate_id: str = Field(min_length=1)
    episodes: tuple[EpisodeSearchCost, ...]

    @model_validator(mode="after")
    def _check(self) -> LatencyEvidence:
        ids = [episode.episode_context_id for episode in self.episodes]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise CheckerRefusal(
                f"episode(s) {duplicates} appear twice; one episode counted twice "
                "moves a correlation without adding a measurement"
            )
        return self


def check_latency_vs_expanded_nodes(evidence: LatencyEvidence) -> CheckOutcome:
    """Do episodes with larger searches record higher planner latency.

    Spearman rather than Pearson: the question is whether the two move
    together, not whether they move linearly, and one runaway episode
    should not carry a correlation on its own.

    A **positive** answer is capped at ``associated`` by the card, and
    this function is where it becomes clear why. Both quantities follow
    from how hard the query was; the association is real and the causal
    reading does not follow from it.
    """
    episodes = evidence.episodes
    if len(episodes) < MINIMUM_EPISODES_FOR_ASSOCIATION:
        raise CheckerRefusal(
            f"{len(episodes)} episode(s) for {evidence.candidate_id}; an association "
            f"needs at least {MINIMUM_EPISODES_FOR_ASSOCIATION} points to be anything "
            "other than the shape a handful of episodes happens to make"
        )

    expansions = [float(episode.expanded_nodes) for episode in episodes]
    latencies = [episode.planner_latency_ms for episode in episodes]
    rho = _spearman(expansions, latencies)
    if rho is None:
        raise CheckerRefusal(
            f"{evidence.candidate_id}: every episode reports the same expanded-node "
            "count or the same latency, so the two cannot be ranked against each "
            "other. A constant column is not a weak association, it is no measurement"
        )

    measurements = {
        "n_episodes": float(len(episodes)),
        "spearman_rho": rho,
        "median_expanded_nodes": _median(expansions),
        "median_latency_ms": _median(latencies),
    }
    if rho >= ASSOCIATION_RHO:
        return CheckOutcome(
            proposition_type="expansion_latency_association",
            verdict="supported",
            measurements=measurements,
            note=(
                f"across {len(episodes)} episodes of {evidence.candidate_id}, expanded "
                f"nodes and planner latency rank together at rho={rho:.2f}"
            ),
        )
    return CheckOutcome(
        proposition_type="expansion_latency_association",
        verdict="refuted",
        measurements=measurements,
        note=(
            f"across {len(episodes)} episodes of {evidence.candidate_id}, expanded "
            f"nodes and planner latency rank together at only rho={rho:.2f}; the "
            "latency this run spent is not tracking the size of the search"
        ),
    )


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _ranks(values: Sequence[float]) -> list[float]:
    """Ranks with ties averaged, which is what makes Spearman well defined."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared = (position + end) / 2.0 + 1.0
        for index in range(position, end + 1):
            ranks[order[index]] = shared
        position = end + 1
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Rank correlation, or ``None`` when one side has no variation.

    ``None`` rather than 0.0: a constant column means the two were never
    comparable, and reporting "no association" for it would be a finding
    about data that could not have produced one.
    """
    a = _ranks(left)
    b = _ranks(right)
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    covariance = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    spread_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    spread_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    if spread_a == 0.0 or spread_b == 0.0:
        return None
    return covariance / (spread_a * spread_b)
