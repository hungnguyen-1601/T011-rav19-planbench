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
import math
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("schemas", "planning", "metrics", "benchmark", "decision", "explanation"):
    sys.path.insert(0, str(ROOT / "packages" / package))
sys.path.insert(0, str(ROOT / "services" / "simulator"))
sys.path.insert(0, str(ROOT / "scripts"))

from plant_golden_runs import (  # noqa: E402
    SECOND_VARIANTS_MISSING,
    WORLDS,
    PlantedWorld,
    build_reference,
)

from planbench_decision.anchors import load_anchors  # noqa: E402
from planbench_decision.candidate import Candidate  # noqa: E402
from planbench_decision.objectives import DecisionSettings  # noqa: E402
from planbench_decision.stats import build_evidence  # noqa: E402
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
from planbench_explanation.waterfall import build_waterfall  # noqa: E402
from planbench_metrics.definitions import compute_metrics  # noqa: E402
from planbench_planning import (  # noqa: E402
    AStarPlanner,
    DWAConfig,  # noqa: E402
    DWAPlanner,
    RRTStarConfig,
    RRTStarPlanner,
)
from planbench_schemas.episode_context import EpisodeContext  # noqa: E402
from planbench_schemas.replanning import ReplanningConfig  # noqa: E402
from planbench_schemas.task_profile import TaskProfile  # noqa: E402
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


#: What a planted world declares about itself when the decision layer
#: has to score it. Written here rather than borrowed from a test fake:
#: a fixture that inherits a test's numbers inherits a test's
#: assumptions, and the two drift apart the first time somebody edits
#: the test for an unrelated reason.
#:
#: The hardware block is the contract's own board budget (HĐ-2.4); the
#: preference profile these worlds are scored under is
#: ``measured_only``, because nothing here declares a tuning budget and
#: a profile that prices engineering effort would charge every candidate
#: for something nobody measured.
def _profile(world: PlantedWorld, goals: Sequence[tuple[float, float]]) -> TaskProfile:
    scenario = world.scenario
    missions = [
        {
            "id": f"m{index + 1}",
            "start": [scenario.start_pose.x, scenario.start_pose.y, 0.0],
            "goal": [goal[0], goal[1], 0.0],
            "probability": 1.0 / len(goals),
        }
        for index, goal in enumerate(goals)
    ]
    return TaskProfile.model_validate(
        {
            "id": f"planted_{world.family}",
            "environment": {
                "map": f"planted://{world.case_id}.pgm",
                "map_yaml": f"planted://{world.case_id}.yaml",
                "dynamic_obstacles": [],
            },
            "missions": missions,
            "robot": {
                "radius": scenario.robot.radius,
                "max_linear_velocity": scenario.robot.max_linear_velocity,
                "max_angular_velocity": scenario.robot.max_angular_velocity,
                "max_linear_acceleration": scenario.robot.max_linear_acceleration,
                "max_angular_acceleration": scenario.robot.max_angular_acceleration,
                "control_period": scenario.simulation_dt,
            },
            "available_observations": ["lidar_2d"],
            "constraints": {
                "success_rate_min": 0.9,
                "collision_probability_max": 0.1,
                "clearance_warning_m": DetectorSettings().near_miss_clearance_m,
                "goal_tolerance_m": scenario.goal_tolerance,
                # Heading unconstrained: the simulator has no final-orientation
                # controller, and a tighter value is refused at load.
                "goal_tolerance_rad": math.pi,
                "episode_timeout_s": scenario.timeout_seconds,
                "stuck_threshold_s": 5.0,
            },
            "hardware": {
                "target_device": "jetson_orin_nano",
                "total_ram_mb": 8192,
                "ram_budget_breakdown": {
                    "os_and_middleware_mb": 1536,
                    "perception_stack_mb": 2048,
                    "localization_mapping_mb": 819,
                    "logging_and_reserve_mb": 512,
                },
                "available_ram_mb": 3277,
            },
        }
    )


#: The two controller tunings the negative control compares. One stack,
#: two horizons: a pair that differs in a planner would give an analyst
#: something true to say, and this family is about the case where there
#: is nothing.
CONTROLLER_TUNINGS: dict[str, DWAConfig] = {
    "dwa_default": DWAConfig(),
    "dwa_patient": DWAConfig(horizon_seconds=1.7),
}


def _decision_candidate(world: PlantedWorld, planner: str, controller_config: str):  # type: ignore[no-untyped-def]
    """The decision layer's view of one stack, for scoring only."""
    return Candidate.model_validate(
        {
            "type": "modular",
            "global_planner": {"name": planner, "version": "v1"},
            "local_controller": {"name": "dwa", "version": "v1"},
            "params": {planner: {}, "dwa": {"config": controller_config}},
            "observation_requirements": ["lidar_2d"],
            "resource_profile": {
                "kind": "structural",
                "target_implementation": "cpp_ros2",
                "bytes_per_search_node": 40,
                "bytes_per_tree_node": 40,
                "bytes_per_costmap_cell": 1,
                "costmap_layers": 3,
                "fixed_overhead_mb": 8.0,
            },
        }
    )


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
    """Run one staged world and write its packet.

    **Episodes, plural.** Three of the six families are about a pattern
    *across* episodes rather than inside one: an association between how
    much a search expanded and how long it took, and a difference that
    straddles zero. One episode is one point, and a point has no slope
    and no interval — so a world may name extra goals, and each becomes
    an episode with its own context id.

    The planning-input sidecar is written **beside the packet**, one
    directory per candidate and one file per episode. Candidates share
    an ``episode_context_id`` — that is what the id is, a hash of the
    conditions — so one flat directory would have the second stack
    overwrite the first.

    A world may also declare that **nothing recorded it**
    (``record_traces=False``). That is not a fixture with its files
    deleted afterwards: the episodes run with no recorder attached, the
    way every run before the trace layout did, and the packet that comes
    out honestly has no observations to carry.
    """
    folder = root / world.case_id
    folder.mkdir(parents=True, exist_ok=True)
    # Start from an empty sidecar tree. Rebuilding in place left the
    # previous build's episodes behind, and a stale sidecar still names
    # a snapshot the new run overwrote — which the reader correctly
    # reports as a file edited after its run, from a build nobody kept.
    if (folder / "sidecar").exists():
        shutil.rmtree(folder / "sidecar")
    traces: list[EpisodeTrace] = []
    timelines: list[EpisodeTimeline] = []
    measurements: list[CandidateMeasurements] = []
    candidates: list[CandidateComponents] = []
    notes: list[str] = []
    routes: dict[str, object] = {}
    sidecars: dict[str, Path] = {}
    report_rows: dict[str, list[dict[str, object]]] = {}
    scored: dict[str, object] = {}

    radius = world.scenario.robot.radius
    inflation_margin = _hard_radius(world.map_data, world.scenario) - radius
    start = (world.scenario.start_pose.x, world.scenario.start_pose.y)
    goals = [(world.scenario.goal_pose.x, world.scenario.goal_pose.y), *world.episode_goals]
    profile = _profile(world, goals)
    anchors = load_anchors().resolve(profile)
    settings = DecisionSettings(preference_profile="measured_only")

    # Two shapes of pair. Most worlds compare two global planners; the
    # negative control compares two tunings of one controller, because a
    # pair that differs in a planner would give an analyst something true
    # to say and this family is about the case where there is nothing.
    tunings = world.stacks
    arms = (
        [(world.global_planner_name, name) for name in tunings]
        if tunings
        else [(name, "dwa_default") for name in STACKS]
    )

    for planner_name, controller_config in arms:
        # The pair every other world runs keeps the name it has always
        # had: renaming a candidate renames every citation into it, and
        # the labels the scorer holds are written against these ids.
        candidate_id = (
            f"{planner_name}+dwa"
            if controller_config == "dwa_default"
            else f"{planner_name}+{controller_config.removeprefix('dwa_')}"
        )
        candidates.append(
            CandidateComponents(
                candidate_id=candidate_id,
                global_planner=planner_name,
                local_controller="dwa",
                local_controller_config=controller_config,
            )
        )
        decision_candidate = _decision_candidate(world, planner_name, controller_config)
        episode_metrics = []
        episode_contexts = []

        for index, goal in enumerate(goals):
            mission = f"m{index + 1}"
            context = EpisodeContext(
                task_profile_id=profile.id, mission_id=mission, seed=7 + index
            )
            episode_context_id = context.episode_context_id
            scenario = world.scenario.model_copy(
                update={"goal_pose": world.scenario.goal_pose.model_copy(
                    update={"x": goal[0], "y": goal[1]}
                )}
            )
            controller = DWAPlanner(CONTROLLER_TUNINGS[controller_config])

            if not world.record_traces:
                # No recorder, no sidecar: the run this fixture is of is
                # one nobody was recording.
                run_stack(
                    world.map_data,
                    scenario,
                    controller,
                    _planner(planner_name),
                    ReplanningConfig(enabled=True, max_replans=2),
                )
                continue

            sidecar_path = (
                folder
                / "sidecar"
                / candidate_id
                / f"{episode_context_id}.planning_inputs.jsonl"
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
                # The recorder's vocabulary, not the packet's: a planted
                # world is a reference run, and the address says so.
                evidence_class="reference",
            )
            try:
                with recorder:
                    run = run_stack(
                        world.map_data,
                        scenario,
                        controller,
                        _planner(planner_name),
                        ReplanningConfig(enabled=True, max_replans=2),
                        recorder=recorder,
                        planning_recorder=planning,
                    )
            except Exception:
                planning.abandon()
                raise
            written = planning.close(expected_attempts=run.replan_attempts + 1)
            # Read it back the way a checker will, so a sidecar nothing
            # can consume fails here rather than inside a graded round.
            _header, reloaded = read_sidecar(sidecar_path)
            validate_episode_attempts(reloaded, expected_attempts=len(written))
            for record in reloaded:
                snapshot_for(sidecar_path, record)

            planned = tuple((point.x, point.y) for point in run.plan.path) or None
            goal_point = (goal[0], goal[1])
            try:
                # Half a cell, not the default 0.1 m: a planted wall is
                # one cell thick, and a 0.1 m walk over a 0.1 m grid
                # lands on cell boundaries where floating point puts
                # 1.4/0.1 at 13.999 - the wall column was stepped over
                # and every cross-section left the grid unbounded.
                measured = measure_route(
                    world.map_data,
                    planned or (start, goal_point),
                    sample_spacing_m=world.map_data.resolution / 2.0,
                )
                routes.setdefault(candidate_id, measured)
            except MapFeatureRefusal as refused:
                notes.append(f"{candidate_id}/{mission}: route not measurable - {refused}")

            reference_line = planned or (start, goal_point)
            trace = _trace_from_parquet(
                recorder.path, candidate_id, episode_context_id, reference_line
            )
            traces.append(trace)
            if not planned:
                notes.append(
                    f"{candidate_id}/{mission}: the planner refused at the start pose; "
                    "the trace is the one row a stopped robot writes, carrying the "
                    "refusal event, and the reference line is the start-to-goal line"
                )

            # The scoring report row this episode contributes. Its two
            # node columns are never added together: a grid frontier and
            # a sampling tree count different structures, and a candidate
            # populates one or the other.
            sampling = planner_name in ("rrtstar", "rrt")
            latencies = [
                value for value in trace.columns["planner_latency_ms"] if value is not None
            ]
            report_rows.setdefault(candidate_id, []).append(
                {
                    "episode_context_id": episode_context_id,
                    "peak_search_nodes": 0 if sampling else run.plan.expanded_nodes,
                    "peak_tree_nodes": run.plan.expanded_nodes if sampling else 0,
                    "p99_latency_ms": _percentile(latencies, 0.99) if latencies else 0.0,
                    "min_clearance": min(
                        (v for v in trace.columns["clearance_m"] if v is not None),
                        default=0.0,
                    ),
                    "collision_count": 1 if run.result.status == "collision" else 0,
                }
            )

            loaded = read_trace(recorder.path)
            try:
                measured = compute_metrics(
                    loaded,
                    profile,
                    context,
                    world.map_data,
                    resource_profile=decision_candidate.resource_profile,
                )
                # The decision layer names a candidate by the hash of
                # its own declaration; the trace names it by the id this
                # fixture reads by. Same run, two names — restamped here
                # rather than renaming the candidate, because every
                # citation in the packet points at the readable one.
                episode_metrics.append(
                    measured.model_copy(
                        update={"candidate_id": decision_candidate.candidate_id}
                    )
                )
                episode_contexts.append(context)
            except Exception as refused:  # noqa: BLE001 - the metrics boundary
                notes.append(f"{candidate_id}/{mission}: metrics refused - {refused}")

        if traces and any(item.candidate_id == candidate_id for item in traces):
            measurements.append(
                _measured_over(
                    candidate_id,
                    [item for item in traces if item.candidate_id == candidate_id],
                    report_rows.get(candidate_id, ()),
                )
            )
        if episode_metrics:
            try:
                scored[candidate_id] = build_evidence(
                    decision_candidate, episode_metrics, episode_contexts, anchors, settings
                )
            except Exception as refused:  # noqa: BLE001 - the decision boundary
                notes.append(f"{candidate_id}: not scored - {refused}")

    # The timelines M2 asks for, one per candidate, on that candidate's
    # first episode. The role is assigned from what the episodes were -
    # the candidate that came closest to something is the safety-critical
    # one - because a planted world ranks nobody and there is no delta U
    # to select exemplars by.
    worst_clearance = {
        trace.candidate_id: min(
            (value for value in trace.columns["clearance_m"] if value is not None),
            default=float("inf"),
        )
        for trace in traces
    }
    closest = min(worst_clearance, key=lambda name: worst_clearance[name], default=None)
    seen_timeline: set[str] = set()
    for trace in traces:
        if trace.candidate_id in seen_timeline:
            continue
        route = routes.get(trace.candidate_id)
        length = getattr(route, "route_length_m", 0.0)
        if not length:
            notes.append(
                f"{trace.candidate_id}: no measured route, so there is no line to "
                "place progress against and no timeline"
            )
            continue
        timeline = timeline_from_trace(
            trace,
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
        seen_timeline.add(trace.candidate_id)

    required_width = 2.0 * (radius + inflation_margin)
    observations, skipped = observations_from_traces(
        traces,
        episodes_total=len(goals),
        route_features=routes,  # type: ignore[arg-type]
        required_passage_width_m=required_width,
    )
    notes.extend(skipped)

    # The comparison, when there is one to make. Two candidates scored
    # over the same contexts decompose into a waterfall; anything less is
    # a run that ranked nobody, and the packet says so rather than
    # carrying an empty structure somebody reads as "no difference".
    waterfall = None
    if len(scored) == 2:
        names = sorted(scored)
        left, right = (scored[key] for key in names)
        try:
            computed = build_waterfall(left, right, settings=settings)
            # The decision layer names a candidate by the hash of its own
            # declaration and the packet names it by the id every citation
            # points at. The packet builder refuses a waterfall about
            # candidates it cannot see — rightly — so the two names are
            # joined here, in the open, rather than the packet carrying a
            # comparison between ids nobody reading it can find.
            waterfall = computed.model_copy(
                update={
                    "candidate_a": names[0],
                    "candidate_b": names[1],
                    "drill_down": computed.drill_down.model_copy(
                        update={"candidate_a": names[0], "candidate_b": names[1]}
                    ),
                }
            )
            notes.append(
                f"waterfall: delta U = {waterfall.delta_utility_mean:+.4f} over "
                f"{waterfall.n_episodes} paired episode(s)"
            )
        except Exception as refused:  # noqa: BLE001 - the waterfall boundary
            notes.append(f"waterfall refused - {refused}")

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
        decision=DecisionFacts(
            status="COMPARED" if waterfall is not None else "GATE_ONLY",
            waterfall=waterfall,
        ),
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
        sidecar_present=bool(sidecars),
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

    # The scoring report, when the run produced one. It is what
    # ``latency_vs_expanded_nodes`` reads: the packet carries per
    # candidate aggregates, and an association between expansion and
    # latency lives per episode.
    if report_rows:
        (folder / "report.json").write_text(
            json.dumps(
                {
                    "identity": {"task_profile_id": world.family},
                    "candidates": [
                        {"candidate_id": name, "episodes": rows}
                        for name, rows in sorted(report_rows.items())
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=1,
            ),
            encoding="utf-8",
        )

    if sidecars:
        notes.append(
            "sidecars: " + ", ".join(f"{name} -> {path.name}" for name, path in sidecars.items())
        )
    else:
        notes.append("no recorder was attached: this run left no traces and no sidecars")
    return folder, len(observations), notes


def _measured_over(
    candidate_id: str,
    traces: Sequence[EpisodeTrace],
    rows: Sequence[dict[str, object]],
) -> CandidateMeasurements:
    """What one candidate scored across its episodes.

    The denominator is the number of episodes behind every rate, and it
    is the packet's own field rather than an assumption a reader has to
    make: a success rate over three episodes and one over thirty are
    different claims wearing one number.
    """
    successes = sum(1 for row in rows if float(row.get("collision_count", 0)) == 0)
    latencies = [
        value
        for trace in traces
        for value in trace.columns["planner_latency_ms"]
        if value is not None
    ]
    clearances = [
        value
        for trace in traces
        for value in trace.columns["clearance_m"]
        if value is not None
    ]
    driven = 0.0
    for trace in traces:
        xs, ys = trace.columns["x"], trace.columns["y"]
        driven += sum(
            ((xs[index] - xs[index - 1]) ** 2 + (ys[index] - ys[index - 1]) ** 2) ** 0.5
            for index in range(1, len(xs))
        )
    count = max(1, len(traces))
    fields: dict[str, MeasuredValue | None] = {
        "success_rate": MeasuredValue(
            value=successes / count, unit="ratio", denominator=count
        ),
        "collisions": MeasuredValue(
            value=float(sum(float(row.get("collision_count", 0)) for row in rows)),
            unit="count",
            denominator=count,
        ),
        "path_length_m": MeasuredValue(
            value=float(driven / count), unit="m", denominator=count
        ),
    }
    if latencies:
        fields["latency_p99_ms"] = MeasuredValue(
            value=_percentile(latencies, 0.99), unit="ms", denominator=count
        )
        fields["latency_median_ms"] = MeasuredValue(
            value=_percentile(latencies, 0.5), unit="ms", denominator=count
        )
    if clearances:
        fields["min_clearance_m"] = MeasuredValue(
            value=min(clearances), unit="m", denominator=count
        )
    # ``decision_utility`` stays absent unless a comparison was scored:
    # a zero here would read as "scored nothing" rather than as "was
    # never scored".
    return CandidateMeasurements(candidate_id=candidate_id, **fields)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=FIXTURE_ROOT)
    args = parser.parse_args()

    staged = {world.family for world in WORLDS}
    print(f"{len(staged)} of 6 families are staged: {', '.join(sorted(staged))}.")
    print(
        "One case per family, not two: the near-boundary and negative twins "
        f"({len(SECOND_VARIANTS_MISSING)} of them) are what separates a mechanism "
        "from its shape, and they are not built."
    )
    reference = build_reference()
    with tempfile.TemporaryDirectory(prefix="golden-traces-") as scratch:
        for world in WORLDS:
            folder, sightings, notes = build(world, args.root, Path(scratch), reference)
            for note in notes:
                print(f"    note: {note}")
            print(f"  built  {world.case_id:16} {sightings} observation(s)  {folder.name}")
    print(f"\n{len(WORLDS)} packet(s) written to {args.root}")
    print(
        "OFFICIAL_GOLDEN_READY stays False: six families is not twelve cases, and "
        "the preregistration reports counts rather than a rate below twelve."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
