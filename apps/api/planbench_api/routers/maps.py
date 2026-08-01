"""Map CRUD + validation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_map_service
from planbench_api.repositories import StoredMap
from planbench_api.schemas import MapResource, MapSummary, ValidationReport
from planbench_api.services import MapService
from planbench_schemas.map import MapData

router = APIRouter(prefix="/maps", tags=["maps"])

Service = Annotated[MapService, Depends(get_map_service)]


def _resource(stored: StoredMap) -> MapResource:
    return MapResource(
        id=stored.id,
        version=stored.version,
        checksum=stored.map_data.checksum(),
        created_at=stored.created_at,
        map_data=stored.map_data,
    )


def _summary(stored: StoredMap) -> MapSummary:
    return MapSummary(
        id=stored.id,
        version=stored.version,
        name=stored.map_data.name,
        width=stored.map_data.width,
        height=stored.map_data.height,
        resolution=stored.map_data.resolution,
        checksum=stored.map_data.checksum(),
        created_at=stored.created_at,
    )


@router.get("", response_model=list[MapSummary])
def list_maps(service: Service, _: ActiveUser) -> list[MapSummary]:
    return [_summary(stored) for stored in service.list()]


@router.post("", response_model=MapResource, status_code=status.HTTP_201_CREATED)
def create_map(map_data: MapData, service: Service, _: ActiveUser) -> MapResource:
    return _resource(service.create(map_data))


@router.get("/{map_id}", response_model=MapResource)
def get_map(map_id: str, service: Service, _: ActiveUser) -> MapResource:
    return _resource(service.get(map_id))


@router.put("/{map_id}", response_model=MapResource)
def update_map(map_id: str, map_data: MapData, service: Service, _: ActiveUser) -> MapResource:
    return _resource(service.update(map_id, map_data))


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map(map_id: str, service: Service, _: ActiveUser) -> None:
    service.delete(map_id)


@router.post("/validate", response_model=ValidationReport)
def validate_map(map_data: MapData, service: Service, _: ActiveUser) -> ValidationReport:
    errors = service.validate(map_data)
    return ValidationReport(valid=not errors, errors=tuple(errors))
