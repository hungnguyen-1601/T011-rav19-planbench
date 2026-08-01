"""Scenario library and leaderboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_map_service, get_repos, get_scenario_service
from planbench_api.leaderboard import Leaderboard, ScoreWeights, build_leaderboard
from planbench_api.services import MapService, ScenarioService
from planbench_benchmark import CURRICULUM_ORDER, build_scenario
from planbench_schemas.scenario import Scenario

router = APIRouter(tags=["library"])

Maps = Annotated[MapService, Depends(get_map_service)]
Scenarios = Annotated[ScenarioService, Depends(get_scenario_service)]


class LibraryEntry(BaseModel):
    name: str
    description: str
    curriculum_index: int
    dynamic_obstacles: int
    map_size_m: tuple[float, float]
    timeout_seconds: float


class ImportedScenario(BaseModel):
    """IDs of the map and scenario created from a library entry."""

    library_name: str
    map_id: str
    scenario_id: str
    scenario: Scenario


@router.get("/scenario-library", response_model=list[LibraryEntry])
def list_library(_: ActiveUser) -> list[LibraryEntry]:
    """Built-in scenarios, ordered easiest to hardest (curriculum order)."""
    entries = []
    for index, name in enumerate(CURRICULUM_ORDER):
        map_data, scenario = build_scenario(name)
        entries.append(
            LibraryEntry(
                name=name,
                description=scenario.description,
                curriculum_index=index,
                dynamic_obstacles=len(scenario.dynamic_obstacles),
                map_size_m=(
                    map_data.width * map_data.resolution,
                    map_data.height * map_data.resolution,
                ),
                timeout_seconds=scenario.timeout_seconds,
            )
        )
    return entries


@router.post(
    "/scenario-library/{name}/import",
    response_model=ImportedScenario,
    status_code=status.HTTP_201_CREATED,
)
def import_library_scenario(
    name: str, maps: Maps, scenarios: Scenarios, _: ActiveUser
) -> ImportedScenario:
    """Materialise a library scenario as a stored map + scenario pair."""
    from planbench_api.errors import DomainValidationError

    try:
        map_data, scenario = build_scenario(name)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc
    stored_map = maps.create(map_data)
    stored_scenario = scenarios.create(stored_map.id, scenario)
    return ImportedScenario(
        library_name=name,
        map_id=stored_map.id,
        scenario_id=stored_scenario.id,
        scenario=scenario,
    )


@router.get("/leaderboard", response_model=Leaderboard)
def leaderboard(
    request_user: ActiveUser,
    repos=Depends(get_repos),  # noqa: B008 - FastAPI dependency
    scenario_name: str | None = Query(default=None),
    algorithm: str | None = Query(default=None),
    accepted_only: bool = Query(
        default=True,
        description=(
            "Only rank accepted benchmarks. Set false to inspect "
            "unreviewed runs — those must not be published as conclusions."
        ),
    ),
    weight_success: float = Query(default=0.40, ge=0),
    weight_safety: float = Query(default=0.30, ge=0),
    weight_efficiency: float = Query(default=0.20, ge=0),
    weight_smoothness: float = Query(default=0.10, ge=0),
) -> Leaderboard:
    """Rank stacks, grouped so only comparable results sit together."""
    weights = ScoreWeights(
        success=weight_success,
        safety=weight_safety,
        efficiency=weight_efficiency,
        smoothness=weight_smoothness,
    )
    return build_leaderboard(
        repos.benchmarks.list(),
        weights,
        scenario_name=scenario_name,
        algorithm=algorithm,
        accepted_only=accepted_only,
    )
