"""Planner interfaces and result contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from planbench_schemas.geometry import Point2D
from planbench_simulator.grid import OccupancyGrid


class PlanResult(BaseModel):
    """Outcome of a global planning attempt.

    ``planning_time_seconds`` is wall-clock measurement — a metric, not
    part of the deterministic contract (path and cost are).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    success: bool
    path: tuple[Point2D, ...] = ()
    path_length: float = 0.0
    cost: float = 0.0
    planning_time_seconds: float = 0.0
    expanded_nodes: int = 0
    failure_reason: str = ""


class GlobalPlanner(ABC):
    """A global planner maps (grid, start, goal) to a world-frame path.

    Planners must be deterministic for identical inputs. The grid passed
    in should already account for the robot footprint (e.g. inflated by
    the robot radius) — planners treat it as the configuration space.
    """

    @abstractmethod
    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult:
        """Compute a path from ``start`` to ``goal`` in world coordinates."""
