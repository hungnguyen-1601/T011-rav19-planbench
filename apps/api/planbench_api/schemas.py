"""API request/response models (wrap the domain schemas, never replace them)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_benchmark import ScenarioSplit
from planbench_metrics import EpisodeMetrics
from planbench_planning import PlanResult
from planbench_schemas.episode import EpisodeResult
from planbench_schemas.geometry import Point2D
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario


class MapResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    checksum: str
    created_at: str
    map_data: MapData


class MapSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    name: str
    width: int
    height: int
    resolution: float
    checksum: str
    created_at: str


class ScenarioCreateRequest(BaseModel):
    map_id: str
    scenario: Scenario


class ScenarioResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    map_id: str
    created_at: str
    scenario: Scenario
    #: Evaluation split (P05), resolved read-only from the protocol file.
    #: Anything authored in the app is ``unassigned``, and there is no
    #: request field that can change that: promoting a scenario is a
    #: reviewed protocol change, not something the author of a scenario
    #: decides about their own scenario.
    split: ScenarioSplit = "unassigned"


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    errors: tuple[str, ...] = ()


class DynamicObstacleSnapshot(BaseModel):
    """Where one moving obstacle is at a given instant."""

    model_config = ConfigDict(frozen=True)

    name: str
    radius: float
    position: Point2D


class ScenarioPreviewRequest(BaseModel):
    """Ask the backend where everything is at ``time``.

    The UI does not evaluate motion laws itself. Every position it draws
    comes from here, computed by the same ``position_at`` the simulator
    uses — otherwise the preview could disagree with the episode, and a
    scenario editor whose preview lies is worse than no preview.
    """

    map_id: str
    scenario: Scenario
    #: Seconds into the episode. 0 is the state the robot starts in.
    time: float = Field(default=0.0, ge=0)
    #: Episode seed. Timing of seeded traffic depends on it, so the
    #: preview states which seed it is showing rather than implying the
    #: scenario looks like this for all of them.
    seed: int = 0


class ScenarioPreview(BaseModel):
    """Obstacle positions at one instant, plus the validation verdict.

    Validation travels with the preview because the editor always needs
    both: a scenario whose start pose sits inside a wall must say so
    while it is being drawn, not when it is saved.
    """

    model_config = ConfigDict(frozen=True)

    time: float
    seed: int
    valid: bool
    errors: tuple[str, ...] = ()
    dynamic_obstacles: tuple[DynamicObstacleSnapshot, ...] = ()


class SimulationCreateRequest(BaseModel):
    map_id: str
    scenario_id: str
    algorithm: str = "astar+dwa"
    config: dict = Field(default_factory=dict)


class SimulationResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    map_id: str
    scenario_id: str
    algorithm: str
    config: dict = Field(default_factory=dict)
    state: str  # created | finished
    created_at: str


class SimulationResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    state: str
    plan: PlanResult | None = None
    result: EpisodeResult | None = None
    metrics: EpisodeMetrics | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    app: str
    version: str
