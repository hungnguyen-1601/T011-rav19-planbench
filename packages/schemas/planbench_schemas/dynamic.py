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
  the classic emergency-brake test for a local planner. Declarable
  either as a heading and a duration or as the point it stops at; see
  :class:`SuddenStopMotion` for why only the first is stored.

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
    """Constant velocity, then a permanent stop at ``stop_time``.

    **Two ways to say it, one way to store it.** A stop can be declared
    as a direction and a duration — ``heading`` and ``stop_time``, what
    every shipped profile uses — or as ``stop_point``, the place the
    obstacle comes to rest. The second is what an author means when they
    click a spot on a map, and working out the angle and the seconds by
    hand to express it is arithmetic nobody should have to do.

    ``stop_point`` is **declaration syntax, not a field**. It is
    resolved to ``heading``/``stop_time`` while the document is being
    validated and never reaches the stored model. That is deliberate and
    it is not tidiness:

    - ``_scenario_checksum`` dumps a scenario with no ``exclude_none``,
      so a new optional field would add ``stop_point: null`` to *every*
      scenario carrying a sudden stop and change its checksum — even
      though nothing about that world had changed. The module docstring
      of :mod:`planbench_schemas.task_profile` calls that orphaning
      every stored benchmark report, and the calibration entry for the
      shipped ``sudden_stop`` scenario would go stale on the spot.
    - The stored form stays the one the golden trajectories were
      recorded against, so ``position_at`` is untouched and
      ``tests/golden/dwa_trajectories.json`` cannot move.

    Exactly one description may be given. Both at once would be two
    statements free to disagree — a heading pointing north beside a stop
    point to the east — with nothing to say which the simulator should
    believe.
    """

    kind: Literal["sudden_stop"] = "sudden_stop"
    start: Point2D
    heading: float
    speed: float = Field(gt=0)
    stop_time: float = Field(gt=0)

    @model_validator(mode="before")
    @classmethod
    def _resolve_stop_point(cls, data: object) -> object:
        """Turn ``stop_point`` into the heading and duration it implies."""
        if not isinstance(data, dict) or "stop_point" not in data:
            return data
        payload = dict(data)
        target = payload.pop("stop_point")
        if target is None:
            return payload
        if payload.get("heading") is not None or payload.get("stop_time") is not None:
            raise ValueError(
                "declare a sudden stop either by stop_point or by heading and "
                "stop_time, not both: they are two descriptions of one motion "
                "and nothing decides between them when they disagree"
            )
        start = Point2D.model_validate(payload.get("start"))
        end = Point2D.model_validate(target)
        dx, dy = end.x - start.x, end.y - start.y
        distance = math.hypot(dx, dy)
        if distance <= EPS:
            raise ValueError(
                "stop_point must differ from start: an obstacle that stops "
                "where it began never moves, and no direction can be read "
                "from a zero-length step"
            )
        speed = payload.get("speed")
        if not isinstance(speed, int | float) or speed <= 0:
            # Leave the complaint about speed to the field that owns it,
            # rather than inventing a second message for the same fault.
            return {**payload, "heading": math.atan2(dy, dx)}
        payload["heading"] = math.atan2(dy, dx)
        payload["stop_time"] = distance / speed
        return payload


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
    seed_time_offset: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Seconds of seed-derived head start. Without it, deterministic "
            "motions (waypoint, periodic, sudden_stop) ignore the seed, so a "
            "multi-seed benchmark would replay the identical episode N times "
            "and report a fake variance of zero. A non-zero value shifts this "
            "obstacle's clock by a hash of (seed, clock_key) in [0, offset), "
            "which is what makes traffic timing vary across seeds. The key is "
            "seed_offset plus the name's LENGTH, not the name — see "
            "``clock_key``, and note that EnvironmentSpec refuses two "
            "obstacles that share one."
        ),
    )
    seed_offset: int = Field(
        default=0, description="Mixes into the hash so obstacles differ from each other."
    )


def max_speed(motion: Motion) -> float:
    """Fastest this law can ever move the obstacle, metres per second.

    **A declared safety bound that nobody checks is a sentence, not a
    guarantee.** A deployment stating ``v_obstacle_max = 1.0`` while one
    of its carts runs a 1.5 m/s ``WaypointMotion`` leaves the braking
    constraint wrong at precisely the place it is trusted most, and it
    fails silently: the robot brakes for traffic slower than the traffic
    it meets. This function is what lets that be refused at load.

    Every law here has a **closed-form** bound, so the check is total and
    there is no "cannot prove it" branch to reason about:

    ============  ==============================================
    Motion        Bound
    ============  ==============================================
    waypoint      ``speed``
    random_walk   ``speed`` (heading turns; the rate does not)
    sudden_stop   ``speed`` (it only ever slows, permanently)
    periodic      ``π · |end − start| / period``
    ============  ==============================================

    The periodic case is the only one worth deriving. The path is
    ``0.5·(1 − cos(2πt/T + φ))`` along the chord, whose derivative peaks
    at ``π/T`` times the chord length — at the midpoint, where a
    sinusoidal crossing is moving fastest, which is also where it is most
    likely to be in front of a robot.

    ``seed_time_offset`` shifts an obstacle's clock and never its rate,
    so a bound taken here holds for every seed.

    A future motion law reaches the explicit refusal below rather than a
    silent zero: an unproven bound must cost a deployment its safety
    claim, not be assumed generous.
    """
    if isinstance(motion, WaypointMotion | RandomWalkMotion | SuddenStopMotion):
        return motion.speed
    if isinstance(motion, PeriodicMotion):
        chord = math.hypot(motion.end.x - motion.start.x, motion.end.y - motion.start.y)
        return math.pi * chord / motion.period
    raise NotImplementedError(
        f"no closed-form speed bound for motion kind {type(motion).__name__}; "
        "a deployment declaring v_obstacle_max cannot be validated against it, so "
        "either derive the bound here or the deployment must not carry that claim"
    )


def position_at(obstacle: DynamicObstacle, time: float, seed: int) -> Point2D:
    """Where the obstacle is at ``time`` seconds, given the episode seed.

    Pure and deterministic: identical inputs give identical positions,
    and positions never depend on how the episode was stepped.
    """
    if time < 0:
        raise ValueError(f"time must be non-negative, got {time!r}")
    time = time + _seed_time_shift(obstacle, seed)
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


def clock_key(obstacle: DynamicObstacle) -> int:
    """The integer that decides this obstacle's seed-derived head start.

    **It is the name's length, not the name.** Two obstacles called
    ``cart`` and ``rack`` with the same ``seed_offset`` therefore share a
    key, and a shared key means one head start: measured at
    ``seed_time_offset = 20``, both start 4.983802 s in at seed 0 and
    19.384681 s in at seed 7, and their positions agree at every instant.
    That is the lockstep the traffic rules exist to prevent, and unique
    names do not prevent it.

    Exposed rather than inlined because ``EnvironmentSpec`` refuses two
    obstacles that share a key, and a validator that recomputed the
    formula would be free to drift from the implementation it protects.

    Hashing the name itself would be the tidier fix and was considered.
    It is a **behaviour** change: every episode whose traffic carries a
    head start would move, which includes five of the seven golden cases
    in ``tests/golden/dwa_trajectories.json`` — a fixture generated
    before ``dwa_core`` was extracted, and the only remaining evidence
    that the extraction changed nothing. Refusing the collision costs
    nobody a re-measurement; regenerating that fixture would cost the
    proof.
    """
    return obstacle.seed_offset + len(obstacle.name)


def _seed_time_shift(obstacle: DynamicObstacle, seed: int) -> float:
    """Deterministic clock offset in [0, seed_time_offset) for this seed."""
    if obstacle.seed_time_offset <= 0:
        return 0.0
    # Reuse the angle hash and map [-pi, pi) onto [0, 1).
    unit = (_hashed_angle(seed, clock_key(obstacle), 0) + math.pi) / (2.0 * math.pi)
    return unit * obstacle.seed_time_offset


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
        # **Reflect or not is decided once, from the whole interval, and
        # only then is the heading applied for the time actually elapsed.**
        #
        # Testing the *partial* step instead made the obstacle teleport.
        # ``elapsed`` grows from 0 to ``change_interval`` as time advances
        # inside the interval in progress, so a test on the partial
        # endpoint flips from "outward" to "inward" partway through — and
        # the position jumps between two extrapolations pointing opposite
        # ways, by up to ``2 · speed · elapsed``. Measured on
        # ``dynamic_warehouse`` before this was fixed: a 0.5 m/s obstacle
        # moved 1.4075 m in a single 0.05 s step, which is 28 m/s and 56x
        # its own declared speed.
        #
        # That also made the closed-form bound in HĐ-2.6 false: the
        # contract states this law's speed bound is ``speed``, and the
        # implementation exceeded it wildly. Deciding on the full interval
        # restores it — within any interval the obstacle travels along one
        # heading at exactly ``speed``, so position is continuous in time
        # and the bound is exact.
        full_x = x + motion.speed * math.cos(heading) * motion.change_interval
        full_y = y + motion.speed * math.sin(heading) * motion.change_interval
        if math.hypot(full_x - motion.origin.x, full_y - motion.origin.y) > motion.max_radius:
            # Reflect: head back toward the origin for this interval.
            heading = math.atan2(motion.origin.y - y, motion.origin.x - x)
        x = x + motion.speed * math.cos(heading) * elapsed
        y = y + motion.speed * math.sin(heading) * elapsed
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
