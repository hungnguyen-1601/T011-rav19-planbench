"""Turn the planted runs into packet fixtures a suite can be scored on.

``plant_golden_runs.py`` stages three of the six families and writes a
planning-input sidecar for each. That is a run, not a case: every
``packet_ref`` in ``VISIBLE_SUITE`` points at
``fixtures/golden/visible/<case_id>/packet.json``, and until that file
exists the suite names twelve cases nobody can grade.

This closes that half. Each staged world is run again with its
trajectory kept, the detectors read it, and the packet is written beside
a provenance file the loader **recomputes** rather than trusts.

**Three families, and the count travels with every result.** The other
three need a sweep across contexts rather than one episode
(``expansion_latency``), a gap the packet builder does not yet declare
(``insufficient_evidence``), or a pairing whose ΔU straddles zero
(``negative_control``). A macro average over three families read against
a bar agreed for six is a comparison nobody should make.

**A single-episode packet carries no waterfall**, which is the builder's
own rule rather than a shortcut taken here: a decomposition is a
statement about a *pair* the statistics chose, and each of these worlds
runs one candidate. The sightings and the geometry are what such a run
has to say.

**What these fixtures do not carry, and why it is said out loud.** The
trajectory gives time and pose. Clearance and planner latency are
recorded by the trace recorder in a real run and are not reproduced
here, so the detectors that read them — near-miss clusters, latency
spikes — cannot fire on these packets. That is a property of the
fixture, not of the analyst, and it is printed per case so nobody reads
a quiet packet as a quiet run.

**``OFFICIAL_GOLDEN_READY`` stays False.** These are visible-suite
fixtures for development. Flipping that constant is a code change with a
diff, made when six families exist — not a side effect of running this.
"""

from __future__ import annotations

import argparse
import json
import sys
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
from planbench_explanation.packet_artifact import (  # noqa: E402
    PacketProvenance,
    packet_checksum,
)
from planbench_explanation.packet_builder import (  # noqa: E402
    EpisodeTrace,
    observations_from_traces,
)
from planbench_explanation.versioning import ExplanationArtifactHeader  # noqa: E402
from planbench_planning import (  # noqa: E402
    AStarPlanner,
    DWAPlanner,
    RRTStarConfig,
    RRTStarPlanner,
)
from planbench_schemas.replanning import ReplanningConfig  # noqa: E402
from planbench_simulator.nav_stack import run_stack  # noqa: E402

#: Where the suite says its packets live. Not a flag: ``VISIBLE_SUITE``
#: names this path in every ``packet_ref``, and a script that could
#: write them somewhere else would produce fixtures the suite cannot
#: find while reporting success.
FIXTURE_ROOT = ROOT / "fixtures" / "golden" / "visible"

RECORDED_AT = "2026-08-26T00:00:00Z"


def _trace_for(
    world: PlantedWorld, run, candidate_id: str
) -> EpisodeTrace | None:  # type: ignore[no-untyped-def]
    """The episode as columns the detectors read.

    ``clearance_m`` and ``planner_latency_ms`` are absent rather than
    filled with zeros: a zero clearance is a collision, and a fixture
    that invented one would plant an answer nobody ran.
    """
    trajectory = run.result.trajectory
    times = [point.time for point in trajectory]
    if not times:
        # The planted mechanism itself: a world whose aisle is closed
        # produces a refusal and no motion. There is no trace to read,
        # and inventing one row so the detectors have something to run
        # on would plant an episode that never happened.
        return None
    events = []
    for event in run.result.events:
        nearest = min(range(len(times)), key=lambda index: abs(times[index] - event.time))
        events.append({"index": nearest, "event": event.type})
    return EpisodeTrace(
        candidate_id=candidate_id,
        episode_context_id=f"{world.case_id}:{candidate_id}",
        columns={
            "t": times,
            "x": [point.x for point in trajectory],
            "y": [point.y for point in trajectory],
            "events": events,
        },
        planned_path=tuple((point.x, point.y) for point in run.plan.path),
    )


def _planner(name: str):  # type: ignore[no-untyped-def]
    return (
        RRTStarPlanner(RRTStarConfig(max_iterations=120), episode_seed=7)
        if name == "rrtstar"
        else AStarPlanner()
    )


#: Both stacks each world is run with.
#:
#: **A packet explains a comparison, and a comparison needs two
#: candidates** — the contract refuses a one-candidate packet, and it is
#: right to: an explanation of why one stack won is a statement about a
#: pair. ``plant_golden_runs.py`` stages one candidate per world because
#: it is planting a *mechanism*, so the second stack is run here, on the
#: same world and the same scenario, which is the fairness rule this
#: platform is built on.
STACKS: tuple[str, ...] = ("astar", "rrtstar")


def build(world: PlantedWorld, root: Path) -> tuple[Path, int]:
    """Run one staged world with both stacks and write its packet."""
    traces: list[EpisodeTrace] = []
    candidates: list[CandidateComponents] = []
    notes: list[str] = []

    for name in STACKS:
        run = run_stack(
            world.map_data,
            world.scenario,
            DWAPlanner(),
            _planner(name),
            ReplanningConfig(enabled=True, max_replans=2),
        )
        candidate_id = f"{name}+dwa"
        candidates.append(
            CandidateComponents(
                candidate_id=candidate_id,
                global_planner=name,
                local_controller="dwa",
                local_controller_config="dwa_default",
            )
        )
        trace = _trace_for(world, run, candidate_id)
        if trace is None:
            notes.append(
                f"{candidate_id}: the robot never moved — this world plants a refusal "
                "for this stack, so there is no trajectory for the detectors to read"
            )
            continue
        traces.append(trace)

    observations, skipped = observations_from_traces(traces, episodes_total=len(STACKS))
    notes.extend(skipped)

    packet = build_case_packet(
        run_id=world.case_id,
        header=ExplanationArtifactHeader.for_current_code(
            # A planted world has no decision manifest to point at, and a
            # reference invented to fill the field would be one nobody
            # can follow. Derived from the case id: stable, and
            # obviously synthetic.
            source_manifest_ref=f"fixtures/golden/visible/{world.case_id}/planted.json",
            source_manifest_checksum=packet_checksum_placeholder(world),
            detector_version=DETECTOR_VERSION,
            knowledge_base_version=KNOWLEDGE_BASE_VERSION,
            tool_catalog_version=TOOL_CATALOG_VERSION,
        ),
        task=TaskFacts(
            task_profile_id=world.family,
            robot=RobotFacts(radius_m=world.scenario.robot.radius),
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
    for note in notes:
        print(f"    note: {note}")
    return folder, len(observations)


def packet_checksum_placeholder(world: PlantedWorld) -> str:
    """A stand-in manifest checksum for a world with no decision run.

    The header requires one and the field is a reference to a manifest
    that does not exist for a planted world. Derived from the case id so
    it is stable and obviously synthetic, rather than a random value
    that would move the packet checksum on every build.
    """
    from planbench_explanation.versioning import artifact_checksum

    return artifact_checksum({"planted_world": world.case_id})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=FIXTURE_ROOT)
    args = parser.parse_args()

    print(f"{len(WORLDS)} of 6 families are staged; the other 3 are not, and no macro")
    print("average over these is comparable with a bar agreed for six.")
    built = 0
    quiet = 0
    for world in WORLDS:
        folder, sightings = build(world, args.root)
        built += 1
        if sightings == 0:
            quiet += 1
        print(f"  built  {world.case_id:16} {sightings} observation(s)  {folder.name}")
    print(f"\n{built} packet(s) written to {args.root}")
    if quiet:
        print(
            f"{quiet} of them carry no sighting: this fixture has no clearance or "
            "latency column, so the detectors that read those cannot fire. That is a "
            "property of the fixture, not of the analyst."
        )
    print("OFFICIAL_GOLDEN_READY stays False: three families are still missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
