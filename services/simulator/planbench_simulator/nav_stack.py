"""Navigation stacks: a global planner + a local planner (controller).

A benchmark always compares *stacks* — ``astar+dwa`` versus
``astar+ppo`` versus Nav2 — never a global planner against a local one
(decision D13).

Planning-safety margin: the planning grid is inflated by
``robot.radius + sqrt(2) * resolution`` so a line-of-sight-sampled path
cannot graze obstacle corners (see the proof in the docstring of
``episode_runner``). The engine still checks collisions with the exact
robot radius.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_metrics import EpisodeMetrics, compute_episode_metrics
from planbench_planning import AStarPlanner, GlobalPlanner, PlanResult
from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import EpisodeEvent, EpisodeResult, EpisodeStatus
from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_schemas.scenario import CircleObstacle, Scenario
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.path_follower import PurePursuitConfig, PurePursuitFollower


class PurePursuitLocalPlanner(LocalPlanner):
    """LocalPlanner adapter around the pure-pursuit follower.

    TEMPORARY reference controller (decision D12) — it ignores sensing
    and therefore must never appear in algorithm comparisons.
    """

    def __init__(self, config: PurePursuitConfig | None = None) -> None:
        self._config = config
        self._follower: PurePursuitFollower | None = None

    @property
    def name(self) -> str:
        return "pure_pursuit"

    def reset(self, global_path: Sequence[Point2D], robot: RobotConfig) -> None:
        self._follower = PurePursuitFollower(global_path, robot, self._config)

    def compute(self, state: RobotState, observation) -> LocalPlanResult:  # noqa: ANN001
        if self._follower is None:
            raise RuntimeError("reset() must be called before compute()")
        return LocalPlanResult(action=self._follower.compute_action(state))


class StackRun(BaseModel):
    """Everything one stack episode produced."""

    model_config = ConfigDict(frozen=True)

    algorithm: str
    plan: PlanResult
    result: EpisodeResult
    metrics: EpisodeMetrics


def _planning_grid(
    map_data: MapData,
    scenario: Scenario,
    extra_obstacles: Sequence[CircleObstacle] = (),
) -> OccupancyGrid:
    """Inflated grid the global planner plans on.

    ``extra_obstacles`` are burned in alongside the static ones. Empty
    for the initial plan — a global planner reasons about the map, not
    about where a pedestrian happened to be at t=0 — and populated on a
    replan, where the whole point is that something is in the way.
    """
    planning_map = rasterize_obstacles(map_data, scenario.static_obstacles)
    if extra_obstacles:
        planning_map = rasterize_obstacles(planning_map, extra_obstacles)
    inflation_radius = scenario.robot.radius + math.sqrt(2.0) * map_data.resolution
    return OccupancyGrid(planning_map).inflate(inflation_radius)


def plan_global_path(
    map_data: MapData, scenario: Scenario, global_planner: GlobalPlanner | None = None
) -> tuple[PlanResult, OccupancyGrid]:
    """Run the global planner on the inflated grid; also return the raw grid.

    Defaults to A* so callers that do not care which global planner runs
    (the RL environment, most tests) keep the historical behaviour.
    """
    planner = global_planner or AStarPlanner()
    plan = planner.plan(
        _planning_grid(map_data, scenario),
        scenario.start_pose.position,
        scenario.goal_pose.position,
    )
    return plan, OccupancyGrid(map_data)


def _with_free_start_cell(grid: OccupancyGrid, position: Point2D) -> OccupancyGrid:
    """Mark the single cell the robot occupies as free, if it is not.

    A robot that has just been blocked is standing close to the thing
    blocking it — closer than the inflation margin, which is a planning
    safety buffer rather than geometry. So its own cell is very often
    occupied on the inflated grid, and a global planner asked to start
    from an occupied cell reports "no path" and the replan never
    happens. That would make the feature fail exactly in the situation
    it exists for.

    Freeing one cell is safe to assert, not merely convenient: the
    engine terminates an episode the instant the robot overlaps an
    obstacle, so a robot that is still driving is provably not in one.
    Only the cell containing the robot is touched. Its neighbours keep
    their inflation, so the path that comes back still has to leave via
    genuinely clear space.
    """
    cell = grid.world_to_grid(position.x, position.y)
    if cell is None:
        return grid
    row, col = cell
    index = row * grid.width + col
    cells = grid.map_data.cells
    if cells[index] == CellState.FREE.value:
        return grid
    patched = list(cells)
    patched[index] = CellState.FREE.value
    return OccupancyGrid(
        grid.map_data.model_copy(update={"cells": tuple(patched)}),
        grid.unknown_as_occupied,
    )


def _replan(
    map_data: MapData,
    scenario: Scenario,
    global_planner: GlobalPlanner,
    engine: SimulationEngine,
) -> PlanResult:
    """Plan again from where the robot is, around where the obstacles are.

    Both halves matter. Replanning from the original start would hand
    back a path the robot has already half-driven; replanning on the
    static-only grid would hand back the identical path, because none of
    the planner's inputs would have changed since it was blocked.
    """
    position = engine.get_state().pose.position
    grid = _planning_grid(map_data, scenario, engine.dynamic_obstacles_now())
    return global_planner.plan(
        _with_free_start_cell(grid, position),
        position,
        scenario.goal_pose.position,
    )


#: Engine verdicts a replan is allowed to overturn. Both mean "the path
#: this robot is following has stopped working", which is the one thing
#: a new path can fix. A collision or a timeout is not on the list.
_REPLANNABLE = (EpisodeStatus.STUCK, EpisodeStatus.NO_PROGRESS)


def run_stack(
    map_data: MapData,
    scenario: Scenario,
    local_planner: LocalPlanner,
    global_planner: GlobalPlanner | None = None,
    replanning: ReplanningConfig | None = None,
) -> StackRun:
    """Run one episode of ``<global_planner>+<local_planner>`` on a scenario.

    Deterministic for identical inputs (given deterministic planners; a
    sampling planner counts as deterministic once its seed is fixed —
    see ``RRTStarPlanner``). Local-planner failures are recorded as
    episode events, not swallowed.

    ``replanning`` is a property of the evaluation conditions, not of the
    stack: it is applied here, on the path every stack goes through, with
    one trigger and one budget for all of them. It defaults to disabled,
    and a disabled run is byte-identical to the behaviour before
    replanning existed.
    """
    global_planner = global_planner or AStarPlanner()
    replanning = replanning or NO_REPLANNING
    algorithm = f"{global_planner.name}+{local_planner.name}"
    plan, raw_grid = plan_global_path(map_data, scenario, global_planner)

    if not plan.success:
        result = EpisodeResult(
            status=EpisodeStatus.NO_GLOBAL_PATH,
            reason=plan.failure_reason,
            elapsed_time=0.0,
            steps=0,
            trajectory=(),
            events=(EpisodeEvent(time=0.0, type="no_global_path", message=plan.failure_reason),),
        )
        metrics = compute_episode_metrics(
            result,
            global_planning_time=plan.planning_time_seconds,
            expanded_nodes=plan.expanded_nodes,
            grid=raw_grid,
            obstacles=scenario.static_obstacles,
            robot_radius=scenario.robot.radius,
            replan_count=0,
        )
        return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)

    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()
    local_planner.reset(plan.path, scenario.robot)

    latencies: list[float] = []
    failures: list[EpisodeEvent] = []
    # Every plan this episode used, initial one first. Planning cost is
    # reported as the total the stack spent, so a stack that recovers by
    # replanning three times is not shown as cheap as one that planned
    # once; the path metrics use the last entry, which is the path the
    # robot was actually following when the episode ended.
    plans: list[PlanResult] = [plan]
    # Controllers run at their own rate; the last command is held between
    # control ticks, exactly as a real /cmd_vel stream behaves.
    control_period = local_planner.control_period
    held_action = None
    next_control_time = 0.0
    while not engine.is_done():
        if held_action is None or control_period is None or engine.time >= next_control_time - EPS:
            decision = local_planner.compute(engine.get_state(), engine.get_observation())
            latencies.append(decision.latency_seconds)
            if decision.failure_reason:
                failures.append(
                    EpisodeEvent(
                        time=engine.time,
                        type="local_planner_failure",
                        message=decision.failure_reason,
                    )
                )
            held_action = decision.action
            if control_period is not None:
                next_control_time = engine.time + control_period
        engine.step(held_action)

        if (
            engine.is_done()
            and replanning.enabled
            and len(plans) <= replanning.max_replans
            and engine.episode_status in _REPLANNABLE
        ):
            blocked_as = engine.episode_status.value
            new_plan = _replan(map_data, scenario, global_planner, engine)
            if new_plan.success:
                plans.append(new_plan)
                local_planner.reset(new_plan.path, scenario.robot)
                engine.resume_after_replan(
                    f"replan {len(plans) - 1}/{replanning.max_replans} after {blocked_as}: "
                    f"new path of {len(new_plan.path)} waypoints, "
                    f"{new_plan.path_length:.2f} m"
                )
                # Force a control decision on the next iteration: the
                # held command was computed for the path that just failed.
                held_action = None

    result = engine.get_result()
    if failures:
        result = result.model_copy(update={"events": tuple(failures) + result.events})
    final_plan = plans[-1]
    metrics = compute_episode_metrics(
        result,
        planned_path_length=final_plan.path_length,
        global_planning_time=sum(entry.planning_time_seconds for entry in plans),
        expanded_nodes=sum(entry.expanded_nodes for entry in plans),
        grid=raw_grid,
        obstacles=scenario.static_obstacles,
        robot_radius=scenario.robot.radius,
        local_planner_latencies=latencies,
        replan_count=len(plans) - 1,
    )
    return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)
