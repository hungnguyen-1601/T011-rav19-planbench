"""A controller on the far side of a pipe.

**It imports nothing from the platform.** No ``LocalPlanResult``, no
``SimAction``, no schemas — it returns a plain mapping, because a plugin
in another process may not have the host's packages installed at all,
and a proof that quietly relied on them would prove the wrong thing.

The navigation is the simplest thing that still needs its inputs: turn
toward the goal, slow for whatever the LiDAR says is close ahead. Under
``stall_ms`` it sleeps before answering, which is how the deadline and
the kill path get exercised by a plugin that is merely slow rather than
broken — the case a timeout exists for.
"""

from __future__ import annotations

import math
import time

OBSERVATION = "planbench://channel/legacy-observation@1"

#: Rays within this angle of straight ahead count as "in the way".
_AHEAD_RAD = math.pi / 6


class RemoteWanderer:
    def __init__(self, cruise_speed: float = 0.5, stall_ms: float = 0.0) -> None:
        self._cruise = cruise_speed
        self._stall_s = stall_ms / 1000.0
        self.steps = 0

    @property
    def name(self) -> str:
        return "remote_wanderer"

    def reset(self, request) -> None:
        self.steps = 0

    def step(self, request):
        if self._stall_s:
            time.sleep(self._stall_s)
        self.steps += 1

        observation = _payload(request, OBSERVATION)
        bearing = float(observation["goal_bearing"])
        ranges = observation["lidar_ranges"]

        angular = max(-1.0, min(1.0, 1.5 * bearing))
        ahead = _closest_ahead(ranges)
        linear = self._cruise * min(1.0, ahead / 1.5) * max(0.0, 1.0 - abs(bearing) / math.pi)
        return {"linear_velocity": linear, "angular_velocity": angular}


def _payload(request, capability: str):
    for envelope in request.channels:
        if envelope.capability == capability:
            return envelope.payload
    raise LookupError(f"{capability!r} was not granted to remote_wanderer")


def _closest_ahead(ranges) -> float:
    """Nearest return within a cone in front.

    Bearings are derived from the ray count rather than declared: the
    sweep is a full circle (the platform refuses any other), so index i
    sits at ``2*pi*i/n``, and the cone is the wrap-around neighbourhood
    of zero.
    """
    if not ranges:
        return math.inf
    count = len(ranges)
    closest = math.inf
    for index, distance in enumerate(ranges):
        angle = 2.0 * math.pi * index / count
        if angle > math.pi:
            angle -= 2.0 * math.pi
        if abs(angle) <= _AHEAD_RAD:
            closest = min(closest, float(distance))
    return closest
