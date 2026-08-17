"""Load the real map a TaskProfile points at (CONTRACTS HĐ-2, HĐ-4).

``EnvironmentSpec`` stores two *paths* — ``map`` and ``map_yaml`` — and
deliberately does not touch the disk, so a profile validates without one.
This module is where those paths become an :class:`~planbench_schemas.map.MapData`:
it is the runner's job (CONTRACTS §16 maps logical ``runner/`` here), and
it is the only layer that knows both the profile and the filesystem.

Two jobs, and the second is the one that earns the module:

**Load.** Read the ``map_server`` pair, hand the bytes to
:func:`~planbench_schemas.map_io.load_map_server`, and cache the result
keyed by path *and* file fingerprint — an evaluation set is 300+ episodes
on one map, and re-parsing 400 000 pixels per episode is minutes of
nothing.

**Refuse a profile the map contradicts.** A mission whose goal sits
inside a shelf produces 0% success for *every* candidate, and the
comparison then reports a tie between four stacks on a question none of
them was asked. That failure is invisible in the numbers — every column
reads a plausible 0.00 — so it has to be caught when the profile meets
the map, which is here and nowhere earlier: the schema cannot see the
map, and the planner sees it one episode too late.

The checks are stated against the robot's *radius*, not its centre
point. A goal 3 cm from a wall is reachable for a point and unreachable
for a 0.26 m robot, and the difference decides whether a G1 no-path rate
is a fact about the candidate or about the profile.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage

from planbench_schemas.map import CellState, MapData
from planbench_schemas.map_io import MapServerFormatError, load_map_server
from planbench_schemas.task_profile import EnvironmentSpec, TaskProfile
from planbench_simulator.grid import OccupancyGrid

__all__ = [
    "MapLoadError",
    "MapServerFormatError",
    "MapProfileMismatch",
    "clear_map_cache",
    "load_environment_map",
    "load_task_map",
    "validate_missions_on_map",
]


class MapLoadError(ValueError):
    """The profile's map files are missing or unreadable."""


class MapProfileMismatch(ValueError):
    """The profile and the map it names disagree.

    Raised before any episode runs. The alternative is a run whose every
    metric is a well-formed number describing a question nobody asked.
    """


@dataclass(frozen=True)
class _CacheKey:
    """Identity of a map on disk: where it is and what it currently is.

    The content digest is in the key so editing a map invalidates the
    cache. A long benchmark session that reloads the same profile after
    the map was regenerated must not keep planning on the previous
    walls.

    Size and mtime alone cannot carry that guarantee. Linux stamps
    mtime from a cached clock updated once per timer tick, so a
    same-size rewrite inside one tick — a regenerator writing both
    files in a loop, or a test — leaves the fingerprint identical and
    the stale map is served. Hashing costs one extra read of a file
    that is about to be read anyway; parsing the image dominates it,
    and that is the work the cache exists to skip.
    """

    image: str
    meta: str
    image_digest: str
    meta_digest: str


_CACHE: dict[_CacheKey, MapData] = {}


def clear_map_cache() -> None:
    """Drop every cached map. For tests and long-lived processes."""
    _CACHE.clear()


def _resolve(path_value: str, base_dir: Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (base_dir / path)


def _fingerprint(path: Path) -> str:
    """Digest of the file's bytes — what the cache keys on."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_environment_map(
    environment: EnvironmentSpec,
    *,
    base_dir: Path | str = ".",
    name: str | None = None,
) -> MapData:
    """Read the ``map_server`` pair an environment names.

    ``base_dir`` resolves the profile's relative paths — profiles are
    written relative to the repository or to a deployment bundle, and
    baking the working directory into them would make a profile mean
    different things depending on where it was run from.

    The map's ``name`` defaults to the image file's stem, so a stored
    map keeps an identity that survives being copied.
    """
    base = Path(base_dir)
    image_path = _resolve(environment.map, base)
    meta_path = _resolve(environment.map_yaml, base)
    for path, field in ((image_path, "map"), (meta_path, "map_yaml")):
        if not path.is_file():
            raise MapLoadError(
                f"task profile field {field} points at {path}, which does not exist. "
                f"Paths are resolved against base_dir={base}"
            )

    key = _CacheKey(
        image=str(image_path.resolve()),
        meta=str(meta_path.resolve()),
        image_digest=_fingerprint(image_path),
        meta_digest=_fingerprint(meta_path),
    )
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    yaml_text = meta_path.read_text(encoding="utf-8")
    map_data = load_map_server(image_path.read_bytes(), yaml_text, name=name or image_path.stem)
    _check_yaml_image_matches(yaml_text, image_path, meta_path)
    _CACHE[key] = map_data
    return map_data


def _check_yaml_image_matches(yaml_text: str, image_path: Path, meta_path: Path) -> None:
    """The sidecar's own ``image:`` must name the file we just read.

    A profile pointing at ``warehouse_a.pgm`` beside a YAML whose
    ``image:`` says ``warehouse_b.pgm`` loads happily: the pixels come
    from A and the resolution, origin and thresholds from B. Every
    coordinate in the run is then offset by whatever B's origin is, and
    nothing in the results looks wrong.
    """
    meta = yaml.safe_load(yaml_text)
    declared = meta.get("image") if isinstance(meta, dict) else None
    if not declared:
        # map_server allows the key to be absent for maps distributed
        # without it; there is then nothing to disagree with.
        return
    declared_path = Path(str(declared))
    if not declared_path.is_absolute():
        declared_path = meta_path.parent / declared_path
    if declared_path.resolve() != image_path.resolve():
        raise MapProfileMismatch(
            f"{meta_path.name} declares image {declared!r} but the profile loaded "
            f"{image_path.name}. The pixels would come from one map and the resolution, "
            "origin and thresholds from another"
        )


def load_task_map(
    profile: TaskProfile,
    *,
    base_dir: Path | str = ".",
    validate: bool = True,
) -> MapData:
    """Load a profile's map and (by default) check the missions fit it."""
    map_data = load_environment_map(profile.environment, base_dir=base_dir)
    if validate:
        validate_missions_on_map(profile, map_data)
    return map_data


def validate_missions_on_map(profile: TaskProfile, map_data: MapData) -> None:
    """Refuse a profile whose missions the map cannot support (HĐ-2).

    Five ways a profile and a map disagree, each of which produces
    numbers rather than an error if left alone:

    1. a pose outside the map — the robot starts nowhere;
    2. a pose on an occupied or unknown cell — start inside a wall is an
       instant collision, goal inside a wall is an unreachable goal;
    3. a pose whose *robot* does not fit, though its centre does;
    4. no route at all between start and goal for a robot of this size —
       every candidate returns no_path and G1 fails the whole field;
    5. start and goal within goal tolerance of each other — the episode
       succeeds at t=0 and measures nothing.

    Checks 3 and 4 share one computation: free space eroded by the robot
    radius. That mask is what the robot can actually occupy, so "does the
    robot fit here" is a lookup in it and "is there a route" is whether
    both poses land in the same connected component of it.
    """
    grid = OccupancyGrid(map_data)
    radius = profile.robot.radius
    tolerance = profile.constraints.goal_tolerance_m
    passable, components = _passable_space(map_data, radius)
    problems: list[str] = []

    for mission in profile.missions:
        cells: dict[str, tuple[int, int] | None] = {}
        for label, pose in (("start", mission.start), ("goal", mission.goal)):
            where = f"mission {mission.id!r} {label} ({pose.x:.2f}, {pose.y:.2f})"
            cells[label] = None
            if not grid.is_inside(pose.x, pose.y):
                problems.append(f"{where} is outside the map")
                continue
            if grid.is_occupied(pose.x, pose.y):
                problems.append(f"{where} is on an occupied or unknown cell")
                continue
            cell = grid.world_to_grid(pose.x, pose.y)
            assert cell is not None  # is_inside already said so
            if not passable[cell]:
                problems.append(
                    f"{where} has less than the robot's radius ({radius} m) of free space; "
                    "its centre fits but the robot does not"
                )
                continue
            cells[label] = cell

        start_cell, goal_cell = cells["start"], cells["goal"]
        if (
            start_cell is not None
            and goal_cell is not None
            and components[start_cell] != components[goal_cell]
        ):
            problems.append(
                f"mission {mission.id!r} has no route from start to goal for a robot of "
                f"radius {radius} m: the two lie in different regions of the free space. "
                "Every candidate would return no_path, and G1 would reject the whole field "
                "for a property of the map"
            )

        gap = (
            (mission.start.x - mission.goal.x) ** 2 + (mission.start.y - mission.goal.y) ** 2
        ) ** 0.5
        if gap <= tolerance:
            problems.append(
                f"mission {mission.id!r} starts within goal tolerance of its goal "
                f"({gap:.2f} m <= {tolerance} m); the episode would succeed at t=0 and "
                "measure nothing"
            )

    if problems:
        raise MapProfileMismatch(
            f"task profile {profile.id!r} does not fit map {map_data.name!r}:\n  "
            + "\n  ".join(problems)
        )


def _passable_space(map_data: MapData, radius: float) -> tuple[np.ndarray, np.ndarray]:
    """Free space eroded by the robot radius, plus its connected components.

    Unknown cells count as blocked, matching ``OccupancyGrid``'s default
    and the conservative reading a safety argument needs: a cell nobody
    surveyed is not a cell to drive through.

    Off-map counts as blocked too — the map edge is a wall — which is why
    the grid is padded before dilation instead of relying on the default
    border handling.
    """
    cells = np.asarray(map_data.cells, dtype=np.int16).reshape(map_data.height, map_data.width)
    blocked = cells != CellState.FREE.value

    span = int(math.ceil(radius / map_data.resolution))
    padded = np.pad(blocked, span + 1, constant_values=True)
    if span > 0:
        offsets = np.arange(-span, span + 1)
        disk = (offsets[:, None] ** 2 + offsets[None, :] ** 2) <= span**2
        padded = ndimage.binary_dilation(padded, structure=disk)
    inflated = padded[span + 1 : -(span + 1), span + 1 : -(span + 1)]

    passable = ~inflated
    components, _count = ndimage.label(passable)
    return passable, components
