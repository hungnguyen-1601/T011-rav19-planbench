"""Scenario CRUD + validation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_map_service, get_scenario_service
from planbench_api.repositories import StoredScenario
from planbench_api.schemas import ScenarioCreateRequest, ScenarioResource, ValidationReport
from planbench_api.services import MapService, ScenarioService

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
    )


@router.get("", response_model=list[ScenarioResource])
def list_scenarios(service: Service, _: ActiveUser) -> list[ScenarioResource]:
    return [_resource(stored) for stored in service.list()]


@router.post("", response_model=ScenarioResource, status_code=status.HTTP_201_CREATED)
def create_scenario(
    request: ScenarioCreateRequest, service: Service, _: ActiveUser
) -> ScenarioResource:
    return _resource(service.create(request.map_id, request.scenario))


@router.get("/{scenario_id}", response_model=ScenarioResource)
def get_scenario(scenario_id: str, service: Service, _: ActiveUser) -> ScenarioResource:
    return _resource(service.get(scenario_id))


@router.put("/{scenario_id}", response_model=ScenarioResource)
def update_scenario(
    scenario_id: str, request: ScenarioCreateRequest, service: Service, _: ActiveUser
) -> ScenarioResource:
    return _resource(service.update(scenario_id, request.map_id, request.scenario))


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: str, service: Service, _: ActiveUser) -> None:
    service.delete(scenario_id)


@router.post("/validate", response_model=ValidationReport)
def validate_scenario(
    request: ScenarioCreateRequest, service: Service, maps: Maps, _: ActiveUser
) -> ValidationReport:
    stored_map = maps.get(request.map_id)
    errors = service.validate_against_map(stored_map.map_data, request.scenario)
    return ValidationReport(valid=not errors, errors=tuple(errors))
