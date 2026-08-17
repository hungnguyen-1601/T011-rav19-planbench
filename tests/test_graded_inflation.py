"""Phase 2 — the buffer stops being a wall and becomes a price.

**What was wrong.** Binary inflation answers *"may the robot be here"*
with a number that is partly about the world and partly about the map
file. On the shipped `sudden_stop` the planner's ring was 0.61 m, of
which 0.35 m was ``√2 × resolution`` — cell geometry. A robot standing
where its own collision test said it could was 0.30 m inside that ring,
and all 55 replans of a 120-second episode reported "no path exists"
from a cell with 0 of 8 free neighbours.

**What replaces it.** Three quantities where there used to be one:

* ``_feasible_clearance`` — the hard set, in metres of world. What L1
  and L4 are stated in.
* ``_hard_radius`` — what the *grid* forbids: the above plus **half** a
  cell diagonal. That half is arithmetic, not caution: an OCCUPIED cell
  says the obstacle touches it and not where, so without it the grid
  would be an **optimistic** approximation of the hard set. Measured on
  the two-doorway room at 0.5 m cells with a 0.3 m robot, inflating by
  the clearance alone marks *not one extra cell*.
* ``_caution_ramp`` — the other half plus a robot's own taper, as
  **cost**. Passable, and priced.

So the robot in that spot has a way out, and the way out is merely
expensive. Nothing has to be un-forbidden for it to exist, which is what
makes the room-to-leave bubble unnecessary rather than smaller — and the
bubble is deleted in this phase rather than kept alongside.

**Why the bubble had to go rather than stay as a safety net.** It freed
everything the *inflation* had marked, handing back genuinely open
space, and open space is worth more to some planners than others.
Measured on `sudden_stop`: A* took a 0.59 m-clear corridor in 3
waypoints, RRT* cut the same gap to 0.13 m in 10, with turns of 170° and
187° that a forward-only robot cannot drive. What replaces it stops at
the hard set and leaves every freed cell at maximum traversal cost, so
the gap is expensive for whoever takes it.

**λ was chosen by measurement, and its effect is not monotone** — which
is why it had to be measured rather than picked:

===  ===================  ===============  ================
λ    two-doorway room     sudden_stop A*   sudden_stop RRT*
===  ===================  ===============  ================
2.0  timeout, 42 replans  success          success
4.0  **success, 1**       **success**      **success**
6.0  success, 1           success          timeout
===  ===================  ===============  ================

Below it the planner still shaves a blocked doorway the controller
cannot drive through; far above it the sampling planner wanders, because
a strong enough gradient makes almost every edge expensive and the tree
stops converging. A working value, not an optimum.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest
import yaml

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.registry import ALGORITHMS, build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_planning.astar import AStarPlanner
from planbench_planning.common.path_utils import segment_cost, simplify_path
from planbench_planning.rrtstar import RRTStarPlanner
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.feasibility import SafetyEnvelope, hard_clearance
from planbench_schemas.geometry import Point2D
from planbench_schemas.map import CellState
from planbench_schemas.task_profile import TaskProfile
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.nav_stack import (
    _caution_ramp,
    _feasible_clearance,
    _hard_radius,
    _planning_grid,
    run_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: What the deployment form writes. The original case only reproduces
#: with all seven; the shipped profile declares two, and two are not
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

STACKS = ("astar+dwa", "rrtstar+dwa")


def _scene(noise: dict, preference: float = 2.0, resolution: float | None = None):
    map_data, library = build_scenario("sudden_stop")
    if resolution is not None:
        map_data = map_data.model_copy(update={"resolution": resolution})
    raw = copy.deepcopy(
        yaml.safe_load((REPO_ROOT / "profiles" / "open_hall_v2.yaml").read_text(encoding="utf-8"))
    )
    raw["id"] = "graded_probe"
    raw["replanning"] = {"enabled": True}
    raw["clearance_preference"] = preference
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


#: Episodes here run to a 120-second timeout, so each combination is
#: simulated once and reused. Safe because a run is a pure function of
#: its inputs, and results are read rather than mutated.
_RUNS: dict[tuple, tuple] = {}


def _episode(stack: str, noise: dict, preference: float = 2.0, resolution: float | None = None):
    key = (stack, tuple(sorted(noise.items())), preference, resolution)
    if key not in _RUNS:
        map_data, profile, scenario = _scene(noise, preference, resolution)
        _RUNS[key] = (
            scenario,
            run_stack(
                map_data,
                scenario,
                build_local_planner(stack, dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])),
                build_global_planner(stack, episode_seed=0),
                profile.replanning,
            ),
        )
    return _RUNS[key]


def _refusals(run) -> list:
    return [event for event in run.result.events if event.type == "replan_failed"]


class TestOnlyTheHardSetForbids:
    """The prohibition carries nothing about the map file any more."""

    def test_the_feasible_set_is_the_shared_clearance(self) -> None:
        """Metres of world, no grid in it. This is what L1 and L4 are
        stated in and what a continuous validator asks for."""
        _, _, scenario = _scene(FORM_NOISE)
        envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
        assert _feasible_clearance(scenario) == pytest.approx(
            hard_clearance(scenario.robot, envelope)
        )

    def test_the_grid_adds_the_obstacle_side_slop_and_only_that(self) -> None:
        """Arithmetic rather than caution. An OCCUPIED cell says the
        obstacle touches it and not where, so without half a cell
        diagonal the grid would be an **optimistic** approximation of the
        hard set — the one thing it may never be.

        Measured: on the two-doorway room at 0.5 m cells with a 0.3 m
        robot, inflating by the clearance alone marks *not one extra
        cell*, because adjacent centres are 0.5 m apart.
        """
        map_data, _, scenario = _scene(FORM_NOISE)
        assert _hard_radius(map_data, scenario) == pytest.approx(
            _feasible_clearance(scenario) + math.sqrt(2.0) * map_data.resolution / 2.0
        )

    def test_the_robot_side_slop_is_in_the_ramp(self) -> None:
        """The other half. It did not vanish — forbidding it was wrong,
        ignoring it would be worse. A path point may sit half a diagonal
        from its cell's centre too, but a path is a continuous object and
        L4 checks it as one, so here it is priced rather than banned."""
        map_data, _, scenario = _scene(FORM_NOISE)
        assert _caution_ramp(map_data, scenario) == pytest.approx(
            math.sqrt(2.0) * map_data.resolution / 2.0 + _feasible_clearance(scenario)
        )

    def test_the_forbidden_area_actually_shrank(self) -> None:
        """The claim in cells rather than in metres, because cells are
        what a planner searches."""
        map_data, _, scenario = _scene(FORM_NOISE)
        graded = _planning_grid(map_data, scenario)
        binary = OccupancyGrid(map_data).inflate(
            _feasible_clearance(scenario) + math.sqrt(2.0) * map_data.resolution
        )
        blocked_now = sum(1 for cell in graded.map_data.cells if cell == CellState.OCCUPIED.value)
        blocked_before = sum(
            1 for cell in binary.map_data.cells if cell == CellState.OCCUPIED.value
        )
        assert blocked_now < blocked_before

    def test_the_hard_set_is_still_absolutely_forbidden(self) -> None:
        """Grading the buffer must not grade the boundary. Every cell
        within the hard clearance of a real obstacle stays blocked, and
        no multiplier anywhere lets a planner buy its way in."""
        import numpy as np
        from scipy import ndimage

        map_data, _, scenario = _scene(FORM_NOISE)
        graded = _planning_grid(map_data, scenario)
        hard = _feasible_clearance(scenario)
        shape = (map_data.height, map_data.width)
        occupied = (
            np.asarray(map_data.cells, dtype=np.int16).reshape(shape)
            == CellState.OCCUPIED.value
        )
        assert occupied.any(), "the map has no obstacles, so this proves nothing"
        distance = ndimage.distance_transform_edt(~occupied) * map_data.resolution
        passable = ~np.asarray(
            [
                [graded.is_blocked_cell(row, col) for col in range(graded.width)]
                for row in range(graded.height)
            ]
        )
        closest = float(distance[passable].min())
        assert closest > hard - 1e-9, (
            f"a passable cell sits {closest:.3f} m from an obstacle, inside the "
            f"hard clearance of {hard:.3f} m"
        )


class TestTheGradientIsAdviceAndNeverAPermit:
    def test_no_multiplier_is_ever_below_one(self) -> None:
        """Below one would make hugging an obstacle *cheaper* than open
        floor — the gradient pointing the wrong way, and a bug that would
        show up as suspiciously short paths rather than as a crash. The
        grid refuses to hold one, which is also what keeps A*'s Euclidean
        heuristic admissible."""
        map_data, _, scenario = _scene(FORM_NOISE)
        graded = _planning_grid(map_data, scenario)
        assert graded.is_graded
        values = [
            graded.traversal_at(row, col)
            for row in range(graded.height)
            for col in range(graded.width)
        ]
        assert min(values) == pytest.approx(1.0)
        assert max(values) == pytest.approx(1.0 + scenario.clearance_preference)

    def test_it_falls_off_with_distance(self) -> None:
        """Monotone, and zero beyond the ramp. A field that stayed costly
        everywhere would be a uniform tax rather than a gradient, and
        would change no decision."""
        map_data, _, scenario = _scene(FORM_NOISE)
        graded = _planning_grid(map_data, scenario)
        # A ray leaving the bottom wall, taken in the middle of the hall
        # so nothing else is near it.
        column = graded.width // 2
        ray = [
            graded.traversal_at(row, column)
            for row in range(graded.height // 2)
            if not graded.is_blocked_cell(row, column)
        ]
        assert len(ray) > 3, "not enough passable cells on this ray to show a slope"
        assert ray[0] > 1.0, "the cell right outside the boundary is not charged for"
        assert ray[-1] == pytest.approx(1.0), "the middle of an open hall is not free"
        assert all(
            later <= earlier + 1e-12 for earlier, later in zip(ray, ray[1:], strict=False)
        ), f"the cost is not monotone leaving the wall: {[round(v, 3) for v in ray]}"

    def test_switching_it_off_restores_pure_distance(self) -> None:
        """A deployment that wants the old behaviour gets it *exactly*,
        with no second code path existing to rot."""
        map_data, _, scenario = _scene(FORM_NOISE, preference=0.0)
        graded = _planning_grid(map_data, scenario)
        assert all(
            graded.traversal_at(row, col) == 1.0
            for row in range(graded.height)
            for col in range(graded.width)
        )

    def test_a_candidate_cannot_reach_it(self) -> None:
        """L2, again. The preference is folded into the grid before any
        planner is handed the map, so no planner needs a λ of its own and
        no candidate config can carry one."""
        for stack in STACKS:
            schema = ALGORITHMS[stack].info.config_schema
            assert "clearance_preference" not in str(schema), (
                f"{stack} exposes the deployment's clearance preference as a "
                "candidate knob, which lets one stack buy a shorter route"
            )


class TestBothPlannersActuallyReadIt:
    """The condition the plan flagged as *not yet met*.

    Before this phase, A*'s step cost was ``1 / √2`` and RRT*'s rewiring
    used ``euclidean_distance`` — pure distance in both. A cost field
    nobody reads is a cost field that does nothing, so this is the test
    that says the phase happened at all.
    """

    def _corridor(self, preference: float):
        """A hall with one obstacle mid-way, so hugging it is an option."""
        map_data, _, scenario = _scene(SHIPPED_NOISE, preference=preference)
        return _planning_grid(map_data, scenario), scenario

    @pytest.mark.parametrize("planner_name", ["astar", "rrtstar"])
    def test_the_path_keeps_further_away_when_the_price_goes_up(
        self, planner_name: str
    ) -> None:
        map_data, _, _ = _scene(SHIPPED_NOISE)
        start = Point2D(x=1.5, y=4.5)
        goal = Point2D(x=12.5, y=4.5)

        def closest(preference: float) -> float:
            grid, _ = self._corridor(preference)
            planner = (
                AStarPlanner() if planner_name == "astar" else RRTStarPlanner(episode_seed=0)
            )
            plan = planner.plan(grid, start, goal)
            assert plan.success, f"{planner_name} found nothing at λ={preference}"
            # The cheapest thing available to a distance-only planner is
            # to graze; what the field buys is distance from the walls.
            return min(
                _clearance_to_blocked(grid, point) for point in _sampled(plan.path, 0.1)
            )

        indifferent = closest(0.0)
        cautious = closest(6.0)
        assert cautious >= indifferent, (
            f"{planner_name} ignores the traversal layer: closest approach "
            f"{cautious:.3f} m at λ=6 against {indifferent:.3f} m at λ=0"
        )

    def test_the_recorded_cost_stops_being_the_length(self) -> None:
        """A planner reading the field must *say* so in what it reports,
        or the number on the report is a different quantity from the one
        that was optimised.

        Asserted on a route that has no choice but to run near a wall.
        Down the middle of an open hall the two numbers agree, and they
        *should* — the first version of this test used that route and
        was measuring nothing.
        """
        grid, _ = self._corridor(4.0)
        open_middle = AStarPlanner().plan(
            grid, Point2D(x=1.5, y=4.5), Point2D(x=12.5, y=4.5)
        )
        assert open_middle.success
        assert open_middle.cost == pytest.approx(open_middle.path_length, rel=1e-6), (
            "an unobstructed route across an open hall was charged extra"
        )

        hugging = _first_free_row_near(grid, wall_side="bottom")
        near_wall = AStarPlanner().plan(
            grid,
            Point2D(x=1.5, y=hugging),
            Point2D(x=12.5, y=hugging),
        )
        assert near_wall.success, "no route along the wall, so this proves nothing"
        assert near_wall.cost > near_wall.path_length

    def test_an_ungraded_grid_is_byte_identical_to_before(self) -> None:
        """The switch-off has to be exact, not approximate: every stored
        run was measured on a binary grid, and a rounding difference in
        ``cost`` would make them all unreproducible."""
        map_data, _, scenario = _scene(SHIPPED_NOISE, preference=0.0)
        grid = _planning_grid(map_data, scenario)
        start, goal = Point2D(x=1.5, y=4.5), Point2D(x=12.5, y=4.5)
        for planner in (AStarPlanner(), RRTStarPlanner(episode_seed=0)):
            plan = planner.plan(grid, start, goal)
            assert plan.success
            assert plan.cost == pytest.approx(plan.path_length, rel=1e-9)


class TestShortcuttingCannotUndoTheGradient:
    """The trap that would have made the whole phase a no-op.

    A* spends real search effort routing around an expensive band.
    ``simplify_path`` then pulls the result straight — and a shortcutter
    that only asked "is anything blocking me" would drag it back through
    the band and hand over a path hugging the obstacle. The caution
    deleted in post-processing, silently, on every plan.
    """

    def test_a_shortcut_that_costs_more_is_refused(self) -> None:
        map_data, _, scenario = _scene(SHIPPED_NOISE, preference=8.0)
        grid = _planning_grid(map_data, scenario)
        detour = [Point2D(x=4.0, y=2.0), Point2D(x=7.0, y=1.0), Point2D(x=10.0, y=2.0)]
        straight = segment_cost(grid, detour[0], detour[-1])
        around = segment_cost(grid, detour[0], detour[1]) + segment_cost(
            grid, detour[1], detour[2]
        )
        if straight <= around:
            pytest.skip("this geometry gives the shortcut no reason to be refused")
        assert simplify_path(grid, detour) == tuple(detour)

    def test_a_shortcut_that_costs_less_is_still_taken(self) -> None:
        """The other side of the same edge. A shortcutter that refused
        everything would leave A*'s cell-by-cell staircase in the path,
        which is a different way of being useless."""
        map_data, _, scenario = _scene(SHIPPED_NOISE, preference=2.0)
        grid = _planning_grid(map_data, scenario)
        zigzag = [
            Point2D(x=3.0, y=2.0),
            Point2D(x=4.0, y=2.05),
            Point2D(x=5.0, y=2.0),
            Point2D(x=6.0, y=2.05),
            Point2D(x=7.0, y=2.0),
        ]
        assert len(simplify_path(grid, zigzag)) < len(zigzag)

    def test_on_an_ungraded_grid_it_shortcuts_exactly_as_before(self) -> None:
        """With every multiplier at one, a straight line between two
        points is never longer than the path through them, so the cost
        test passes for free."""
        map_data, _, scenario = _scene(SHIPPED_NOISE, preference=0.0)
        grid = _planning_grid(map_data, scenario)
        zigzag = [
            Point2D(x=3.0, y=2.0),
            Point2D(x=4.0, y=2.05),
            Point2D(x=5.0, y=2.0),
        ]
        assert simplify_path(grid, zigzag) == (zigzag[0], zigzag[-1])


class TestTheBubbleIsGoneAndTheRobotStillLeaves:
    """The whole point of the phase, asserted on the original case."""

    def test_the_room_to_leave_bubble_no_longer_exists(self) -> None:
        """Keeping it alongside would keep a patch whose reason has gone
        — and that patch has a *measured* bias towards A*."""
        source = (
            REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "nav_stack.py"
        ).read_text(encoding="utf-8")
        assert "_with_room_to_leave" not in source
        assert "_with_standing_room" in source

    @pytest.mark.parametrize("stack", STACKS)
    def test_the_scene_that_refused_55_times_refuses_none(self, stack: str) -> None:
        """Asserted on the refusals, not on ``success``. Whether the robot
        then gets past the cart is a question about the candidate; this
        change is about the harness no longer answering it on the
        candidate's behalf."""
        _, run = _episode(stack, FORM_NOISE, preference=0.0)
        assert _refusals(run) == [], f"{stack}: {len(_refusals(run))} replans still found nothing"
        assert run.metrics.replan_count > 0, "nothing replanned, so nothing was shown"

    @pytest.mark.parametrize("stack", STACKS)
    def test_the_gradient_is_not_what_fixed_it(self, stack: str) -> None:
        """Two changes shipped together, and only one of them fixed the
        bug. Shrinking the prohibition did; the gradient is a separate
        improvement. Recording which is which stops the next person
        crediting the wrong one — and stops them switching the gradient
        off and being surprised."""
        _, run = _episode(stack, FORM_NOISE, preference=0.0)
        assert _refusals(run) == []

    def test_standing_room_is_one_cell_and_never_a_real_return(self) -> None:
        """The bubble freed a disc; this frees the cell the robot is
        demonstrably standing in. A cell holding a LiDAR return is never
        freed — that would hand back a route through the cart."""
        source = (
            REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "nav_stack.py"
        ).read_text(encoding="utf-8")
        body = source[source.index("def _with_standing_room") :]
        body = body[: body.index("\ndef ")]
        # It relaxes the grid's caution, never the hard set: a cell is
        # freed only when the physics-only grid calls it free.
        assert "legal[index] != CellState.OCCUPIED.value" in body
        # Except the robot's own cell, which is freed by demonstration.
        assert "cells[here] = CellState.FREE.value" in body


class TestTheConclusionSurvivesTheResolution:
    """The original bug came out of a quantity of the *grid*.

    So the fence has to catch exactly that: the same scene drawn at
    different cell sizes must reach the same conclusion. Not the same
    path — a finer grid legitimately finds a different route — the same
    *answer to the question being asked*.
    """

    @pytest.mark.parametrize("resolution", [0.125, 0.25])
    def test_no_replan_is_refused_at_any_resolution(self, resolution: float) -> None:
        _, run = _episode("astar+dwa", FORM_NOISE, preference=0.0, resolution=resolution)
        assert _refusals(run) == []

    @pytest.mark.parametrize("resolution", [0.125, 0.25, 0.5])
    def test_what_is_forbidden_does_not_move_with_the_cell_size(
        self, resolution: float
    ) -> None:
        """The hard radius is metres of physics, so it must be the same
        number at every resolution. The ramp is allowed to move — it
        contains a cell diagonal on purpose — and it must *shrink* as the
        grid gets finer, because a finer grid is less unsure."""
        map_data, _, scenario = _scene(FORM_NOISE, resolution=resolution)
        envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
        assert _feasible_clearance(scenario) == pytest.approx(
            hard_clearance(scenario.robot, envelope)
        )
        coarse_map, _, coarse = _scene(FORM_NOISE, resolution=resolution * 2)
        assert _caution_ramp(map_data, scenario) < _caution_ramp(coarse_map, coarse)
        # And the grid's own prohibition shrinks with the cells too, since
        # a finer grid is less unsure about where the obstacle is.
        assert _hard_radius(map_data, scenario) < _hard_radius(coarse_map, coarse)


def _first_free_row_near(grid: OccupancyGrid, wall_side: str) -> float:
    """World ``y`` of the closest passable row to a wall, in the middle.

    Found rather than written down: the hard radius depends on the
    deployment's declared noise, so a hard-coded ``y`` would silently
    become "the middle of the hall" the moment somebody changed a noise
    amplitude, and the test would pass while measuring nothing.
    """
    column = grid.width // 2
    rows = range(grid.height) if wall_side == "bottom" else reversed(range(grid.height))
    for row in rows:
        if not grid.is_blocked_cell(row, column):
            return grid.grid_to_world(row, column).y
    raise AssertionError("the whole column is blocked")


def _sampled(path, step: float):
    """Points along a polyline, no further apart than ``step``."""
    yield path[0]
    for start, end in zip(path, path[1:], strict=False):
        span = math.hypot(end.x - start.x, end.y - start.y)
        for index in range(1, max(1, math.ceil(span / step))):
            fraction = index * step / span
            yield Point2D(
                x=start.x + (end.x - start.x) * fraction,
                y=start.y + (end.y - start.y) * fraction,
            )
        yield end


def _clearance_to_blocked(grid: OccupancyGrid, point: Point2D) -> float:
    """Distance from a world point to the nearest blocked cell centre."""
    best = math.inf
    for row in range(grid.height):
        for col in range(grid.width):
            if not grid.is_blocked_cell(row, col):
                continue
            centre = grid.grid_to_world(row, col)
            best = min(best, math.hypot(point.x - centre.x, point.y - centre.y))
    return best
