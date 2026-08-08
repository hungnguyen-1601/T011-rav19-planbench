"""Task / deployment profile schema (CONTRACTS HĐ-2).

A ``TaskProfile`` is the *question* the selector answers: which
candidate should this deployment use. It bundles the environment, the
mission(s), the robot, the observations the site actually has, the
operational constraints and the hardware budget. Every feasibility-gate
threshold (G1–G6) is read from here — gates must never hardcode a
threshold (HĐ-7).

Two rules from the contract are enforced in code rather than prose:

- ``claim_level`` in the input is only the *desired* level. The level a
  Decision Card may print is computed from the data actually provided
  (``effective_claim_level``): one mission can never support a
  deployment-level claim, and a robust claim additionally requires that
  a neighborhood evaluation was run (HĐ-2.2).
- ``n_min_evaluation_episodes`` derives from the accepted collision
  risk by the rule of three (HĐ-7.1): observing zero collisions in N
  runs only bounds the true probability by ~3/N at 95% confidence, so
  the constraint fixes the minimum N — not the other way round.

This schema deliberately does not touch ``Scenario``/``RobotConfig``:
adding fields to those would change ``_scenario_checksum`` and orphan
every stored benchmark report. ``TaskRobotSpec`` extends ``RobotConfig``
with the deployment's control period instead.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig

ClaimLevel = Literal["mission", "deployment", "robust_deployment"]

#: Ordering used to cap the effective claim at the desired one.
_CLAIM_ORDER: dict[str, int] = {"mission": 0, "deployment": 1, "robust_deployment": 2}

#: Tolerance for the mission-probability sum. Probabilities are user
#: input, often written as decimals that do not sum to exactly 1.0 in
#: binary floating point (0.40 + 0.35 + 0.25).
_PROBABILITY_SUM_TOLERANCE = 1e-6


class EnvironmentRef(BaseModel):
    """Where the map lives, in ROS ``map_server`` format (HĐ-2/HĐ-4).

    Paths are stored as given; resolving and loading them is the map
    loader's job, so a profile can be validated without touching disk.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    map: str = Field(min_length=1, description="Path to the .pgm occupancy image.")
    map_yaml: str = Field(min_length=1, description="Path to the map_server .yaml metadata.")


class Mission(BaseModel):
    """One start/goal pair with its share of the deployment's workload."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: str = Field(min_length=1)
    start: Pose2D
    goal: Pose2D
    probability: float = Field(default=1.0, gt=0, le=1.0)

    @field_validator("start", "goal", mode="before")
    @classmethod
    def _pose_from_triplet(cls, value: object) -> object:
        """Accept the contract's ``[x, y, theta]`` YAML form."""
        if isinstance(value, (list, tuple)) and len(value) == 3:
            x, y, theta = value
            return {"x": x, "y": y, "theta": theta}
        return value


class TaskRobotSpec(RobotConfig):
    """Deployment robot: physical limits plus the control-loop budget.

    ``control_period`` is the deployment's T_cycle — the wall-clock
    budget one control step has on the target board. It is the source
    of gate G4's threshold and of the latency anchors, which is why it
    lives here and not on the candidate: the candidate declares how fast
    it *is*, the deployment declares how fast it *must be*.
    """

    type: Literal["differential_drive"] = "differential_drive"
    control_period: float = Field(gt=0, description="Control loop period, seconds (T_cycle).")

    @property
    def t_cycle_ms(self) -> float:
        """G4 threshold in the unit latency metrics are reported in."""
        return self.control_period * 1000.0


class TaskConstraints(BaseModel):
    """Operational constraints — the thresholds gates G1–G3 read.

    ``collision_probability_max`` is the accepted collision risk; the
    minimum number of clean evaluation episodes follows from it (rule
    of three), see :attr:`n_min_evaluation_episodes`.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    success_rate_min: float = Field(gt=0, le=1.0)
    collision_probability_max: float = Field(gt=0, le=1.0)
    no_path_rate_max: float = Field(default=0.02, ge=0, le=1.0)
    goal_tolerance_m: float = Field(gt=0)
    goal_tolerance_rad: float = Field(gt=0)
    episode_timeout_s: float = Field(gt=0)
    stuck_threshold_s: float = Field(gt=0)
    clearance_warning_m: float = Field(ge=0, description="Near-miss counting threshold.")

    @property
    def n_min_evaluation_episodes(self) -> int:
        """Minimum clean runs G2 demands: ``ceil(3 / p_max)`` (HĐ-7.1).

        The quotient is rounded before ceiling so binary-float noise in
        an exact decimal (3 / 0.01 = 299.999…94) cannot inflate the
        requirement by one episode.
        """
        return math.ceil(round(3.0 / self.collision_probability_max, 6))


class HardwareSpec(BaseModel):
    """Target-board budget — the thresholds gates G4/G5 read.

    The benchmark host is faster than the target, so host measurements
    against these budgets are one-directional screening only
    (``screened_on_host``): failing here proves failure on the target,
    passing proves nothing (HĐ-7.2).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    target_device: str = Field(min_length=1)
    available_ram_mb: float = Field(gt=0)


class TaskProfile(BaseModel):
    """Complete deployment question, per CONTRACTS HĐ-2.

    ``claim_level`` is the level the author *wants* to claim; what may
    actually be printed on a Decision Card comes from
    :meth:`effective_claim_level`.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: str = Field(min_length=1)
    claim_level: ClaimLevel = "mission"
    environment: EnvironmentRef
    missions: tuple[Mission, ...] = Field(min_length=1)
    robot: TaskRobotSpec
    available_observations: tuple[str, ...] = Field(min_length=1)
    constraints: TaskConstraints
    hardware: HardwareSpec

    @field_validator("available_observations")
    @classmethod
    def _canonical_observations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Sorted, deduplicated, no blanks — G6 is a set-subset check,
        and two spellings of the same set must compare equal."""
        cleaned = {entry.strip() for entry in value}
        if "" in cleaned:
            raise ValueError("available_observations must not contain blank entries")
        return tuple(sorted(cleaned))

    @model_validator(mode="after")
    def _validate_missions(self) -> TaskProfile:
        ids = [mission.id for mission in self.missions]
        if len(set(ids)) != len(ids):
            raise ValueError(f"mission ids must be unique, got {ids}")
        total = sum(mission.probability for mission in self.missions)
        if not math.isclose(total, 1.0, abs_tol=_PROBABILITY_SUM_TOLERANCE):
            raise ValueError(f"mission probabilities must sum to 1.0, got {total}")
        return self

    def effective_claim_level(self, *, neighborhood_evaluated: bool = False) -> ClaimLevel:
        """The claim the data supports, capped at the desired level.

        HĐ-2.2: computed by the system, never taken from the input.
        One mission ⇒ ``mission``. Several ⇒ ``deployment``. Robust
        additionally requires a neighborhood evaluation. The desired
        ``claim_level`` acts only as a cap — an author may claim *less*
        than the data supports, never more.
        """
        if len(self.missions) == 1:
            supported: ClaimLevel = "mission"
        elif neighborhood_evaluated:
            supported = "robust_deployment"
        else:
            supported = "deployment"
        if _CLAIM_ORDER[self.claim_level] < _CLAIM_ORDER[supported]:
            return self.claim_level
        return supported
