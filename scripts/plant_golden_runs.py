"""Produce the planted runs the golden suite grades against — E6b / blocker 4.

The visible suite (``planbench_explanation.golden_fixtures``) names twelve
cases and points each at a packet fixture. Nothing produced those
fixtures, and :data:`~planbench_explanation.golden.OFFICIAL_GOLDEN_READY`
has been false ever since — first because the sidecar writer did not
exist, then because no run had used it.

This script closes the second half: it stages each family's world,
executes it through the **real** contract pipeline with the sidecar on,
and validates what came out. What it deliberately does **not** do is
flip that constant. Two things still stand between these runs and an
official golden suite, and both are decisions rather than code:

* a ``CasePacket`` has to be built from a run, which is **E4.1** — build
  at scoring time or on demand — and is not settled;
* the six families need agreement that each staged world really plants
  the mechanism it claims to, which is a review, not an execution.

So this produces evidence and prints what it produced. Somebody reads
that and decides.

**Every family here is staged from geometry, not sampled from luck.**
A planted case whose mechanism appears only on some seeds is a case
that grades an analyst on whether it got a lucky draw. Where a family
cannot be staged honestly with what the simulator can express today,
this script says so and skips it rather than shipping a world that
almost demonstrates the mechanism.

Usage::

    python scripts/plant_golden_runs.py --root artifacts/golden/visible
    python scripts/plant_golden_runs.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("schemas", "planning", "metrics", "benchmark", "decision", "explanation"):
    sys.path.insert(0, str(ROOT / "packages" / package))
sys.path.insert(0, str(ROOT / "services" / "simulator"))

from planbench_explanation.planning_input_evidence import (  # noqa: E402
    SidecarViolation,
    validate_episode_attempts,
)
from planbench_explanation.sidecar_writer import (  # noqa: E402
    PlanningInputRecorder,
    read_sidecar,
    snapshot_for,
)
from planbench_planning import AStarPlanner, DWAPlanner, RRTStarConfig, RRTStarPlanner  # noqa: E402
from planbench_schemas.geometry import Point2D, Pose2D  # noqa: E402
from planbench_schemas.map import CellState, MapData  # noqa: E402
from planbench_schemas.replanning import ReplanningConfig  # noqa: E402
from planbench_schemas.robot import RobotConfig  # noqa: E402
from planbench_schemas.scenario import Scenario  # noqa: E402
from planbench_simulator.nav_stack import run_stack  # noqa: E402


#: Build reference for the sidecars this script writes. Resolved once,
#: and it fails loudly rather than substituting a placeholder — a
#: planted run whose build nobody can name replays nothing.
def build_reference() -> str:
    from planbench_decision.card import resolve_git_sha

    return f"git:{resolve_git_sha(ROOT)}"


@dataclass(frozen=True)
class PlantedWorld:
    """One family's staged world, and what it is supposed to demonstrate."""

    case_id: str
    family: str
    map_data: MapData
    scenario: Scenario
    global_planner_name: str
    plants: str
    #: Why this world demonstrates the mechanism, in a sentence somebody
    #: reviewing the suite can disagree with. Not decoration: a planted
    #: case nobody can argue with is a case nobody checked.
    rationale: str


def _grid(width: int, height: int, resolution: float, blocked) -> MapData:  # type: ignore[no-untyped-def]
    cells = [
        CellState.OCCUPIED if blocked(col, row) else CellState.FREE
        for row in range(height)
        for col in range(width)
    ]
    return MapData(
        name="planted",
        width=width,
        height=height,
        resolution=resolution,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(int(cell) for cell in cells),
    )


def _robot(radius: float = 0.26) -> RobotConfig:
    return RobotConfig(
        radius=radius,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )


def _scenario(robot: RobotConfig, start: Point2D, goal: Point2D, **overrides) -> Scenario:  # type: ignore[no-untyped-def]
    fields = {
        "name": "planted",
        "robot": robot,
        "start_pose": Pose2D(x=start.x, y=start.y, theta=0.0),
        "goal_pose": Pose2D(x=goal.x, y=goal.y, theta=0.0),
        "goal_tolerance": 0.25,
        "timeout_seconds": 40.0,
        "simulation_dt": 0.1,
    }
    fields.update(overrides)
    return Scenario(**fields)  # type: ignore[arg-type]


def inflation_gap_closure() -> PlantedWorld:
    """A corridor the footprint clears and the configured inflation does not."""
    robot = _robot(0.26)
    gap_rows = {12, 13}

    def blocked(col: int, row: int) -> bool:
        if col != 14:
            return False
        return row not in gap_rows

    return PlantedWorld(
        case_id="inflation-001",
        family="inflation_gap_closure",
        map_data=_grid(30, 26, 0.1, blocked),
        scenario=_scenario(robot, Point2D(x=0.6, y=1.25), Point2D(x=2.4, y=1.25)),
        global_planner_name="astar",
        plants="geometric_infeasibility / costmap_inflation",
        rationale=(
            "The gap is 0.20 m of free cells. A 0.26 m robot needs 0.52 m of corridor "
            "before any inflation margin at all, so the passage is closed by geometry "
            "and the planner's refusal is the mechanism rather than an accident of "
            "where the robot happened to be."
        ),
    )


def rrt_sample_starvation() -> PlantedWorld:
    """A corridor a sampling tree reaches only sometimes at its budget.

    **Tuned against the planner, not guessed at.** The first version put
    a 0.30 m door in front of a 0.18 m robot and called it narrow; the
    convergence check ran it and returned ``refuted`` with 0% at both
    budgets, which is what it should say — 0.30 m of corridor is
    geometrically closed to a robot needing 0.36 m, so that world planted
    the *inflation* mechanism while claiming the sampling one. The same
    width-against-radius mistake E6a had, in a fixture.

    Measured rates on this world, twelve seeds:

    ==========  ============
    budget      corridor found
    ==========  ============
    120 (1x)    0 / 12
    480 (4x)    7 / 12
    ==========  ============

    Zero to 58% on budget alone is the signature: the door is passable,
    and whether the tree finds it is a matter of how many samples it
    draws.
    """
    robot = _robot(0.18)
    width, height = 120, 100
    wall_col = width // 2
    door = set(range(height // 2 - 2, height // 2 + 3))

    def blocked(col: int, row: int) -> bool:
        return col == wall_col and row not in door

    return PlantedWorld(
        case_id="rrt-001",
        family="rrt_sample_starvation",
        map_data=_grid(width, height, 0.1, blocked),
        scenario=_scenario(
            robot,
            Point2D(x=0.5, y=5.0),
            Point2D(x=11.5, y=5.0),
            timeout_seconds=90.0,
        ),
        global_planner_name="rrtstar",
        plants="sampling_budget_insufficiency / global_planner",
        rationale=(
            "The doorway is 0.50 m for a 0.18 m robot, so it is passable — and it is a "
            "small share of a 12 x 10 m room, so a tree at 120 iterations reaches it on "
            "none of twelve seeds and at 480 on seven. The passability is the point: a "
            "closed door would be the inflation family wearing another name, which is "
            "exactly what the first draft of this world was."
        ),
    )


def dwa_local_minimum() -> PlantedWorld:
    """A concave pocket the controller stalls in while a global route exists.

    Measured: the global planner returns a 6.1 m route out of the mouth
    and around, and the robot stops at x = 4.63 m — pressed against the
    pocket's back wall at 4.90 m, having driven *deeper* in. Episode
    status ``stuck``, zero replans. That pair is the mechanism: the
    route exists and the layer that had to follow it could not.

    The start is **inside** the pocket on purpose. A robot that has to
    enter one first is a robot whose stall depends on how it approached,
    and a planted case should not turn on that.
    """
    robot = _robot(0.18)
    width, height, depth, mouth = 80, 60, 18, 6
    centre_col, centre_row = width // 2, height // 2
    back_wall = centre_col + depth // 2
    arms = {centre_row - mouth, centre_row + mouth}

    def blocked(col: int, row: int) -> bool:
        if col == back_wall and centre_row - mouth <= row <= centre_row + mouth:
            return True
        return row in arms and centre_col - depth // 2 <= col <= back_wall

    return PlantedWorld(
        case_id="dwa-001",
        family="dwa_local_minimum",
        map_data=_grid(width, height, 0.1, blocked),
        scenario=_scenario(
            robot,
            Point2D(x=3.2, y=3.0),
            Point2D(x=7.2, y=3.0),
            timeout_seconds=45.0,
            stuck_time_window=3.0,
            stuck_min_displacement=0.15,
        ),
        global_planner_name="astar",
        plants="local_minimum_entrapment / local_controller",
        rationale=(
            "Inside a concave pocket every short-horizon rollout that leaves scores "
            "worse than one that stays, so the controller drives to the back wall and "
            "holds there — while the global planner has already returned a route out "
            "of the mouth. Global feasible, local stuck, and the detector's pair of "
            "facts is exactly that."
        ),
    )


#: Families this script cannot stage honestly yet, and why. Printed
#: rather than silently omitted: a suite missing two of its six families
#: is a suite whose macro average is over four, and a reader who is not
#: told will assume six.
CANNOT_STAGE_YET: dict[str, str] = {
    "expansion_latency": (
        "needs episodes whose searches differ in expanded nodes by enough to rank, "
        "which is a property of a sweep across contexts rather than of one world"
    ),
    "negative_control": (
        "needs two candidates whose decision utility difference straddles zero - "
        "a pairing, not a single "
        "episode, so it belongs to the sweep this script feeds rather than here"
    ),
    "insufficient_evidence": (
        "needs a run with a declared gap (perception accounting, or a missing trace); "
        "producible, but the gap has to be declared by the packet builder, which is "
        "E4.1 and not settled"
    ),
}

WORLDS: tuple[PlantedWorld, ...] = (
    inflation_gap_closure(),
    rrt_sample_starvation(),
    dwa_local_minimum(),
)


def plant(world: PlantedWorld, root: Path, reference: str) -> tuple[Path, int]:
    """Run one staged world with the sidecar on; validate what it wrote."""
    directory = root / world.family / world.case_id
    sidecar = directory / "planning_inputs.jsonl"
    recorder = PlanningInputRecorder.to_path(
        sidecar,
        run_id=world.case_id,
        episode_context_id=world.case_id,
        candidate_id=f"{world.global_planner_name}+dwa",
        execution_environment_ref=reference,
    )
    planner = (
        RRTStarPlanner(RRTStarConfig(max_iterations=120), episode_seed=7)
        if world.global_planner_name == "rrtstar"
        else AStarPlanner()
    )
    try:
        run = run_stack(
            world.map_data,
            world.scenario,
            DWAPlanner(),
            planner,
            ReplanningConfig(enabled=True, max_replans=2),
            planning_recorder=recorder,
        )
    except Exception:
        recorder.abandon()
        raise
    records = recorder.close(expected_attempts=run.replan_attempts + 1)

    # Read it back the way a checker will, so a file that cannot be
    # consumed fails here rather than in a gate run.
    _header, reloaded = read_sidecar(sidecar)
    validate_episode_attempts(reloaded, expected_attempts=len(records))
    for record in reloaded:
        snapshot_for(sidecar, record)
    return sidecar, len(reloaded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "artifacts" / "golden" / "visible")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be staged, and what cannot be, without running anything",
    )
    args = parser.parse_args()

    print(f"{len(WORLDS)} of 6 families can be staged as a single episode today.")
    for family, why in sorted(CANNOT_STAGE_YET.items()):
        print(f"  skipped  {family}: {why}")
    if args.dry_run:
        for world in WORLDS:
            print(f"  would plant  {world.case_id}  ({world.plants})")
        return 0

    reference = build_reference()
    for world in WORLDS:
        sidecar, attempts = plant(world, args.root, reference)
        try:
            shown = sidecar.relative_to(ROOT).as_posix()
        except ValueError:
            # A root outside the repository is a legitimate choice — a
            # scratch directory, another disk — and printing an absolute
            # path is a better answer than refusing to report the run
            # that just succeeded.
            shown = sidecar.as_posix()
        print(f"  planted  {world.case_id:16} {attempts} attempt(s)  {shown}")
    print(
        "\\nOFFICIAL_GOLDEN_READY stays False: a packet still has to be built from a "
        "run (E4.1), and four families are not staged. These are runs, not a suite."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SidecarViolation as error:  # pragma: no cover - surfaced to a person
        print(f"a planted run wrote a sidecar nothing can consume: {error}")
        raise SystemExit(1) from error
