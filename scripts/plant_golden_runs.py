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
    #: One episode per goal, in addition to the scenario's own. Three of
    #: the six families are about a **pattern across episodes** rather
    #: than about one run — an association between search size and
    #: latency, a difference that straddles zero — and a single episode
    #: cannot carry either. G6.
    episode_goals: tuple[tuple[float, float], ...] = ()
    #: Which stacks run this world. ``None`` means the pair every other
    #: world uses. The negative control needs two *tunings of one stack*
    #: instead, because a pair that differs in nothing is the only pair
    #: whose difference is honestly zero.
    stacks: tuple[str, ...] | None = None
    #: Whether the episodes are recorded at all. The insufficient-evidence
    #: family is precisely a run whose traces nobody kept, and faking that
    #: by deleting files afterwards would leave a fixture claiming a
    #: recording it never had.
    record_traces: bool = True


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


def expansion_latency() -> PlantedWorld:
    """Searches of very different sizes in one maze, timed as they ran.

    The association this family plants lives **across** episodes: one
    episode is one point, and a point has no slope. So the world is a
    40 x 20 m hall divided by eight walls whose doorways alternate top
    and bottom - a zigzag - and eight goals at increasing distance. The
    detour forces the grid search to open sixteen nodes for the nearest
    goal and roughly fifty thousand for the furthest, which is the range
    a rank correlation needs.

    Measured while tuning this world (A-star + DWA, one episode a goal):

    ==========  ==============  ================
    goal        expanded nodes  p99 tick latency
    ==========  ==============  ================
    2 m         16              5.0 ms
    10 m        16 145          9.6 ms
    14 m        19 273          14.6 ms
    22 m        33 578          35.0 ms
    30 m        47 726          17.4 ms
    ==========  ==============  ================

    The first draft of this world was a plain hall with wide doorways.
    It produced a clean set of episodes and searches of 16 to 246 nodes,
    which is nothing: latency stayed flat at 5 ms and the checker
    correctly answered ``refuted``. A fixture has to plant a mechanism
    big enough for the platform's own instrument to see, and that is a
    property of the world rather than of the wording.

    **The ceiling stays at ``associated``.** A longer episode runs more
    ticks and has more chances to draw a slow one, so part of the rise
    is the run being longer rather than the search being bigger, and
    this platform cannot separate the two - the standing unknown every
    packet declares. An analyst reaching for candidate latency
    attribution here has crossed exactly that gap.
    """
    robot = _robot(0.18)
    width, height = 400, 200
    walls = [40, 80, 120, 160, 200, 240, 280, 320]
    top_door = range(12, 30)
    bottom_door = range(height - 30, height - 12)

    def blocked(col: int, row: int) -> bool:
        if col not in walls:
            return False
        door = top_door if walls.index(col) % 2 == 0 else bottom_door
        return row not in door

    return PlantedWorld(
        case_id="latency-001",
        family="expansion_latency",
        map_data=_grid(width, height, 0.1, blocked),
        scenario=_scenario(
            robot,
            Point2D(x=0.5, y=2.0),
            Point2D(x=2.0, y=2.0),
            timeout_seconds=200.0,
        ),
        # Eight episodes, not four: the association checker refuses fewer
        # than eight, and it is right to - a slope through three points
        # is a shape, not a measurement.
        episode_goals=(
            (6.0, 2.0),
            (10.0, 2.0),
            (14.0, 2.0),
            (18.0, 2.0),
            (22.0, 2.0),
            (26.0, 2.0),
            (30.0, 2.0),
        ),
        global_planner_name="astar",
        plants="expansion_latency_association / global_planner",
        rationale=(
            "Eight goals down a zigzag corridor, each one wall further than the last. "
            "The grid search opens sixteen nodes for the nearest and about fifty "
            "thousand for the furthest, and the tick latency rises with it - an "
            "association, not a cause, because a longer episode also draws more ticks "
            "and the platform cannot split the planner's share of a tick from the "
            "deployment's."
        ),
    )


def negative_control() -> PlantedWorld:
    """Two tunings of one stack on an easy map: nothing to explain.

    The hardest case for an analyst is the one where the right answer is
    "there is nothing here". A pair that differs in a planner would give
    it something to say; a pair that differs in a controller's horizon
    by a tenth of a second, on a map with no obstacle worth the name,
    gives it a difference that is noise and a set of detections that is
    empty.
    """
    robot = _robot(0.18)
    width, height = 80, 60

    def blocked(col: int, row: int) -> bool:
        return col == 40 and row < 10

    return PlantedWorld(
        case_id="control-001",
        family="negative_control",
        map_data=_grid(width, height, 0.1, blocked),
        scenario=_scenario(
            robot,
            Point2D(x=0.6, y=4.0),
            Point2D(x=7.2, y=4.0),
            timeout_seconds=60.0,
        ),
        episode_goals=((7.0, 3.4), (7.4, 4.6)),
        stacks=("dwa_default", "dwa_patient"),
        global_planner_name="astar",
        plants="nothing - the answer is an abstention",
        rationale=(
            "One stack, two controller tunings, an open map and three missions. Neither "
            "side has a detection and the utility difference is a rounding error, so "
            "any mechanism proposed here was pattern-matched onto noise - which is the "
            "failure this whole layer exists to prevent."
        ),
    )


def insufficient_evidence() -> PlantedWorld:
    """A run whose per-episode traces nobody kept.

    Not a synthetic gap: the episodes are executed with **no recorder
    attached**, exactly as a run predating the trace layout was. The
    packet that comes out has candidates, a decision and the platform's
    declared unknowns, and no observations at all - and the correct
    answer is to say which evidence is missing rather than to reach for
    a mechanism the run cannot support.
    """
    robot = _robot(0.18)
    width, height = 70, 50

    def blocked(col: int, row: int) -> bool:
        return col == 35 and row < 20

    return PlantedWorld(
        case_id="gap-002",
        family="insufficient_evidence",
        map_data=_grid(width, height, 0.1, blocked),
        scenario=_scenario(
            robot,
            Point2D(x=0.6, y=3.5),
            Point2D(x=6.2, y=3.5),
            timeout_seconds=45.0,
        ),
        record_traces=False,
        global_planner_name="astar",
        plants="insufficient evidence - every mechanism check is unavailable",
        rationale=(
            "The stacks ran and nothing recorded them, so no detector saw anything and "
            "no replay is possible. A packet like this is common in practice - it is "
            "what every run before the trace address change looks like - and the only "
            "correct answer names the gap."
        ),
    )


#: Families this script cannot stage honestly yet, and why. Printed
#: rather than silently omitted: a suite missing two of its six families
#: is a suite whose macro average is over four, and a reader who is not
#: told will assume six.
CANNOT_STAGE_YET: dict[str, str] = {}

#: What the six staged worlds still do **not** cover: the second variant
#: of each family — the near-boundary and negative twins that separate
#: "this mechanism is here" from "this shape is here and the mechanism is
#: not". Six cases is six families and not twelve cases, and the
#: preregistration reports counts rather than a rate below twelve.
SECOND_VARIANTS_MISSING: tuple[str, ...] = (
    "inflation-002",
    "rrt-002",
    "dwa-002",
    "latency-002",
    "control-002",
    "gap-001",
)

WORLDS: tuple[PlantedWorld, ...] = (
    inflation_gap_closure(),
    rrt_sample_starvation(),
    dwa_local_minimum(),
    expansion_latency(),
    negative_control(),
    insufficient_evidence(),
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
