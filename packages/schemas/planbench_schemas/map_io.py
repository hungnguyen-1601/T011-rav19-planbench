"""Load a map from the ROS ``map_server`` format: a PGM image plus a
YAML sidecar (spec section 7.1, F01).

This is the format `map_server`/`nav2_map_server` itself reads and
writes — PGM only here, not PNG: `map_server` outputs PGM by default,
and decoding PNG correctly needs a real image codec (Pillow), which is
a heavier dependency than one grayscale-map format justifies. See
docs/KNOWN_LIMITATIONS.md.

YAML fields read (ROS map_server's own names, not renamed):

- ``resolution``: metres per pixel.
- ``origin``: ``[x, y, theta]`` — the pose of pixel (0, height-1) in the
  map frame. ``theta`` must be 0 (see :class:`planbench_schemas.map.MapData`
  — rotated origins are rejected everywhere in this codebase, not just
  here).
- ``negate``: 0 (default) or 1. Flips which end of the greyscale range
  means "occupied" — see :func:`_pixel_to_cell` for the exact formula,
  taken from ``map_server``'s own conversion.
- ``occupied_thresh`` (default 0.65), ``free_thresh`` (default 0.196):
  occupancy-probability cutoffs, same defaults `map_server` ships with.
- ``mode`` (default ``trinary``): how pixels between the two thresholds
  are interpreted. Only ``trinary`` is supported; the others are
  rejected rather than approximated — see :data:`SUPPORTED_MODES`.
"""

from __future__ import annotations

import numpy as np
import yaml

from planbench_schemas.geometry import Pose2D
from planbench_schemas.map import CellState, MapData

#: The ``mode`` values map_server defines. Only the default is
#: implemented, and the other two are refused instead of being silently
#: treated as trinary: under ``scale`` a mid-grey pixel is a *partially
#: occupied* cell rather than an unknown one, so reading a scale map as
#: trinary turns a corridor of light-grey clutter into open floor. The
#: robot then plans straight through it and every candidate looks
#: equally good on a map that does not exist.
SUPPORTED_MODES = ("trinary",)
KNOWN_MODES = ("trinary", "scale", "raw")


class MapServerFormatError(ValueError):
    """The PGM or YAML payload is not a map_server map this loader understands."""


def load_map_server(image_bytes: bytes, yaml_text: str, name: str) -> MapData:
    """Build a :class:`MapData` from a map_server PGM + YAML pair.

    Both are taken as bytes/text rather than file paths so the caller
    (an API upload handler, a test, a script) owns how the data reached
    memory — this function has no filesystem dependency of its own.
    """
    try:
        meta = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        # yaml.YAMLError is not a ValueError, so a caller catching only
        # MapServerFormatError/ValueError (as the API router does) would
        # otherwise see this surface as an unhandled 500.
        raise MapServerFormatError(f"invalid YAML: {exc}") from exc
    if not isinstance(meta, dict):
        raise MapServerFormatError("map_server YAML must be a mapping")

    try:
        resolution = float(meta["resolution"])
        origin = meta["origin"]
    except KeyError as exc:
        raise MapServerFormatError(f"map_server YAML missing required key: {exc}") from None
    if not (isinstance(origin, list | tuple) and len(origin) == 3):
        raise MapServerFormatError(f"origin must be [x, y, theta], got {origin!r}")
    origin_x, origin_y, origin_theta = (float(v) for v in origin)
    if abs(origin_theta) > 1e-9:
        # MapData itself rejects this too (Pose2D.theta != 0), but a
        # loader-level message that names the YAML field is more useful
        # than a generic Pydantic validation error would be.
        raise MapServerFormatError(
            f"rotated map origins are not supported: origin theta = {origin_theta!r}, must be 0"
        )

    mode = str(meta.get("mode", "trinary"))
    if mode not in SUPPORTED_MODES:
        known = f"{mode!r}" if mode in KNOWN_MODES else f"{mode!r} (not a map_server mode)"
        raise MapServerFormatError(
            f"unsupported map_server mode {known}; this loader implements "
            f"{list(SUPPORTED_MODES)}. Reading it as trinary would reinterpret partially "
            "occupied cells as open floor, which changes the map the robot plans on"
        )

    negate = bool(int(meta.get("negate", 0)))
    occupied_thresh = float(meta.get("occupied_thresh", 0.65))
    free_thresh = float(meta.get("free_thresh", 0.196))
    if free_thresh >= occupied_thresh:
        # Ordered the other way round every pixel falls in the middle
        # band and the whole map loads as UNKNOWN — which, with
        # unknown_as_occupied, is a solid wall the planner reports as
        # "no path" for every candidate alike.
        raise MapServerFormatError(
            f"free_thresh ({free_thresh}) must be below occupied_thresh ({occupied_thresh}); "
            "with them reversed every pixel reads as unknown and the entire map is a wall"
        )

    width, height, maxval, pixels = _parse_pgm(image_bytes)
    cells = _pixels_to_cells(pixels, width, height, negate, occupied_thresh, free_thresh, maxval)

    return MapData(
        name=name,
        width=width,
        height=height,
        resolution=resolution,
        origin=Pose2D(x=origin_x, y=origin_y, theta=0.0),
        cells=tuple(cells),
    )


def _pixel_to_cell(
    pixel: int, maxval: int, negate: bool, occupied_thresh: float, free_thresh: float
) -> CellState:
    """map_server's own pixel -> occupancy-probability -> cell conversion.

    Un-negated (the common case): a white pixel (near maxval) is free, a
    black pixel (near 0) is occupied — the same convention as the
    original ``map_server`` C++ implementation. ``negate`` flips it, for
    maps authored the other way around.
    """
    occ = (pixel / maxval) if negate else ((maxval - pixel) / maxval)
    if occ > occupied_thresh:
        return CellState.OCCUPIED
    if occ < free_thresh:
        return CellState.FREE
    return CellState.UNKNOWN


def _pixels_to_cells(
    pixels: list[int],
    width: int,
    height: int,
    negate: bool,
    occupied_thresh: float,
    free_thresh: float,
    maxval: int,
) -> list[int]:
    """Convert PGM pixels (row 0 = image top) to MapData cells (row 0 =
    map origin, at the bottom) — the two disagree about which edge is
    row 0, so this flips vertically while converting.

    Vectorised because real deployment maps are large: the contract's own
    warehouse is 40 x 25 m at 0.05 m, i.e. 400 000 cells, and a Python
    loop over that runs per map load. The arithmetic is exactly
    :func:`_pixel_to_cell`, which stays as the readable statement of the
    rule (and as what the tests pin).
    """
    values = np.asarray(pixels, dtype=np.float64).reshape(height, width)
    occ = (values / maxval) if negate else ((maxval - values) / maxval)
    cells = np.full((height, width), CellState.UNKNOWN.value, dtype=np.int16)
    cells[occ > occupied_thresh] = CellState.OCCUPIED.value
    cells[occ < free_thresh] = CellState.FREE.value
    return [int(value) for value in np.flipud(cells).reshape(-1)]


def _parse_pgm(data: bytes) -> tuple[int, int, int, list[int]]:
    """Parse a PGM (P5 binary or P2 ASCII) image. Returns (width, height,
    maxval, pixels) with pixels in row-major order, row 0 = image top —
    the raw PGM orientation, not yet flipped for MapData.

    Hand-rolled rather than a library: the PGM header is five whitespace-
    separated tokens (magic, width, height, maxval) followed by raw
    pixel data, simple enough that a dependency would cost more than it
    saves, and comment lines (`#...`) need explicit handling either way.
    """
    tokens, body_start = _read_pgm_header_tokens(data, count=4)
    magic, width_s, height_s, maxval_s = tokens
    if magic not in ("P5", "P2"):
        raise MapServerFormatError(f"not a PGM file (expected P5 or P2 magic, got {magic!r})")
    width, height, maxval = int(width_s), int(height_s), int(maxval_s)
    if width <= 0 or height <= 0:
        raise MapServerFormatError(f"invalid PGM dimensions: {width}x{height}")
    if maxval <= 0 or maxval > 65535:
        raise MapServerFormatError(f"invalid PGM maxval: {maxval}")

    expected = width * height
    if magic == "P5":
        body = data[body_start:]
        step = 2 if maxval > 255 else 1
        if len(body) < expected * step:
            raise MapServerFormatError(
                f"PGM body too short: expected {expected * step} bytes, got {len(body)}"
            )
        if step == 1:
            pixels = list(body[:expected])
        else:
            pixels = [(body[i] << 8) | body[i + 1] for i in range(0, expected * step, step)]
    else:  # P2: whitespace-separated ASCII integers
        values = data[body_start:].split()
        if len(values) < expected:
            raise MapServerFormatError(
                f"PGM body too short: expected {expected} values, got {len(values)}"
            )
        pixels = [int(v) for v in values[:expected]]
    return width, height, maxval, pixels


def _read_pgm_header_tokens(data: bytes, count: int) -> tuple[list[str], int]:
    """Read whitespace-separated header tokens, skipping ``#`` comment
    lines exactly as the PGM format spec requires. Returns the tokens
    and the byte offset where pixel data begins (right after the single
    whitespace character that must follow the maxval token)."""
    tokens: list[str] = []
    i = 0
    n = len(data)
    while len(tokens) < count:
        while i < n and data[i : i + 1].isspace():
            i += 1
        if i < n and data[i : i + 1] == b"#":
            while i < n and data[i] != 0x0A:  # skip to end of line
                i += 1
            continue
        start = i
        while i < n and not data[i : i + 1].isspace():
            i += 1
        if start == i:
            raise MapServerFormatError("truncated PGM header")
        tokens.append(data[start:i].decode("ascii", errors="replace"))
    if i >= n:
        raise MapServerFormatError("truncated PGM header")
    return tokens, i + 1  # skip the single separator byte before pixel data


__all__ = ["KNOWN_MODES", "SUPPORTED_MODES", "MapServerFormatError", "load_map_server"]
