"""Generate the reference deployment map: ``maps/warehouse_a.{pgm,yaml}``.

The contract's worked example (HĐ-2.1, and the run-through in §6.2 of the
topic document) is a 40 x 25 m warehouse at 0.05 m resolution with a
0.68 m narrowest shelf gap and a 0.52 m wide robot. Everything downstream
quotes those numbers — the memory estimate of §7.3 assumes 400 000 cells,
G1's no-path rate assumes the aisles are actually passable — so the map
they refer to has to exist rather than be described.

Committed as a generator plus its output: the ``.pgm`` is what the loader
reads, and this file is what makes the walls auditable. Regenerate with

    python scripts/make_warehouse_map.py

Layout (metres, origin at the lower-left corner of the map):

    +---------------------------------------------------+ 25
    |  receiving                              packing    |
    |    +-----+   +-----+   +-----+   +-----+           |
    |    |shelf|   |shelf|   |shelf|   |shelf|           |   shelf blocks,
    |    +-----+   +-----+   +-----+   +-----+           |   0.68 m gaps
    |                                                    |
    +---------------------------------------------------+ 0
    0                                                   40
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

RESOLUTION = 0.05
WIDTH_M = 40.0
HEIGHT_M = 25.0
WALL_M = 0.30

#: Four shelf blocks with 0.68 m aisles between them — the narrowest gap
#: the contract's example quotes, and the reason a 0.52 m robot is a
#: tight but legal fit.
SHELF_ROWS = ((6.0, 11.0), (14.0, 19.0))
SHELF_X_START = 6.0
SHELF_LENGTH_M = 6.6
AISLE_M = 0.68
SHELF_COUNT = 4

OCCUPIED_PIXEL = 0
FREE_PIXEL = 254

MAPS_DIR = Path(__file__).resolve().parents[1] / "maps"


def _fill(pixels: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> None:
    """Mark a world-coordinate rectangle occupied.

    Rows are flipped on write, so this works in map coordinates (y up)
    and the caller never thinks in image rows.
    """
    col0 = max(int(x0 / RESOLUTION), 0)
    col1 = min(int(np.ceil(x1 / RESOLUTION)), pixels.shape[1])
    row0 = max(int(y0 / RESOLUTION), 0)
    row1 = min(int(np.ceil(y1 / RESOLUTION)), pixels.shape[0])
    pixels[row0:row1, col0:col1] = OCCUPIED_PIXEL


def build_pixels() -> np.ndarray:
    width = int(WIDTH_M / RESOLUTION)
    height = int(HEIGHT_M / RESOLUTION)
    pixels = np.full((height, width), FREE_PIXEL, dtype=np.uint8)

    # Perimeter walls.
    _fill(pixels, 0.0, 0.0, WIDTH_M, WALL_M)
    _fill(pixels, 0.0, HEIGHT_M - WALL_M, WIDTH_M, HEIGHT_M)
    _fill(pixels, 0.0, 0.0, WALL_M, HEIGHT_M)
    _fill(pixels, WIDTH_M - WALL_M, 0.0, WIDTH_M, HEIGHT_M)

    # Shelf blocks: two banks, four blocks each, 0.68 m between blocks.
    for y0, y1 in SHELF_ROWS:
        x = SHELF_X_START
        for _ in range(SHELF_COUNT):
            _fill(pixels, x, y0, x + SHELF_LENGTH_M, y1)
            x += SHELF_LENGTH_M + AISLE_M

    return pixels


def write_pgm(path: Path, pixels: np.ndarray) -> None:
    """Write a binary P5 PGM. Image row 0 is the top, map row 0 the
    bottom, so the array is flipped on the way out — the mirror of what
    :func:`planbench_schemas.map_io._pixels_to_cells` does on the way in.
    """
    height, width = pixels.shape
    header = f"P5\n{width} {height}\n255\n".encode("ascii")
    path.write_bytes(header + np.flipud(pixels).tobytes())


def write_yaml(path: Path, image_name: str) -> None:
    path.write_text(
        "\n".join(
            [
                f"image: {image_name}",
                f"resolution: {RESOLUTION}",
                "origin: [0.0, 0.0, 0.0]",
                "negate: 0",
                "occupied_thresh: 0.65",
                "free_thresh: 0.196",
                "mode: trinary",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    pixels = build_pixels()
    image_path = MAPS_DIR / "warehouse_a.pgm"
    write_pgm(image_path, pixels)
    write_yaml(MAPS_DIR / "warehouse_a.yaml", image_path.name)
    occupied = int((pixels == OCCUPIED_PIXEL).sum())
    print(
        f"wrote {image_path} ({pixels.shape[1]}x{pixels.shape[0]} px, "
        f"{occupied / pixels.size:.1%} occupied)"
    )


if __name__ == "__main__":
    main()
