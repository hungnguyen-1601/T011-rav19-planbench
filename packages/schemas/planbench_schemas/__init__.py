"""Shared Pydantic domain schemas for PlanBench (contract-first core)."""

from planbench_schemas.episode import (
    EpisodeEvent,
    EpisodeResult,
    EpisodeStatus,
    Observation,
    TrajectoryPoint,
)
from planbench_schemas.geometry import (
    EPS,
    Point2D,
    Pose2D,
    distance_point_to_aabb,
    euclidean_distance,
    normalize_angle,
)
from planbench_schemas.map import CellState, MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.robot import RobotConfig, RobotState, SimAction
from planbench_schemas.scenario import (
    CircleObstacle,
    RectangleObstacle,
    Scenario,
    StaticObstacle,
)
from planbench_schemas.sensor import LidarConfig
from planbench_schemas.task_profile import (
    ClaimLevel,
    EnvironmentRef,
    HardwareSpec,
    Mission,
    TaskConstraints,
    TaskProfile,
    TaskRobotSpec,
)

__all__ = [
    "EPS",
    "NO_REPLANNING",
    "CellState",
    "CircleObstacle",
    "ClaimLevel",
    "EnvironmentRef",
    "EpisodeEvent",
    "EpisodeResult",
    "EpisodeStatus",
    "HardwareSpec",
    "LidarConfig",
    "MapData",
    "Mission",
    "Observation",
    "Point2D",
    "Pose2D",
    "RectangleObstacle",
    "ReplanningConfig",
    "RobotConfig",
    "RobotState",
    "Scenario",
    "SimAction",
    "StaticObstacle",
    "TaskConstraints",
    "TaskProfile",
    "TaskRobotSpec",
    "TrajectoryPoint",
    "distance_point_to_aabb",
    "euclidean_distance",
    "normalize_angle",
]
