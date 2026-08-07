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
"""

from __future__ import annotations

import yaml

from planbench_schemas.geometry import Pose2D
from planbench_schemas.map import CellState, MapData


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

    negate = bool(int(meta.get("negate", 0)))
    occupied_thresh = float(meta.get("occupied_thresh", 0.65))
    free_thresh = float(meta.get("free_thresh", 0.196))

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
    row 0, so this flips vertically while converting."""
    cells = [0] * (width * height)
    for pgm_row in range(height):
        map_row = height - 1 - pgm_row
        for col in range(width):
            pixel = pixels[pgm_row * width + col]
            cell = _pixel_to_cell(pixel, maxval, negate, occupied_thresh, free_thresh)
            cells[map_row * width + col] = cell.value
    return cells


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


__all__ = ["MapServerFormatError", "load_map_server"]
