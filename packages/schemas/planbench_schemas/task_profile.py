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

from planbench_schemas.dynamic import DynamicObstacle
from planbench_schemas.geometry import Pose2D
from planbench_schemas.observations import ObservationToken, canonical_observations
from planbench_schemas.robot import RobotConfig

ClaimLevel = Literal["mission", "deployment", "robust_deployment"]

#: Ordering used to cap the effective claim at the desired one.
_CLAIM_ORDER: dict[str, int] = {"mission": 0, "deployment": 1, "robust_deployment": 2}

#: Tolerance for the mission-probability sum. Probabilities are user
#: input, often written as decimals that do not sum to exactly 1.0 in
#: binary floating point (0.40 + 0.35 + 0.25).
_PROBABILITY_SUM_TOLERANCE = 1e-6

#: Motion kinds that are pure functions of time and therefore ignore the
#: episode seed unless given a seed-derived clock offset. Listed as a set
#: rather than tested with ``isinstance`` so a new motion kind has to be
#: classified deliberately: forgetting to add one here would silently
#: reintroduce the zero-variance failure described in
#: :meth:`EnvironmentSpec._validate_obstacles`.
_TIME_DETERMINISTIC_MOTIONS = frozenset({"waypoint", "periodic", "sudden_stop"})

#: How far the RAM budget arithmetic may drift before a profile is
#: refused, as a fraction of ``total_ram_mb`` (HĐ-2.4). Rounded megabyte
#: figures in a hand-written budget will not add up to the last MB; 1%
#: absorbs that without absorbing a forgotten claimant on the board.
_RAM_BUDGET_TOLERANCE = 0.01


class EnvironmentSpec(BaseModel):
    """The environment episodes run in: static map plus moving traffic.

    The static layer is a ROS ``map_server`` pair (HĐ-2/HĐ-4). Paths are
    stored as given; resolving and loading them is the map loader's job,
    so a profile validates without touching disk.

    The moving layer lives here because HĐ-3.3 defines the evaluation
    sample set as *mission × obstacle realisation × seed*: without a
    declared traffic population there is no realisation to draw, and the
    deployment — not the candidate — is what decides how busy the site is.
    Putting it on the candidate would let one stack be evaluated in an
    empty warehouse and another at shift change.

    An environment with no dynamic obstacles is legal (a purely static
    site, or a run studying global path quality alone), but note what it
    means statistically: with deterministic planners and no moving
    traffic, every seed replays the same episode, so 300 runs carry the
    information of one. The gates are where that has to be said out loud
    (G2's bound assumes independent draws); the schema does not forbid it.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    map: str = Field(min_length=1, description="Path to the .pgm occupancy image.")
    map_yaml: str = Field(min_length=1, description="Path to the map_server .yaml metadata.")
    dynamic_obstacles: tuple[DynamicObstacle, ...] = Field(
        default=(),
        description="Moving traffic the deployment expects (people, carts, other AMRs).",
    )

    @model_validator(mode="after")
    def _validate_obstacles(self) -> EnvironmentSpec:
        """Names unique, and traffic timing must actually vary with the seed.

        The second rule is the one that matters. ``waypoint``,
        ``periodic`` and ``sudden_stop`` are pure functions of time, so
        with ``seed_time_offset = 0`` they ignore the seed entirely: 300
        seeds would replay one identical episode 300 times, report a
        variance of zero, and hand G2 a rule-of-three bound whose
        effective sample size is 1 rather than 300. The bound would then
        claim 1% when the evidence supports nothing of the sort — the
        exact direction of error a safety claim must never take
        (HĐ-7.1, HĐ-11.4).

        ``random_walk`` draws its heading from the episode seed already,
        so it needs no offset.
        """
        names = [obstacle.name for obstacle in self.dynamic_obstacles]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(
                f"dynamic obstacle names must be unique, got duplicates {duplicates}; "
                "the name is mixed into each obstacle's seed hash, so two obstacles "
                "sharing one name would move in lockstep"
            )
        frozen_in_time = sorted(
            obstacle.name
            for obstacle in self.dynamic_obstacles
            if obstacle.motion.kind in _TIME_DETERMINISTIC_MOTIONS
            and obstacle.seed_time_offset <= 0.0
        )
        if frozen_in_time:
            raise ValueError(
                f"dynamic obstacle(s) {frozen_in_time} have deterministic motion but "
                "seed_time_offset = 0, so every seed replays the identical episode. "
                "An evaluation set built from them has an effective sample size of 1, "
                "which would make G2's collision upper bound far too optimistic. Set "
                "seed_time_offset > 0 (a few seconds) so traffic timing varies per seed"
            )
        return self


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
    #: What the site is willing to pay per mission, in the currency the
    #: business profile declares. Optional and defaulted to nothing on
    #: purpose: it is the scale that ``business_adjusted`` prices
    #: engineering effort against, and a default here would be the
    #: platform inventing a budget for the customer. Absent, the money
    #: anchor does not resolve and business mode refuses rather than
    #: guesses (HĐ-8.3 law 4, HĐ-9.3).
    cost_per_mission_max: float | None = Field(default=None, gt=0)

    @property
    def n_min_evaluation_episodes(self) -> int:
        """Minimum clean runs G2 demands: ``ceil(3 / p_max)`` (HĐ-7.1).

        The quotient is rounded before ceiling so binary-float noise in
        an exact decimal (3 / 0.01 = 299.999…94) cannot inflate the
        requirement by one episode.
        """
        return math.ceil(round(3.0 / self.collision_probability_max, 6))


class RamBudgetItem(BaseModel):
    """What else is resident on the target board besides navigation.

    The four items are the contract's (HĐ-2.4); unknown keys are refused
    so a typo cannot silently drop a claimant on the RAM budget and
    inflate what navigation appears to be allowed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    os_and_middleware_mb: float = Field(ge=0)
    perception_stack_mb: float = Field(ge=0)
    localization_mapping_mb: float = Field(ge=0)
    logging_and_reserve_mb: float = Field(ge=0)

    @property
    def total_mb(self) -> float:
        return (
            self.os_and_middleware_mb
            + self.perception_stack_mb
            + self.localization_mapping_mb
            + self.logging_and_reserve_mb
        )


class HardwareSpec(BaseModel):
    """Target-board budget — the thresholds gates G4/G5 read.

    The benchmark host is faster than the target, so host measurements
    against these budgets are one-directional screening only
    (``screened_on_host``): failing here proves failure on the target,
    passing proves nothing (HĐ-7.2).

    ``available_ram_mb`` is an *allocation decision*, not a measurement
    (HĐ-2.4): it is what remains after the OS and every other stack
    sharing the board. Requiring the breakdown alongside it is what makes
    the number checkable by somebody else, and it names the place to edit
    when perception later grows. A bare ``available_ram_mb: 2048`` is a
    guess wearing a hardware label — and G5 loses its meaning if the
    threshold it compares against was invented.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    target_device: str = Field(min_length=1)
    total_ram_mb: float = Field(gt=0, description="Physical RAM on the target board.")
    ram_budget_breakdown: RamBudgetItem
    available_ram_mb: float = Field(gt=0, description="What is left for navigation.")

    @model_validator(mode="after")
    def _validate_budget(self) -> HardwareSpec:
        """``total − Σ(breakdown) == available``, within 1% (HĐ-2.4)."""
        expected = self.total_ram_mb - self.ram_budget_breakdown.total_mb
        drift = abs(expected - self.available_ram_mb)
        if drift > self.total_ram_mb * _RAM_BUDGET_TOLERANCE:
            raise ValueError(
                f"ram budget does not add up: total {self.total_ram_mb} MB minus the "
                f"breakdown ({self.ram_budget_breakdown.total_mb} MB) leaves {expected} MB, "
                f"but available_ram_mb says {self.available_ram_mb} MB (off by {drift} MB). "
                "G5 compares candidates against available_ram_mb, so an unexplained "
                "budget makes the gate meaningless"
            )
        return self


class TaskProfile(BaseModel):
    """Complete deployment question, per CONTRACTS HĐ-2.

    ``claim_level`` is the level the author *wants* to claim; what may
    actually be printed on a Decision Card comes from
    :meth:`effective_claim_level`.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: str = Field(min_length=1)
    claim_level: ClaimLevel = "mission"
    environment: EnvironmentSpec
    missions: tuple[Mission, ...] = Field(min_length=1)
    robot: TaskRobotSpec
    available_observations: tuple[ObservationToken, ...] = Field(min_length=1)
    constraints: TaskConstraints
    hardware: HardwareSpec

    @field_validator("available_observations", mode="before")
    @classmethod
    def _canonical_observations(cls, value: object) -> object:
        """Canonicalise against the closed G6 vocabulary.

        Deferred to :mod:`planbench_schemas.observations` so the
        deployment side and the candidate side cannot drift apart — a
        gate that compares tokens literally is only as good as the two
        validators feeding it.
        """
        if isinstance(value, (list, tuple)):
            return canonical_observations(
                (entry for entry in value if isinstance(entry, str)),
                field="available_observations",
            )
        return value

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
