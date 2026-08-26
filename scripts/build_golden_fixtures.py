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

from plant_golden_runs import WORLDS, PlantedWorld  # noqa: E402

from planbench_explanation.case_packet import (  # noqa: E402
    DecisionFacts,
    RobotFacts,
    TaskFacts,
    build_case_packet,
)
from planbench_explanation.catalog import TOOL_CATALOG_VERSION  # noqa: E402
from planbench_explanation.contrast import CandidateComponents  # noqa: E402
from planbench_explanation.detectors import DETECTOR_VERSION  # noqa: E402
from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION  # noqa: E402
from planbench_explanation.map_features import MapFeatureRefusal, measure_route  # noqa: E402
from planbench_explanation.packet_artifact import (  # noqa: E402
    PacketProvenance,
    packet_checksum,
)
from planbench_explanation.packet_builder import (  # noqa: E402
    EpisodeTrace,
    observations_from_traces,
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


def build(world: PlantedWorld, root: Path, trace_root: Path) -> tuple[Path, int, list[str]]:
    """Run one staged world with both stacks and write its packet."""
    traces: list[EpisodeTrace] = []
    candidates: list[CandidateComponents] = []
    notes: list[str] = []
    routes: dict[str, object] = {}

    radius = world.scenario.robot.radius
    inflation_margin = _hard_radius(world.map_data, world.scenario) - radius
    start = (world.scenario.start_pose.x, world.scenario.start_pose.y)
    goal = (world.scenario.goal_pose.x, world.scenario.goal_pose.y)

    for name in STACKS:
        candidate_id = f"{name}+dwa"
        episode_context_id = f"{world.case_id}:{candidate_id}"
        candidates.append(
            CandidateComponents(
                candidate_id=candidate_id,
                global_planner=name,
                local_controller="dwa",
                local_controller_config="dwa_default",
            )
        )
        recorder = EpisodeTraceRecorder(
            _context(world),
            candidate_id,
            root=trace_root,
            # The recorder's vocabulary, not the packet's: a planted world is
            # a reference run, and the trace address says so.
            evidence_class="reference",
        )
        with recorder:
            run = run_stack(
                world.map_data,
                world.scenario,
                DWAPlanner(),
                _planner(name),
                ReplanningConfig(enabled=True, max_replans=2),
                recorder=recorder,
            )
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
        reference = planned or (start, goal)
        traces.append(
            _trace_from_parquet(recorder.path, candidate_id, episode_context_id, reference)
        )
        if not planned:
            notes.append(
                f"{candidate_id}: the planner refused at the start pose; the trace is "
                "the one row a stopped robot writes, carrying the refusal event, and "
                "the reference line is the task's start-to-goal line"
            )

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
        evidence_class="research",
    )

    folder = root / world.case_id
    folder.mkdir(parents=True, exist_ok=True)
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
    return folder, len(observations), notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=FIXTURE_ROOT)
    args = parser.parse_args()

    print(f"{len(WORLDS)} of 6 families are staged; the other 3 are not, and no macro")
    print("average over these is comparable with a bar agreed for six.")
    with tempfile.TemporaryDirectory(prefix="golden-traces-") as scratch:
        for world in WORLDS:
            folder, sightings, notes = build(world, args.root, Path(scratch))
            for note in notes:
                print(f"    note: {note}")
            print(f"  built  {world.case_id:16} {sightings} observation(s)  {folder.name}")
    print(f"\n{len(WORLDS)} packet(s) written to {args.root}")
    print("OFFICIAL_GOLDEN_READY stays False: three families are still missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
