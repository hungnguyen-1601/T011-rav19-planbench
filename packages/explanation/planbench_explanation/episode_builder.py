"""Assembling one episode's packet from what the platform already serves.

The pieces all exist: the scoring pass stored a row per episode per
candidate, the detectors read a served trace, the replay view lines two
of them up, and the sidecar records planning attempts. None of them was
ever folded into an answer about *one* episode — ``summarise`` folds
detections into run-level observations, and that is the only fold there
was.

This module is that fold, and it does no arithmetic of its own. Every
number it puts in the packet was computed by the code that owns it:
outcomes are copied from the report, detections come from
``detect_all``, timelines from ``timeline_from_trace``. A second way to
work out how long an episode took is a second answer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from planbench_explanation.case_packet import EpisodeTimeline, RobotFacts
from planbench_explanation.contrast import CandidateComponents
from planbench_explanation.detectors import (
    Detection,
    DetectorRefusal,
    DetectorSettings,
    detect_all,
    read_trace,
)
from planbench_explanation.episode_packet import (
    CandidateOutcome,
    EpisodePacket,
    EpisodePacketRefusal,
    build_contrasts,
    build_diagnoses,
    build_verdict,
    classify_unknown,
    episode_unknowns,
    outcome_from_row,
)
from planbench_explanation.ledger import KnownUnknown
from planbench_explanation.map_features import RouteFeatures
from planbench_explanation.packet_builder import (
    DeploymentThresholds,
    EpisodeTrace,
    timeline_from_trace,
)
from planbench_explanation.replay_sync import (
    ReplaySyncRefusal,
    choose_reference,
)
from planbench_explanation.versioning import ExplanationArtifactHeader

#: The role a timeline built for a chosen episode carries.
#:
#: Not one of ``TIMELINE_ROLES``: those name a place in an exemplar set,
#: and this episode is here because a reader clicked it. Saying
#: ``typical`` of an episode nobody ranked would be a claim about the
#: run's distribution made by a mouse click.
SELECTED_ROLE = "selected"


class EpisodeBuildRefusal(EpisodePacketRefusal):
    """The episode cannot be assembled, and what was missing."""


def episode_rows(report: Mapping[str, Any], candidate_id: str) -> dict[str, Mapping[str, Any]]:
    """Every scored episode of one candidate, keyed by episode."""
    for entry in report.get("candidates") or ():
        if entry.get("candidate_id") != candidate_id:
            continue
        rows = entry.get("episodes") or ()
        return {
            str(row["episode_context_id"]): row for row in rows if row.get("episode_context_id")
        }
    return {}


def components_from_report(
    report: Mapping[str, Any], candidate_id: str
) -> CandidateComponents | None:
    """One candidate's stack, as the report recorded it."""
    for entry in report.get("candidates") or ():
        if entry.get("candidate_id") != candidate_id:
            continue
        parts = entry.get("components") or {}
        try:
            return CandidateComponents(
                candidate_id=candidate_id,
                global_planner=str(parts.get("global_planner") or entry.get("stack_label") or "?"),
                local_controller=str(parts.get("local_controller") or "?"),
                local_controller_config=str(
                    parts.get("local_controller_config")
                    or entry.get("local_controller_config")
                    or "default"
                ),
            )
        except ValueError:  # pragma: no cover - a report with no stack at all
            return None
    return None


def detections_for(
    trace: Mapping[str, Any],
    *,
    settings: DetectorSettings | None = None,
    route: RouteFeatures | None = None,
    required_passage_width_m: float | None = None,
) -> tuple[tuple[Detection, ...], tuple[str, ...]]:
    """Every detector over one served trace, and what stopped them.

    Refusals are returned rather than raised: one candidate's trace being
    unreadable is a reason to say so beside the other one's findings, not
    a reason to have no packet.
    """
    try:
        view = read_trace(trace)
    except DetectorRefusal as refusal:
        return (), (f"detectors did not run: {refusal}",)

    reference = choose_reference(
        planned_path=_first_route(trace),
        candidate_path=[
            (x, y) for x, y in zip(trace.get("x") or (), trace.get("y") or (), strict=False)
        ],
    )
    found = detect_all(
        view,
        reference=reference,
        settings=settings,
        narrowest_passage_m=route.narrowest_passage_m if route else None,
        required_passage_width_m=required_passage_width_m,
    )
    omissions: tuple[str, ...] = ()
    if reference.is_degraded:
        omissions = (
            f"arc length is measured along a {reference.quality} line, not the planner's route",
        )
    return found, omissions


def _first_route(trace: Mapping[str, Any]) -> list[tuple[float, float]] | None:
    """The first plan the episode recorded, if the endpoint served one.

    First rather than last, for the reason the replay view takes it:
    arc length has to be measured along one line for the whole episode,
    and a route produced after a replan describes only what came after.
    """
    routes = trace.get("planned_routes") or ()
    for route in routes:
        points = route.get("points") if isinstance(route, Mapping) else None
        if points:
            return [(float(x), float(y)) for x, y in points]
    return None


#: How a recorded sidecar is named beside its trace.
#:
#: The episode is in the filename, not only inside the records: one
#: directory holds every episode a candidate ran, and a reader that
#: globbed for the first file would summarise a different episode's
#: attempts without anything looking wrong.
SIDECAR_SUFFIX = ".planning_inputs.jsonl"


def planning_summary(
    sidecar_directory: Path | None,
    *,
    candidate_id: str,
    episode_context_id: str = "",
) -> Mapping[str, int | None]:
    """How many times the planner was asked, and how often it refused.

    A summary rather than the records themselves: the packet is about
    what happened, and the attempt bodies are what a checker replays.

    Returns ``{}`` for every way there is nothing to read — no
    directory, no file, an unreadable one. A missing sidecar is a fact
    about the run, reported by the gap :func:`episode_unknowns` raises,
    and not an error worth losing the packet over.
    """
    if sidecar_directory is None:
        return {}
    from planbench_explanation.sidecar_writer import read_sidecar

    named = sidecar_directory / f"{episode_context_id}{SIDECAR_SUFFIX}"
    if episode_context_id and named.exists():
        path = named
    else:
        found = sorted(sidecar_directory.glob(f"*{SIDECAR_SUFFIX}"))
        if len(found) != 1:
            # Zero: nothing recorded. More than one: several episodes
            # live here and picking one would attribute another
            # episode's refusals to this one.
            return {}
        path = found[0]
    try:
        _, records = read_sidecar(path)
    except (ValueError, OSError):
        return {}
    if episode_context_id:
        records = tuple(
            record for record in records if record.episode_context_id == episode_context_id
        )
    mine = [record for record in records if record.candidate_id == candidate_id]
    if not mine:
        return {}
    refusals = [record for record in mine if record.outcome != "path"]
    return {
        "attempts": len(mine),
        "no_path": len(refusals),
        "first_no_path_tick": min((r.simulation_tick for r in refusals), default=None),
    }


def divergence_for(
    trace_a: Mapping[str, Any],
    trace_b: Mapping[str, Any],
) -> tuple[bool, str]:
    """Whether the two runs parted before their outcomes did, and where.

    Temporal only. That one run left the other's line at 12 m says when
    they stopped agreeing, never why — which is why the contrast this
    feeds is context and cannot support a mechanism on its own.
    """
    from planbench_explanation.replay_view import build_replay_sync_view

    try:
        view = build_replay_sync_view(trace_a, trace_b, planned_path=_first_route(trace_a))
    except (ReplaySyncRefusal, ValueError):
        return False, ""
    earliest = view.divergence.earliest
    if earliest is None:
        return False, ""
    if earliest.kind == "event":
        detail = (
            f"the two runs parted at {earliest.progress_m:.1f} m along the route, where "
            f"{earliest.event} fired on one side"
        )
    else:
        detail = f"the two runs parted at {earliest.progress_m:.1f} m along the route"
    return True, detail


def build_episode_packet(
    *,
    header: ExplanationArtifactHeader,
    run_id: str,
    episode_context_id: str,
    candidate_a: str,
    candidate_b: str,
    report: Mapping[str, Any],
    trace_a: Mapping[str, Any] | None,
    trace_b: Mapping[str, Any] | None,
    tie_epsilon: float,
    robot: RobotFacts | None = None,
    route: RouteFeatures | None = None,
    run_packet_checksum: str = "",
    run_context_unknowns: Sequence[KnownUnknown] = (),
    thresholds: DeploymentThresholds | None = None,
    sidecars: Mapping[str, Path] = {},
    detector_settings: DetectorSettings | None = None,
    evidence_class: str = "production",
) -> EpisodePacket:
    """One episode, assembled, with every gap it has written down.

    ``tie_epsilon`` arrives from the preregistration rather than being
    chosen here: a margin decided in the module that applies it is a
    margin that can be adjusted once the answers are visible.
    """
    if candidate_a == candidate_b:
        raise EpisodeBuildRefusal("an episode packet compares two candidates, not one twice")

    outcomes: dict[str, CandidateOutcome | None] = {}
    for candidate_id in (candidate_a, candidate_b):
        row = episode_rows(report, candidate_id).get(episode_context_id)
        outcomes[candidate_id] = (
            outcome_from_row(row, candidate_id=candidate_id) if row is not None else None
        )

    verdict = build_verdict(
        episode_context_id=episode_context_id,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        outcome_a=outcomes[candidate_a],
        outcome_b=outcomes[candidate_b],
        tie_epsilon=tie_epsilon,
    )

    width = None
    if robot is not None:
        width = robot.required_passage_width_m or robot.derived_passage_width_m

    detections: list[Detection] = []
    omissions: list[str] = []
    traces = {candidate_a: trace_a, candidate_b: trace_b}
    for candidate_id, trace in traces.items():
        if trace is None:
            omissions.append(f"no trace was served for {candidate_id}")
            continue
        # Two canvases side by side already assert a paired comparison
        # (HĐ-3.2). Building one from the wrong episode, or from the
        # other candidate's run, is the most convincing wrong picture
        # this layer could draw — so it is checked here rather than
        # trusted from the caller's argument order.
        served_episode = str(trace.get("episode_context_id") or "")
        served_candidate = str(trace.get("candidate_id") or "")
        if served_episode and served_episode != episode_context_id:
            raise EpisodeBuildRefusal(
                f"the trace served for {candidate_id!r} is episode {served_episode!r} and "
                f"this packet is about {episode_context_id!r}"
            )
        if served_candidate and served_candidate != candidate_id:
            raise EpisodeBuildRefusal(
                f"the trace passed as {candidate_id!r} records {served_candidate!r}"
            )
        found, notes = detections_for(
            trace,
            settings=detector_settings,
            route=route,
            required_passage_width_m=width,
        )
        detections.extend(found)
        omissions.extend(f"{candidate_id}: {note}" for note in notes)

    planning = {
        candidate_id: planning_summary(
            sidecars.get(candidate_id),
            candidate_id=candidate_id,
            episode_context_id=episode_context_id,
        )
        for candidate_id in (candidate_a, candidate_b)
    }

    components = {}
    for candidate_id in (candidate_a, candidate_b):
        found = components_from_report(report, candidate_id)
        if found is None:
            raise EpisodeBuildRefusal(
                f"the report records no stack for {candidate_id!r}, so nothing can be "
                "said about which component a difference lives in"
            )
        components[candidate_id] = found

    parted, detail = divergence_for(trace_a, trace_b) if trace_a and trace_b else (False, "")
    contrasts, ruled_out = build_contrasts(
        verdict=verdict,
        outcomes=outcomes,
        components=components,
        detections=detections,
        divergence_precedes=parted,
        divergence_detail=detail,
    )

    timelines: list[EpisodeTimeline] = []
    if thresholds is not None:
        for candidate_id, trace in traces.items():
            if trace is None:
                continue
            built = timeline_from_trace(
                EpisodeTrace(
                    candidate_id=candidate_id,
                    episode_context_id=episode_context_id,
                    columns=dict(trace),
                    planned_path=tuple(_first_route(trace) or ()) or None,
                ),
                role=SELECTED_ROLE,
                deployment=thresholds.for_length(1.0),
            )
            if built is None:
                omissions.append(f"{candidate_id}: no timeline — the trace is missing a column")
                continue
            timelines.append(built)

    sidecar_present = any(planning.get(candidate_id) for candidate_id in traces)
    has_clearance = any(bool((trace or {}).get("clearance_m")) for trace in traces.values())
    has_latency = any(bool((trace or {}).get("planner_latency_ms")) for trace in traces.values())
    gaps = episode_unknowns(
        sidecar_present=sidecar_present,
        route=route,
        robot=robot,
        has_clearance=has_clearance,
        has_latency=has_latency,
    )
    carried = tuple(
        scoped.unknown
        for scoped in (classify_unknown(unknown) for unknown in run_context_unknowns)
        if scoped.blocks
    )
    context_only = tuple(
        scoped.unknown
        for scoped in (classify_unknown(unknown) for unknown in run_context_unknowns)
        if not scoped.blocks
    )

    return EpisodePacket(
        header=header,
        run_id=run_id,
        run_packet_checksum=run_packet_checksum,
        episode_context_id=episode_context_id,
        verdict=verdict,
        diagnoses=build_diagnoses(
            verdict=verdict,
            outcomes=outcomes,
            detections=detections,
            planning=planning,
        ),
        contrasts=contrasts,
        ruled_out=ruled_out,
        candidates=(components[candidate_a], components[candidate_b]),
        robot=robot,
        route=route,
        timelines=tuple(timelines),
        known_unknowns=(*carried, *gaps),
        run_context_unknowns=context_only,
        omissions=tuple(omissions),
        evidence_class=evidence_class,
    )
