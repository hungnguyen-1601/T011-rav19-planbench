"""Scenario schemas: static obstacles and the full episode scenario.

A ``Scenario`` bundles everything an episode needs besides the map:
robot limits, start/goal, obstacles, timing and termination thresholds.
Map-dependent validation (start/goal inside the map and collision-free)
happens in the simulation engine, which has the grid.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_schemas.dynamic import DynamicObstacle
from planbench_schemas.geometry import EPS, Point2D, Pose2D, euclidean_distance
from planbench_schemas.robot import RobotConfig
from planbench_schemas.sensor import LidarConfig


class CircleObstacle(BaseModel):
    """Static circular obstacle in world coordinates (metres)."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    type: Literal["circle"] = "circle"
    center: Point2D
    radius: float = Field(gt=0)


class RectangleObstacle(BaseModel):
    """Static axis-aligned rectangular obstacle in world coordinates."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    type: Literal["rectangle"] = "rectangle"
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @model_validator(mode="after")
    def _validate_extent(self) -> RectangleObstacle:
        if self.max_x <= self.min_x or self.max_y <= self.min_y:
            raise ValueError(
                "rectangle must have positive extent: "
                f"({self.min_x}, {self.min_y}) .. ({self.max_x}, {self.max_y})"
            )
        return self


StaticObstacle = Annotated[CircleObstacle | RectangleObstacle, Field(discriminator="type")]


class Scenario(BaseModel):
    """Complete episode configuration (map is referenced separately).

    Termination thresholds have explicit defaults here so no magic
    numbers live in engine logic:
    - stuck: displacement below ``stuck_min_displacement`` over the last
      ``stuck_time_window`` seconds;
    - failure to progress: goal distance shrinking by less than
      ``progress_min_decrease`` over ``progress_time_window`` seconds.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str
    description: str = ""
    robot: RobotConfig
    start_pose: Pose2D
    goal_pose: Pose2D
    goal_tolerance: float = Field(default=0.25, gt=0)
    timeout_seconds: float = Field(gt=0)
    simulation_dt: float = Field(default=0.05, gt=0)
    static_obstacles: tuple[StaticObstacle, ...] = ()
    dynamic_obstacles: tuple[DynamicObstacle, ...] = ()
    lidar: LidarConfig = Field(default_factory=lambda: LidarConfig(num_rays=72, max_range=5.0))
    random_seed: int = 0
    stuck_time_window: float = Field(default=5.0, gt=0)
    stuck_min_displacement: float = Field(default=0.05, gt=0)
    # Failure-to-progress uses straight-line goal distance, so a legitimate
    # detour that leads away from the goal for longer than this window is
    # reported as a failure. Scenarios with long detours must widen it
    # (see docs/KNOWN_LIMITATIONS.md).
    progress_time_window: float = Field(default=30.0, gt=0)
    progress_min_decrease: float = Field(default=0.05, gt=0)

    @model_validator(mode="after")
    def _validate(self) -> Scenario:
        if self.simulation_dt >= self.timeout_seconds:
            raise ValueError(
                f"simulation_dt ({self.simulation_dt}) must be smaller than "
                f"timeout_seconds ({self.timeout_seconds})"
            )
        if euclidean_distance(self.start_pose.position, self.goal_pose.position) <= EPS:
            raise ValueError("start_pose and goal_pose must differ")
        return self
