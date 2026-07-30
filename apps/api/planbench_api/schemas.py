"""API request/response models (wrap the domain schemas, never replace them)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_metrics import EpisodeMetrics
from planbench_planning import PlanResult
from planbench_schemas.episode import EpisodeResult
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


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    errors: tuple[str, ...] = ()


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
