"""Wire A* + pure-pursuit + engine into one headless episode.

Planning-safety margin: the planning grid is inflated by
``robot.radius + sqrt(2) * resolution``. With the centre-to-centre
inflation criterion, any point inside a cell left free is then at least
``radius`` away from every occupied cell box (triangle inequality: the
point is within half a cell diagonal of its centre, and the box within
half a diagonal of its own centre), so line-of-sight-sampled paths
cannot graze obstacle corners. The engine still checks collisions with
the exact robot radius.

Not exported from the package ``__init__`` to keep the
simulator↔planning import graph acyclic at package-init time — import
as ``planbench_simulator.episode_runner`` explicitly.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from planbench_metrics import EpisodeMetrics, compute_episode_metrics
from planbench_planning import AStarConfig, AStarPlanner, PlanResult
from planbench_schemas.episode import EpisodeEvent, EpisodeResult, EpisodeStatus
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.path_follower import PurePursuitConfig, PurePursuitFollower


class EpisodeRun(BaseModel):
    """Bundle of everything one headless episode produced."""

    model_config = ConfigDict(frozen=True)

    plan: PlanResult
    result: EpisodeResult
    metrics: EpisodeMetrics


def run_episode(
    map_data: MapData,
    scenario: Scenario,
    astar_config: AStarConfig | None = None,
    follower_config: PurePursuitConfig | None = None,
) -> EpisodeRun:
    """Plan with A* on the inflated grid, then follow with pure pursuit.

    Deterministic for identical inputs. Planning happens on a copy of
    the map with shape obstacles rasterized and inflated by the robot
    radius; the engine itself uses exact geometry for collisions.
    """
    planning_map = rasterize_obstacles(map_data, scenario.static_obstacles)
    inflation_radius = scenario.robot.radius + math.sqrt(2.0) * map_data.resolution
    planning_grid = OccupancyGrid(planning_map).inflate(inflation_radius)
    plan = AStarPlanner(astar_config).plan(
        planning_grid, scenario.start_pose.position, scenario.goal_pose.position
    )

    raw_grid = OccupancyGrid(map_data)
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
        return EpisodeRun(plan=plan, result=result, metrics=metrics)

    engine = SimulationEngine()
    engine.load_map(map_data)
    engine.load_scenario(scenario)
    engine.reset()
    follower = PurePursuitFollower(plan.path, scenario.robot, follower_config)
    while not engine.is_done():
        engine.step(follower.compute_action(engine.get_state()))

    result = engine.get_result()
    metrics = compute_episode_metrics(
        result,
        planned_path_length=plan.path_length,
        global_planning_time=plan.planning_time_seconds,
        expanded_nodes=plan.expanded_nodes,
        grid=raw_grid,
        obstacles=scenario.static_obstacles,
        robot_radius=scenario.robot.radius,
    )
    return EpisodeRun(plan=plan, result=result, metrics=metrics)
