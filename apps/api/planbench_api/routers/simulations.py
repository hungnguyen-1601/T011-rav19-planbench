"""Simulation session endpoints (headless run + stored result)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_simulation_service
from planbench_api.repositories import StoredSimulation
from planbench_api.schemas import (
    SimulationCreateRequest,
    SimulationResource,
    SimulationResultResponse,
)
from planbench_api.services import SimulationService

router = APIRouter(prefix="/simulations", tags=["simulations"])

Service = Annotated[SimulationService, Depends(get_simulation_service)]


def _resource(stored: StoredSimulation) -> SimulationResource:
    return SimulationResource(
        id=stored.id,
        map_id=stored.map_id,
        scenario_id=stored.scenario_id,
        algorithm=stored.algorithm,
        state=stored.state,
        created_at=stored.created_at,
    )


@router.get("", response_model=list[SimulationResource])
def list_simulations(service: Service, _: ActiveUser) -> list[SimulationResource]:
    return [_resource(stored) for stored in service.list()]


@router.post("", response_model=SimulationResource, status_code=status.HTTP_201_CREATED)
def create_simulation(
    request: SimulationCreateRequest, service: Service, _: ActiveUser
) -> SimulationResource:
    return _resource(
        service.create(request.map_id, request.scenario_id, request.algorithm, request.config)
    )


@router.get("/{simulation_id}", response_model=SimulationResource)
def get_simulation(simulation_id: str, service: Service, _: ActiveUser) -> SimulationResource:
    return _resource(service.get(simulation_id))


@router.post("/{simulation_id}/run", response_model=SimulationResultResponse)
def run_simulation(
    simulation_id: str, service: Service, _: ActiveUser
) -> SimulationResultResponse:
    stored = service.run(simulation_id)
    assert stored.run is not None
    return SimulationResultResponse(
        id=stored.id,
        state=stored.state,
        plan=stored.run.plan,
        result=stored.run.result,
        metrics=stored.run.metrics,
    )


@router.get("/{simulation_id}/result", response_model=SimulationResultResponse)
def get_simulation_result(
    simulation_id: str, service: Service, _: ActiveUser
) -> SimulationResultResponse:
    stored = service.get(simulation_id)
    return SimulationResultResponse(
        id=stored.id,
        state=stored.state,
        plan=stored.run.plan if stored.run else None,
        result=stored.run.result if stored.run else None,
        metrics=stored.run.metrics if stored.run else None,
    )
