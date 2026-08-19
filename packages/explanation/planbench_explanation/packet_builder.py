"""Assembling the analyst's packet during the scoring pass — E4.1.

E4 defined the packet and gave it a builder that takes finished parts.
Nothing produced those parts, so the packet existed as a type and never
as a file, and the decision page has been showing the *frame* of an
explanation — which outcome this run had, what it is allowed to display
— with nothing inside it.

**Built while scoring, not afterwards, and that was a decision with a
price.** The waterfall needs two
:class:`~planbench_decision.stats.CandidateEvidence` objects, and those
exist only inside the scoring pass. Rebuilding them from the report
afterwards would mean a second piece of code computing the same ΔU — the
parallel source HĐ-5 forbids everywhere else in this system, reintroduced
in the one layer whose whole purpose is that numbers can be traced to
where they came from. So the packet is assembled here, and the costs are
paid openly: the comparison report grows a block, and a run scored
before this exists has no packet and cannot get one.

**The detectors read every episode's trace, and that is the expensive
part.** It is also the part that makes the packet worth having: without
observations an analyst is handed a ΔU decomposition and no sightings,
which is a summary rather than a case. The read happens at scoring time,
when the traces have just been written and are warm.

**This module still imports no simulator.** Traces arrive as column
mappings — the same shape the API already serves — so the layer that
explains a run does not depend on the layer that produces one. The
caller does the reading; that caller is allowed to know what a Parquet
file is.

**A run that ranked nobody still gets a packet — E4.2.** The first cut
built one only inside the ranked branch, so a gate-only field or a run
where nobody cleared six gates produced no packet at all: the detectors
never ran, and the endpoint answered 409 to the very question those runs
provoke. What such a run lacks is a *pair*, and therefore a waterfall and
exemplars. It does not lack sightings, geometry or a gate table.

**A missing part is absent, never approximated.** No map features, no
``narrow_gap_refusal``. No per-episode utility, no exemplars. No
recorded components, no lattice. Each of those is a silence the packet
carries honestly, and the analyst is told what is missing through the
packet's own known-unknowns rather than left to infer it from an empty
list.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from planbench_explanation.case_packet import (
    CasePacket,
    CasePacketRefusal,
    DecisionFacts,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.contrast import (
    CandidateComponents,
    ContrastFinding,
    ContrastRefusal,
    components_from_report,
    read_lattice,
)
from planbench_explanation.detectors import (
    DetectionType,
    DetectorRefusal,
    DetectorSettings,
    Observation,
    detect_all,
    read_trace,
    summarise,
)
from planbench_explanation.exemplars import (
    ExemplarRefusal,
    ExemplarSet,
    ReportExemplarRefusal,
    select_exemplars_from_report,
)
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.replay_sync import ReplaySyncRefusal, choose_reference
from planbench_explanation.versioning import ExplanationArtifactHeader
from planbench_explanation.waterfall import Waterfall

#: Every detection type the lattice is read for. Fixed rather than
#: derived from what fired: a pattern that appears on neither candidate
#: is a real finding ("neither stack does this"), and deriving the list
#: from the detections would silently drop it.
LATTICE_TYPES: tuple[DetectionType, ...] = (
    "detour",
    "stuck_cluster",
    "near_miss_cluster",
    "replan_storm",
    "oscillation",
    "latency_spike",
    "narrow_gap_refusal",
)


class EpisodeTrace(BaseModel):
    """One episode's trace, in the shape the detectors already read.

    A column mapping rather than a path, so this package keeps its
    distance from the one that writes Parquet. ``planned_path`` is the
    global route, used to place arc length on a declared reference line;
    absent, the reference degrades and says so.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    candidate_id: str = Field(min_length=1)
    episode_context_id: str = Field(min_length=1)
    columns: Mapping[str, object]
    planned_path: tuple[tuple[float, float], ...] | None = None


class PacketBuildReport(BaseModel):
    """The packet, and an account of what could not be built.

    Two fields rather than one because "the packet has no observations"
    and "the detectors refused on nine episodes" look identical from the
    outside, and only the second is a problem somebody should look at.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    packet: CasePacket
    #: Episodes whose trace the detectors would not read, and why. Empty
    #: is the normal number.
    skipped_episodes: tuple[str, ...] = ()
    #: Parts left out of the packet, each with its reason. Carried so a
    #: reader of the report can tell a thin packet from a broken one.
    omissions: tuple[str, ...] = ()


def observations_from_traces(
    traces: Sequence[EpisodeTrace],
    *,
    episodes_total: int,
    settings: DetectorSettings | None = None,
    route_features: Mapping[str, RouteFeatures] | None = None,
    required_passage_width_m: float | None = None,
) -> tuple[tuple[Observation, ...], tuple[str, ...]]:
    """Run every detector over every episode, per candidate.

    ``episodes_total`` is the number of episodes **looked at**, passed in
    rather than counted from the traces that parsed: counting the ones
    that arrived would make a pattern that fired in three of three
    unreadable traces look universal.

    Returns the observations and the episodes that were skipped. A trace
    the detectors refuse is not silently dropped — it is one fewer
    episode behind every rate in the packet, and that belongs in the
    report.
    """
    by_candidate: dict[str, list] = {}
    skipped: list[str] = []
    features = route_features or {}

    for trace in traces:
        payload = dict(trace.columns)
        payload.setdefault("candidate_id", trace.candidate_id)
        payload.setdefault("episode_context_id", trace.episode_context_id)
        try:
            view = read_trace(payload)
            reference = choose_reference(
                planned_path=trace.planned_path,
                candidate_path=[(point.x, point.y) for point in view.track],
            )
            route = features.get(trace.candidate_id)
            detections = detect_all(
                view,
                reference=reference,
                settings=settings,
                narrowest_passage_m=route.narrowest_passage_m if route else None,
                required_passage_width_m=required_passage_width_m,
            )
        except (DetectorRefusal, ReplaySyncRefusal) as refusal:
            skipped.append(f"{trace.candidate_id}/{trace.episode_context_id}: {refusal}")
            continue
        by_candidate.setdefault(trace.candidate_id, []).extend(detections)

    observations: list[Observation] = []
    for candidate_id in sorted(by_candidate):
        observations.extend(summarise(by_candidate[candidate_id], episodes_total=episodes_total))
    return tuple(observations), tuple(skipped)


def lattice_from(
    components: Sequence[CandidateComponents],
    observations: Sequence[Observation],
) -> tuple[tuple[ContrastFinding, ...], tuple[str, ...]]:
    """Read the contrast graph for every detection type.

    Presence is taken from the observations rather than from a separate
    pass: a type is "present" for a candidate when a detector saw it,
    which is the same fact the packet already carries. Deriving it twice
    would let the lattice and the observations disagree.
    """
    if len(components) < 2:
        return (), ("lattice: fewer than two candidates declared their components",)
    seen = {
        (observation.candidate_id, observation.type)
        for observation in observations
        if observation.episodes_seen > 0
    }
    findings: list[ContrastFinding] = []
    refused: list[str] = []
    for detection_type in LATTICE_TYPES:
        present = {
            item.candidate_id: (item.candidate_id, detection_type) in seen for item in components
        }
        try:
            findings.append(read_lattice(components, present, detection_type=detection_type))
        except ContrastRefusal as refusal:
            refused.append(f"lattice/{detection_type}: {refusal}")
    return tuple(findings), tuple(refused)


def build_scoring_packet(
    *,
    run_id: str,
    source_manifest_ref: str,
    source_manifest_checksum: str,
    detector_version: str,
    knowledge_base_version: str,
    tool_catalog_version: str,
    task_profile_id: str,
    robot_radius_m: float,
    inflation_margin_m: float | None,
    decision_status: str,
    waterfall: Waterfall | None,
    report: Mapping[str, object],
    traces: Sequence[EpisodeTrace],
    episodes_total: int,
    evidence_class: str,
    detector_settings: DetectorSettings | None = None,
    route_features: Mapping[str, RouteFeatures] | None = None,
    gates: Mapping[str, Mapping[str, object]] | None = None,
) -> PacketBuildReport:
    """Assemble one run's case packet from what the scoring pass holds.

    The robot's required passage **width** is derived here from the
    radius and the margin, in one place, using the same formula the
    checker validates against: ``2 * (radius + margin)``. A run that did
    not record its inflation gets ``None`` for both, and the packet then
    carries no width at all rather than one built on a guessed margin.
    """
    omissions: list[str] = []

    required_width = (
        None if inflation_margin_m is None else 2.0 * (robot_radius_m + inflation_margin_m)
    )
    if required_width is None:
        omissions.append(
            "required_passage_width_m: the run did not record its inflation margin, so "
            "no clearance comparison is possible and narrow_gap_refusal cannot run"
        )

    observations, skipped = observations_from_traces(
        traces,
        episodes_total=episodes_total,
        settings=detector_settings,
        route_features=route_features,
        required_passage_width_m=required_width,
    )
    if not traces:
        omissions.append(
            "observations: no episode traces were available to this run, so the packet "
            "carries the decomposition and no sightings"
        )

    components = components_from_report(report)
    lattice, lattice_refusals = lattice_from(components, observations)
    omissions.extend(lattice_refusals)

    exemplars: ExemplarSet | None = None
    if waterfall is None:
        # No ranking, so no pair, so no roles. Recorded as an omission
        # with its reason rather than left as an empty field somebody
        # reads as "the recipe found nothing".
        omissions.append(
            "decision.waterfall: this run ranked nobody, so there is no pair to "
            "decompose and no exemplar roles to fill. The sightings and the gate "
            "table are what this run has to say."
        )
    else:
        try:
            exemplars = select_exemplars_from_report(report)
        except (ExemplarRefusal, ReportExemplarRefusal) as refusal:
            omissions.append(f"representative_episodes: {refusal}")

    packet = build_case_packet(
        run_id=run_id,
        header=ExplanationArtifactHeader.for_current_code(
            source_manifest_ref=source_manifest_ref,
            source_manifest_checksum=source_manifest_checksum,
            detector_version=detector_version,
            knowledge_base_version=knowledge_base_version,
            tool_catalog_version=tool_catalog_version,
        ),
        task=TaskFacts(
            task_profile_id=task_profile_id,
            robot=RobotFacts(
                radius_m=robot_radius_m,
                inflation_margin_m=inflation_margin_m,
                required_passage_width_m=required_width,
            ),
        ),
        candidates=components,
        decision=DecisionFacts(
            status=decision_status,
            waterfall=waterfall,
            gates={name: dict(row) for name, row in (gates or {}).items()},
        ),
        lattice=lattice,
        observations=observations,
        representative_episodes=exemplars,
        evidence_class=evidence_class,
    )
    return PacketBuildReport(packet=packet, skipped_episodes=skipped, omissions=tuple(omissions))


def packet_block(built: PacketBuildReport) -> dict[str, object]:
    """What goes into ``report["case_packet"]``.

    The omissions travel **with** the packet rather than in a log,
    because the person who needs them is whoever later asks why an
    explanation is thin, and they will be reading the report.
    """
    return {
        "packet": built.packet.model_dump(mode="json"),
        "skipped_episodes": list(built.skipped_episodes),
        "omissions": list(built.omissions),
    }


def packet_from_block(block: Mapping[str, object]) -> CasePacket:
    """Read a packet back out of a report. Refuses a run that has none.

    A run scored before E4.1 has no block here, and that is the declared
    price of building at scoring time — reported as itself rather than
    as an empty packet, which would look like a run nobody could explain
    instead of a run recorded before explanations existed.
    """
    if not isinstance(block, Mapping) or "packet" not in block:
        raise CasePacketRefusal(
            "this report has no case packet: it was scored before E4.1, and a packet "
            "cannot be built afterwards without recomputing the utilities a second way"
        )
    payload = block.get("packet")
    if not isinstance(payload, Mapping):
        # **A different fact, and it took one line to nearly lose.** The
        # block is here, so this run was scored after E4.1 — the build
        # was attempted and failed. Reporting it as "scored before E4.1"
        # would send somebody to re-run a sweep when what they need is
        # the reason in ``omissions``.
        raise CasePacketRefusal(
            "this run was scored with the packet builder present and the build failed: "
            f"{list(block.get('omissions') or []) or 'no reason recorded'}"
        )
    return CasePacket.model_validate(payload)
