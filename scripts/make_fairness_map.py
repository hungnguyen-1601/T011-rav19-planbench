"""Generate ``maps/open_hall.{pgm,yaml}`` — the fairness reference map.

**This map exists to test the platform, not the planners.** Everything about
it is chosen so that a difference between two candidates can only come from
the candidates:

- **Easy.** 24 x 16 m of open floor with one block in the middle. Both ways
  around are 5.5 m wide against a 0.52 m robot, so no stack is defeated by
  geometry and nobody has to squeeze past anything. A map that fails a
  candidate tells you about the map.
- **Mirror-symmetric about the mission line.** The block is centred on
  ``y = 8.0``, which is exactly the straight line from start to goal. Going
  left of it and going right of it are the same length and the same width,
  so a planner biased toward one side gains nothing. On an asymmetric map,
  "A* beat RRT*" could just mean "A* happened to prefer the shorter side".
- **One decision, not none.** An empty room would let every planner drive
  the same straight line and measure nothing. One block forces a choice
  while keeping the choice symmetric.

The symmetry is asserted by ``tests/test_fairness.py`` rather than trusted,
because it is the property the whole map is for.

Usage::

    python scripts/make_fairness_map.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPS = REPO_ROOT / "maps"

RESOLUTION = 0.05
WIDTH_M, HEIGHT_M = 24.0, 16.0
WIDTH = int(round(WIDTH_M / RESOLUTION))
HEIGHT = int(round(HEIGHT_M / RESOLUTION))

#: Wall thickness. Enough that no LiDAR ray slips between cells.
WALL_M = 0.30

#: The single block, centred on the mission line at y = 8.0.
BLOCK_X0, BLOCK_X1 = 10.0, 14.0
BLOCK_Y0, BLOCK_Y1 = 6.5, 9.5

FREE, OCCUPIED = 254, 0


def build() -> bytearray:
    pixels = bytearray([FREE]) * (WIDTH * HEIGHT)

    def cell(metres: float) -> int:
        """Metres to cell index, rounded — never truncated.

        ``int(15.7 / 0.05)`` is 313, not 314: the quotient lands on
        313.9999999999999. Truncating it made the top wall seven cells
        thick and the bottom wall six, so this "symmetric" hall was 5 cm
        wider on one side than the other — which is exactly the kind of
        bias the map exists to rule out, and it would have favoured
        whichever planner prefers that side while looking like a
        property of the planner.
        """
        return int(round(metres / RESOLUTION))

    def fill(x0: float, x1: float, y0: float, y1: float) -> None:
        for row in range(cell(y0), cell(y1)):
            for col in range(cell(x0), cell(x1)):
                # PGM rows run top-down; the occupancy grid runs bottom-up.
                pixels[(HEIGHT - 1 - row) * WIDTH + col] = OCCUPIED

    fill(0.0, WIDTH_M, 0.0, WALL_M)
    fill(0.0, WIDTH_M, HEIGHT_M - WALL_M, HEIGHT_M)
    fill(0.0, WALL_M, 0.0, HEIGHT_M)
    fill(WIDTH_M - WALL_M, WIDTH_M, 0.0, HEIGHT_M)
    fill(BLOCK_X0, BLOCK_X1, BLOCK_Y0, BLOCK_Y1)
    return pixels


def main() -> None:
    MAPS.mkdir(exist_ok=True)
    image = MAPS / "open_hall.pgm"
    image.write_bytes(f"P5\n{WIDTH} {HEIGHT}\n255\n".encode("ascii") + bytes(build()))

    (MAPS / "open_hall.yaml").write_text(
        yaml.safe_dump(
            {
                "image": "open_hall.pgm",
                "resolution": RESOLUTION,
                "origin": [0.0, 0.0, 0.0],
                "negate": 0,
                "occupied_thresh": 0.65,
                "free_thresh": 0.196,
                "mode": "trinary",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"wrote {image} ({WIDTH}x{HEIGHT} @ {RESOLUTION} m = {WIDTH_M}x{HEIGHT_M} m)")
    print(f"  block x {BLOCK_X0}-{BLOCK_X1}, y {BLOCK_Y0}-{BLOCK_Y1}, centred on y = 8.0")
    print(f"  free width each side of the block: {BLOCK_Y0 - WALL_M:.2f} m")


if __name__ == "__main__":
    main()
