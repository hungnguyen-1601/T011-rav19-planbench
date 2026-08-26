"""The packet, read once, as a list of facts that can be pointed at.

The analyst is given a :class:`~planbench_explanation.case_packet.CasePacket`
and must return statements that cite it. Two things have to be true for
that to mean anything, and neither is true of the packet as a nested
document:

**Every number a reader sees has to be reachable by a name.** A
statement carrying its own ``0.74`` is a statement whose number nobody
can check without re-deriving it. So each quantity in the packet gets a
``ref`` here, the analyst cites the ref, and the renderer prints the
value out of this index. The model never transcribes a number, which is
the only version of "the model does not invent numbers" that a test can
hold it to.

**A citation that resolves is not a citation that supports.** The
advisor's live run turned up the case that motivates
:attr:`Fact.subject`: a model cited a field that existed, held the value
it implied, and did not say what the sentence claimed it said. So a fact
records *what it is about* — the component when the packet attributes
one, the candidate when it names one, the scope always — and the guard
compares that against the proposal rather than only asking whether the
ref exists.

The view is also the layer that refuses a packet built by code this
service does not implement. Five versions travel in the header and each
one changes what the layer would output from byte-identical run data; a
view that read a packet from another schema would answer confidently
about fields that moved.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from planbench_analyst.sanitize import Aliases, label_components
from planbench_explanation.case_packet import CasePacket
from planbench_explanation.detectors import DETECTOR_VERSION
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
from planbench_explanation.ledger import EvidenceKind
from planbench_explanation.subjects import Subject
from planbench_explanation.versioning import (
    EXPLANATION_SCHEMA_VERSION,
    PROMOTION_MATRIX_VERSION,
    artifact_checksum,
)
from planbench_schemas.identity import canonical_json

__all__ = [
    "Fact",
    "PacketView",
    "PacketViewRefusal",
    "build_packet_view",
]


class PacketViewRefusal(ValueError):
    """The packet cannot be read by this build of the analyst."""


#: Unit for a measurement, read off the suffix the platform already
#: writes into its field and key names. Read rather than tabulated
#: because the keys of ``Observation.typical`` are the detectors' own and
#: a table here would be a second list to keep in step with them — and
#: the failure of that table would be a unit quietly reported as blank
#: for a number a reader is comparing against a threshold.
_UNIT_BY_SUFFIX: tuple[tuple[str, str], ...] = (
    ("_m", "m"),
    ("_ms", "ms"),
    ("_s", "s"),
    ("_deg", "deg"),
    ("_hz", "Hz"),
)


def _unit_for(name: str) -> str:
    for suffix, unit in _UNIT_BY_SUFFIX:
        if name.endswith(suffix):
            return unit
    return ""


class Fact(BaseModel):
    """One value in the packet, and everything needed to cite it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: How the analyst names it. Extends the vocabulary already in use —
    #: ``obs:<type>:<candidate>``, ``episode:<context_id>`` — rather than
    #: inventing a second one, because the model-free floor already emits
    #: those two and a guard that accepted only new-style refs would
    #: reject the floor it is meant to be compared against.
    ref: str = Field(min_length=1)
    kind: EvidenceKind
    #: What the value is, in words, for the renderer and for a reader
    #: checking a citation by hand.
    label: str = Field(min_length=1)
    #: ``None`` for a named gap: a known unknown is a fact about this
    #: packet and has no value, and leaving it out of the index would
    #: mean an analyst could not cite the reason it is abstaining.
    value: float | int | str | None = None
    unit: str = ""
    #: The component the packet attributes this to, or ``None`` when it
    #: attributes none. Most measurements are ``None`` on purpose:
    #: naming who is responsible is the lattice's job, not a
    #: measurement's, and a fact that guessed would hand the guard a
    #: confident wrong answer.
    subject: Subject | None = None
    candidate_id: str | None = None
    #: Where the value lives: ``run``, ``robot``, ``route``,
    #: ``candidate:<id>``, ``pair:<a>|<b>``, ``episode:<id>``,
    #: ``gate:<id>``.
    scope: str = Field(min_length=1)


class PacketView:
    """A packet plus its fact index. Immutable, and deterministic."""

    def __init__(
        self, packet: CasePacket, facts: tuple[Fact, ...], aliases: Aliases | None = None
    ) -> None:
        self._packet = packet
        self._aliases = aliases or Aliases()
        self._facts = tuple(sorted(facts, key=lambda fact: fact.ref))
        seen: dict[str, Fact] = {}
        for fact in self._facts:
            if fact.ref in seen:
                raise PacketViewRefusal(
                    f"two facts claim the ref {fact.ref!r}; a ref that names two values "
                    "is a citation a reader cannot follow"
                )
            seen[fact.ref] = fact
        self._by_ref = seen

    @property
    def packet(self) -> CasePacket:
        return self._packet

    @property
    def aliases(self) -> Aliases:
        """Labels standing in for strings a third party wrote.

        The model is shown ``C1``; the renderer holds what ``C1`` is.
        See :mod:`planbench_analyst.sanitize` for why the isolation and
        not the warning in the prompt is what holds.
        """
        return self._aliases

    @property
    def facts(self) -> tuple[Fact, ...]:
        return self._facts

    def fact(self, ref: str) -> Fact | None:
        return self._by_ref.get(ref)

    def __contains__(self, ref: object) -> bool:
        return isinstance(ref, str) and ref in self._by_ref

    def refs_for_subject(self, subject: Subject) -> tuple[str, ...]:
        """Refs the packet attributes to one component.

        The guard's sixth rule reads this: a proposal about the local
        controller supported only by facts the packet attributes to the
        costmap is not a citation problem, it is a different claim.
        """
        return tuple(fact.ref for fact in self._facts if fact.subject == subject)

    @property
    def identifiers(self) -> frozenset[str]:
        """Names a statement may contain although they carry digits.

        ``aisle_B7`` and ``ep-004`` are identifiers; ``0.74`` is a
        measurement. The guard's rule against quantities in a statement
        has to tell them apart, and the only honest way to do that is a
        list of the names this packet actually uses.
        """
        packet = self._packet
        names: set[str] = {packet.run_id, packet.task.task_profile_id}
        for candidate in packet.candidates:
            # The candidate id is the platform's; the three component
            # names are whatever the uploader called them, so what a
            # statement may legitimately contain is the **label**.
            names.add(candidate.candidate_id)
        names.update(self._aliases.by_label)
        for observation in packet.observations:
            names.add(observation.type)
            if observation.worst_episode_context_id is not None:
                names.add(observation.worst_episode_context_id)
        for finding in packet.lattice:
            names.add(finding.detection_type)
            if finding.subject is not None:
                names.add(finding.subject)
        if packet.representative_episodes is not None:
            names.update(
                exemplar.episode_context_id
                for exemplar in packet.representative_episodes.exemplars
            )
        if packet.decision.waterfall is not None:
            names.update(bar.objective for bar in packet.decision.waterfall.bars)
        names.update(unknown.id for unknown in packet.known_unknowns)
        return frozenset(names)

    def serialize(self) -> str:
        """The bytes an analyst is shown, and the ones a checksum covers.

        Sorted by ref and rendered through the canonical JSON the rest
        of the layer uses, so the same packet is the same string on
        every machine and a cache key over it means what it says.
        """
        header = self._packet.header
        return canonical_json(
            {
                "header": {
                    "explanation_schema_version": header.explanation_schema_version,
                    "promotion_matrix_version": header.promotion_matrix_version,
                    "detector_version": header.detector_version,
                    "knowledge_base_version": header.knowledge_base_version,
                    "tool_catalog_version": header.tool_catalog_version,
                    "source_manifest_checksum": header.source_manifest_checksum,
                },
                "run_id": self._packet.run_id,
                "evidence_class": self._packet.evidence_class,
                "facts": [fact.model_dump(mode="json") for fact in self._facts],
                "blocked_claim_types": sorted(
                    {
                        claim
                        for unknown in self._packet.known_unknowns
                        for claim in unknown.blocks_claim_types
                    }
                ),
            }
        )

    @property
    def checksum(self) -> str:
        return artifact_checksum(self.serialize())


def _header_mismatches(packet: CasePacket, *, tool_catalog_version: str) -> list[str]:
    header = packet.header
    expected = (
        (
            "explanation_schema_version",
            header.explanation_schema_version,
            EXPLANATION_SCHEMA_VERSION,
        ),
        ("promotion_matrix_version", header.promotion_matrix_version, PROMOTION_MATRIX_VERSION),
        ("detector_version", header.detector_version, DETECTOR_VERSION),
        ("knowledge_base_version", header.knowledge_base_version, KNOWLEDGE_BASE_VERSION),
        ("tool_catalog_version", header.tool_catalog_version, tool_catalog_version),
    )
    return [
        f"{field}={found!r} but this build implements {wanted!r}"
        for field, found, wanted in expected
        if found != wanted
    ]


def _scalar_facts(
    prefix: str,
    scope: str,
    values: Mapping[str, Any],
    *,
    kind: EvidenceKind = "fact",
    subject: Subject | None = None,
    candidate_id: str | None = None,
    label_prefix: str = "",
) -> list[Fact]:
    facts: list[Fact] = []
    for name, value in sorted(values.items()):
        keep: float | int | str | None
        if value is None:
            # Kept, not skipped. ``inflation_margin_m`` holding null is
            # the packet saying the run did not record it, and an
            # analyst that cannot cite that has to either guess or go
            # quiet about the one thing it knows is missing.
            keep = None
        elif isinstance(value, bool):
            keep = "true" if value else "false"
        elif isinstance(value, int | float | str):
            keep = value
        else:
            # Structured values are skipped rather than stringified: a
            # dict rendered into a ref would be a number a reader cannot
            # locate in the packet, which is the thing this index exists
            # to prevent.
            continue
        facts.append(
            Fact(
                ref=f"{prefix}{name}",
                kind=kind,
                label=f"{label_prefix}{name.replace('_', ' ')}",
                value=keep,
                unit=_unit_for(name),
                subject=subject,
                candidate_id=candidate_id,
                scope=scope,
            )
        )
    return facts


def build_packet_view(
    packet: CasePacket, *, tool_catalog_version: str, aliases: Aliases | None = None
) -> PacketView:
    """Index one packet, or refuse to read it.

    ``tool_catalog_version`` is passed in rather than imported: the
    catalog the round runs against is named by the frozen bundle, and a
    view that read the version from the catalog module would agree with
    itself while disagreeing with the bundle being graded.
    """
    mismatches = _header_mismatches(packet, tool_catalog_version=tool_catalog_version)
    if mismatches:
        raise PacketViewRefusal(
            "this packet was written by a different build of the explanation layer: "
            + "; ".join(mismatches)
            + ". Reading it would answer about fields that may have moved."
        )

    if aliases is None:
        aliases = label_components(
            name
            for candidate in packet.candidates
            for name in (
                candidate.global_planner,
                candidate.local_controller,
                candidate.local_controller_config,
            )
        )

    facts: list[Fact] = []

    # The stack each candidate ran, as labels. A component name is the
    # one string in this packet a third party wrote — see
    # :mod:`planbench_analyst.sanitize`. The label is what the model
    # reasons with and what a statement may name; the renderer holds
    # what it stands for.
    for candidate in packet.candidates:
        for field_name, subject in (
            ("global_planner", "global_planner"),
            ("local_controller", "local_controller"),
            ("local_controller_config", "local_controller"),
        ):
            facts.append(
                Fact(
                    ref=f"fact:candidate:{candidate.candidate_id}.{field_name}",
                    kind="fact",
                    label=f"{candidate.candidate_id} {field_name.replace('_', ' ')}",
                    value=aliases.label_for(getattr(candidate, field_name)),
                    subject=subject,  # type: ignore[arg-type]
                    candidate_id=candidate.candidate_id,
                    scope=f"candidate:{candidate.candidate_id}",
                )
            )

    robot = packet.task.robot
    facts.extend(
        _scalar_facts(
            "fact:robot.",
            "robot",
            {
                "radius_m": robot.radius_m,
                "inflation_margin_m": robot.inflation_margin_m,
                "required_passage_width_m": robot.required_passage_width_m,
            },
            subject="costmap_inflation",
            label_prefix="robot ",
        )
    )
    if packet.task.route is not None:
        facts.extend(
            _scalar_facts(
                "fact:route.",
                "route",
                packet.task.route.model_dump(mode="json"),
                subject="task_geometry",
                label_prefix="route ",
            )
        )

    # What each candidate scored. The decomposition says how a pair
    # differed; this says what either of them did, and it is the first
    # thing a reader asking "why did this one win" reaches for.
    for measured in packet.measurements:
        for name, value in sorted(measured.recorded.items()):
            facts.append(
                Fact(
                    ref=f"fact:metric:{measured.candidate_id}.{name}",
                    kind="fact",
                    label=f"{measured.candidate_id} {name.replace('_', ' ')}",
                    value=value.value,
                    unit=value.unit,
                    candidate_id=measured.candidate_id,
                    scope=f"candidate:{measured.candidate_id}",
                )
            )
            if value.denominator is not None:
                # The denominator is a fact of its own so a statement can
                # cite it: "over thirty episodes" is the half of a rate
                # that keeps it from being read as a promise.
                facts.append(
                    Fact(
                        ref=f"fact:metric:{measured.candidate_id}.{name}.denominator",
                        kind="fact",
                        label=f"episodes behind {measured.candidate_id} {name}",
                        value=value.denominator,
                        unit="episodes",
                        candidate_id=measured.candidate_id,
                        scope=f"candidate:{measured.candidate_id}",
                    )
                )

    facts.append(
        Fact(
            ref="fact:decision.status",
            kind="fact",
            label="decision status",
            value=packet.decision.status,
            scope="run",
        )
    )
    for row in packet.decision.gate_outcomes:
        # ``{"passed": false}`` says a candidate was eliminated and
        # refuses to say by how much. Where the run recorded the number
        # and the threshold, both are facts a statement can cite; where
        # it did not, the null says "not recorded" rather than zero.
        facts.extend(
            _scalar_facts(
                f"fact:gate:{row.gate_id}.",
                f"gate:{row.gate_id}",
                {
                    "passed": row.passed,
                    "threshold": row.threshold,
                    "value": row.value,
                    "direction": row.direction or None,
                },
                label_prefix=f"gate {row.gate_id} ",
            )
        )

    waterfall = packet.decision.waterfall
    if waterfall is not None:
        pair = f"pair:{waterfall.candidate_a}|{waterfall.candidate_b}"
        facts.extend(
            _scalar_facts(
                "fact:waterfall.",
                pair,
                {
                    "delta_utility_mean": waterfall.delta_utility_mean,
                    "delta_utility_median": waterfall.delta_utility_median,
                    "total_ci95_low": waterfall.total_ci95[0],
                    "total_ci95_high": waterfall.total_ci95[1],
                    "n_episodes": waterfall.n_episodes,
                },
                label_prefix="paired ",
            )
        )
        for bar in waterfall.bars:
            facts.append(
                Fact(
                    ref=f"bar:{bar.objective}",
                    kind="fact",
                    label=f"{bar.objective} contribution to paired ΔU",
                    value=bar.contribution,
                    scope=pair,
                )
            )
            facts.extend(
                _scalar_facts(
                    f"bar:{bar.objective}/",
                    pair,
                    {
                        "weight": bar.weight,
                        "delta_objective_mean": bar.delta_objective_mean,
                        "ci95_low": bar.ci95[0],
                        "ci95_high": bar.ci95[1],
                    },
                    label_prefix=f"{bar.objective} ",
                )
            )

    for observation in packet.observations:
        base = f"obs:{observation.type}:{observation.candidate_id}"
        facts.append(
            Fact(
                ref=base,
                kind="observation",
                label=f"{observation.type} on {observation.candidate_id}",
                value=observation.episodes_seen,
                unit="episodes",
                candidate_id=observation.candidate_id,
                scope=f"candidate:{observation.candidate_id}",
            )
        )
        facts.extend(
            _scalar_facts(
                f"{base}/",
                f"candidate:{observation.candidate_id}",
                {
                    "episodes_total": observation.episodes_total,
                    "prevalence": observation.prevalence,
                    **observation.typical,
                },
                kind="observation",
                candidate_id=observation.candidate_id,
                label_prefix=f"{observation.type} ",
            )
        )

    for finding in packet.lattice:
        facts.append(
            Fact(
                ref=f"contrast:{finding.detection_type}",
                kind="contrast",
                label=f"lattice reading for {finding.detection_type}",
                value=finding.verdict,
                subject=finding.subject,
                scope="run",
            )
        )

    chosen = packet.representative_episodes
    if chosen is not None:
        # One episode can hold two roles — the worst on utility is often
        # also the worst on clearance — and the ref names the episode,
        # not the role, because that is the ref the floor and the replay
        # window already use. So the roles are collected onto one fact
        # rather than fighting over the name.
        roles: dict[str, list[str]] = {}
        for exemplar in chosen.exemplars:
            roles.setdefault(exemplar.episode_context_id, []).append(exemplar.role)
        seen_episodes: set[str] = set()
        for exemplar in chosen.exemplars:
            if exemplar.episode_context_id in seen_episodes:
                continue
            seen_episodes.add(exemplar.episode_context_id)
            named = ", ".join(roles[exemplar.episode_context_id])
            facts.append(
                Fact(
                    ref=f"episode:{exemplar.episode_context_id}",
                    kind="trace_window",
                    label=f"{named} episode",
                    value=exemplar.delta_utility,
                    unit="utility",
                    scope=f"episode:{exemplar.episode_context_id}",
                )
            )

    # How the exemplar episodes went while they were going. The clock
    # is **in the ref**, not implied by position: "who is ahead" and
    # "who did the same work better" are two questions, and a citation
    # that did not say which one it meant would be unreadable.
    for timeline in packet.timelines:
        for point in timeline.points:
            base = (
                f"episode:{timeline.episode_context_id}/{point.clock}/"
                f"{point.mark:g}"
            )
            facts.extend(
                _scalar_facts(
                    f"{base}.",
                    f"episode:{timeline.episode_context_id}",
                    {
                        "progress_fraction": point.progress_fraction,
                        "safety_margin": point.safety_margin,
                        "compute_budget": point.compute_budget,
                        "path_efficiency": point.path_efficiency,
                        "replans": point.replans,
                    },
                    kind="trace_window",
                    candidate_id=timeline.candidate_id,
                    label_prefix=f"{timeline.role} episode at {point.clock} {point.mark:g} ",
                )
            )

    for unknown in packet.known_unknowns:
        facts.append(
            Fact(
                ref=f"unknown:{unknown.id}",
                kind="fact",
                label=f"declared gap, from {unknown.source}",
                value=None,
                scope="run",
            )
        )

    return PacketView(packet, tuple(facts), aliases)
