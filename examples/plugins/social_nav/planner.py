"""Steer to the goal while giving moving obstacles a wide berth.

**This plugin requires ``human_state_estimates``, and that is the point
of the proof.** No stack in the registry has ever required it: every
candidate the platform has run declared ``lidar_2d`` and nothing else,
so G6's observation pricing has never had to price a real difference.
This is the first thing that asks for something more.

It is also why the proof is *not* a production candidate. In this MVP
the only source of that capability is ``GroundTruthTrackProvider``,
whose provenance is ``oracle`` — so an execution feeding this plugin is
oracle-class evidence (§5.10), refused at admission by a production
fairness policy and barred from every production scoring path. The
plugin measures an upper bound: *what would a navigator do if the
tracking problem were already solved?* That is a real question — it is
the one P4 asked and answered — and it is not a deployment
recommendation.

The navigation itself is deliberately simple. A proof of the data plane
should be readable, and a clever controller here would invite reading it
as a candidate.
"""

from __future__ import annotations

import math

HUMAN_STATE_ESTIMATES = "human_state_estimates"
OBSERVATION = "planbench://channel/legacy-observation@1"

#: Obstacles predicted to come within this distance are worth avoiding.
_PERSONAL_SPACE_M = 1.2
#: How far ahead the prediction looks. Short: constant velocity stops
#: being true the moment anything turns.
_LOOKAHEAD_S = 1.5


class SocialNavPlanner:
    """Local plugin: goal-seeking with a berth around predicted motion."""

    def __init__(self, cruise_speed: float = 0.6, turn_gain: float = 1.5) -> None:
        self._cruise = cruise_speed
        self._turn_gain = turn_gain
        self._robot: dict | None = None
        self.diagnostics: dict[str, int] = {"yields": 0, "steps": 0}

    @property
    def name(self) -> str:
        return "social_nav"

    @property
    def control_period(self) -> float | None:
        return None

    def reset(self, request) -> None:
        self._robot = request.robot.get("robot_config")
        self.diagnostics = {"yields": 0, "steps": 0}

    def step(self, request):
        from planbench_planning.common.local_base import LocalPlanResult
        from planbench_schemas.robot import SimAction

        self.diagnostics["steps"] += 1
        observation = _payload(request, OBSERVATION)
        tracks = _payload(request, HUMAN_STATE_ESTIMATES) or ()

        bearing = observation.goal_bearing
        angular = max(-1.0, min(1.0, self._turn_gain * bearing))

        # Slow for anything predicted to cross the robot's personal space.
        linear = self._cruise
        closest = _closest_predicted_gap(observation, tracks)
        if closest < _PERSONAL_SPACE_M:
            self.diagnostics["yields"] += 1
            linear = self._cruise * max(0.0, closest / _PERSONAL_SPACE_M)

        # Turning hard means not driving hard, whatever the traffic says.
        linear *= max(0.0, 1.0 - abs(bearing) / math.pi)

        return LocalPlanResult(
            action=SimAction(linear_velocity=linear, angular_velocity=angular),
            cost_components={"closest_predicted_gap": closest},
        )


def _payload(request, capability: str):
    for envelope in request.channels:
        if envelope.capability == capability:
            return envelope.payload
    raise LookupError(f"{capability!r} was not granted to social_nav")


def _closest_predicted_gap(observation, tracks) -> float:
    """Nearest approach over the lookahead, assuming constant velocity.

    Sampled rather than solved: the closed form is not hard, but it is
    one more thing to get wrong in a file whose job is to demonstrate the
    data plane rather than the mathematics.
    """
    if not tracks:
        return math.inf
    pose = observation.pose
    best = math.inf
    for step in range(6):
        horizon = _LOOKAHEAD_S * step / 5.0
        for track in tracks:
            future_x = track["x"] + track["vx"] * horizon
            future_y = track["y"] + track["vy"] * horizon
            gap = math.hypot(future_x - pose.x, future_y - pose.y) - track["radius"]
            best = min(best, gap)
    return best
