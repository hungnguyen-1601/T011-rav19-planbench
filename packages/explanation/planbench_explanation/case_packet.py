"""The file an analyst is given, and the only thing it may read — E4.

Everything upstream of here produces facts: the waterfall takes ΔU
apart, the detectors say what happened, the lattice says what that rules
out, the map says how wide the corridor was. The packet is where those
arrive as one document, and it is deliberately the *whole* input: an
analyst — human or model — never opens a Parquet file.

**Because reading the trace is where fabrication starts.** Give a model
546 rows of telemetry and it will produce a number that looks like a
measurement and is not one. Give it a packet, and every number in its
answer either appears here or is a number it invented, which is a
difference a reviewer can check by looking.

**Known unknowns are mandatory and structured.** Not a paragraph asking
the analyst to be careful — a list of claim types the orchestrator
*refuses to promote*, each naming what makes it unavailable. A packet
with an empty list would be claiming the platform knows everything about
this run, and the H4 accounting gaps alone mean that is never true
today, which is why :data:`STANDING_UNKNOWNS` exists rather than each
caller remembering.

**Nothing in the packet is a claim.** Observations are patterns, the
lattice reading is a constraint on attribution, the map features are
measurements. The one thing a packet cannot contain is a conclusion
about why one candidate won — that is what the analyst is for, and what
the promotion matrix is for after it.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.contrast import CandidateComponents, ContrastFinding
from planbench_explanation.detectors import Observation
from planbench_explanation.exemplars import ExemplarSet
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import KnownUnknown
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_explanation.waterfall import Waterfall


class CasePacketRefusal(ValueError):
    """The evidence on hand cannot be assembled into a packet."""


#: The gaps every packet carries today, because they are properties of
#: the platform rather than of any run.
#:
#: Listed as data so a caller cannot forget them, and re-stated per
#: packet rather than assumed by the reader: an analyst that has to
#: remember which attributions are unavailable will eventually not.
STANDING_UNKNOWNS: tuple[KnownUnknown, ...] = (
    KnownUnknown(
        id="latency_accounting_unavailable",
        blocks_claim_types=("candidate_latency_attribution", "perception_attribution"),
        source="h4_not_complete",
    ),
    KnownUnknown(
        id="ppo_golden_runtime_missing",
        blocks_claim_types=("ppo_behavior_attribution",),
        source="h0_debt",
    ),
)


class RobotFacts(BaseModel):
    """The robot, as the two numbers a geometric argument needs."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    radius_m: float = Field(gt=0)
    #: The costmap's inflation margin **beyond** the robot's own radius,
    #: per side. Recorded so :attr:`required_passage_width_m` can be
    #: checked against the parts it was derived from rather than taken
    #: on trust.
    inflation_margin_m: float | None = Field(default=None, ge=0)
    #: **The narrowest corridor this configuration can drive through**,
    #: as a width: ``2 * (radius + inflation_margin)``. ``None`` when the
    #: run did not record the inflation — absent rather than assumed,
    #: because a clearance argument built on a guessed inflation is an
    #: argument about a costmap nobody configured.
    #:
    #: It was called ``required_clearance_m`` and documented as "radius
    #: plus the costmap's inflation", which is a **radius**, and it was
    #: being compared against ``narrowest_passage_m``, which is a
    #: **cross-section**. Both halves of a corridor have to clear, so the
    #: comparison was short by a factor of two and a 0.50 m doorway read
    #: as passable for a 0.26 m robot with a 0.22 m margin. Renamed so
    #: the unit is in the name: two quantities that are not the same kind
    #: of thing must not share a plausible name.
    required_passage_width_m: float | None = Field(default=None, gt=0)

    @property
    def derived_passage_width_m(self) -> float | None:
        """What the width should be, from the parts. ``None`` without a margin."""
        if self.inflation_margin_m is None:
            return None
        return 2.0 * (self.radius_m + self.inflation_margin_m)


class TaskFacts(BaseModel):
    """The world both candidates drove in."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    task_profile_id: str = Field(min_length=1)
    robot: RobotFacts
    #: ``None`` when no route could be measured against the map — see
    #: :class:`RouteFeatures`. The packet says so rather than omitting
    #: the section, because "not measured" and "wide open" read very
    #: differently to somebody looking for a geometric cause.
    route: RouteFeatures | None = None


class DecisionFacts(BaseModel):
    """What the run decided, and the decomposition behind it if there is one."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    status: str = Field(min_length=1)
    #: ``None`` on a run that ranked nobody — a gate-only deployment, a
    #: field where no candidate cleared all six gates, a sweep
    #: interrupted before ranking.
    #:
    #: **Absent rather than the packet being absent.** The first version
    #: required it, which meant those runs got no packet at all: the
    #: detectors never ran and an analyst asking "why did it fail" was
    #: handed a 409. Those are precisely the runs somebody asks that
    #: about. A ΔU decomposition is a statement about a *pair* the
    #: statistics chose, and without a ranking there is no such pair —
    #: but the sightings, the geometry and the gate table are all still
    #: facts about this run, and they are what is left to look at.
    waterfall: Waterfall | None = None
    #: Gate verdicts as the report holds them: who was eliminated where.
    gates: dict[str, dict[str, object]] = Field(default_factory=dict)


class CasePacket(BaseModel):
    """Everything an analyst may look at, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    header: ExplanationArtifactHeader
    run_id: str = Field(min_length=1)
    task: TaskFacts
    #: Full stacks, not algorithm names. A candidate is a whole
    #: navigation configuration (HĐ-1.1), and "RRT* is slow here" names
    #: nothing that was measured.
    candidates: tuple[CandidateComponents, ...]
    decision: DecisionFacts
    #: What the lattice rules out, per detection type. Mostly refusals,
    #: and they are the most valuable part: they narrow what an analyst
    #: may propose before it proposes anything.
    lattice: tuple[ContrastFinding, ...] = ()
    observations: tuple[Observation, ...] = ()
    representative_episodes: ExemplarSet | None = None
    known_unknowns: tuple[KnownUnknown, ...]
    #: The fairness lane this evidence came from (§5.10). A research-lane
    #: packet is diagnostic evidence and never a card statistic.
    evidence_class: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> CasePacket:
        if not self.known_unknowns:
            raise CasePacketRefusal(
                "a packet with no known unknowns claims the platform knows everything "
                "about this run; the H4 accounting gaps alone make that untrue today. "
                "Start from STANDING_UNKNOWNS"
            )
        if len(self.candidates) < 2:
            raise CasePacketRefusal(
                "a packet explains a comparison, and a comparison needs two candidates"
            )
        known = {item.candidate_id for item in self.candidates}
        waterfall = self.decision.waterfall
        if waterfall is not None:
            compared = {waterfall.candidate_a, waterfall.candidate_b}
            if not compared <= known:
                raise CasePacketRefusal(
                    f"the waterfall compares {sorted(compared)} but the packet describes "
                    f"{sorted(known)}; an analyst reading this would be explaining a "
                    "comparison between candidates it cannot see"
                )
        strangers = {item.candidate_id for item in self.observations} - known
        if strangers:
            raise CasePacketRefusal(
                f"observations name candidate(s) {sorted(strangers)} that are not in this packet"
            )
        lattice_strangers = {
            candidate_id
            for finding in self.lattice
            for pair in finding.pairs
            for candidate_id in pair
        } - known
        if lattice_strangers:
            raise CasePacketRefusal(
                f"the lattice reading rests on candidate(s) {sorted(lattice_strangers)} "
                "that are not in this packet; a contrast from another run would read as "
                "a constraint on this one"
            )

        if self.representative_episodes is not None and waterfall is None:
            raise CasePacketRefusal(
                "this packet carries exemplars and no waterfall. Three of the four "
                "roles are defined against the pair ΔU was computed for, so exemplars "
                "without a ranking are four episodes with labels nothing earned"
            )
        if self.representative_episodes is not None and waterfall is not None:
            # **Ordered**, not a set. ``strongest_for_winner`` is defined
            # against whichever candidate ΔU was computed *for*, so an
            # exemplar set built the other way round is the same four
            # episodes with two of the labels swapped.
            ordered = (
                self.representative_episodes.candidate_a,
                self.representative_episodes.candidate_b,
            )
            expected = (waterfall.candidate_a, waterfall.candidate_b)
            if ordered != expected:
                raise CasePacketRefusal(
                    f"the exemplars are about {ordered} and the waterfall about "
                    f"{expected}; the same pair the other way round relabels "
                    "'best for the winner' as the runner-up's best episode"
                )
        return self

    @property
    def blocked_claim_types(self) -> tuple[str, ...]:
        """Every claim type this packet forbids, deduplicated and sorted.

        Convenience for a caller wiring the promotion matrix, so the
        enforcement reads from the packet rather than from a list
        somebody kept in step by hand.
        """
        return tuple(
            sorted({kind for unknown in self.known_unknowns for kind in unknown.blocks_claim_types})
        )


def build_case_packet(
    *,
    run_id: str,
    header: ExplanationArtifactHeader,
    task: TaskFacts,
    candidates: Sequence[CandidateComponents],
    decision: DecisionFacts,
    lattice: Sequence[ContrastFinding] = (),
    observations: Sequence[Observation] = (),
    representative_episodes: ExemplarSet | None = None,
    extra_unknowns: Sequence[KnownUnknown] = (),
    evidence_class: str = "production",
) -> CasePacket:
    """Assemble one packet from parts every other module already made.

    **A packet with no comparison is still a packet.** See
    :attr:`DecisionFacts.waterfall`: a run that ranked nobody has
    sightings, geometry and a gate table, and those are the evidence
    somebody asking "why did it fail" needs. What it does not have is a
    pair, so it carries no waterfall and no exemplars — and the panel
    matrix already knows not to draw either.

    A composition, on purpose. Detectors, the waterfall, the lattice and
    the exemplar recipe are each testable alone and each refuse their
    own bad inputs; a builder that recomputed any of them here would be
    a second implementation to keep in step.

    ``extra_unknowns`` are added to :data:`STANDING_UNKNOWNS` rather than
    replacing them: a caller who knows about one more gap should not be
    able to drop the ones that always apply.
    """
    unknowns = list(STANDING_UNKNOWNS)
    seen = {unknown.id for unknown in unknowns}
    for unknown in extra_unknowns:
        if unknown.id in seen:
            raise CasePacketRefusal(
                f"known unknown {unknown.id!r} is already one of the standing gaps; "
                "two entries with one id would let a reader think two things were "
                "unavailable when one is"
            )
        seen.add(unknown.id)
        unknowns.append(unknown)

    if header.knowledge_base_version != KNOWLEDGE_BASE_VERSION:
        raise CasePacketRefusal(
            f"header names knowledge base {header.knowledge_base_version!r} but this "
            f"build carries {KNOWLEDGE_BASE_VERSION!r}; a packet whose citations "
            "resolve against a different base is a packet nobody can re-read"
        )

    return CasePacket(
        header=header,
        run_id=run_id,
        task=task,
        candidates=tuple(candidates),
        decision=decision,
        lattice=tuple(lattice),
        observations=tuple(observations),
        representative_episodes=representative_episodes,
        known_unknowns=tuple(unknowns),
        evidence_class=evidence_class,
    )
