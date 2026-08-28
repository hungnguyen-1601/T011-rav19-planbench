"""The fact index for one episode: what may be cited, and what it says.

Built beside :class:`~planbench_analyst.packet_view.PacketView` rather
than inside it. The two answer the same three questions the guard
asks — is this ref real, what does it attribute, which strings are names
rather than quantities — and index different things: that one holds a
run's aggregates, this one holds one episode and the two sides of it.

**What is deliberately absent.** No ``fact:waterfall.*``, no
``bar:<objective>``, no exemplar-role episode facts, no lattice verdict.
Every one of those is a set-level statement over thirty episodes, and a
sentence about this episode that rested on one would be borrowing weight
from the other twenty-nine.

**Run context is here and cannot be cited.** Facts about the run travel
as a labelled block in the prompt with no ref, so the existing rule 1 —
a citation must resolve in the index — drops any attempt to lean on
them. No new rule, no new field: what has no name cannot be named.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from planbench_analyst.packet_view import Fact, PacketViewRefusal
from planbench_analyst.sanitize import Aliases, label_components
from planbench_explanation.episode_packet import (
    EpisodeContrast,
    EpisodePacket,
)
from planbench_explanation.knowledge_contract import MechanismReferenceCandidate
from planbench_explanation.subjects import Subject
from planbench_explanation.versioning import artifact_checksum
from planbench_schemas.identity import canonical_json


class EpisodeViewRefusal(PacketViewRefusal):
    """This episode packet cannot be read by this build of the analyst."""


class EpisodeView:
    """One episode's packet and its fact index. Immutable, deterministic.

    The same surface the guard already uses — ``fact``, ``__contains__``,
    ``identifiers``, ``refs_for_subject``, ``packet.blocked_claim_types``
    — so the seven rules run over an episode round unchanged. Widening
    ``PacketView`` to take either shape would have put a branch in every
    one of its builders instead.
    """

    def __init__(
        self,
        packet: EpisodePacket,
        facts: tuple[Fact, ...],
        aliases: Aliases | None = None,
    ) -> None:
        self._packet = packet
        self._aliases = aliases or Aliases()
        self._facts = tuple(sorted(facts, key=lambda fact: fact.ref))
        seen: dict[str, Fact] = {}
        for fact in self._facts:
            if fact.ref in seen:
                raise EpisodeViewRefusal(
                    f"two facts claim the ref {fact.ref!r}; a ref that names two values "
                    "is a citation a reader cannot follow"
                )
            seen[fact.ref] = fact
        self._by_ref = seen

    @property
    def packet(self) -> EpisodePacket:
        return self._packet

    @property
    def aliases(self) -> Aliases:
        return self._aliases

    @property
    def facts(self) -> tuple[Fact, ...]:
        return self._facts

    def fact(self, ref: str) -> Fact | None:
        return self._by_ref.get(ref)

    def __contains__(self, ref: object) -> bool:
        return isinstance(ref, str) and ref in self._by_ref

    def refs_for_subject(self, subject: Subject) -> tuple[str, ...]:
        return tuple(fact.ref for fact in self._facts if fact.subject == subject)

    @property
    def identifiers(self) -> frozenset[str]:
        """Strings that are names, not quantities.

        Rule 2 forbids a number in a statement and has to let ``C1`` and
        an episode id through. The component names themselves are never
        here: the model sees labels, and the labels are what it may
        write.
        """
        names: set[str] = {self._packet.episode_context_id, self._packet.run_id}
        names.update(self._aliases.by_label)
        for stack in self._packet.candidates:
            names.add(stack.candidate_id)
        return frozenset(name for name in names if name)

    @property
    def checksum(self) -> str:
        """What the round records as the facts it was answering about.

        Over the **serialised index** rather than over the packet: what
        identifies a round is what the model was shown, and the budgeter
        may have trimmed the packet on the way here.
        """
        return artifact_checksum(self.serialize())

    def serialize(self) -> str:
        """The index as the model will read it. Same input, same string."""
        return canonical_json(
            {
                "episode": self._packet.episode_context_id,
                "facts": [fact.model_dump(mode="json") for fact in self._facts],
            }
        )


def _verdict_facts(packet: EpisodePacket) -> list[Fact]:
    """Who won, as facts nothing may contradict.

    ``subject`` is ``None`` throughout: a verdict is an arithmetic over
    two scored rows and attributes nothing to any component. A verdict
    fact that named one would hand the guard a confident wrong answer
    about what a citation supports.
    """
    verdict = packet.verdict
    scope = f"episode:{packet.episode_context_id}"
    facts = [
        Fact(
            ref="verdict:basis",
            kind="observation",
            label="how this episode was decided",
            value=verdict.basis,
            scope=scope,
        ),
        Fact(
            ref="verdict:caveat",
            kind="observation",
            label="what a single episode can carry",
            value=verdict.caveat,
            scope=scope,
        ),
    ]
    if verdict.winner is not None:
        facts.append(
            Fact(
                ref="verdict:winner",
                kind="observation",
                label="the candidate this episode went to",
                value=verdict.winner,
                candidate_id=verdict.winner,
                scope=scope,
            )
        )
        facts.append(
            Fact(
                ref="verdict:loser",
                kind="observation",
                label="the candidate this episode went against",
                value=verdict.loser,
                candidate_id=verdict.loser,
                scope=scope,
            )
        )
    else:
        facts.append(
            Fact(
                ref="verdict:undecided",
                kind="observation",
                label="why this episode names no winner",
                value=verdict.undecided_reason,
                scope=scope,
            )
        )
    for name, measured in (
        ("verdict:utility_a", verdict.utility_a),
        ("verdict:utility_b", verdict.utility_b),
        ("verdict:delta_utility", verdict.delta_utility),
    ):
        if measured is None:
            continue
        facts.append(
            Fact(
                ref=name,
                kind="fact",
                label=f"{name.rsplit(':', 1)[-1].replace('_', ' ')} over one episode",
                value=measured.value,
                unit=measured.unit,
                scope=scope,
            )
        )
        facts.append(
            Fact(
                ref=f"{name}.denominator",
                kind="fact",
                label="episodes this figure is over",
                value=measured.denominator,
                unit="count",
                scope=scope,
            )
        )
    return facts


def _diagnosis_facts(packet: EpisodePacket, aliases: Aliases) -> list[Fact]:
    """What happened to each side, one fact per number the run recorded."""
    facts: list[Fact] = []
    scope = f"episode:{packet.episode_context_id}"
    for diagnosis in packet.diagnoses:
        # The platform's own id, not a label: a candidate id is a hash
        # this side computed, and the strings a third party wrote are
        # the component names inside the stack.
        label = diagnosis.candidate_id
        if diagnosis.outcome is not None:
            outcome = diagnosis.outcome
            for field, unit in (
                ("success", ""),
                ("collision_count", "count"),
                ("min_clearance", "m"),
                ("travel_time_s", "s"),
                ("p99_latency_ms", "ms"),
                ("replan_count", "count"),
            ):
                value = getattr(outcome, field)
                if value is None:
                    continue
                facts.append(
                    Fact(
                        ref=f"diag:{label}.{field}",
                        kind="fact",
                        label=f"{field.replace('_', ' ')} for {label}",
                        value=value,
                        unit=unit,
                        candidate_id=diagnosis.candidate_id,
                        scope=scope,
                    )
                )
        for attempt_field in ("planning_attempts", "no_path_attempts", "first_no_path_tick"):
            value = getattr(diagnosis, attempt_field)
            if value is None:
                continue
            facts.append(
                Fact(
                    ref=f"attempts:{label}.{attempt_field}",
                    kind="plan_attempt",
                    label=f"{attempt_field.replace('_', ' ')} for {label}",
                    value=value,
                    unit="count",
                    candidate_id=diagnosis.candidate_id,
                    scope=scope,
                )
            )
        for detection in diagnosis.detections:
            base = f"obs:{detection.type}:{label}@{packet.episode_context_id}"
            facts.append(
                Fact(
                    ref=base,
                    kind="observation",
                    label=f"{detection.type.replace('_', ' ')} on {label} in this episode",
                    value=detection.type,
                    candidate_id=detection.candidate_id,
                    scope=scope,
                )
            )
            for key, number in sorted(detection.measurements.items()):
                facts.append(
                    Fact(
                        ref=f"{base}/{key}",
                        kind="fact",
                        label=f"{key.replace('_', ' ')} of that {detection.type}",
                        value=number,
                        unit=_unit_for(key),
                        candidate_id=detection.candidate_id,
                        scope=scope,
                    )
                )
            if detection.window is not None:
                window = detection.window
                for key, number, unit in (
                    ("start_m", window.start_m, "m"),
                    ("end_m", window.end_m, "m"),
                    ("start_s", window.start_s, "s"),
                    ("end_s", window.end_s, "s"),
                ):
                    facts.append(
                        Fact(
                            ref=f"{base}/window.{key}",
                            kind="fact",
                            label=f"where that {detection.type} sits ({key})",
                            value=number,
                            unit=unit,
                            candidate_id=detection.candidate_id,
                            scope=scope,
                        )
                    )
    return facts


def _unit_for(key: str) -> str:
    for suffix, unit in (("_m", "m"), ("_ms", "ms"), ("_s", "s"), ("_deg", "deg")):
        if key.endswith(suffix):
            return unit
    return ""


def _contrast_facts(
    packet: EpisodePacket, aliases: Aliases
) -> tuple[list[Fact], dict[str, EpisodeContrast]]:
    """Differences, each carrying how much it can support.

    ``subject`` travels with the fact, which is what lets rule 6 catch a
    citation about one component propping up a claim about another.
    """
    facts: list[Fact] = []
    indexed: dict[str, EpisodeContrast] = {}
    scope = f"episode:{packet.episode_context_id}"
    for position, contrast in enumerate(packet.contrasts, start=1):
        ref = f"contrast:{contrast.kind}:{position}"
        indexed[ref] = contrast
        facts.append(
            Fact(
                ref=ref,
                kind="contrast",
                label=contrast.detail,
                value=contrast.strength,
                subject=contrast.subject,
                candidate_id=contrast.against_candidate_id,
                scope=scope,
            )
        )
        for key, number in sorted(contrast.measurements.items()):
            facts.append(
                Fact(
                    ref=f"{ref}/{key}",
                    kind="fact",
                    label=f"{key.replace('_', ' ')} behind that difference",
                    value=number,
                    unit=_unit_for(key),
                    candidate_id=contrast.against_candidate_id,
                    scope=scope,
                )
            )
    for position, withheld in enumerate(packet.ruled_out, start=1):
        facts.append(
            Fact(
                ref=f"ruled_out:{withheld.kind}:{position}",
                kind="observation",
                label=withheld.detail,
                value=withheld.reason,
                scope=scope,
            )
        )
    return facts, indexed


def _timeline_facts(packet: EpisodePacket, aliases: Aliases) -> list[Fact]:
    """Where each side stood at the marks, with the clock in the ref.

    The candidate is in the ref because ``episode_context_id`` is a hash
    of the **conditions**: both candidates of a comparison share one, and
    a ref without the candidate would have the two of them claiming the
    same name.
    """
    facts: list[Fact] = []
    scope = f"episode:{packet.episode_context_id}"
    for timeline in packet.timelines:
        label = timeline.candidate_id
        for point in timeline.points:
            base = f"episode:{packet.episode_context_id}/{label}/{point.clock}/{point.mark:g}"
            for field, unit in (
                ("progress_fraction", ""),
                ("safety_margin", "radii"),
                ("compute_budget", ""),
                ("path_efficiency", ""),
                ("elapsed_s", "s"),
                ("replans", "count"),
            ):
                facts.append(
                    Fact(
                        ref=f"{base}.{field}",
                        kind="fact",
                        label=f"{field.replace('_', ' ')} for {label} at that mark",
                        value=getattr(point, field),
                        unit=unit,
                        candidate_id=timeline.candidate_id,
                        scope=scope,
                    )
                )
    return facts


def build_episode_view(
    packet: EpisodePacket,
    *,
    aliases: Aliases | None = None,
    knowledge: Sequence[MechanismReferenceCandidate] = (),
) -> EpisodeView:
    """The index an episode round reads, and nothing outside this episode.

    Component names are replaced by labels before anything reaches the
    model, the same way the run-level view does it: a candidate id is a
    string a third party wrote, and the only safe place for it is behind
    a name the platform chose.
    """
    resolved = aliases or label_components(
        name
        for stack in packet.candidates
        for name in (
            stack.global_planner,
            stack.local_controller,
            stack.local_controller_config,
        )
    )

    facts: list[Fact] = []
    facts.extend(_verdict_facts(packet))
    facts.extend(_diagnosis_facts(packet, resolved))
    contrast_facts, _ = _contrast_facts(packet, resolved)
    facts.extend(contrast_facts)
    facts.extend(_timeline_facts(packet, resolved))

    scope = f"episode:{packet.episode_context_id}"
    for stack in packet.candidates:
        label = stack.candidate_id
        for field in ("global_planner", "local_controller", "local_controller_config"):
            facts.append(
                Fact(
                    ref=f"fact:candidate:{label}.{field}",
                    kind="fact",
                    label=f"{field.replace('_', ' ')} of {label}",
                    value=resolved.label_for(getattr(stack, field)),
                    candidate_id=stack.candidate_id,
                    scope=f"candidate:{stack.candidate_id}",
                )
            )

    if packet.robot is not None:
        for field, unit in (
            ("radius_m", "m"),
            ("inflation_margin_m", "m"),
            ("required_passage_width_m", "m"),
        ):
            value = getattr(packet.robot, field)
            if value is None:
                continue
            facts.append(
                Fact(
                    ref=f"fact:robot.{field}",
                    kind="fact",
                    label=field.replace("_", " "),
                    value=value,
                    unit=unit,
                    subject="costmap_inflation",
                    scope="robot",
                )
            )
    if packet.route is not None and packet.route.narrowest_passage_m is not None:
        facts.append(
            Fact(
                ref="fact:route.narrowest_passage_m",
                kind="fact",
                label="narrowest measured passage on the route",
                value=packet.route.narrowest_passage_m,
                unit="m",
                subject="task_geometry",
                scope="route",
            )
        )

    for unknown in packet.known_unknowns:
        facts.append(
            Fact(
                ref=f"unknown:{unknown.id}",
                kind="observation",
                label=unknown.source,
                scope=scope,
            )
        )

    for entry in knowledge:
        facts.append(
            Fact(
                ref=f"kb:{entry.entry_id}@{entry.entry_version}",
                kind="knowledge_entry",
                label="a curated mechanism reference offered for this episode",
                value=entry.entry_id,
                scope=f"mechanism:{entry.retrieved_for or entry.entry_id}",
            )
        )

    return EpisodeView(packet, tuple(facts), resolved)


def run_context_block(packet: EpisodePacket, measurements: Mapping[str, object] = {}) -> str:
    """Run-level context, rendered as text with no refs of its own.

    Deliberately not indexed. Rule 1 already drops a citation that does
    not resolve, so a block with no names in the index cannot be leaned
    on — which is the whole intent, and costs neither a new guard rule
    nor a new field on a frozen contract.
    """
    lines = [
        "RUN CONTEXT (not citable — nothing here may support a statement about this episode)",
        f"  run: {packet.run_id}",
    ]
    for unknown in packet.run_context_unknowns:
        lines.append(f"  the run as a whole: {unknown.source}")
    for key, value in sorted(measurements.items()):
        lines.append(f"  over the whole run, {key}: {value}")
    return "\n".join(lines)
