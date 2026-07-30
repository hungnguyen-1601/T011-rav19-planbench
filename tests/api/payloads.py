"""JSON payload builders shared by API tests."""

from __future__ import annotations

from planbench_schemas.geometry import Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario


def bordered_map_payload(width: int = 12, height: int = 12, name: str = "api-test-map") -> dict:
    free, occupied = CellState.FREE.value, CellState.OCCUPIED.value
    cells = [free] * (width * height)
    for col in range(width):
        cells[col] = occupied
        cells[(height - 1) * width + col] = occupied
    for row in range(height):
        cells[row * width] = occupied
        cells[row * width + width - 1] = occupied
    map_data = MapData(
        name=name,
        width=width,
        height=height,
        resolution=1.0,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )
    return map_data.model_dump(mode="json")


def scenario_payload(name: str = "api-test-scenario", **overrides) -> dict:
    defaults: dict = {
        "name": name,
        "robot": RobotConfig(
            radius=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=2.0,
            max_linear_acceleration=1.0,
            max_angular_acceleration=3.0,
        ),
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=9.5, y=9.5, theta=0.0),
        "goal_tolerance": 0.3,
        "timeout_seconds": 120.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults).model_dump(mode="json")
