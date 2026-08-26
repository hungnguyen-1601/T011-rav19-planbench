"""Turn the planted runs into packet fixtures a suite can be scored on.

``plant_golden_runs.py`` stages three of the six families and writes a
planning-input sidecar for each. That is a run, not a case: every
``packet_ref`` in ``VISIBLE_SUITE`` points at
``fixtures/golden/visible/<case_id>/packet.json``, and until that file
exists the suite names twelve cases nobody can grade.

This closes that half. Each staged world is run again — with **both**
stacks, because a packet explains a comparison and the contract refuses
a one-candidate packet — under the same :class:`EpisodeTraceRecorder`
production uses, so the trace carries the columns the detectors read:
``clearance_m`` from the recorder's own probe, ``planner_latency_ms``
from the planner, and the ``event`` column that says where a refusal
happened. The first version of this script rebuilt the trace from the
trajectory alone and could not fire the clearance or latency detectors;
that is the difference between a fixture and a drawing of one.

**A refusal is a one-row trace, not an absent one.** A world whose aisle
is closed produces a planner refusal at the start pose and no motion.
The recorder writes that as a single row carrying a ``no_path`` event —
which is exactly what ``narrow_gap_refusal`` reads, alongside the route
geometry measured on the map and the width the configuration needs. Both
of those are computed here from the world, with the same functions the
platform uses (``measure_route``, the planning grid's own inflation), so
the packet says what the run would have said.

**Three families, and the count travels with every result.** The other
three need a sweep across contexts rather than one episode, a gap the
packet builder does not yet declare, or a pairing whose ΔU straddles
zero. A macro average over three families read against a bar agreed for
six is a comparison nobody should make.

**``OFFICIAL_GOLDEN_READY`` stays False.** These are visible-suite
fixtures for development. Flipping that constant is a code change with a
diff, made when six families exist — not a side effect of running this.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("schemas", "planning", "metrics", "benchmark", "decision", "explanation"):
    sys.path.insert(0, str(ROOT / "packages" / package))
sys.path.insert(0, str(ROOT / "services" / "simulator"))
sys.path.insert(0, str(ROOT / "scripts"))

from plant_golden_runs import WORLDS, PlantedWorld, build_reference  # noqa: E402

from planbench_explanation.case_packet import (  # noqa: E402
    CandidateMeasurements,
    DecisionFacts,
    EpisodeTimeline,
    MeasuredValue,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.catalog import TOOL_CATALOG_VERSION  # noqa: E402
from planbench_explanation.contrast import CandidateComponents  # noqa: E402
from planbench_explanation.detectors import (  # noqa: E402
    DETECTOR_VERSION,
    DetectorSettings,
)
from planbench_explanation.detectors import (  # noqa: E402
    read_trace as read_trace_view,
)
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION  # noqa: E402
from planbench_explanation.map_features import MapFeatureRefusal, measure_route  # noqa: E402
from planbench_explanation.packet_artifact import (  # noqa: E402
    PacketProvenance,
    packet_checksum,
)
from planbench_explanation.packet_builder import (  # noqa: E402
    EpisodeTrace,
    observations_from_traces,
    timeline_from_trace,
)
from planbench_explanation.replay_sync import choose_reference, project  # noqa: E402
from planbench_explanation.running_metrics import Deployment  # noqa: E402
from planbench_explanation.sidecar_writer import (  # noqa: E402
    PlanningInputRecorder,
    read_sidecar,
    snapshot_for,
    validate_episode_attempts,
)
from planbench_explanation.versioning import (  # noqa: E402
    ExplanationArtifactHeader,
    artifact_checksum,
)
from planbench_planning import (  # noqa: E402
    AStarPlanner,
    DWAPlanner,
    RRTStarConfig,
    RRTStarPlanner,
)
from planbench_schemas.episode_context import EpisodeContext  # noqa: E402
from planbench_schemas.replanning import ReplanningConfig  # noqa: E402
from planbench_simulator.nav_stack import _hard_radius, run_stack  # noqa: E402
from planbench_simulator.trace import EpisodeTraceRecorder, read_trace  # noqa: E402

#: Where the suite says its packets live. Not a flag: ``VISIBLE_SUITE``
#: names this path in every ``packet_ref``, and a script that could
#: write them somewhere else would produce fixtures the suite cannot
#: find while reporting success.
FIXTURE_ROOT = ROOT / "fixtures" / "golden" / "visible"

RECORDED_AT = "2026-08-26T00:00:00Z"

#: Both stacks each world is run with. A packet explains a comparison,
#: and a comparison needs two candidates; ``plant_golden_runs.py``
#: stages one per world because it is planting a *mechanism*, so the
#: second stack runs here on the same world and scenario.
STACKS: tuple[str, ...] = ("astar", "rrtstar")


def _planner(name: str):  # type: ignore[no-untyped-def]
    return (
        RRTStarPlanner(RRTStarConfig(max_iterations=120), episode_seed=7)
        if name == "rrtstar"
        else AStarPlanner()
    )


def _context(world: PlantedWorld) -> EpisodeContext:
    return EpisodeContext(task_profile_id=world.family, mission_id=world.case_id, seed=7)


def _trace_from_parquet(path: Path, candidate_id: str, episode_context_id: str, planned_path):  # type: ignore[no-untyped-def]
    """The recorded episode, in the columns the detectors read.

    Read back through the platform's own reader rather than from the
    in-memory result, so the fixture holds what a real run leaves on
    disk — including the refusal row a stopped robot still writes.
    """
    loaded = read_trace(path)
    events = [
        {"index": index, "event": name}
        for index, name in enumerate(loaded.column("event"))
        if name
    ]
    return EpisodeTrace(
        candidate_id=candidate_id,
        episode_context_id=episode_context_id,
        columns={
            "t": loaded.column("t"),
            "x": loaded.column("x"),
            "y": loaded.column("y"),
            "clearance_m": loaded.column("clearance_m"),
            "planner_latency_ms": loaded.column("planner_latency_ms"),
            "events": events,
        },
        planned_path=planned_path,
    )


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile over a short series."""
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _measured(candidate_id: str, run, trace) -> CandidateMeasurements:  # type: ignore[no-untyped-def]
    """What this candidate scored, read back off what it left on disk — W1.1.

    One episode per candidate on a planted world, so every denominator
    here is 1 and says so. That is not a formality: a success rate over
    one episode and one over thirty are different claims wearing one
    number, and the packet carries the figure that tells them apart
    rather than leaving a reader to assume the larger.

    Latency and clearance come from the **trace columns** rather than
    from the in-memory result, for the reason the observations do: what
    a checker reads later is what the recorder wrote.
    """
    latencies = [value for value in trace.columns["planner_latency_ms"] if value is not None]
    clearances = [value for value in trace.columns["clearance_m"] if value is not None]
    xs, ys = trace.columns["x"], trace.columns["y"]
    driven = sum(
        ((xs[index] - xs[index - 1]) ** 2 + (ys[index] - ys[index - 1]) ** 2) ** 0.5
        for index in range(1, len(xs))
    )
    fields: dict[str, MeasuredValue | None] = {
        "success_rate": MeasuredValue(
            value=1.0 if run.result.status == "success" else 0.0,
            unit="ratio",
            denominator=1,
        ),
        "collisions": MeasuredValue(
            value=1.0 if run.result.status == "collision" else 0.0,
            unit="count",
            denominator=1,
        ),
        "path_length_m": MeasuredValue(value=float(driven), unit="m", denominator=1),
    }
    if latencies:
        fields["latency_p99_ms"] = MeasuredValue(
            value=_percentile(latencies, 0.99), unit="ms", denominator=1
        )
        fields["latency_median_ms"] = MeasuredValue(
            value=_percentile(latencies, 0.5), unit="ms", denominator=1
        )
    if clearances:
        fields["min_clearance_m"] = MeasuredValue(value=min(clearances), unit="m", denominator=1)
    # ``decision_utility`` stays absent. These worlds are GATE_ONLY: no
    # preference profile ranked anybody, so there is no utility to
    # report, and a zero would read as "scored nothing" rather than as
    # "was never scored".
    return CandidateMeasurements(candidate_id=candidate_id, **fields)


def _with_progress(trace: EpisodeTrace) -> EpisodeTrace:
    """The same episode with its arc length along the reference line.

    The recorder writes where the robot was; how far along the task that
    is depends on the line it is measured against, so it is computed
    here through the platform's own projection — the one the detectors
    already run — rather than by a second rule that would place the
    half-way mark somewhere else.
    """
    payload = dict(trace.columns)
    payload.setdefault("candidate_id", trace.candidate_id)
    payload.setdefault("episode_context_id", trace.episode_context_id)
    view = read_trace_view(payload)
    reference = choose_reference(
        planned_path=trace.planned_path,
        candidate_path=[(point.x, point.y) for point in view.track],
    )
    projected = project(view.track, reference)
    return trace.model_copy(
        update={
            "columns": {
                **trace.columns,
                "progress_m": [sample.progress_m for sample in projected.samples],
            }
        }
    )


def _deployment(world: PlantedWorld, reference_length_m: float) -> Deployment:
    """The thresholds the running numbers are read against.

    Every figure is the world's own, except the near-miss distance:
    these planted worlds carry no task profile, so the platform's own
    detector threshold stands in and is named here rather than being a
    number somebody chose. ``clearance_preference`` is a planner cost
    weight, not a distance, and using it would put a preference where a
    metre belongs.
    """
    return Deployment(
        robot_radius_m=world.scenario.robot.radius,
        control_period_s=world.scenario.simulation_dt,
        clearance_warning_m=DetectorSettings().near_miss_clearance_m,
        max_linear_velocity=world.scenario.robot.max_linear_velocity,
        reference_length_m=reference_length_m,
    )


def build(
    world: PlantedWorld, root: Path, trace_root: Path, reference: str
) -> tuple[Path, int, list[str]]:
    """Run one staged world with both stacks and write its packet.

    The planning-input sidecar is written **beside the packet**, one
    directory per candidate. Both candidates run the same conditions, so
    they share an ``episode_context_id`` — that is what the id is, a hash
    of the conditions — and one flat directory would have the second
    stack's sidecar overwrite the first's under the same name. Per
    candidate is also how the trace layout files them in production.

    Without the sidecar the two replay checks have nothing to read, and
    ``rrt_convergence`` is exactly the check that separates a sampling
    planner running out of budget from a corridor that was never open.
    A fixture for that family with no sidecar is a case whose mechanism
    cannot be verified, however good the analyst is.
    """
    folder = root / world.case_id
    folder.mkdir(parents=True, exist_ok=True)
    traces: list[EpisodeTrace] = []
    timelines: list[EpisodeTimeline] = []
    measurements: list[CandidateMeasurements] = []
    candidates: list[CandidateComponents] = []
    notes: list[str] = []
    routes: dict[str, object] = {}
    sidecars: dict[str, Path] = {}

    radius = world.scenario.robot.radius
    inflation_margin = _hard_radius(world.map_data, world.scenario) - radius
    start = (world.scenario.start_pose.x, world.scenario.start_pose.y)
    goal = (world.scenario.goal_pose.x, world.scenario.goal_pose.y)

    context = _context(world)
    # The platform's own id: a hash of task profile, mission, variant and
    # seed. The first draft of this script wrote "<case>:<candidate>",
    # which is not what a run produces and is not a filename a sidecar
    # can live under on Windows.
    episode_context_id = context.episode_context_id

    for name in STACKS:
        candidate_id = f"{name}+dwa"
        candidates.append(
            CandidateComponents(
                candidate_id=candidate_id,
                global_planner=name,
                local_controller="dwa",
                local_controller_config="dwa_default",
            )
        )
        sidecar_path = (
            folder / "sidecar" / candidate_id / f"{episode_context_id}.planning_inputs.jsonl"
        )
        planning = PlanningInputRecorder.to_path(
            sidecar_path,
            run_id=world.case_id,
            episode_context_id=episode_context_id,
            candidate_id=candidate_id,
            execution_environment_ref=reference,
        )
        sidecars[candidate_id] = sidecar_path.parent
        recorder = EpisodeTraceRecorder(
            context,
            candidate_id,
            root=trace_root,
            # The recorder's vocabulary, not the packet's: a planted world is
            # a reference run, and the trace address says so.
            evidence_class="reference",
        )
        try:
            with recorder:
                run = run_stack(
                    world.map_data,
                    world.scenario,
                    DWAPlanner(),
                    _planner(name),
                    ReplanningConfig(enabled=True, max_replans=2),
                    recorder=recorder,
                    planning_recorder=planning,
                )
        except Exception:
            planning.abandon()
            raise
        written = planning.close(expected_attempts=run.replan_attempts + 1)
        # Read it back the way a checker will, so a sidecar nothing can
        # consume fails here rather than inside a graded round.
        _header, reloaded = read_sidecar(sidecar_path)
        validate_episode_attempts(reloaded, expected_attempts=len(written))
        for record in reloaded:
            snapshot_for(sidecar_path, record)
        planned = tuple((point.x, point.y) for point in run.plan.path) or None
        # Geometry along the route the stack set out on — or, when the
        # planner refused and there is no route, along the straight line
        # the task asks for, which is the corridor the refusal is about.
        try:
            # Half a cell, not the default 0.1 m: the planted wall is one
            # cell thick, and a 0.1 m walk over a 0.1 m grid lands on cell
            # boundaries where floating point puts 1.4/0.1 at 13.999 — the
            # wall column was stepped over and every cross-section left the
            # grid unbounded, which read as "no passage measured".
            routes[candidate_id] = measure_route(
                world.map_data,
                planned or (start, goal),
                sample_spacing_m=world.map_data.resolution / 2.0,
            )
        except MapFeatureRefusal as refused:
            notes.append(f"{candidate_id}: route not measurable — {refused}")
        # A refused plan leaves no route to measure progress along. The
        # task's own start-to-goal line stands in as the reference — the
        # corridor the refusal is about — and the note says so, because a
        # reference nobody drove is a different thing from a plan.
        reference_line = planned or (start, goal)
        traces.append(
            _trace_from_parquet(recorder.path, candidate_id, episode_context_id, reference_line)
        )
        measurements.append(_measured(candidate_id, run, traces[-1]))
        if not planned:
            notes.append(
                f"{candidate_id}: the planner refused at the start pose; the trace is "
                "the one row a stopped robot writes, carrying the refusal event, and "
                "the reference line is the task's start-to-goal line"
            )

    # The timelines M2 asks for. A planted world ranks nobody, so there
    # is no ΔU to select exemplars by; the roles are assigned from what
    # the episodes were — the candidate that came closest to something
    # is the safety-critical one, the other is typical — and both are
    # carried, because a comparison with one timeline shows a shape with
    # nothing to read it against.
    worst_clearance = {
        trace.candidate_id: min(
            (value for value in trace.columns["clearance_m"] if value is not None),
            default=float("inf"),
        )
        for trace in traces
    }
    closest = min(worst_clearance, key=lambda name: worst_clearance[name], default=None)
    for trace in traces:
        route = routes.get(trace.candidate_id)
        length = getattr(route, "route_length_m", 0.0)
        if not length:
            notes.append(
                f"{trace.candidate_id}: no measured route, so there is no line to "
                "place progress against and no timeline"
            )
            continue
        timeline = timeline_from_trace(
            _with_progress(trace),
            role="safety_critical" if trace.candidate_id == closest else "typical",
            deployment=_deployment(world, length),
        )
        if timeline is None:
            notes.append(
                f"{trace.candidate_id}: the trace is missing a column the running "
                "metrics read, so no point on it can be placed"
            )
            continue
        timelines.append(timeline)

    required_width = 2.0 * (radius + inflation_margin)
    observations, skipped = observations_from_traces(
        traces,
        episodes_total=len(STACKS),
        route_features=routes,  # type: ignore[arg-type]
        required_passage_width_m=required_width,
    )
    notes.extend(skipped)

    # The packet carries one route: the first candidate's, which on a
    # planted single-episode world is the same corridor for both.
    route = next(iter(routes.values()), None)
    packet = build_case_packet(
        run_id=world.case_id,
        header=ExplanationArtifactHeader.for_current_code(
            source_manifest_ref=f"fixtures/golden/visible/{world.case_id}/planted.json",
            source_manifest_checksum=artifact_checksum({"planted_world": world.case_id}),
            detector_version=DETECTOR_VERSION,
            knowledge_base_version=KNOWLEDGE_BASE_VERSION,
            tool_catalog_version=TOOL_CATALOG_VERSION,
        ),
        task=TaskFacts(
            task_profile_id=world.family,
            robot=RobotFacts(
                radius_m=radius,
                inflation_margin_m=inflation_margin,
                required_passage_width_m=required_width,
            ),
            route=route,  # type: ignore[arg-type]
        ),
        candidates=candidates,
        decision=DecisionFacts(status="GATE_ONLY"),
        observations=observations,
        measurements=measurements,
        timelines=timelines,
        evidence_class="research",
    )

    provenance = PacketProvenance(
        packet_ref=f"fixtures/golden/visible/{world.case_id}/packet.json",
        packet_checksum=packet_checksum(packet),
        run_id=world.case_id,
        recorded_at=RECORDED_AT,
        sidecar_present=True,
        source="planted_run",
    )
    (folder / "packet.json").write_text(
        json.dumps(packet.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    (folder / "provenance.json").write_text(
        json.dumps(
            {**provenance.model_dump(mode="json"), "provenance_checksum": provenance.checksum},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    notes.append(
        "sidecars: " + ", ".join(f"{name} -> {path.name}" for name, path in sidecars.items())
    )
    return folder, len(observations), notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=FIXTURE_ROOT)
    args = parser.parse_args()

    print(f"{len(WORLDS)} of 6 families are staged; the other 3 are not, and no macro")
    print("average over these is comparable with a bar agreed for six.")
    reference = build_reference()
    with tempfile.TemporaryDirectory(prefix="golden-traces-") as scratch:
        for world in WORLDS:
            folder, sightings, notes = build(world, args.root, Path(scratch), reference)
            for note in notes:
                print(f"    note: {note}")
            print(f"  built  {world.case_id:16} {sightings} observation(s)  {folder.name}")
    print(f"\n{len(WORLDS)} packet(s) written to {args.root}")
    print("OFFICIAL_GOLDEN_READY stays False: three families are still missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
