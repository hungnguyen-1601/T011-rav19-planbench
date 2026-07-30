"""Dynamic obstacle schemas and their deterministic motion laws.

Every motion is a pure function of ``(spec, time, seed)`` — there is no
hidden state and no global RNG, so an episode replays identically from
its seed (determinism-first).

Motion kinds:

- ``waypoint``: constant-speed traversal of a polyline; ``loop`` chooses
  between cycling back to the first point and ping-ponging.
- ``periodic``: sinusoidal oscillation between two endpoints — the
  "crossing" and "bidirectional corridor" traffic pattern.
- ``random_walk``: seeded piecewise-constant heading changes; the seed
  comes from the episode, so the same seed replays the same walk.
- ``sudden_stop``: constant velocity until ``stop_time``, then parked —
  the classic emergency-brake test for a local planner.

All obstacles are circles: the simulator's collision and LiDAR layers
already handle circles exactly, and a moving polygon adds no benchmark
value at this fidelity.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_schemas.geometry import EPS, Point2D


class _MotionBase(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)


class WaypointMotion(_MotionBase):
    """Constant-speed motion along a polyline."""

    kind: Literal["waypoint"] = "waypoint"
    waypoints: tuple[Point2D, ...] = Field(min_length=2)
    speed: float = Field(gt=0, description="Metres per second along the path.")
    loop: bool = True
    ping_pong: bool = False

    @model_validator(mode="after")
    def _validate(self) -> WaypointMotion:
        for a, b in zip(self.waypoints, self.waypoints[1:], strict=False):
            if math.hypot(b.x - a.x, b.y - a.y) <= EPS:
                raise ValueError("waypoints must not repeat the same point consecutively")
        return self


class PeriodicMotion(_MotionBase):
    """Sinusoidal oscillation between two endpoints."""

    kind: Literal["periodic"] = "periodic"
    start: Point2D
    end: Point2D
    period: float = Field(gt=0, description="Seconds for a full there-and-back cycle.")
    phase: float = 0.0

    @model_validator(mode="after")
    def _validate(self) -> PeriodicMotion:
        if math.hypot(self.end.x - self.start.x, self.end.y - self.start.y) <= EPS:
            raise ValueError("periodic motion needs two distinct endpoints")
        return self


class RandomWalkMotion(_MotionBase):
    """Seeded random walk: constant speed, heading resampled every interval."""

    kind: Literal["random_walk"] = "random_walk"
    origin: Point2D
    speed: float = Field(gt=0)
    change_interval: float = Field(gt=0, description="Seconds between heading changes.")
    max_radius: float = Field(gt=0, description="Stay within this distance of origin.")
    seed_offset: int = Field(
        default=0, description="Mixed with the episode seed so obstacles differ from each other."
    )


class SuddenStopMotion(_MotionBase):
    """Constant velocity, then a permanent stop at ``stop_time``."""

    kind: Literal["sudden_stop"] = "sudden_stop"
    start: Point2D
    heading: float
    speed: float = Field(gt=0)
    stop_time: float = Field(gt=0)


Motion = Annotated[
    WaypointMotion | PeriodicMotion | RandomWalkMotion | SuddenStopMotion,
    Field(discriminator="kind"),
]


class DynamicObstacle(BaseModel):
    """A moving circular obstacle (person, cart, another AMR)."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = "obstacle"
    radius: float = Field(gt=0)
    motion: Motion


def position_at(obstacle: DynamicObstacle, time: float, seed: int) -> Point2D:
    """Where the obstacle is at ``time`` seconds, given the episode seed.

    Pure and deterministic: identical inputs give identical positions,
    and positions never depend on how the episode was stepped.
    """
    if time < 0:
        raise ValueError(f"time must be non-negative, got {time!r}")
    motion = obstacle.motion
    if isinstance(motion, WaypointMotion):
        return _waypoint_position(motion, time)
    if isinstance(motion, PeriodicMotion):
        return _periodic_position(motion, time)
    if isinstance(motion, RandomWalkMotion):
        return _random_walk_position(motion, time, seed)
    if isinstance(motion, SuddenStopMotion):
        return _sudden_stop_position(motion, time)
    raise TypeError(f"unsupported motion kind: {type(motion).__name__}")


def _waypoint_position(motion: WaypointMotion, time: float) -> Point2D:
    points = list(motion.waypoints)
    if motion.ping_pong:
        points = points + points[-2:0:-1]  # forward then back, no duplicate ends
    segments = [
        (a, b, math.hypot(b.x - a.x, b.y - a.y)) for a, b in zip(points, points[1:], strict=False)
    ]
    if motion.loop or motion.ping_pong:
        closing = math.hypot(points[0].x - points[-1].x, points[0].y - points[-1].y)
        if closing > EPS:
            segments.append((points[-1], points[0], closing))

    total = sum(length for _, _, length in segments)
    travelled = motion.speed * time
    if motion.loop or motion.ping_pong:
        travelled = travelled % total
    elif travelled >= total:
        return points[-1]  # one-shot motion parks at the far end

    for a, b, length in segments:
        if travelled <= length:
            t = travelled / length
            return Point2D(x=a.x + (b.x - a.x) * t, y=a.y + (b.y - a.y) * t)
        travelled -= length
    return points[-1]


def _periodic_position(motion: PeriodicMotion, time: float) -> Point2D:
    # 0 at the start point, 1 at the end point, back to 0 over one period.
    angle = 2.0 * math.pi * time / motion.period + motion.phase
    t = 0.5 * (1.0 - math.cos(angle))
    return Point2D(
        x=motion.start.x + (motion.end.x - motion.start.x) * t,
        y=motion.start.y + (motion.end.y - motion.start.y) * t,
    )


def _random_walk_position(motion: RandomWalkMotion, time: float, seed: int) -> Point2D:
    """Integrate seeded piecewise-constant headings up to ``time``.

    Headings come from a hash of (seed, seed_offset, interval index), so
    the walk is reproducible and independent of step size. If a step
    would leave ``max_radius``, the obstacle reflects back toward the
    origin instead of drifting away.
    """
    intervals = int(time // motion.change_interval)
    x, y = motion.origin.x, motion.origin.y
    for index in range(intervals + 1):
        elapsed = min(motion.change_interval, time - index * motion.change_interval)
        if elapsed <= 0:
            break
        heading = _hashed_angle(seed, motion.seed_offset, index)
        next_x = x + motion.speed * math.cos(heading) * elapsed
        next_y = y + motion.speed * math.sin(heading) * elapsed
        if math.hypot(next_x - motion.origin.x, next_y - motion.origin.y) > motion.max_radius:
            # Reflect: head back toward the origin for this interval.
            toward = math.atan2(motion.origin.y - y, motion.origin.x - x)
            next_x = x + motion.speed * math.cos(toward) * elapsed
            next_y = y + motion.speed * math.sin(toward) * elapsed
        x, y = next_x, next_y
    return Point2D(x=x, y=y)


def _hashed_angle(seed: int, offset: int, index: int) -> float:
    """Deterministic angle in [-pi, pi) from integer inputs (no global RNG)."""
    # splitmix64-style mixing keeps consecutive indices well separated.
    value = seed * 0x9E3779B97F4A7C15 + offset * 0xBF58476D1CE4E5B9 + index * 0x94D049BB133111EB
    value &= (1 << 64) - 1
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & ((1 << 64) - 1)
    value ^= value >> 31
    return (value / float(1 << 64)) * 2.0 * math.pi - math.pi


def _sudden_stop_position(motion: SuddenStopMotion, time: float) -> Point2D:
    elapsed = min(time, motion.stop_time)
    return Point2D(
        x=motion.start.x + motion.speed * math.cos(motion.heading) * elapsed,
        y=motion.start.y + motion.speed * math.sin(motion.heading) * elapsed,
    )
