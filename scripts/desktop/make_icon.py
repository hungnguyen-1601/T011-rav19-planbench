"""Generate `installer/planbench.ico` from code rather than from a file.

    python scripts/desktop/make_icon.py

A checked-in binary nobody can regenerate is a small liability: the day
the colours need to change, whoever picks it up has an `.ico` and no way
back to it. This is a few dozen lines of stdlib instead — `zlib` writes
the PNG, and an ICO is a header plus PNG payloads at Vista and later.

The mark: a planned route turning around an obstacle. It is the thing
the product does, at 16 pixels it still reads as a line with a bend, and
it is not another gear.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "installer" / "planbench.ico"

SIZES = (16, 32, 48, 64, 128, 256)

BACKGROUND = (16, 24, 38, 255)  # deep navy
ROUTE = (94, 200, 255, 255)  # the planned path
OBSTACLE = (244, 106, 106, 255)  # what it goes around
GOAL = (120, 235, 168, 255)  # where it ends


def _blend(base: tuple[int, int, int, int], over: tuple[int, int, int, int], alpha: float):
    a = max(0.0, min(1.0, alpha))
    return tuple(round(base[i] * (1 - a) + over[i] * a) for i in range(4))


def _disc(pixels, size, cx, cy, radius, colour) -> None:
    """A filled circle, antialiased by sampling the edge."""
    for y in range(size):
        for x in range(size):
            distance = ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
            coverage = min(1.0, max(0.0, radius + 0.5 - distance))
            if coverage > 0:
                pixels[y][x] = _blend(pixels[y][x], colour, coverage)


def _segment(pixels, size, x0, y0, x1, y1, width, colour) -> None:
    """A round-capped line, drawn by distance to the segment."""
    dx, dy = x1 - x0, y1 - y0
    length_sq = dx * dx + dy * dy or 1.0
    half = width / 2
    for y in range(size):
        for x in range(size):
            px, py = x + 0.5 - x0, y + 0.5 - y0
            t = max(0.0, min(1.0, (px * dx + py * dy) / length_sq))
            distance = ((px - t * dx) ** 2 + (py - t * dy) ** 2) ** 0.5
            coverage = min(1.0, max(0.0, half + 0.5 - distance))
            if coverage > 0:
                pixels[y][x] = _blend(pixels[y][x], colour, coverage)


def render(size: int) -> bytes:
    """One square of RGBA pixels, as raw rows."""
    u = size / 64  # the geometry below is written for 64px
    pixels = [[BACKGROUND for _ in range(size)] for _ in range(size)]

    stroke = max(1.6, 5 * u)
    # Start low-left, up around the obstacle, out to the goal at top-right.
    route = ((12, 52), (12, 34), (30, 22), (52, 22))
    for (x0, y0), (x1, y1) in zip(route, route[1:], strict=False):
        _segment(pixels, size, x0 * u, y0 * u, x1 * u, y1 * u, stroke, ROUTE)

    _disc(pixels, size, 33 * u, 42 * u, 7.5 * u, OBSTACLE)
    _disc(pixels, size, 52 * u, 22 * u, 5.5 * u, GOAL)

    rows = bytearray()
    for row in pixels:
        rows.append(0)  # PNG filter type 0
        for pixel in row:
            rows.extend(pixel)
    return bytes(rows)


def png(size: int) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(render(size), 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    images = [(size, png(size)) for size in SIZES]
    offset = 6 + 16 * len(images)
    directory = bytearray()
    body = bytearray()
    for size, data in images:
        # 256 is stored as 0 in the directory; the field is one byte.
        directory += struct.pack(
            "<BBBBHHII",
            0 if size == 256 else size,
            0 if size == 256 else size,
            0,
            0,
            1,
            32,
            len(data),
            offset,
        )
        body += data
        offset += len(data)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + bytes(directory) + bytes(body))
    print(f"wrote {TARGET} ({TARGET.stat().st_size:,} bytes, {len(images)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
