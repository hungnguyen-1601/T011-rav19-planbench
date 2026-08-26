"""Sensor configuration schemas."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LidarConfig(BaseModel):
    """Planar LiDAR configuration.

    Ray ``i`` (0-based) points at relative angle
    ``-angle_span / 2 + i * angle_span / num_rays`` from the robot
    heading, so a full 2*pi span covers the circle without duplicating
    the first ray at the end.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    num_rays: int = Field(gt=0, description="Number of evenly spaced rays.")
    max_range: float = Field(gt=0, description="Maximum measurable range in metres.")
    angle_span: float = Field(
        default=2 * math.pi,
        gt=0,
        le=2 * math.pi,
        description=(
            "Total angular coverage in radians, centred on the robot heading. "
            "Only a full circle is supported today — see the validator below."
        ),
    )

    @model_validator(mode="after")
    def _only_a_full_circle_is_implemented(self) -> LidarConfig:
        """Refuse a partial sweep at the point it is declared.

        The simulator honours ``angle_span`` faithfully
        (``planbench_simulator.lidar.scan`` spaces its rays by
        ``angle_span / num_rays``). **The consumers do not.** Both
        ``planbench_planning.common.dwa_core.obstacle_points`` — used by
        every ``lidar_only`` candidate, including plain ``dwa`` — and the
        predictive tracker's clusterer rebuild world-frame points with a
        hard-coded ``span = 2 * pi``.

        So a deployment declaring a 180-degree scanner would get a
        correct scan spread back over the whole circle by the controller:
        every obstacle placed at the wrong bearing, and no error
        anywhere. That is a wrong answer arriving quietly, which is worth
        more care than an unimplemented feature.

        Refusing here rather than teaching the consumers is a scope
        judgement, not a preference: threading the sensor specification
        down to both controllers touches the planner protocol and the
        golden trajectories of two candidates. Until that is done, the
        honest state is that this field has one supported value, and the
        way to say so is to reject the others rather than to accept them
        and behave as though they had not been asked for.
        """
        if abs(self.angle_span - 2.0 * math.pi) > 1e-9:
            raise ValueError(
                "angle_span must be a full circle (2*pi) for now: "
                f"got {self.angle_span!r}. A partial sweep is simulated correctly but "
                "read back incorrectly — dwa_core.obstacle_points and the dwa_predictive "
                "clusterer both assume a full circle when rebuilding world-frame points, "
                "so every return would be placed at the wrong bearing with nothing "
                "raising. See KNOWN_LIMITATIONS L20."
            )
        return self


#: How far a relocalisation jump moves the believed pose, in metres.
#:
#: **Part of what the field means, not an implementation detail**, which
#: is why it lives beside the field rather than inside the noise model.
#: ``localization_jump_probability`` says *how often* the estimate jumps;
#: this says *how far*, and anything computing a safety envelope from the
#: declared noise needs both. Two copies of it — one in the simulator and
#: one in whatever bounds the error — is exactly how the controller's
#: keep-out and the planner's came to differ.
#:
#: The jump is sized against the drift so one profile field governs "how
#: wrong can this estimate be", with the jump landing at the upper end;
#: this is the floor for a deployment that declares little or no drift.
MIN_JUMP_MAGNITUDE_M = 0.25


class SensorNoise(BaseModel):
    """How badly this deployment's robot measures and executes.

    A property of the **deployment** — the site and the vehicle being
    deployed there — never of the candidate. A candidate allowed to
    declare its own noise amplitude would be choosing its own exam.

    Both amplitudes default to zero, so every profile written before this
    existed keeps its behaviour to the last float, and switching noise on
    is a deliberate change visible in the profile and on the manifest.
    Turning it on is *correcting a simulator that was more optimistic
    than reality*, and it should be expected to make results worse.

    Amplitudes follow the noise-axis table of the topic document (N5):
    LiDAR sigma 2 cm, wheel slip 2%.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    lidar_range_sigma_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Std-dev of per-ray range error, metres. Measurement only: it "
        "reaches Observation and never the collision test.",
    )
    wheel_slip_fraction: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="Std-dev of the gap between commanded and delivered velocity, as "
        "a fraction. This one does change the real motion — the robot really slipped.",
    )

    # -- added 2026-08-13 -------------------------------------------------
    #
    # Four more ways a real robot is worse than this simulator was. Every
    # one defaults to zero, so a profile written before them keeps its
    # behaviour to the last float, and switching one on is a deliberate
    # change visible in the profile and on the manifest.
    #
    # **Zero is the off switch, and there is no second one.** A separate
    # ``enabled`` flag beside an amplitude gives two ways to say "off"
    # and lets them disagree — a profile with ``enabled: false`` and a
    # declared sigma reads as noise to anybody scanning the file. A UI
    # toggle belongs in the UI, where it zeroes the field.

    localization_drift_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Peak error between where the robot is and where it believes it "
        "is, metres. Measurement only: it reaches Observation.pose and never the "
        "collision test. Slow and correlated rather than per-step noise — a pose "
        "estimate is wrong in the same direction for a while, which is why it is "
        "dangerous and why a zero-mean jitter would not model it.",
    )
    localization_jump_probability: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Chance per relocalisation window that the estimate jumps and "
        "stays wrong. Distinct from drift on purpose: a controller can ride out a "
        "slow error and cannot ride out a step change.",
    )
    lidar_dropout_probability: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="Chance a ray returns nothing. Glass, mirrors and dark surfaces "
        "do this, and a dropped return reads to a costmap as free space — which is "
        "how a real robot drives into a glass door. Reported as max range, never as "
        "zero: zero would read as an obstacle touching the sensor.",
    )
    odometry_bias_fraction: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="Std-dev of a per-episode systematic error in delivered velocity. "
        "Unlike wheel slip this is drawn ONCE and held, so it accumulates instead of "
        "averaging out — unevenly worn wheels, not a wet patch. Changes the real "
        "motion, like slip.",
    )
    command_latency_steps: int = Field(
        default=0,
        ge=0,
        description="Control steps between issuing a command and it taking effect. A "
        "real /cmd_vel arrives late; a controller tuned on an instant response is "
        "measured optimistically without it.",
    )

    @property
    def active(self) -> bool:
        return (
            self.lidar_range_sigma_m > 0.0
            or self.wheel_slip_fraction > 0.0
            or self.localization_drift_m > 0.0
            or self.localization_jump_probability > 0.0
            or self.lidar_dropout_probability > 0.0
            or self.odometry_bias_fraction > 0.0
            or self.command_latency_steps > 0
        )
