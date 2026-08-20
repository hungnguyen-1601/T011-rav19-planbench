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

This schema mostly does not touch ``Scenario``/``RobotConfig``: adding
fields to those changes ``_scenario_checksum`` and orphans every stored
benchmark report. ``TaskRobotSpec`` extends ``RobotConfig`` with the
deployment's control period instead of pushing it down.

**One deliberate exception, added with ``sensor_noise``.** That rule is
about not letting *bookkeeping* leak into the fairness identity; noise is
not bookkeeping, it is the episode's physics. Two runs at the same seed
under different sigma really are two different worlds, so the checksum
*should* separate them — excluding it would be the bug. The accepted cost
is that every stored scenario's checksum moved, which stales the P03
difficulty cache; that cache is keyed to the old scenario library and
holds no entry for any contract-era profile, so nothing in use was lost.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from planbench_schemas.dynamic import DynamicObstacle, clock_key, max_speed
from planbench_schemas.geometry import Pose2D
from planbench_schemas.observations import ObservationToken, canonical_observations
from planbench_schemas.recovery import NO_RECOVERY, RecoveryConfig
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.robot import RobotConfig
from planbench_schemas.sensor import SensorNoise

ClaimLevel = Literal["mission", "deployment", "robust_deployment"]

#: What a deployment *is for*, declared rather than inferred.
#:
#: Q1 of plan 08-12 found a third kind: ``open_hall`` is neither a
#: customer site nor merely a symmetric instrument, but an **acceptance
#: deployment** — a place where one failure is a diagnostic symptom, not
#: a statistic, which is why its ``success_rate_min`` is 1.00. Until now
#: that finding lived only in a comment.
#:
#: It is declared because the alternative is inferring the role from
#: ``success_rate_min == 1.0``, and HĐ-1.4 already refused that shape of
#: reasoning for ``experiment_scope``: the day somebody declares a real
#: warehouse at 1.00, it would silently acquire a role nobody chose.
DeploymentRole = Literal["acceptance", "customer", "instrument"]

#: Ordering used to cap the effective claim at the desired one.
_CLAIM_ORDER: dict[str, int] = {"mission": 0, "deployment": 1, "robust_deployment": 2}

#: Episodes every candidate runs before early stopping may retire it.
#:
#: The floor buys a *distribution*, not a gate verdict. B1 is the worked
#: example: both stacks were doomed at episode 12 of 600, and stopping
#: there would have cost the three findings that actually mattered —
#: ``n_distinct = 85/245``, the 78% paired disagreement, and the ~15%
#: collision rate. Thirty episodes is enough to see the shape of a
#: failure and cheap against 300.
DEFAULT_MIN_EPISODES_BEFORE_STOP = 30

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
    #: How badly the robot measures and executes at this site.
    #:
    #: Zero by default, so every profile written before this existed
    #: keeps its behaviour to the last float. Switching it on is a
    #: deliberate change, visible here and on the manifest, and it is a
    #: *fidelity correction* rather than an improvement: a simulator with
    #: no noise is more optimistic than reality, and the price of that
    #: optimism was a collision bound resting on a single episode driven
    #: once per seed.
    #:
    #: It belongs to ``environment`` because it describes the site and
    #: the vehicle deployed there, not the algorithm being judged.
    sensor_noise: SensorNoise = Field(default_factory=SensorNoise)
    #: Fastest anything at this site may close on the robot, m/s.
    #:
    #: **Layer 2, and it fixes a hole with a reproducible collision.**
    #: The admissible-velocity criterion bounds speed by what the robot
    #: can brake before the *scan it has now*, which is the same as
    #: promising it can stop before an obstacle that is **standing**. P0
    #: measured what that omits: a cart driving head-on at 0.2 m/s —
    #: slower than a person strolling — puts the robot through 6 to 25
    #: consecutive steps its own criterion calls admissible and ends the
    #: episode in contact, under the shipped weights as readily as under
    #: adversarial ones. Declaring this number restores the guarantee for
    #: **every** candidate equally; see
    #: :func:`~planbench_schemas.feasibility.admissible_speed`.
    #:
    #: **Three meanings, and ``None`` is not one of the numbers.**
    #:
    #: * ``None`` — not declared. Behaviour is byte-identical to before
    #:   this field existed, and the deployment carries **no** braking
    #:   claim against moving traffic; the manifest says so. Nothing is
    #:   validated, because there is no claim to check.
    #: * a positive number — declared, and checked against every motion
    #:   law below at load.
    #: * ``0.0`` — the assertion that *nothing here moves*. Legal, and
    #:   refused if the environment declares a moving obstacle. A wrong
    #:   assertion is worse than an absent one.
    #:
    #: ``None`` rather than ``0.0`` as the default, and the difference is
    #: not cosmetic: every profile written before this field exists
    #: declares moving traffic, so a ``0.0`` default would fail its own
    #: validator on load and break every stored deployment. Precedent:
    #: ``robustness_margin: float | None``, where null has the defined
    #: meaning "not measured" rather than "measured as zero".
    #:
    #: Declared on the deployment and not on the candidate for the same
    #: reason as ``sensor_noise`` and ``recovery``: a candidate that could
    #: choose the traffic it braked for would be choosing its own exam,
    #: and a comparison in which only one stack braked correctly would be
    #: measuring **safety** rather than the layer it claims to compare.
    v_obstacle_max: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Worst-case speed at which traffic may close on the robot, m/s. Null means "
            "undeclared: legacy behaviour, and no braking guarantee against moving "
            "obstacles."
        ),
    )

    @model_validator(mode="after")
    def _validate_obstacle_speed_bound(self) -> EnvironmentSpec:
        """A declared bound must survive the traffic declared beside it.

        **Fail at startup, not after 300 episodes.** A profile whose
        bound is too small does not crash; it produces a robot that
        brakes for slower traffic than it meets, and the episodes it
        yields answer a question nobody asked. Same shape as HĐ-1.4's
        refusal to infer a scope: the error is only cheap while the
        deployment is still being loaded.

        Skipped entirely when ``v_obstacle_max`` is ``None`` — there is
        no claim to falsify, and a profile written before this field
        existed must load exactly as it did.

        ``default=0.0`` on the ``max`` is not decoration. Without it an
        environment with no dynamic obstacles raises ``ValueError`` from
        inside the validator on an empty sequence, and 0.0 is also the
        right answer: nothing moving means nothing closes.
        """
        if self.v_obstacle_max is None:
            return self
        # A motion whose bound cannot be proven raises rather than
        # guessing, and that refusal has to reach the person filing the
        # deployment as a load rejection — not as a NotImplementedError
        # three frames down inside pydantic, which does not convert it.
        try:
            bounds = [max_speed(obstacle.motion) for obstacle in self.dynamic_obstacles]
        except NotImplementedError as unbounded:
            raise ValueError(
                f"v_obstacle_max is declared as {self.v_obstacle_max} m/s, but one of "
                f"this environment's obstacles has no provable speed bound: {unbounded}"
            ) from unbounded
        fastest = max(bounds, default=0.0)
        if fastest > self.v_obstacle_max:
            culprits = sorted(
                f"{obstacle.name} ({max_speed(obstacle.motion):.3g} m/s)"
                for obstacle in self.dynamic_obstacles
                if max_speed(obstacle.motion) > self.v_obstacle_max
            )
            raise ValueError(
                f"v_obstacle_max is {self.v_obstacle_max} m/s but this environment "
                f"declares faster traffic: {', '.join(culprits)}. The robot would size "
                "its braking distance for traffic slower than the traffic it meets, and "
                f"nothing would report it. Either raise v_obstacle_max to at least "
                f"{fastest:.3g}, slow the obstacle(s) down, or remove the field to run "
                "without a braking guarantee against moving obstacles"
            )
        return self

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

        **A partial-cycle offset is the same failure, quieter.** Shifting
        a 24-second patrol by 6 seconds lets the seeds explore a quarter
        of the cycle, and if the robot crosses that lane in a two-second
        window it can still meet the obstacle at essentially one phase —
        or, as the reference warehouse did, at none. Its hundred episodes
        collapsed to one distinct episode and G2 printed a 3% bound built
        on it. So periodic motion must shift by at least a full period.
        The scenario library had this convention in its comments from the
        start ("one full cycle: seeds meet the pedestrian anywhere"); it
        simply was not enforced, and the profile written later did not
        follow it.

        **A shared clock key is the same failure a third way**, and it is
        the one that hid behind a rule that reads as if it covered it.
        The head start is hashed from ``seed_offset + len(name)``, so two
        obstacles whose names merely have the same length get the same
        fraction of their offset — ``cart`` and ``rack`` start together at
        every seed. The name-uniqueness rule above used to claim it
        prevented that; it never could. So the key itself is checked, by
        calling the same :func:`clock_key` the shift is computed from
        rather than by restating the formula here.

        Only obstacles that actually take a head start are compared: at
        ``seed_time_offset = 0`` the shift is zero for everyone, and for a
        ``random_walk`` — the one motion allowed to sit at zero — the seed
        still reaches the headings.
        """
        names = [obstacle.name for obstacle in self.dynamic_obstacles]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(
                f"dynamic obstacle names must be unique, got duplicates {duplicates}; "
                "the name is how a trace, a snapshot and a refusal say which obstacle "
                "they mean, and two of them answering to one name makes every such "
                "record ambiguous"
            )
        shifted: dict[int, list[str]] = {}
        for obstacle in self.dynamic_obstacles:
            if obstacle.seed_time_offset > 0.0:
                shifted.setdefault(clock_key(obstacle), []).append(obstacle.name)
        lockstep = sorted(
            f"[{', '.join(sorted(group))}] (key {key})"
            for key, group in shifted.items()
            if len(group) > 1
        )
        if lockstep:
            raise ValueError(
                f"dynamic obstacle(s) {lockstep} share a clock key, so the seed shifts "
                "their clocks by the same fraction and they move together across every "
                "seed. Unique names do not prevent this: the key is seed_offset plus the "
                "name's LENGTH, so 'cart' and 'rack' collide (measured: identical head "
                "start at every seed). Give them different seed_offset values"
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
                "seed_time_offset to at least one full cycle of the motion so traffic "
                "timing varies per seed"
            )
        partial_cycle = sorted(
            f"{obstacle.name} (offset {obstacle.seed_time_offset}s < period "
            f"{obstacle.motion.period}s)"
            for obstacle in self.dynamic_obstacles
            if obstacle.motion.kind == "periodic"
            and obstacle.seed_time_offset < obstacle.motion.period
        )
        if partial_cycle:
            raise ValueError(
                f"periodic obstacle(s) {partial_cycle} shift by less than one period, so the "
                "seeds only ever explore that fraction of the cycle. This is the same failure "
                "as seed_time_offset = 0, just quieter: the reference warehouse shifted a "
                "24-second patrol by 6 seconds, the robot crossed its lane in a two-second "
                "window, and no seed ever met it — 100 episodes collapsed to one distinct "
                "episode while looking entirely normal. Set seed_time_offset >= period"
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

    @model_validator(mode="after")
    def _heading_must_be_unconstrained(self) -> TaskConstraints:
        """Refuse a heading requirement the platform cannot evaluate.

        HĐ-6 judges arrival on position *and* heading, and the simulator
        has no final-orientation controller: it stops the moment the
        position tolerance is met, whatever way the robot is pointing. A
        profile asking for a heading therefore scores every candidate as
        failing, for a property of the platform rather than of any
        planner — the shape of wrong answer this whole layer exists to
        prevent.

        This is refused at load rather than noted, because the note was
        already tried. Both reference profiles carry a paragraph
        explaining why they write π here; that paragraph protects only
        the profiles whose author read it. The lesson is written into
        the contract in as many words after Phase 5.1 lost a hundred
        episodes to it: *a note saying "remember this later" is not a
        safeguard, only code is.*

        The reservation and its removal condition live in CONTRACTS
        HĐ-6; when an orientation controller exists, drop this validator
        and bump ``contracts_version`` MINOR.
        """
        if self.goal_tolerance_rad < math.pi:
            raise ValueError(
                f"goal_tolerance_rad = {self.goal_tolerance_rad} constrains the arrival "
                "heading, and this platform cannot evaluate that: the simulator has no "
                "final-orientation controller, so every candidate would fail for a "
                "property of the simulator. Declare goal_tolerance_rad >= pi (heading "
                "unconstrained). See the reservation in CONTRACTS HĐ-6"
            )
        return self

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


class CapabilityGrant(BaseModel):
    """One capability this deployment owns beyond the v1 vocabulary (§5.2).

    ``available_observations`` is a closed list of two tokens, and it has
    to stay closed: gate G6 compares those tokens literally, so a typo
    there would read as a hardware incompatibility that does not exist.
    But a deployment that genuinely runs a tracker of its own has no way
    to say so, and until it does, "custom capability" is a plugin-side
    idea the deployment side cannot answer.

    **Additive, and empty by default.** A profile that declares none
    hashes and validates exactly as it did before this field existed —
    which is not a convenience but a requirement: every stored profile
    predates it, and a field that moved their fingerprints would orphan
    the runs they describe.

    ``provider_config`` is the deployment's, and it reaches the execution
    fingerprint: a tracker retuned between two sweeps is a different
    experimental condition, whatever the candidates did.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    provider_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("capability", mode="before")
    @classmethod
    def _canonical_capability(cls, value: object) -> object:
        """One spelling, through the SDK's alias bridge.

        The same door ``CandidateProviderBinding`` uses, for the same
        reason: a deployment granting ``lidar_2d`` and a plugin requiring
        ``planbench://channel/lidar-2d@1`` must meet, and they only meet
        if both sides reduce to one form before anything compares them.
        """
        if not isinstance(value, str):
            return value
        from planbench_plugin_sdk import canonical_requirement

        return canonical_requirement(value)


class AmbiguousGrantError(ValueError):
    """Two providers offer one capability and nothing chose between them.

    Refused rather than resolved. A tracker and a ground-truth source can
    both produce ``human_state_estimates`` and they are **different
    experiments**; picking the better one on the deployment's behalf
    would change what a result means without saying so (§5.4).

    Raised inside a validator, so callers see it wrapped in pydantic's
    ``ValidationError`` — the same way every other refusal in this schema
    layer surfaces. It exists as its own type so the *reason* is
    greppable, not so it can be caught separately.
    """


class TaskProfile(BaseModel):
    """Complete deployment question, per CONTRACTS HĐ-2.

    ``claim_level`` is the level the author *wants* to claim; what may
    actually be printed on a Decision Card comes from
    :meth:`effective_claim_level`.

    **Unknown fields are refused, and that is a change made for a
    reason.** Pydantic's default is to ignore them, so until now a
    profile could declare something this model had never heard of and be
    accepted with the declaration quietly discarded — the document said
    one thing and the measurement did another, with nothing anywhere
    saying so. Two ways that bites, both real:

    * a typo. ``replaning: {enabled: true}`` parsed, stored and measured
      with replanning off, and the author had no way to find out.
    * a server behind the document. A profile naming a field the running
      code does not have yet is exactly what a half-deployed upgrade
      looks like, and silently dropping it turns "my new setting does
      nothing" into an unfindable bug rather than a 422 naming the field.

    HĐ-2 makes this model the single statement of a deployment. A single
    statement that discards half of what it was told is not one.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1)
    claim_level: ClaimLevel = "mission"
    #: Declared, never inferred — see :data:`DeploymentRole`. Defaults to
    #: ``customer`` because that is the case the platform exists for; a
    #: profile that is something else has to say so.
    deployment_role: DeploymentRole = "customer"
    #: Episodes before early stopping may retire a candidate. ``None``
    #: means "take the default"; the value actually used is recorded on
    #: the report, because two runs of one profile under two floors are
    #: two different measurements — the same hole ``constraints`` had in
    #: the manifest until A4.
    min_episodes_before_stop: int | None = Field(default=None, ge=0)
    #: Whether a candidate may replan when the engine gives up, and — if
    #: anybody insists — how often. Defaults to off, which is what every
    #: stored run was measured under.
    #:
    #: **Top level, beside the early-stop floor, because it is the same
    #: kind of thing**: not the world (that is ``environment``), not the
    #: vehicle, not a threshold a gate reads — a condition of how the
    #: evaluation runs. `run_stack` says it outright: *"replanning is a
    #: property of the evaluation conditions, not of the stack: applied
    #: on the path every stack goes through, with one trigger and one
    #: budget for all of them."* Putting it on the candidate is what
    #: would let one stack replan while another waited.
    #:
    #: **It is not in ``episode_context_id``'s payload** (HĐ-3.1 freezes
    #: that at task profile, mission, variant, seed), so two runs of one
    #: deployment under two replanning settings produce the *same*
    #: context ids for two different experiments — the same trap
    #: ``sensor_noise`` sprang. Two defences, both already standing: the
    #: manifest records it (HĐ-13), and re-filing a changed profile under
    #: an existing id is refused, so switching it on is a new deployment
    #: with a new id rather than an edit.
    replanning: ReplanningConfig = NO_REPLANNING
    #: What the robot may do when replanning cannot find a way out.
    #:
    #: On the **deployment** for the reason HĐ-4.1 gives about replan
    #: information: recovery applied to one candidate and not another
    #: measures recovery rather than the layer the run claims to compare.
    #: A scope where recovery *is* the thing compared
    #: (``recovery_selection``) would move it to the candidate, and does
    #: not exist yet — see ``planbench_schemas.recovery``.
    #:
    #: Off by default, like ``replanning``: it changes where the robot
    #: ends up, so it changes every metric downstream, and every stored
    #: run was measured without it.
    recovery: RecoveryConfig = NO_RECOVERY
    #: How much a metre hugging the hard boundary costs a global planner
    #: compared with a metre in the open, minus one. At ``4.0`` a metre
    #: against the boundary costs five, so a planner takes any detour up
    #: to five times as long rather than shave the obstacle.
    #:
    #: **This is a number a person chooses and there is no deriving it**,
    #: unlike the safety envelope or ``N_min``. So it is treated the way
    #: every other such number here is: declared on the **deployment**,
    #: identical for every candidate in the comparison, and written into
    #: the manifest (HĐ-13). A candidate-owned version would let one
    #: stack buy a shorter route by caring less, which is the same defect
    #: ``safety_margin`` had while it was a hard refusal.
    #:
    #: **The default is measured rather than picked, and its effect is
    #: not monotone** — which is why it took measuring. Across the two
    #: scenarios the suite pins, only ``4.0`` gets every case home:
    #:
    #: ===  =================  ==============  ================
    #: λ    two-doorway room   sudden_stop A*   sudden_stop RRT*
    #: ===  =================  ==============  ================
    #: 2.0  timeout, 42 replans  success        success
    #: 4.0  **success, 1**       **success**    **success**
    #: 6.0  success, 1           success        timeout
    #: ===  =================  ==============  ================
    #:
    #: Below it the planner still shaves a blocked doorway the controller
    #: cannot drive through; far above it the sampling planner wanders,
    #: because a strong enough gradient makes almost every edge expensive
    #: and the tree stops converging on anything. So this is a working
    #: value, not an optimum, and it has not been calibrated against real
    #: deployment data — see ``docs/KNOWN_LIMITATIONS.md``.
    #:
    #: Zero switches the gradient off: every planner reverts to pure
    #: distance.
    clearance_preference: float = Field(default=4.0, ge=0)
    environment: EnvironmentSpec
    missions: tuple[Mission, ...] = Field(min_length=1)
    robot: TaskRobotSpec
    available_observations: tuple[ObservationToken, ...] = Field(min_length=1)
    #: Capabilities this deployment owns beyond the v1 vocabulary (§5.2).
    #:
    #: Empty for every profile written before H11, and empty must mean
    #: *unchanged*: the fingerprint payload omits the key entirely rather
    #: than hashing ``[]``, so a stored profile keeps the conditions hash
    #: its runs were recorded under.
    capability_grants: tuple[CapabilityGrant, ...] = ()
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
    def _grants_do_not_collide(self) -> TaskProfile:
        """Two grants for one capability is a choice nobody made.

        Checked here rather than at resolution so the profile is refused
        when it is *written*, not when a sweep is three hours in: the
        deployment is the thing that is wrong, and it is wrong before any
        episode runs.
        """
        seen: dict[str, str] = {}
        for grant in self.capability_grants:
            previous = seen.get(grant.capability)
            if previous is not None and previous != grant.provider_id:
                raise AmbiguousGrantError(
                    f"{grant.capability} is granted by both {previous!r} and "
                    f"{grant.provider_id!r}, and this profile does not say which. The "
                    "host will not choose: two sources of one capability are two "
                    "different experiments"
                )
            seen[grant.capability] = grant.provider_id
        overlap = {
            grant.capability
            for grant in self.capability_grants
            if grant.capability in set(self.available_observations)
        }
        if overlap:
            raise AmbiguousGrantError(
                f"{sorted(overlap)} appear both in available_observations and in "
                "capability_grants; the first says the deployment simply has it and the "
                "second names a provider for it, and a resolver reading both would have "
                "to guess which the deployment meant"
            )
        return self

    def granted_capabilities(self) -> tuple[str, ...]:
        """v1 tokens and v2 grants as one canonical set.

        The single answer to *what does this deployment offer*. Sorted
        and deduplicated for the reason the observation tokens are: a set
        written in two orders is one set, and anything hashing it must
        not see two.
        """
        return tuple(
            sorted(
                {*self.available_observations, *(g.capability for g in self.capability_grants)}
            )
        )

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
