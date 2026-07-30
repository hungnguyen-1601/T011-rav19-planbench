"""Built-in scenario library: the standard PlanBench test environments.

Each builder returns ``(MapData, Scenario)`` fully specified — same
robot, same LiDAR, same dt — so scenarios differ only in geometry and
traffic. That is what makes cross-scenario comparison meaningful.

Difficulty ordering (also the PPO curriculum order, spec section 23):
``open_space`` → ``static_obstacles`` → ``wide_corridor`` →
``narrow_corridor`` → ``doorway`` → ``crossing_obstacle`` →
``sudden_stop`` → ``bidirectional_corridor`` → ``intersection`` →
``dynamic_warehouse``.
"""

from __future__ import annotations

from collections.abc import Callable

from planbench_schemas.dynamic import (
    DynamicObstacle,
    PeriodicMotion,
    RandomWalkMotion,
    SuddenStopMotion,
    WaypointMotion,
)
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_schemas.sensor import LidarConfig

RESOLUTION = 0.25
LIDAR = LidarConfig(num_rays=72, max_range=6.0)

STANDARD_ROBOT = RobotConfig(
    radius=0.3,
    max_linear_velocity=1.0,
    max_angular_velocity=2.0,
    max_linear_acceleration=1.0,
    max_angular_acceleration=3.0,
)


def _blank(name: str, width_m: float, height_m: float) -> list[int]:
    width = int(width_m / RESOLUTION)
    height = int(height_m / RESOLUTION)
    cells = [CellState.FREE.value] * (width * height)
    for col in range(width):
        cells[col] = CellState.OCCUPIED.value
        cells[(height - 1) * width + col] = CellState.OCCUPIED.value
    for row in range(height):
        cells[row * width] = CellState.OCCUPIED.value
        cells[row * width + width - 1] = CellState.OCCUPIED.value
    return cells


class _MapBuilder:
    """Paint walls in world metres; the grid stays an implementation detail."""

    def __init__(self, name: str, width_m: float, height_m: float) -> None:
        self.name = name
        self.width = int(width_m / RESOLUTION)
        self.height = int(height_m / RESOLUTION)
        self.cells = _blank(name, width_m, height_m)

    def wall(self, min_x: float, min_y: float, max_x: float, max_y: float) -> _MapBuilder:
        """Fill an axis-aligned rectangle (world metres) with OCCUPIED."""
        for row in range(int(min_y / RESOLUTION), int(max_y / RESOLUTION)):
            for col in range(int(min_x / RESOLUTION), int(max_x / RESOLUTION)):
                if 0 <= row < self.height and 0 <= col < self.width:
                    self.cells[row * self.width + col] = CellState.OCCUPIED.value
        return self

    def build(self) -> MapData:
        return MapData(
            name=self.name,
            width=self.width,
            height=self.height,
            resolution=RESOLUTION,
            origin=Pose2D(x=0.0, y=0.0, theta=0.0),
            cells=tuple(self.cells),
        )


def _scenario(
    name: str,
    description: str,
    start: tuple[float, float],
    goal: tuple[float, float],
    *,
    timeout: float = 120.0,
    dynamic: tuple[DynamicObstacle, ...] = (),
    progress_window: float = 30.0,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        robot=STANDARD_ROBOT,
        start_pose=Pose2D(x=start[0], y=start[1], theta=0.0),
        goal_pose=Pose2D(x=goal[0], y=goal[1], theta=0.0),
        goal_tolerance=0.3,
        timeout_seconds=timeout,
        simulation_dt=0.05,
        dynamic_obstacles=dynamic,
        lidar=LIDAR,
        progress_time_window=progress_window,
    )


def open_space() -> tuple[MapData, Scenario]:
    """Empty 12 x 9 m hall — the sanity baseline."""
    map_data = _MapBuilder("open-space", 12.0, 9.0).build()
    return map_data, _scenario(
        "open_space", "Empty hall, straight run to the goal.", (1.5, 4.5), (10.5, 4.5)
    )


def static_obstacles() -> tuple[MapData, Scenario]:
    """Scattered pillars: local planner must weave without a detour plan."""
    builder = _MapBuilder("static-obstacles", 12.0, 9.0)
    for x, y in ((4.0, 3.0), (6.0, 6.0), (8.0, 3.5)):
        builder.wall(x, y, x + 0.75, y + 0.75)
    return builder.build(), _scenario(
        "static_obstacles", "Pillar field between start and goal.", (1.5, 4.5), (10.5, 4.5)
    )


def wide_corridor() -> tuple[MapData, Scenario]:
    """3 m corridor — comfortable for a 0.6 m robot."""
    builder = _MapBuilder("wide-corridor", 14.0, 8.0)
    builder.wall(2.0, 0.0, 12.0, 2.5).wall(2.0, 5.5, 12.0, 8.0)
    return builder.build(), _scenario(
        "wide_corridor", "3 m wide straight corridor.", (1.0, 4.0), (13.0, 4.0)
    )


def narrow_corridor() -> tuple[MapData, Scenario]:
    """1.5 m corridor — clearance costs start to bite."""
    builder = _MapBuilder("narrow-corridor", 14.0, 8.0)
    builder.wall(2.0, 0.0, 12.0, 3.25).wall(2.0, 4.75, 12.0, 8.0)
    return builder.build(), _scenario(
        "narrow_corridor", "1.5 m wide corridor.", (1.0, 4.0), (13.0, 4.0)
    )


def doorway() -> tuple[MapData, Scenario]:
    """A 1.6 m gap in a wall: the precision-alignment test.

    The gap cannot go much below 1.4 m: A* plans on a grid inflated by
    ``robot.radius + sqrt(2) * resolution`` (0.65 m here), so a narrower
    doorway is closed on the planning grid even though the 0.6 m robot
    would physically fit. See docs/KNOWN_LIMITATIONS.md.
    """
    builder = _MapBuilder("doorway", 12.0, 9.0)
    builder.wall(5.5, 0.0, 6.5, 3.7).wall(5.5, 5.3, 6.5, 9.0)
    return builder.build(), _scenario(
        "doorway", "Single 1.6 m doorway in a dividing wall.", (2.0, 4.5), (10.0, 4.5)
    )


def crossing_obstacle() -> tuple[MapData, Scenario]:
    """A pedestrian crossing the lane, back and forth."""
    map_data = _MapBuilder("crossing", 14.0, 9.0).build()
    walker = DynamicObstacle(
        name="pedestrian",
        radius=0.35,
        motion=PeriodicMotion(start=Point2D(x=7.0, y=1.5), end=Point2D(x=7.0, y=7.5), period=10.0),
    )
    return map_data, _scenario(
        "crossing_obstacle",
        "A pedestrian crosses the robot's lane periodically.",
        (1.5, 4.5),
        (12.5, 4.5),
        dynamic=(walker,),
    )


def sudden_stop() -> tuple[MapData, Scenario]:
    """A cart drives into the lane and brakes: emergency-avoid test."""
    map_data = _MapBuilder("sudden-stop", 14.0, 9.0).build()
    cart = DynamicObstacle(
        name="cart",
        radius=0.4,
        motion=SuddenStopMotion(
            start=Point2D(x=7.0, y=8.0), heading=-1.5707963267948966, speed=1.0, stop_time=3.5
        ),
    )
    return map_data, _scenario(
        "sudden_stop",
        "A cart enters the lane and stops dead in front of the robot.",
        (1.5, 4.5),
        (12.5, 4.5),
        dynamic=(cart,),
    )


def bidirectional_corridor() -> tuple[MapData, Scenario]:
    """Oncoming traffic in a 2 m corridor — someone must yield."""
    builder = _MapBuilder("bidirectional-corridor", 16.0, 8.0)
    builder.wall(2.0, 0.0, 14.0, 3.0).wall(2.0, 5.0, 14.0, 8.0)
    oncoming = DynamicObstacle(
        name="oncoming-amr",
        radius=0.35,
        motion=WaypointMotion(
            waypoints=(Point2D(x=13.0, y=4.0), Point2D(x=3.0, y=4.0)),
            speed=0.6,
            loop=True,
        ),
    )
    return builder.build(), _scenario(
        "bidirectional_corridor",
        "Another AMR drives head-on down the same 2 m corridor.",
        (1.0, 4.0),
        (15.0, 4.0),
        dynamic=(oncoming,),
        timeout=150.0,
    )


def intersection() -> tuple[MapData, Scenario]:
    """Cross-shaped junction with traffic on the perpendicular arm."""
    builder = _MapBuilder("intersection", 14.0, 14.0)
    for x0, y0, x1, y1 in (
        (0.0, 0.0, 5.5, 5.5),
        (8.5, 0.0, 14.0, 5.5),
        (0.0, 8.5, 5.5, 14.0),
        (8.5, 8.5, 14.0, 14.0),
    ):
        builder.wall(x0, y0, x1, y1)
    crosser = DynamicObstacle(
        name="crossing-amr",
        radius=0.35,
        motion=WaypointMotion(
            waypoints=(Point2D(x=7.0, y=1.0), Point2D(x=7.0, y=13.0)),
            speed=0.8,
            ping_pong=True,
        ),
    )
    return builder.build(), _scenario(
        "intersection",
        "Four-way junction with an AMR crossing the robot's path.",
        (1.0, 7.0),
        (13.0, 7.0),
        dynamic=(crosser,),
        timeout=150.0,
    )


def dynamic_warehouse() -> tuple[MapData, Scenario]:
    """Shelf aisles plus mixed traffic — the hardest standard scenario."""
    builder = _MapBuilder("dynamic-warehouse", 18.0, 12.0)
    for y in (3.0, 7.5):
        builder.wall(3.0, y, 8.0, y + 1.0).wall(10.0, y, 15.0, y + 1.0)
    obstacles = (
        DynamicObstacle(
            name="picker-1",
            radius=0.35,
            motion=PeriodicMotion(
                start=Point2D(x=9.0, y=2.0), end=Point2D(x=9.0, y=10.0), period=14.0
            ),
        ),
        DynamicObstacle(
            name="cart-1",
            radius=0.4,
            motion=WaypointMotion(
                waypoints=(
                    Point2D(x=4.0, y=6.0),
                    Point2D(x=14.0, y=6.0),
                ),
                speed=0.7,
                ping_pong=True,
            ),
        ),
        DynamicObstacle(
            name="wanderer",
            radius=0.3,
            motion=RandomWalkMotion(
                origin=Point2D(x=12.0, y=2.0),
                speed=0.5,
                change_interval=1.5,
                max_radius=1.5,
                seed_offset=17,
            ),
        ),
    )
    return builder.build(), _scenario(
        "dynamic_warehouse",
        "Shelf aisles with a picker, a cart and a wandering obstacle.",
        (1.5, 6.0),
        (16.5, 6.0),
        dynamic=obstacles,
        timeout=180.0,
        progress_window=60.0,
    )


# Ordered easiest -> hardest; also the PPO curriculum order.
SCENARIO_LIBRARY: dict[str, Callable[[], tuple[MapData, Scenario]]] = {
    "open_space": open_space,
    "static_obstacles": static_obstacles,
    "wide_corridor": wide_corridor,
    "narrow_corridor": narrow_corridor,
    "doorway": doorway,
    "crossing_obstacle": crossing_obstacle,
    "sudden_stop": sudden_stop,
    "bidirectional_corridor": bidirectional_corridor,
    "intersection": intersection,
    "dynamic_warehouse": dynamic_warehouse,
}

CURRICULUM_ORDER: tuple[str, ...] = tuple(SCENARIO_LIBRARY)


def build_scenario(name: str) -> tuple[MapData, Scenario]:
    """Build a library scenario by name."""
    try:
        builder = SCENARIO_LIBRARY[name]
    except KeyError:
        raise ValueError(
            f"unknown scenario {name!r}; available: {sorted(SCENARIO_LIBRARY)}"
        ) from None
    return builder()
