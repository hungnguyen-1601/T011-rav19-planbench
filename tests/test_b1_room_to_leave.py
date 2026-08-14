"""B1 — the planner's buffer is relaxed around the robot, never the walls.

**The defect this closes, measured rather than argued.** Two layers hold
a "forbidden zone" around the same obstacle and they are not the same
zone. The local controller rejects a trajectory at ``robot.radius +
safety_margin``, measured as continuous distance to obstacle geometry.
The global planner inflates by ``robot.radius + √2 × resolution``, on
cells. On the shipped `sudden_stop` those are **0.31 m** and **0.61 m**,
and the entire 0.30 m difference is the grid-quantisation term — a
property of the *map's resolution*, not of the world.

So the robot parked where its own test said it could and the planner's
said it could not. Freeing only the cell it stood in left it with **0 of
8** free neighbours: A* entered the start cell and could not take one
step, reporting "no path exists between start and goal" while a
point-robot flood fill of the same scene reached the goal easily. The
robot never moved, so all 55 replans of a 120-second episode met the
identical grid and returned the identical refusal.

**Why this is a harness defect and not a planner one.** Every candidate
hit it identically, so no comparison was skewed — but no candidate could
recover, which made *"can this stack get itself out?"* unanswerable for a
reason belonging to the evaluation rig. Same shape as the replan
information privilege (HĐ-4.1) and the `max_replans` cap: an evaluation
condition quietly deciding the result.

Full investigation:
``docs/antongduy/notes/2026-08-13/tongduyan_hai-vung-cam-mot-con-robot.md``
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import yaml

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.registry import build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.geometry import Point2D
from planbench_schemas.task_profile import TaskProfile
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.nav_stack import (
    _inflation_radius,
    _map_as_the_robot_sees_it,
    _planning_grid,
    _with_room_to_leave,
    run_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: What the deployment form writes. **The case only reproduces with all
#: seven**, which is exactly why it survived every test until somebody
#: ran the real thing: the shipped profile declares two, and two are not
#: enough to tip it.
FORM_NOISE = {
    "lidar_range_sigma_m": 0.02,
    "wheel_slip_fraction": 0.02,
    "localization_drift_m": 0.1,
    "localization_jump_probability": 0.02,
    "lidar_dropout_probability": 0.02,
    "odometry_bias_fraction": 0.01,
    "command_latency_steps": 2,
}

SHIPPED_NOISE = {"lidar_range_sigma_m": 0.02, "wheel_slip_fraction": 0.02}


def _scene(noise: dict, resolution: float | None = None):
    """`sudden_stop` as a deployment, the way the form builds one."""
    map_data, library = build_scenario("sudden_stop")
    if resolution is not None:
        map_data = map_data.model_copy(update={"resolution": resolution})
    raw = copy.deepcopy(
        yaml.safe_load((REPO_ROOT / "profiles" / "open_hall_v2.yaml").read_text(encoding="utf-8"))
    )
    raw["id"] = "b1_probe"
    raw["replanning"] = {"enabled": True}
    raw["missions"] = [
        {
            "id": "m",
            "start": [library.start_pose.x, library.start_pose.y, 0.0],
            "goal": [library.goal_pose.x, library.goal_pose.y, 0.0],
            "probability": 1.0,
        }
    ]
    raw["environment"]["dynamic_obstacles"] = [
        obstacle.model_dump(mode="json") for obstacle in library.dynamic_obstacles
    ]
    raw["environment"]["sensor_noise"] = noise
    profile = TaskProfile.model_validate(raw)
    scenario = scenario_for(
        profile, EpisodeContext(task_profile_id=profile.id, mission_id="m", seed=0)
    )
    return map_data, profile, scenario


def _engine_at_start(map_data, scenario) -> SimulationEngine:
    """An engine parked at the mission start, ready to be observed."""
    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()
    return engine


def _episode(noise: dict, resolution: float | None = None, config: str = "dwa_balanced"):
    map_data, profile, scenario = _scene(noise, resolution)
    return run_stack(
        map_data,
        scenario,
        build_local_planner("astar+dwa", dict(LOCAL_CONTROLLER_CONFIGS[config])),
        build_global_planner("astar+dwa", episode_seed=0),
        profile.replanning,
    )


class TestTheRobotCanLeaveWhereItStands:
    def test_the_scene_that_refused_55_times_refuses_none(self) -> None:
        """Asserted on the refusals, not on ``success``.

        Whether the robot then gets past the cart is a question about the
        candidate. This change is about the harness no longer answering
        that question on the candidate's behalf, so the claim stops where
        the change does.
        """
        run = _episode(FORM_NOISE)
        refused = [event for event in run.result.events if event.type == "replan_failed"]
        assert refused == [], f"{len(refused)} replans still found nothing"
        assert run.metrics.replan_count > 0, "nothing replanned, so nothing was shown"

    def test_the_case_that_already_worked_still_does(self) -> None:
        """A relaxation bought by breaking the working case is a bad trade."""
        assert _episode(SHIPPED_NOISE).result.status is EpisodeStatus.SUCCESS

    def test_it_holds_at_a_finer_resolution(self) -> None:
        """The whole gap came from a term proportional to cell size, so a
        fix that only worked at 0.25 m would be tuned to the one map that
        happened to show the bug."""
        run = _episode(FORM_NOISE, resolution=0.125)
        assert [e for e in run.result.events if e.type == "replan_failed"] == []


class TestItRelaxesTheBufferAndNothingElse:
    def test_no_cell_holding_a_real_return_is_ever_freed(self) -> None:
        """The one guard against "fixing" this by relaxing too far.

        A bubble that cleared occupied cells would hand back a path
        straight through the cart — a plan that looks like a recovery and
        is a collision the controller then has to refuse.
        """
        map_data, _, scenario = _scene(FORM_NOISE)
        engine = _engine_at_start(map_data, scenario)
        believed = _map_as_the_robot_sees_it(map_data, engine.get_observation(), scenario.lidar)
        inflated = _planning_grid(believed, scenario)
        solid = OccupancyGrid(rasterize_obstacles(believed, scenario.static_obstacles))
        relaxed = _with_room_to_leave(
            inflated,
            solid,
            Point2D(x=scenario.start_pose.x, y=scenario.start_pose.y),
            _inflation_radius(believed, scenario),
        )
        occupied = [index for index, cell in enumerate(solid.map_data.cells) if cell == 100]
        assert occupied, "the scene has no obstacles at all, so this proves nothing"
        for index in occupied:
            assert relaxed.map_data.cells[index] == 100, (
                "a cell holding a real return was freed; the bubble may only undo inflation"
            )

    def test_the_relaxation_is_local(self) -> None:
        """Beyond the bubble the map keeps its buffer.

        A global relaxation would be a different change wearing this
        one's name: every path in the episode would run closer to every
        wall, not just the one leaving the spot the robot is stuck in.
        """
        map_data, _, scenario = _scene(FORM_NOISE)
        engine = _engine_at_start(map_data, scenario)
        believed = _map_as_the_robot_sees_it(map_data, engine.get_observation(), scenario.lidar)
        inflated = _planning_grid(believed, scenario)
        solid = OccupancyGrid(rasterize_obstacles(believed, scenario.static_obstacles))
        position = Point2D(x=scenario.start_pose.x, y=scenario.start_pose.y)
        radius = _inflation_radius(believed, scenario)
        relaxed = _with_room_to_leave(inflated, solid, position, radius)

        centre = inflated.world_to_grid(position.x, position.y)
        assert centre is not None
        reach = math.ceil(radius / inflated.resolution)
        changed = [
            index
            for index, (before, after) in enumerate(
                zip(inflated.map_data.cells, relaxed.map_data.cells, strict=True)
            )
            if before != after
        ]
        for index in changed:
            row, col = divmod(index, inflated.width)
            assert abs(row - centre[0]) <= reach and abs(col - centre[1]) <= reach, (
                "a cell outside the bubble was changed"
            )

    def test_the_inflation_radius_has_exactly_one_definition(self) -> None:
        """Two copies of this number are how the two layers drifted apart.

        The relaxation, the planning grid and anything that later draws
        the ring have to quote the same expression, or the next version of
        this bug is a rounding difference nobody can see.
        """
        source = (
            REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "nav_stack.py"
        ).read_text(encoding="utf-8")
        assert source.count("math.sqrt(2.0) * map_data.resolution") == 1


class TestAReplanThatStillFindsNothingIsRecorded:
    """The failure path stays wired even though this scene no longer takes it.

    B1 removed the *harness* reason a replan came back empty; it did not
    make refusal impossible, and it must not. A genuinely enclosed robot
    still has nowhere to go, and that has to reach the screen — "it never
    tried" and "it tried and there was nothing" are opposite diagnoses.
    """

    def test_the_event_type_and_its_retry_behaviour_survive(self) -> None:
        source = (
            REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "nav_stack.py"
        ).read_text(encoding="utf-8")
        assert 'type="replan_failed"' in source
        # And a refusal still does not end the episode: the budget is the
        # timeout, not the first "no".
        assert "carrying on until the timeout" in source

    def test_the_count_still_counts_attempts(self) -> None:
        """Counting successes reported 3 for an episode that asked eleven
        times, hiding the eight refusals — the expensive half."""
        source = (
            REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "nav_stack.py"
        ).read_text(encoding="utf-8")
        assert "replan_count=replan_attempts," in source
        assert "replan_count=len(plans) - 1" not in source
