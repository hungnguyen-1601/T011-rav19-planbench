"""The one premise every replanning test is built on, in one place.

A room split by a wall with two doorways. The short way through is the
lower one; a cart parks in it before the robot arrives. Nothing about the
map changes — the only remaining route to the goal is the upper doorway,
and only a planner that is told where the cart is can find it.

Shared rather than duplicated because two suites need it and they need
the *same* one: ``tests/test_replanning.py`` proves the engine replans,
``tests/api/test_api_simulations.py`` proves the ``/simulate`` path
reaches that engine. If those two drifted apart, the API test could pass
against a scenario nothing was ever blocked in, and the wiring it exists
to check would be untested while looking checked.
"""

from __future__ import annotations

import math

from planbench_schemas.dynamic import DynamicObstacle, SuddenStopMotion
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario

RESOLUTION = 0.5
WIDTH, HEIGHT = 40, 28
WALL_COL = 20
LOWER_DOORWAY = range(4, 11)
UPPER_DOORWAY = range(17, 24)


def blocked_robot() -> RobotConfig:
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )


def two_doorway_map() -> MapData:
    cells = [CellState.FREE.value] * (WIDTH * HEIGHT)

    def occupy(row: int, col: int) -> None:
        cells[row * WIDTH + col] = CellState.OCCUPIED.value

    for col in range(WIDTH):
        occupy(0, col)
        occupy(HEIGHT - 1, col)
    for row in range(HEIGHT):
        occupy(row, 0)
        occupy(row, WIDTH - 1)
    for row in range(1, HEIGHT - 1):
        if row not in LOWER_DOORWAY and row not in UPPER_DOORWAY:
            occupy(row, WALL_COL)
    return MapData(
        name="two-doorway-room",
        width=WIDTH,
        height=HEIGHT,
        resolution=RESOLUTION,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )


def blocked_scenario(robot: RobotConfig | None = None) -> Scenario:
    """Lower doorway blocked by a cart that parks before the robot arrives.

    The cart starts clear of both the start and the goal (the engine
    rejects a scenario whose robot begins inside an obstacle) and rolls
    into the doorway, stopping there for good at t = 5 s. The robot needs
    about eight seconds to cross the room, so it always meets a parked
    cart rather than a moving one: the episode tests recovery from a
    blocked route, not luck with timing.
    """
    return Scenario(
        name="doorway-blocked",
        robot=robot or blocked_robot(),
        start_pose=Pose2D(x=2.0, y=3.5, theta=0.0),
        goal_pose=Pose2D(x=18.0, y=3.5, theta=0.0),
        goal_tolerance=0.4,
        timeout_seconds=240.0,
        simulation_dt=0.05,
        dynamic_obstacles=(
            DynamicObstacle(
                name="parked-cart",
                radius=1.8,
                motion=SuddenStopMotion(
                    start=Point2D(x=10.25, y=6.0),
                    heading=-math.pi / 2,
                    speed=0.5,
                    stop_time=5.0,
                ),
            ),
        ),
    )
