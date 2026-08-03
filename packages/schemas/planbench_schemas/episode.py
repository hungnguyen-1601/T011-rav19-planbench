"""Episode schemas: status, trajectory, events, observations, results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from planbench_schemas.geometry import Pose2D


class EpisodeStatus(StrEnum):
    """Terminal (or in-flight) status of one simulation episode."""

    RUNNING = "running"
    SUCCESS = "success"
    COLLISION = "collision"
    TIMEOUT = "timeout"
    STUCK = "stuck"
    NO_PROGRESS = "no_progress"
    STOPPED = "stopped"
    NO_GLOBAL_PATH = "no_global_path"


class ObstacleSnapshot(BaseModel):
    """Ground-truth pose of one dynamic obstacle at a trajectory sample.

    Recorded for replay and failure analysis — never given to a planner,
    which must infer moving obstacles from its LiDAR scan.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str
    x: float
    y: float
    radius: float


class TrajectoryPoint(BaseModel):
    """One sample of the robot state along an episode."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    time: float
    x: float
    y: float
    theta: float
    linear_velocity: float
    angular_velocity: float
    obstacles: tuple[ObstacleSnapshot, ...] = ()


class EpisodeEvent(BaseModel):
    """Discrete event recorded during an episode (termination, collision...)."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    time: float
    type: str
    message: str = ""


class Observation(BaseModel):
    """What a local planner may see at one step (no ground-truth map)."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    time: float
    pose: Pose2D
    linear_velocity: float
    angular_velocity: float
    goal_distance: float
    goal_bearing: float
    lidar_ranges: tuple[float, ...]


class EpisodeResult(BaseModel):
    """Final outcome of one episode, with full trajectory and events."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    status: EpisodeStatus
    reason: str = ""
    elapsed_time: float
    steps: int
    trajectory: tuple[TrajectoryPoint, ...]
    events: tuple[EpisodeEvent, ...]
