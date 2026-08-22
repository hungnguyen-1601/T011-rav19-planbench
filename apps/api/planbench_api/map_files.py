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

from pathlib import Path

from planbench_api.repositories import StoredMap
from planbench_schemas.map_io import dump_map_server

__all__ = ["materialise_map"]


def materialise_map(stored: StoredMap, map_root: Path) -> tuple[str, str]:
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
    safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in stored.id)
    stem = f"{safe_id}__v{stored.version}"
    directory = map_root / "maps" / "custom"
    directory.mkdir(parents=True, exist_ok=True)

    image_bytes, sidecar = dump_map_server(stored.map_data, image_name=f"{stem}.pgm")
    (directory / f"{stem}.pgm").write_bytes(image_bytes)
    (directory / f"{stem}.yaml").write_text(sidecar, encoding="utf-8")
    return f"maps/custom/{stem}.pgm", f"maps/custom/{stem}.yaml"
