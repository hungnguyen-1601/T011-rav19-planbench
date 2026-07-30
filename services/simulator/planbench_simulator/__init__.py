"""PlanBench 2D simulator core: pure Python, framework-free.

``episode_runner`` is intentionally not re-exported here (it imports
planning, which imports this package's modules); import it as
``planbench_simulator.episode_runner``.
"""

from planbench_simulator.collision import (
    clearance_to_circle,
    clearance_to_grid,
    clearance_to_obstacle,
    clearance_to_obstacles,
    clearance_to_rectangle,
    collides_with_grid,
    collides_with_obstacle,
)
from planbench_simulator.engine import EngineState, SimulationEngine
from planbench_simulator.grid import OccupancyGrid, rasterize_obstacles
from planbench_simulator.kinematics import clamp, step
from planbench_simulator.lidar import cast_ray, scan
from planbench_simulator.path_follower import PurePursuitConfig, PurePursuitFollower

__all__ = [
    "EngineState",
    "OccupancyGrid",
    "PurePursuitConfig",
    "PurePursuitFollower",
    "SimulationEngine",
    "cast_ray",
    "clamp",
    "clearance_to_circle",
    "clearance_to_grid",
    "clearance_to_obstacle",
    "clearance_to_obstacles",
    "clearance_to_rectangle",
    "collides_with_grid",
    "collides_with_obstacle",
    "rasterize_obstacles",
    "scan",
    "step",
]
