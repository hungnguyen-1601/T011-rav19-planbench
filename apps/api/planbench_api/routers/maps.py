"""Map CRUD + validation endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from planbench_api.auth import CurrentUser
from planbench_api.dependencies import get_map_root, get_map_service
from planbench_api.map_files import materialise_map
from planbench_api.repositories import StoredMap
from planbench_api.schemas import MapResource, MapSummary, ValidationReport
from planbench_api.services import MapService
from planbench_schemas.map import MapData

router = APIRouter(prefix="/maps", tags=["maps"])

Service = Annotated[MapService, Depends(get_map_service)]
MapRoot = Annotated[Path, Depends(get_map_root)]


class MaterialisedMap(BaseModel):
    """The two paths a task profile names, for a map held in the store.

    Exactly the pair that goes into ``environment.map`` and
    ``environment.map_yaml`` — so a caller building a profile puts these
    two strings in and gets a document identical to one somebody typed
    by hand. That identity is the point: a form and a pasted YAML have
    to produce the same artifact, or there are two definitions of what a
    deployment is.
    """

    map: str
    map_yaml: str


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
def list_maps(service: Service) -> list[MapSummary]:
    return [_summary(stored) for stored in service.list()]


@router.post("", response_model=MapResource, status_code=status.HTTP_201_CREATED)
def create_map(map_data: MapData, service: Service) -> MapResource:
    return _resource(service.create(map_data))


@router.get("/{map_id}", response_model=MapResource)
def get_map(map_id: str, service: Service) -> MapResource:
    return _resource(service.get(map_id))


@router.put("/{map_id}", response_model=MapResource)
def update_map(map_id: str, map_data: MapData, service: Service) -> MapResource:
    return _resource(service.update(map_id, map_data))


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map(map_id: str, service: Service) -> None:
    service.delete(map_id)


@router.post("/validate", response_model=ValidationReport)
def validate_map(map_data: MapData, service: Service) -> ValidationReport:
    errors = service.validate(map_data)
    return ValidationReport(valid=not errors, errors=tuple(errors))


@router.post("/{map_id}/materialise", response_model=MaterialisedMap)
def materialise(
    map_id: str, service: Service, map_root: MapRoot, _: CurrentUser
) -> MaterialisedMap:
    """Write this map out as a map_server pair and return the two paths.

    **The step between drawing a map and running on it.** A task profile
    names its map by path (HĐ-2); the editor stores grids in a database.
    Nothing else bridges the two, so a map somebody painted could be
    saved and never evaluated on.

    Not a GET, and not because it reads oddly: it writes two files. Safe
    to call twice — the name is (map id, version), so a repeat writes
    identical bytes to the same path.

    Editing the map afterwards bumps its version and therefore its
    filename, which is deliberate: a deployment filed from v1 keeps
    pointing at v1's walls, and its stored traces stay evidence of a run
    that actually happened somewhere.
    """
    image, sidecar = materialise_map(service.get(map_id), map_root)
    return MaterialisedMap(map=image, map_yaml=sidecar)
