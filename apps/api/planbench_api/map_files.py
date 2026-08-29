"""Write a stored grid out as the map_server pair a profile names.

**The one crossing between two ways of holding a map.** The editor keeps
grids in the database, because that is what a painting UI needs; a task
profile names its map by *path* (HĐ-2), because that is what the runner
reads. Neither is wrong and neither can be dropped, so something has to
turn one into the other. This is it, and it is a module rather than a
method because two callers need it: deriving a deployment from a base,
and a form filing one from scratch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

_log = logging.getLogger("planbench.map_files")

from planbench_api.repositories import StoredMap
from planbench_schemas.map_io import dump_map_server

if TYPE_CHECKING:
    from planbench_api.repository_ports import MapRepositoryPort
    from planbench_schemas.task_profile import TaskProfile

__all__ = [
    "ensure_custom_map_files",
    "ensure_profile_map_materialised",
    "materialise_map",
    "pinned_map_reference",
]


def pinned_map_reference(map_path: str | None) -> tuple[str, int] | None:
    """The map id and version a profile's path pins, or ``None``.

    One reader for the one filename shape this module invents, because
    two places now need it: the recovery below, which must not serve a
    different version than the one asked for, and the endpoint that tells
    a person which deployments are pinned to the map they are editing.
    Parsing it twice would be two definitions of the same convention.

    Returns ``None`` for anything that is not a custom map — a profile
    naming a bundled map pins nothing, and neither does a path shaped
    some other way.
    """
    if not map_path or not str(map_path).startswith("maps/custom/"):
        return None
    stem = Path(str(map_path)).stem
    if "__v" not in stem:
        return None
    map_id, _, version = stem.rpartition("__v")
    if not map_id or not version.isdigit():
        return None
    return map_id, int(version)


def materialise_map(
    stored: StoredMap, map_root: Path, *, stem: str | None = None
) -> tuple[str, str]:
    """Write the pair, return the two paths **relative to the map root**.

    Relative, never absolute. A profile carrying an absolute path is a
    profile that is only true on one machine, and HĐ-13's acceptance
    criterion is that somebody else rebuilds the run from what the
    profile says.

    The name is ``<id>__v<version>``, so a map edited after a deployment
    was filed from it lands in a different file. The deployment keeps
    pointing at the walls its episodes were driven on — which is the only
    reading under which its stored traces are still evidence.

    Idempotent per (map id, version): calling it twice writes identical
    bytes to the same path, so a caller that fails validation afterwards
    leaves nothing to clean up.
    """
    if stem is None:
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in stored.id)
        stem = f"{safe_id}__v{stored.version}"
    directory = map_root / "maps" / "custom"
    directory.mkdir(parents=True, exist_ok=True)

    image_bytes, sidecar = dump_map_server(stored.map_data, image_name=f"{stem}.pgm")
    pgm_path = directory / f"{stem}.pgm"
    yaml_path = directory / f"{stem}.yaml"
    pgm_path.write_bytes(image_bytes)
    yaml_path.write_text(sidecar, encoding="utf-8")
    _log.warning(
        "materialise_map: wrote %s (exists=%s size=%s)",
        pgm_path,
        pgm_path.is_file(),
        pgm_path.stat().st_size if pgm_path.is_file() else "N/A",
    )
    return f"maps/custom/{stem}.pgm", f"maps/custom/{stem}.yaml"


def ensure_custom_map_files(
    map_rel_path: str,
    map_root: Path,
    map_repo: MapRepositoryPort | None = None,
) -> bool:
    """Ensure a custom map (maps/custom/<stem>.pgm) exists on disk.

    If the file is missing on disk (e.g. after container restart or checkout),
    retrieves the StoredMap from the repository by id and writes the pgm + yaml pair.
    Returns True if the file exists or was successfully written, False otherwise.
    """
    if not map_rel_path or not str(map_rel_path).startswith("maps/custom/"):
        return False

    full_path = map_root / map_rel_path
    _log.warning(
        "ensure_custom_map_files: checking map_root=%s rel=%s full_path=%s exists=%s repo=%s",
        map_root,
        map_rel_path,
        full_path,
        full_path.is_file(),
        type(map_repo).__name__ if map_repo else None,
    )
    if full_path.is_file():
        return True

    if map_repo is None:
        _log.warning(
            "ensure_custom_map_files: map file missing but no map_repo; cannot recover: %s",
            full_path,
        )
        return False

    # Extract exact requested stem: e.g. "7d52494dc3b5__v1"
    requested_stem = Path(map_rel_path).stem
    map_id_candidate = requested_stem.split("__v")[0] if "__v" in requested_stem else requested_stem
    pinned = pinned_map_reference(map_rel_path)
    requested_version = pinned[1] if pinned else None

    def _recover(stored: StoredMap) -> bool:
        """Write the pair back, but only when it is the version asked for.

        **The version in the filename is the whole point of the
        filename.** ``materialise_map`` names a map ``<id>__v<version>``
        precisely so that editing a map after a deployment was filed
        lands in a *different* file and leaves that deployment pointing
        at the walls its episodes were driven on. Recovery that wrote
        whatever the row holds now under the name of an older version
        would undo that in the one situation nobody is watching: the file
        is missing, so this runs, so the deployment silently starts
        measuring a world it never agreed to — and every stored trace
        beside it keeps claiming to describe the same place.

        A refusal is recoverable and a wrong grid is not. Whoever hits
        this can derive a deployment on the current version, which is the
        supported way to move a comparison onto new walls.
        """
        if requested_version is not None and stored.version != requested_version:
            _log.error(
                "ensure_custom_map_files: refusing to recover %s. The deployment pins map "
                "%s at v%s and the store now holds v%s; writing the newer grid under the "
                "older name would change the walls under runs already recorded against it. "
                "Derive a deployment on the current version instead "
                "(POST /api/v1/task-profiles/derive).",
                map_rel_path,
                stored.id,
                requested_version,
                stored.version,
            )
            return False
        materialise_map(stored, map_root, stem=requested_stem)
        return full_path.is_file()

    try:
        stored_map = map_repo.get(map_id_candidate)
        recovered = _recover(stored_map)
        if recovered:
            _log.warning(
                "ensure_custom_map_files: recovered map %s from DB (direct id)", map_rel_path
            )
        return recovered
    except Exception as exc:
        _log.debug("ensure_custom_map_files: direct get(%s) failed: %s", map_id_candidate, exc)

    try:
        for stored in map_repo.list():
            safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in stored.id)
            if safe_id == map_id_candidate or stored.id == map_id_candidate:
                recovered = _recover(stored)
                if recovered:
                    _log.warning(
                        "ensure_custom_map_files: recovered map %s from DB (list scan)",
                        map_rel_path,
                    )
                return recovered
    except Exception as exc:
        _log.warning("ensure_custom_map_files: list scan failed: %s", exc)

    _log.error(
        "ensure_custom_map_files: FAILED to recover map %s (map_root=%s, map_id=%s)",
        map_rel_path,
        map_root,
        map_id_candidate,
    )
    return False


def ensure_profile_map_materialised(
    profile_data: Mapping[str, Any] | TaskProfile | None,
    map_root: Path,
    map_repo: MapRepositoryPort | None = None,
) -> bool:
    """Check if profile uses a custom map and ensure its files exist on disk."""
    if profile_data is None:
        return False

    if hasattr(profile_data, "environment"):
        env = profile_data.environment
        map_path = getattr(env, "map", None) if env else None
    elif isinstance(profile_data, Mapping):
        env = profile_data.get("environment") or {}
        map_path = env.get("map") if isinstance(env, Mapping) else None
    else:
        map_path = None

    _log.warning(
        "ensure_profile_map_materialised: map_path=%r starts_custom=%s map_root=%s",
        map_path,
        str(map_path).startswith("maps/custom/") if map_path else False,
        map_root,
    )

    if map_path and str(map_path).startswith("maps/custom/"):
        return ensure_custom_map_files(str(map_path), map_root, map_repo)
    return False
