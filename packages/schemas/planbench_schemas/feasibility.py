"""The hard feasible set: one definition, owned by the deployment.

**Why this module exists.** A robot once stood 0.31 m from a cart, which
its own controller called legal, inside a 0.61 m ring its planner called
forbidden — and replanned 55 times without moving. The two layers held
two different answers to "may the robot be here", and the whole 0.30 m
difference was a grid-quantisation term: a property of the *map's
resolution*, not of the world.

Three layers of boundary, and **"who owns it" is a different axis from
"hard or soft"**:

======================  ==================================  =========  ============
Layer                   Meaning                             Hard/soft  Owner
======================  ==================================  =========  ============
Collision footprint     certain geometric contact           hard       robot/engine
Safety envelope         position the estimate may be wrong  hard       **deployment**
Comfort / preference    wants more room than it needs       soft       candidate
======================  ==================================  =========  ============

The contract between the global planner and the local controller follows
from that split:

* **L1** — global may only return paths inside the hard feasible set the
  local controller can execute.
* **L2** — local may be *more* cautious by scoring cost higher, but may
  **not** silently shrink the hard set with a candidate parameter the
  global planner never sees.
* **L3** — every layer shares the footprint and this envelope.
* **L4** — an integration test drives both stacks and requires every
  global path to pass the local feasibility check.

L1 and L2 stop pulling against each other exactly because the extra
caution lives in the soft layer. If a candidate's caution were a hard
refusal, L1 would force the two keep-outs equal and the split would be
pointless.

**L2 is enforced structurally rather than by discipline**: every function
here takes ``(RobotConfig, SafetyEnvelope)`` and none of them takes a
candidate configuration. A controller that wanted to narrow the hard set
has no argument to do it with.

**Grid quantisation belongs to none of the three layers.** It is an
artifact of representing a continuous set on cells. The hard set is
defined continuously here; a grid may be a conservative approximation of
it, and the conservatism it adds belongs in cost, never in prohibition.
Anything validating L1 or L4 must ask *this* module, not the grid, or it
will confuse "infeasible" with "coarsely rasterised".
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.robot import RobotConfig
from planbench_schemas.sensor import MIN_JUMP_MAGNITUDE_M, SensorNoise

__all__ = [
    "SafetyEnvelope",
    "hard_clearance",
    "reaction_distance",
    "stopping_distance",
]


class SafetyEnvelope(BaseModel):
    """How far the robot may be from where it believes it is.

    **Derived, not chosen.** Every field a deployment already declares
    about its sensing is enough to bound this, so the platform does not
    ask anybody for another number — the same reason ``N_min`` is a
    consequence of the accepted collision risk rather than a setting.

    Only *position* uncertainty lives here. Braking is deliberately
    excluded: it is proportional to the square of the speed, and folding
    it into a static envelope would forbid a robot creeping past an
    obstacle at 0.1 m/s exactly as hard as one charging it at 0.8 m/s —
    0.64 m of margin against a real requirement of 0.01 m. Braking is a
    *dynamic* constraint; see :func:`stopping_distance`.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    position_uncertainty_m: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Worst-case distance between the robot's true pose and the pose it "
            "believes it has. Bounds the localisation error a deployment declares."
        ),
    )

    @classmethod
    def for_noise(cls, noise: SensorNoise) -> SafetyEnvelope:
        """The envelope the declared sensing implies.

        **Worst case, not a percentile.** A percentile would need
        somebody to choose which one, and a hard constraint that is
        exceeded five per cent of the time is not hard. Worst case is the
        only bound with no free parameter in it.

        Two contributors, and only these two:

        * **Drift** is a weighted sum of sinusoids whose weights sum to
          one, so each axis is bounded by the declared amplitude and both
          axes together by ``amplitude × √2``.
        * **A jump** adds a step change of
          :data:`~planbench_schemas.sensor.MIN_JUMP_MAGNITUDE_M` or the
          drift, whichever is larger. It is counted whenever the
          probability is non-zero: over an episode of many relocalisation
          windows, "unlikely per window" is "it happens".

        Wheel slip is **not** here. Slip moves the robot for real, so it
        is already inside the true pose the collision test reads; it
        widens no gap between truth and belief. Command latency is not
        here either — it costs distance proportional to speed, which is
        :func:`reaction_distance`.
        """
        drift = noise.localization_drift_m
        bound = drift * math.sqrt(2.0)
        if noise.localization_jump_probability > 0.0:
            bound += max(drift, MIN_JUMP_MAGNITUDE_M)
        return cls(position_uncertainty_m=bound)


def hard_clearance(robot: RobotConfig, envelope: SafetyEnvelope) -> float:
    """Smallest distance from the robot's *centre* to an obstacle surface.

    Below this the robot may be in contact and nobody could tell: the
    footprint accounts for the body, the envelope for the possibility
    that the body is not where the estimate says.

    **This is the number both layers must agree on.** The planner may
    keep further away and the controller may prefer to — neither may go
    inside it.

    Note the signature: ``RobotConfig`` and ``SafetyEnvelope``, both
    deployment-owned. No candidate configuration reaches this, which is
    L2 enforced by the type system rather than by a rule somebody has to
    remember.
    """
    return robot.radius + envelope.position_uncertainty_m


def stopping_distance(speed: float, robot: RobotConfig) -> float:
    """How far the robot travels before it can come to rest.

    ``v² / (2a)`` — the classic admissibility term (Fox, Burgard and
    Thrun, 1997), and the half of "can I be here" that a static envelope
    cannot express, because it depends on how fast the robot is going.

    A controller that checks only whether its *rollout* collides is not
    checking this: a trajectory can clear every obstacle inside a
    one-second horizon and still be travelling too fast to stop before
    the one just beyond it.
    """
    if speed <= 0.0:
        return 0.0
    return (speed * speed) / (2.0 * robot.max_linear_acceleration)


def reaction_distance(speed: float, control_period: float, latency_steps: int = 0) -> float:
    """Distance covered before a new command can take effect.

    One control period at the current speed, plus any actuation latency
    the deployment declares. It is the gap between deciding to stop and
    the wheels beginning to: braking from the moment of decision would
    assume a robot that reacts instantly, which is the assumption
    ``command_latency_steps`` exists to remove.
    """
    if speed <= 0.0:
        return 0.0
    return speed * control_period * (1 + max(0, latency_steps))
