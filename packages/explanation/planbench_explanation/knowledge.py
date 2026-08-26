"""The curated mechanism knowledge base, and a matcher with no model in it — E3.

An analyst that reaches a mechanism has to cite something. This is the
something: a small, hand-written, versioned set of entries saying *under
these conditions, this mechanism is a known explanation of that
behaviour*, each with the sources it came from and how strong they are.

**Curated, not learned, and not inside a model's weights.** A mechanism
an LLM recalls is a mechanism nobody can check; an entry here has an id,
a version, and a list of sources a reader can go and read. Citing
``kb:inflation_gap_closure@2`` is checkable in a way that "as is well
known" is not.

**Nothing here promotes a claim.** ``source_strength`` and
``review_status`` are metadata *about the entry*, and the promotion
matrix does not read them: a strongly-sourced entry is still only a
citation, and what promotes a claim is a checker result on this run's
data. That separation is why a wrong entry cannot, by itself, produce a
verified-looking claim — it produces a suggestion that a checker then
fails to confirm.

**v1 ships as ``draft``.** Every entry below was written from the
project's own notes and standard navigation literature by one person and
reviewed by nobody, and E0's rule is that an unapproved entry may not
back a promoted claim. Shipping them as ``approved`` because they look
right to their author is precisely the move the review status exists to
prevent. They are useful today as reading for whoever is looking at a
detection, and they become promotable when somebody has actually read
and signed them.

**The matcher is deterministic and dull on purpose.** Conditions are
compared literally — a detection type, a subject, and optional numeric
bounds — with ties broken by entry id. No embedding, no similarity, no
model. Retrieval that is *approximately* right is exactly what turns a
narrow entry into a plausible-sounding wrong explanation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.detectors import DetectionType
from planbench_explanation.propositions import PropositionType
from planbench_explanation.subjects import Subject

#: How well-founded an entry is. Metadata for a reader, never an input
#: to promotion.
SourceStrength = Literal["textbook", "peer_reviewed", "project_measurement", "practitioner_lore"]

#: Whether a human has signed this entry off. Only ``approved`` entries
#: may back a promoted claim (E0); the matcher returns the others so a
#: reader can still see them, labelled.
ReviewStatus = Literal["draft", "approved", "withdrawn"]

KNOWLEDGE_BASE_ID = "navigation-mechanisms"

#: Bumped whenever any entry changes. A claim cites an entry *at a
#: version*, so an edit must not silently change what an old claim said.
KNOWLEDGE_BASE_VERSION = "v1.0.0"


class KnowledgeRefusal(ValueError):
    """An entry or a query that cannot be used as it stands."""


class ActivationConditions(BaseModel):
    """When an entry applies. Narrow by construction.

    A condition set that matches everything is worse than no entry: it
    attaches a mechanism to every detection and teaches a reader to
    ignore the citations.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    detection_types: tuple[DetectionType, ...]
    subject: Subject
    #: Optional numeric gates on the detection's own measurements, in
    #: the detection's units. Both bounds inclusive.
    measurement_at_most: dict[str, float] = Field(default_factory=dict)
    measurement_at_least: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> ActivationConditions:
        if not self.detection_types:
            raise KnowledgeRefusal(
                "an entry that names no detection type matches every observation, "
                "which is how a knowledge base becomes noise"
            )
        return self

    def matches(self, detection_type: str, measurements: Mapping[str, float]) -> bool:
        if detection_type not in self.detection_types:
            return False
        for key, ceiling in self.measurement_at_most.items():
            if key not in measurements or measurements[key] > ceiling:
                return False
        for key, floor in self.measurement_at_least.items():
            if key not in measurements or measurements[key] < floor:
                return False
        return True


class KnowledgeEntry(BaseModel):
    """One mechanism, its conditions, and where it comes from."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    entry_id: str = Field(min_length=1)
    entry_version: int = Field(ge=1)
    title: str = Field(min_length=1)
    #: What the mechanism *is*, in a sentence a reader can disagree with.
    mechanism: str = Field(min_length=1)
    #: The proposition an analyst would be arguing for by citing this.
    #: Present so a citation can be lined up against what a checker can
    #: actually verify, rather than left as prose.
    proposition_type: PropositionType
    conditions: ActivationConditions
    source_strength: SourceStrength
    review_status: ReviewStatus
    source_refs: tuple[str, ...] = ()
    #: What this entry does **not** explain. Written down because the
    #: near-miss reading is the one a reader makes on their own.
    does_not_explain: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> KnowledgeEntry:
        if self.review_status == "approved" and not self.source_refs:
            raise KnowledgeRefusal(
                f"entry {self.entry_id!r} is approved with no sources; approval is a "
                "statement that somebody checked something, and there is nothing here "
                "to have checked"
            )
        return self

    @property
    def citation(self) -> str:
        """How a claim refers to this entry — pinned to the version."""
        return f"kb:{self.entry_id}@{self.entry_version}"


class KnowledgeMatch(BaseModel):
    """One entry the matcher offered, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    entry: KnowledgeEntry
    detection_type: DetectionType
    #: True only for an approved entry. A caller that promotes anything
    #: reads this rather than re-deriving the rule.
    may_support_a_claim: bool

    @model_validator(mode="after")
    def _check(self) -> KnowledgeMatch:
        expected = self.entry.review_status == "approved"
        if self.may_support_a_claim != expected:
            raise KnowledgeRefusal(
                f"entry {self.entry.entry_id!r} is {self.entry.review_status!r} but the "
                f"match says may_support_a_claim={self.may_support_a_claim}"
            )
        return self


#: Curated v1. Every entry is ``draft`` — see the module docstring.
KNOWLEDGE_BASE: tuple[KnowledgeEntry, ...] = (
    KnowledgeEntry(
        entry_id="inflation_gap_closure",
        entry_version=1,
        title="Inflation closes a passage the robot would physically fit through",
        mechanism=(
            "A costmap inflates obstacles by the robot's radius plus a safety margin. "
            "Where two obstacles are closer together than twice that margin, the "
            "inflated regions meet and the planner sees no free cells, so it refuses a "
            "passage the robot's footprint would in fact clear."
        ),
        proposition_type="geometric_infeasibility",
        conditions=ActivationConditions(
            detection_types=("narrow_gap_refusal",),
            subject="costmap_inflation",
            measurement_at_most={"margin_m": 0.0},
        ),
        source_strength="textbook",
        review_status="draft",
        source_refs=("ROS navigation costmap_2d inflation layer documentation",),
        does_not_explain=(
            "why the robot approached that passage rather than another route",
            "how much of the utility difference the refusal accounts for",
        ),
    ),
    KnowledgeEntry(
        entry_id="local_minimum_in_concave_obstacle",
        entry_version=1,
        title="Local controller stalls in a concave pocket",
        mechanism=(
            "A sampling local controller scores short-horizon rollouts against distance "
            "to the goal. Inside a concave obstacle every sample that leaves the pocket "
            "scores worse than one that stays, so the controller oscillates or stops "
            "until something outside its horizon changes."
        ),
        proposition_type="local_minimum_entrapment",
        conditions=ActivationConditions(
            detection_types=("stuck_cluster", "oscillation"),
            subject="local_controller",
        ),
        source_strength="textbook",
        review_status="draft",
        source_refs=("Fox, Burgard & Thrun (1997), The Dynamic Window Approach",),
        does_not_explain=(
            "whether the global planner could have routed around the pocket",
            "cases where the robot stopped for a moving obstacle",
        ),
    ),
    KnowledgeEntry(
        entry_id="sampling_budget_exhausted",
        entry_version=1,
        title="Sampling planner runs out of samples before the corridor is found",
        mechanism=(
            "A sampling-based global planner needs enough samples inside a narrow "
            "corridor for the tree to pass through it. When the sample budget is small "
            "relative to the corridor's share of free space, the planner returns a "
            "longer route or none, and it does so intermittently across seeds."
        ),
        proposition_type="sampling_budget_insufficiency",
        conditions=ActivationConditions(
            detection_types=("detour", "narrow_gap_refusal"),
            subject="global_planner",
        ),
        source_strength="peer_reviewed",
        review_status="draft",
        source_refs=(
            "Karaman & Frazzoli (2011), Sampling-based Algorithms for Optimal Motion Planning",
        ),
        does_not_explain=(
            "a detour that appears on every seed, which points at geometry rather than sampling",
        ),
    ),
    KnowledgeEntry(
        entry_id="expansion_cost_tracks_latency",
        entry_version=1,
        title="Search expansions and control latency move together",
        mechanism=(
            "A grid search's running time grows with the number of nodes it expands. "
            "Where a replan expands a large frontier, the control tick carrying that "
            "replan takes correspondingly longer."
        ),
        proposition_type="expansion_latency_association",
        conditions=ActivationConditions(
            detection_types=("latency_spike",),
            subject="global_planner",
        ),
        source_strength="project_measurement",
        review_status="draft",
        source_refs=(
            "planbench: replan rows carry the global planner's latency (CONTRACTS 6.8.0)",
        ),
        does_not_explain=(
            "that the expansions caused the latency rather than both following from the "
            "same difficult query",
            "latency attributable to the deployment's own compute, which H4 has not yet split out",
        ),
    ),
    KnowledgeEntry(
        entry_id="replan_thrash_on_moving_obstacle",
        entry_version=1,
        title="Repeated replanning around a moving obstacle",
        mechanism=(
            "When a dynamic obstacle keeps invalidating the current route, the stack "
            "replans each time the path is blocked. Each replan costs a control tick and "
            "may produce a route the obstacle blocks again a moment later."
        ),
        proposition_type="replan_instability",
        conditions=ActivationConditions(
            detection_types=("replan_storm",),
            subject="global_planner",
        ),
        source_strength="practitioner_lore",
        review_status="draft",
        source_refs=(
            "planbench: replanning is priced in travel time and p99 latency (CONTRACTS 6.8.0)",
        ),
        does_not_explain=("which of the two layers should have handled the obstacle",),
    ),
)


def match(
    detection_type: str,
    measurements: Mapping[str, float],
    *,
    subject: Subject | None = None,
    entries: Sequence[KnowledgeEntry] = KNOWLEDGE_BASE,
) -> tuple[KnowledgeMatch, ...]:
    """Entries whose conditions this detection satisfies, id-ordered.

    Deterministic and literal: same detection, same list, in the same
    order, forever. Ordered by entry id rather than by any notion of
    relevance — a ranking would be a judgement the platform cannot
    defend, and the caller can see every match anyway.

    Returns nothing when nothing matches, which is the answer. An
    unmatched detection is rendered as the bare symptom; inventing a
    mechanism for it is the failure this whole layer is built against.
    """
    found = [
        entry
        for entry in entries
        if entry.review_status != "withdrawn"
        and entry.conditions.matches(detection_type, measurements)
        and (subject is None or entry.conditions.subject == subject)
    ]
    return tuple(
        KnowledgeMatch(
            entry=entry,
            detection_type=detection_type,  # type: ignore[arg-type]
            may_support_a_claim=entry.review_status == "approved",
        )
        for entry in sorted(found, key=lambda item: item.entry_id)
    )


def resolve(citation: str, *, entries: Sequence[KnowledgeEntry] = KNOWLEDGE_BASE) -> KnowledgeEntry:
    """The entry a ``kb:<id>@<version>`` citation names.

    Refuses an unknown id and a version mismatch alike. This is the
    canonical lookup E0's knowledge contract requires: a retrieval layer
    may propose an entry key, and what the platform believes about that
    entry comes from here — never from the fields the retrieval sent.
    """
    if not citation.startswith("kb:") or "@" not in citation:
        raise KnowledgeRefusal(
            f"{citation!r} is not a knowledge citation; write kb:<entry_id>@<entry_version>"
        )
    entry_id, _, version = citation[3:].partition("@")
    for entry in entries:
        if entry.entry_id == entry_id:
            if str(entry.entry_version) != version:
                raise KnowledgeRefusal(
                    f"{citation} names version {version} but the knowledge base holds "
                    f"version {entry.entry_version}; an edited entry does not silently "
                    "become what an older claim cited"
                )
            return entry
    raise KnowledgeRefusal(f"no knowledge entry {entry_id!r} in {KNOWLEDGE_BASE_ID}")
