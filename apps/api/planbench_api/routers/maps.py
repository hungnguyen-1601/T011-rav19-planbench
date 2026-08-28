"""Map CRUD + validation endpoints.

**Reading is open to any signed-in account; writing is not.** Until
contract 7.0.0 none of these asked for a token at all, so a passer-by
could rewrite the grid a stored scenario stood on.

Deleting is now archiving. A map is referenced by scenarios, by task
profiles and by every run made against it, and a removed row turns each
of those references into a hole — an audit trail that points at nothing
is not an audit trail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from planbench_api.auth import CurrentUser, ReadingUser, WritingUser
from planbench_api.decision_service import TaskProfileService
from planbench_api.dependencies import get_map_root, get_map_service, get_task_profile_service
from planbench_api.map_files import materialise_map, pinned_map_reference
from planbench_api.repositories import StoredMap
from planbench_api.schemas import MapResource, MapSummary, ValidationReport
from planbench_api.services import MapService
from planbench_schemas.map import MapData

router = APIRouter(prefix="/maps", tags=["maps"])

Service = Annotated[MapService, Depends(get_map_service)]
MapRoot = Annotated[Path, Depends(get_map_root)]
Profiles = Annotated[TaskProfileService, Depends(get_task_profile_service)]


class MapPin(BaseModel):
    """One deployment holding this map at one version.

    ``stale`` is the field this endpoint exists for. A deployment names
    its map by path, and the path carries the version — so editing a map
    leaves every deployment filed before the edit pointing at the walls
    its episodes were driven on. That is deliberate and load-bearing:
    ``episode_context_id`` does not hash the map (HĐ-3.1), so silently
    moving a deployment onto new walls would make stored runs describe a
    world that no longer exists.

    What was missing was anybody being *told*. Somebody edited a map,
    re-ran a comparison, and watched it measure the old grid with nothing
    on screen to explain why.
    """

    task_profile_id: str
    pinned_version: int
    #: True when the store has moved past the version this deployment
    #: names — the case worth drawing attention to.
    stale: bool


class MapPins(BaseModel):
    current_version: int
    pins: list[MapPin]


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
def list_maps(service: Service, _: ReadingUser) -> list[MapSummary]:
    return [_summary(stored) for stored in service.list()]


@router.post("", response_model=MapResource, status_code=status.HTTP_201_CREATED)
def create_map(map_data: MapData, service: Service, user: WritingUser) -> MapResource:
    return _resource(service.create(map_data, owner_user_id=user.id))


@router.get("/{map_id}", response_model=MapResource)
def get_map(map_id: str, service: Service, _: ReadingUser) -> MapResource:
    return _resource(service.get(map_id))


@router.put("/{map_id}", response_model=MapResource)
def update_map(map_id: str, map_data: MapData, service: Service, user: WritingUser) -> MapResource:
    return _resource(service.update(map_id, map_data, actor_user_id=user.id))


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_map(map_id: str, service: Service, user: WritingUser) -> None:
    """Archive, despite the verb.

    The method stays ``DELETE`` because that is what "take this off my
    list" means to a caller, and changing it would break every client for
    a distinction they do not have to care about. What changes is the
    storage: the row survives, so a run made against this map can still
    say what it ran on.
    """
    service.archive(map_id, actor_user_id=user.id)


@router.get("/{map_id}/pins", response_model=MapPins)
def map_pins(map_id: str, service: Service, profiles: Profiles, _: ReadingUser) -> MapPins:
    """Which deployments run this map, and which of them are behind.

    Open to any reader: this answers "why did my edit not change what the
    bench ran?", and that question belongs to whoever is doing the
    editing rather than to whoever administers the deployment.

    Scanning the profiles rather than keeping an index. There are tens of
    deployments, not millions, and an index would be a second copy of a
    fact the profile already states — free to disagree the moment a
    profile is filed by any path that forgot to update it.
    """
    stored = service.get(map_id)
    pins: list[MapPin] = []
    for profile in profiles.list():
        environment = (profile.profile or {}).get("environment") or {}
        reference = pinned_map_reference(environment.get("map"))
        if reference is None or reference[0] != map_id:
            continue
        pins.append(
            MapPin(
                task_profile_id=profile.id,
                pinned_version=reference[1],
                stale=reference[1] != stored.version,
            )
        )
    pins.sort(key=lambda pin: (not pin.stale, pin.task_profile_id))
    return MapPins(current_version=stored.version, pins=pins)


@router.post("/validate", response_model=ValidationReport)
def validate_map(map_data: MapData, service: Service, _: ReadingUser) -> ValidationReport:
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
