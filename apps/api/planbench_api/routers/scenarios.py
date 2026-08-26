"""Scenario CRUD + validation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from planbench_api.dependencies import get_map_service, get_scenario_service
from planbench_api.repositories import StoredScenario
from planbench_api.schemas import (
    DynamicObstacleSnapshot,
    ScenarioCreateRequest,
    ScenarioPreview,
    ScenarioPreviewRequest,
    ScenarioResource,
    ValidationReport,
)
from planbench_api.services import MapService, ScenarioService
from planbench_benchmark import scenario_split
from planbench_schemas.dynamic import position_at

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

Service = Annotated[ScenarioService, Depends(get_scenario_service)]
Maps = Annotated[MapService, Depends(get_map_service)]


def _resource(stored: StoredScenario) -> ScenarioResource:
    return ScenarioResource(
        id=stored.id,
        version=stored.version,
        map_id=stored.map_id,
        created_at=stored.created_at,
        scenario=stored.scenario,
        # Resolved, never stored and never accepted from the request: a
        # scenario authored here is unassigned until a reviewed change to
        # scenario_protocol.json says otherwise.
        split=scenario_split(stored.scenario.name),
    )


@router.get("", response_model=list[ScenarioResource])
def list_scenarios(service: Service) -> list[ScenarioResource]:
    return [_resource(stored) for stored in service.list()]


@router.post("", response_model=ScenarioResource, status_code=status.HTTP_201_CREATED)
def create_scenario(request: ScenarioCreateRequest, service: Service) -> ScenarioResource:
    return _resource(service.create(request.map_id, request.scenario))


@router.get("/{scenario_id}", response_model=ScenarioResource)
def get_scenario(scenario_id: str, service: Service) -> ScenarioResource:
    return _resource(service.get(scenario_id))


@router.put("/{scenario_id}", response_model=ScenarioResource)
def update_scenario(
    scenario_id: str, request: ScenarioCreateRequest, service: Service
) -> ScenarioResource:
    return _resource(service.update(scenario_id, request.map_id, request.scenario))


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: str, service: Service) -> None:
    service.delete(scenario_id)


@router.post("/validate", response_model=ValidationReport)
def validate_scenario(
    request: ScenarioCreateRequest, service: Service, maps: Maps
) -> ValidationReport:
    """Check a scenario against a map with the real engine.

    The editor calls this before saving. It is the same check ``create``
    and ``update`` run, so a scenario that validates here cannot be
    rejected on save for a reason the author was not shown — and the
    browser never decides for itself that a scenario is legal.
    """
    stored_map = maps.get(request.map_id)
    errors = service.validate_against_map(stored_map.map_data, request.scenario)
    return ValidationReport(valid=not errors, errors=tuple(errors))


@router.post("/preview", response_model=ScenarioPreview)
def preview_scenario(
    request: ScenarioPreviewRequest, service: Service, maps: Maps
) -> ScenarioPreview:
    """Where the moving obstacles are at ``time``, plus the verdict.

    Exists so the editor can draw traffic without implementing motion
    laws in the browser. Two reasons that matters beyond tidiness: a
    second implementation would drift from the simulator's, and a preview
    that disagrees with the episode is worse than no preview at all —
    the author would place the start pose clear of an obstacle that is
    somewhere else when the episode actually runs.
    """
    stored_map = maps.get(request.map_id)
    errors = service.validate_against_map(stored_map.map_data, request.scenario)
    snapshots = tuple(
        DynamicObstacleSnapshot(
            name=obstacle.name,
            radius=obstacle.radius,
            position=position_at(obstacle, request.time, request.seed),
        )
        for obstacle in request.scenario.dynamic_obstacles
    )
    return ScenarioPreview(
        time=request.time,
        seed=request.seed,
        valid=not errors,
        errors=tuple(errors),
        dynamic_obstacles=snapshots,
    )
