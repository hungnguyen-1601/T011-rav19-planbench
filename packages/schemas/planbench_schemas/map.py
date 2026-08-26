"""Occupancy map schema.

Cell values follow the ROS ``nav_msgs/OccupancyGrid`` convention so the
ROS2 bridge (later phase) needs no value translation: FREE=0,
OCCUPIED=100, UNKNOWN=-1.
"""

from __future__ import annotations

import hashlib
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_schemas.geometry import EPS, Pose2D


class CellState(IntEnum):
    """Occupancy value of one grid cell (ROS occupancy grid convention)."""

    FREE = 0
    OCCUPIED = 100
    UNKNOWN = -1


_VALID_CELL_VALUES = frozenset(state.value for state in CellState)


class MapData(BaseModel):
    """Row-major occupancy grid: cell index = row * width + col.

    Cell (row 0, col 0) is the cell whose lower-left corner sits at the
    map origin; rows grow along world +y, columns along world +x.

    Rotated map origins are not supported in Phase 1A: ``origin.theta``
    must be 0 within EPS, otherwise validation fails explicitly (it is
    never silently ignored).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str
    width: int = Field(gt=0, description="Number of columns.")
    height: int = Field(gt=0, description="Number of rows.")
    resolution: float = Field(gt=0, description="Metres per cell.")
    origin: Pose2D
    cells: tuple[int, ...]

    @model_validator(mode="after")
    def _validate(self) -> MapData:
        if abs(self.origin.theta) > EPS:
            raise ValueError(
                "Rotated map origins are not supported in Phase 1A: "
                f"origin.theta must be 0 within EPS, got {self.origin.theta!r}"
            )
        expected = self.width * self.height
        if len(self.cells) != expected:
            raise ValueError(
                f"cells has {len(self.cells)} entries, expected width*height={expected}"
            )
        invalid = sorted({value for value in self.cells if value not in _VALID_CELL_VALUES})
        if invalid:
            raise ValueError(
                f"cells contains invalid values {invalid}; "
                f"allowed values are {sorted(_VALID_CELL_VALUES)}"
            )
        return self

    def checksum(self) -> str:
        """Stable SHA-256 over a canonical serialization of all fields."""
        canonical = "|".join(
            [
                self.name,
                str(self.width),
                str(self.height),
                repr(self.resolution),
                repr(self.origin.x),
                repr(self.origin.y),
                repr(self.origin.theta),
                ",".join(str(value) for value in self.cells),
            ]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
