"""Local planner (controller) interface.

A local planner turns the robot state plus a global path and local
sensing into a velocity command for the next step. DWA and PPO both
implement this; a benchmark compares *stacks* (A* + local planner),
never a global planner against a local one (decision D13).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig, RobotState, SimAction


class LocalPlanResult(BaseModel):
    """One control decision plus the debug data benchmarks record."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    action: SimAction
    predicted_trajectory: tuple[Point2D, ...] = ()
    cost_components: dict[str, float] = {}
    latency_seconds: float = 0.0
    failure_reason: str = ""


class LocalPlanner(ABC):
    """Deterministic controller: identical inputs give identical commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Algorithm identifier used in benchmark records."""

    @property
    def control_period(self) -> float | None:
        """Controller period in seconds, or None to run every sim step.

        Real controllers run slower than the simulator (e.g. Nav2 at
        20 Hz); the stack holds the last command between control ticks.
        """
        return None

    @abstractmethod
    def reset(self, global_path: Sequence[Point2D], robot: RobotConfig) -> None:
        """Prepare for a new episode with a fresh global path."""

    @abstractmethod
    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        """Return the command for the next simulation step."""
