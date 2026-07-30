"""Navigation stacks: A* global planner + a local planner (controller).

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
from planbench_planning import AStarConfig, AStarPlanner, PlanResult
from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_schemas.episode import EpisodeEvent, EpisodeResult, EpisodeStatus
from planbench_schemas.geometry import EPS, Point2D
from planbench_schemas.map import MapData
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_schemas.scenario import Scenario
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


def plan_global_path(
    map_data: MapData, scenario: Scenario, astar_config: AStarConfig | None = None
) -> tuple[PlanResult, OccupancyGrid]:
    """Run A* on the inflated planning grid; also return the raw grid."""
    planning_map = rasterize_obstacles(map_data, scenario.static_obstacles)
    inflation_radius = scenario.robot.radius + math.sqrt(2.0) * map_data.resolution
    planning_grid = OccupancyGrid(planning_map).inflate(inflation_radius)
    plan = AStarPlanner(astar_config).plan(
        planning_grid, scenario.start_pose.position, scenario.goal_pose.position
    )
    return plan, OccupancyGrid(map_data)


def run_stack(
    map_data: MapData,
    scenario: Scenario,
    local_planner: LocalPlanner,
    astar_config: AStarConfig | None = None,
) -> StackRun:
    """Run one episode of ``astar+<local_planner>`` on a scenario.

    Deterministic for identical inputs (given a deterministic local
    planner). Local-planner failures are recorded as episode events, not
    swallowed.
    """
    algorithm = f"astar+{local_planner.name}"
    plan, raw_grid = plan_global_path(map_data, scenario, astar_config)

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
        )
        return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)

    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()
    local_planner.reset(plan.path, scenario.robot)

    latencies: list[float] = []
    failures: list[EpisodeEvent] = []
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

    result = engine.get_result()
    if failures:
        result = result.model_copy(update={"events": tuple(failures) + result.events})
    metrics = compute_episode_metrics(
        result,
        planned_path_length=plan.path_length,
        global_planning_time=plan.planning_time_seconds,
        expanded_nodes=plan.expanded_nodes,
        grid=raw_grid,
        obstacles=scenario.static_obstacles,
        robot_radius=scenario.robot.radius,
        local_planner_latencies=latencies,
    )
    return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)
