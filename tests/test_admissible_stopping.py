"""Does the braking guarantee survive an obstacle that is closing in?

P0 measured that it does not; P1 declared ``environment.v_obstacle_max``
and measured again. Both readings live here on purpose — one instrument,
two readings, and nothing between them but a number a deployment
declares.

Phase 1b turned admissible stopping into a real constraint: the speed
bound now reads the distance to the nearest *obstacle* rather than to the
goal, and ``tests/test_hard_feasible_set.py`` proves it holds on
``sudden_stop`` even with every soft term switched off. That guarantee is
stated against **the scan taken now**, which is the same as saying: *the
robot can stop before the obstacle is standing.*

This module asks the next question, and it is the one the layer-2
guarantee never answered. When the obstacle is **driving at the robot**,
the gap closes at ``v + u`` while the robot only budgets for ``v``. Two
expressions, both computed here at every step:

.. code-block:: text

    static_required_gap = v·T + v²/(2a)                     <- what the controller enforces
    moving_required_gap = (v+u)·T + v²/(2a) + u·v/a         <- what the world requires

``u·v/a`` is the ground the obstacle covers during the ``t_stop = v/a``
seconds the robot spends braking; ``(v+u)·T`` is the ground *both* cover
during the one control period of reaction. With ``u = 0`` the second
expression collapses onto the first — it is a strict extension, not a
different rule, which is what makes P1 able to adopt it without changing
a byte of today's behaviour on deployments that declare no moving traffic.

**Why the pinch state is the evidence and a collision is only a bonus.**
A step where ``static ≤ gap < moving`` is a step the controller called
safe and the world did not. It is the defect itself. Waiting for a
collision would make the reading depend on whether *this* scene happens
to leave the robot enough room to swerve, and P0 is meant to answer a
question about the guarantee, not about one hall.

Measured 2026-08-14, ``astar+dwa`` on an open hall, a cart driving head-on
down the lane, every noise stream off. ``T`` is the controller's own
control period (0.05 s), ``a`` = 0.5 m/s², robot ``v_max`` = 0.8 m/s:

.. code-block:: text

    cart speed   adversarial weights          shipped weights
    (m/s)        outcome    pinch  min gap    outcome    pinch  min gap
    0.001        success        0    1.624    success        0    1.624
    0.10         success        0    0.584    success        0    0.567
    0.15         success       21    0.005    collision      1   -0.001
    0.20         collision      6   -0.026    collision     24   -0.007
    0.30         collision     11   -0.026    collision     25   -0.017
    0.60         collision     17   -0.051    collision     19   -0.020
    1.00         collision     19   -0.064    collision     20   -0.037
    1.50         collision     21   -0.015    collision     22   -0.104

**Positive, and wider than the plan assumed.** The plan expected the hole
to open around the 1.0 m/s of a walking pedestrian. It opens between 0.10
and 0.20 m/s — slower than a person strolling, and far below any
``v_obstacle_max`` a deployment would think to declare. It is also **not
an artifact of the adversarial configuration**: the shipped weights
collide one row *earlier* than the adversarial ones. Whatever the
clearance term was buying before phase 1b, it does not buy this.

The mechanism, stepped out at ``u`` = 1.0 m/s, is worth reading once:

.. code-block:: text

    t=4.25 .. 5.15   gap 2.310 -> 0.690   v 0.800   static 0.680   moving 2.330
                     21 consecutive steps the controller calls admissible
    t=5.20           gap 0.601 < static 0.639        brakes at the limit
    t=5.40 .. 5.55   "all 24 candidate velocities collide; commanding stop"
    t=5.60           collision

Nothing goes wrong at t=5.20. The controller brakes as hard as it can the
instant its own criterion is breached, and it is already too late — it
needed 2.330 m of room and had 0.601 m,
because the criterion was measured against a cart that had been standing
still only inside the controller's model of the world.

**P1 reads the same instrument again**, with the deployment declaring
``environment.v_obstacle_max``. Speed at contact is **swept** — timed
inside the step, and read at the velocity the engine actually held across
it; see :func:`speed_at_first_contact` for why both halves of that were
got wrong before they were got right:

.. code-block:: text

    cart speed   bound undeclared              bound declared
    (m/s)        breaches   speed at contact   breaches   speed at contact
    0.20                16       0.350 m/s            0       0.000 m/s
    0.30                12       0.378 m/s            0       0.000 m/s
    0.60                 9       0.440 m/s            0       0.000 m/s
    1.00                 8       0.575 m/s            0       0.000 m/s
    1.50                 6       0.638 m/s            0       0.000 m/s

Under the shipped weights the undeclared column reads 0.155 to 0.575 m/s
and the declared column is 0.000 throughout — the bound is not a soft
term a configuration can turn down.

**What is verified.** *The controller respects the speed bound at every
step*, never exceeding it by more than the one deceleration step it
physically cannot have already applied — and it uses 99% of that
allowance, so the allowance is real rather than padding. From which:
**the robot is at rest when the cart reaches it**, at every cart speed,
instead of running into it at up to 0.638 m/s.

It does **not** say the episode ends without contact, and in this scene
it cannot — the cart drives down the lane and into a robot standing
still. No speed bound reaches that; only getting out of the way does, and
with ``weight_clearance = 0`` nothing asks the robot to. So the
collisions at 0.15 m/s and above **stay**, and reading them as a failure
of P1 is reading the wrong claim.

Traced at ``u`` = 1.0 m/s, the declared run against the P0 run above:

.. code-block:: text

    t=4.45    gap 2.175   first step below full speed: 0.75 s and 1.574 m
                          earlier than the undeclared run's t=5.20, gap 0.601
    t=4.45 .. 6.00        v tracks the bound down, one deceleration step behind
    t=6.00    gap 0.029   v reaches 0.0140, and the next step takes it to 0
    t=6.0294  contact     inside a step the robot spends stationary, moving 0 mm
                          (the undeclared run reached contact at t=5.5595,
                           still doing 0.575 m/s)
    t=6.05    sample      v = 0.000, gap −0.021 — the cart closed it, alone

Both columns are read at the same reference point — the first sample below
``v_max``. Taking the last sample still *at* ``v_max`` (5.15 against 4.40)
gives the identical difference; mixing the two is what put a wrong "1.16 s"
in a report.

**What the discrete model does and does not settle.** These numbers are
the simulator's own physics: ``kinematics.step`` holds one velocity per
step, so a robot whose speed reaches zero at the top of a step covers no
ground in it. A robot decelerating *continuously* would travel
``½·a·dt²`` further per step — 0.625 mm here, roughly 20 mm over a full
stop from 0.8 m/s — so the simulator is mildly **optimistic** about
stopping distance. That is a fidelity property of the kinematics layer,
not of this bound, and it applies to every measurement the platform makes
(KNOWN_LIMITATIONS L8).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.registry import build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_schemas.dynamic import DynamicObstacle, WaypointMotion, position_at
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.feasibility import admissible_speed, stopping_distance
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_schemas.sensor import LidarConfig, SensorNoise
from planbench_simulator.nav_stack import run_stack

#: The vehicle ``open_hall_v2`` and ``warehouse_a_v2`` both deploy. Taken
#: as literals rather than read from a profile because this probe is
#: about the controller's braking arithmetic, and a profile edit that
#: changed ``max_linear_acceleration`` would silently move the numbers in
#: this module's docstring without anything failing.
ROBOT = RobotConfig(
    radius=0.26,
    max_linear_velocity=0.8,
    max_angular_velocity=1.2,
    max_linear_acceleration=0.5,
    max_angular_acceleration=1.0,
)

#: Same cart as ``sudden_stop``, so the two probes describe one vehicle.
CART_RADIUS = 0.4

#: The lane the cart drives down, and the lane the robot drives up.
LANE_Y = 4.5

#: ``weight_clearance=0`` with a half-second horizon: the configuration
#: that exposed the phase-1b hole. Both are ordinary candidate knobs, and
#: a layer-2 guarantee has to stand with every soft term turned off or it
#: is a habit rather than a guarantee.
ADVERSARIAL = {"weight_clearance": 0.0, "horizon_seconds": 0.5}

#: A cart at 0.001 m/s covers 60 mm over the whole episode. Parked, for
#: every purpose this file has, and it runs the *same* motion law as the
#: moving rows — a static obstacle would take a different code path and
#: prove less.
PARKED = 0.001

#: The plan's sweep, plus the two rows that bracket where the hole opens.
CART_SPEEDS = (PARKED, 0.1, 0.15, 0.2, 0.3, 0.6, 1.0, 1.5)

#: ``dwa_balanced``'s control period, and the reaction time the bound is
#: stated with. Read from the shipped configuration rather than typed, so
#: a change there fails this file instead of quietly rescaling it.
CONTROL_PERIOD = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]["control_period"]


def _scene(cart_speed: float) -> tuple:
    """An open hall with a cart driving straight down the lane at the robot.

    Head-on and in the open on purpose. A corridor would confound "could
    not stop" with "had nowhere to go", and the question here is only
    whether the speed bound is the right one.
    """
    map_data, _ = build_scenario("open_space")
    cart = DynamicObstacle(
        name="cart",
        radius=CART_RADIUS,
        motion=WaypointMotion(
            waypoints=(Point2D(x=11.5, y=LANE_Y), Point2D(x=1.0, y=LANE_Y)),
            speed=cart_speed,
            # One-shot: it drives the lane once and parks at the far end.
            # Looping would send it back up the hall and add a second
            # encounter that says nothing new.
            loop=False,
        ),
        # No seed jitter. This is an instrument, not a sample: every row
        # of the table has to differ in exactly one quantity.
        seed_time_offset=0.0,
    )
    scenario = Scenario(
        name=f"head_on_{cart_speed}",
        description="A cart drives straight down the lane at the robot.",
        robot=ROBOT,
        start_pose=Pose2D(x=1.5, y=LANE_Y, theta=0.0),
        goal_pose=Pose2D(x=9.5, y=LANE_Y, theta=0.0),
        goal_tolerance=0.3,
        timeout_seconds=60.0,
        simulation_dt=0.05,
        dynamic_obstacles=(cart,),
        lidar=LidarConfig(num_rays=72, max_range=6.0),
        # Every stream off. P0 asks whether the *arithmetic* of the speed
        # bound is complete; noise would put a second explanation on the
        # table for every number in it.
        sensor_noise=SensorNoise(),
        progress_time_window=30.0,
    )
    return map_data, scenario


#: Episodes are simulated once and read many times. Safe because a run is
#: a pure function of its inputs — the platform rests on that — and these
#: results are read, never mutated.
_RUNS: dict[tuple, tuple] = {}


def _run(
    cart_speed: float,
    overrides: dict | None = None,
    obstacle_speed: float | None = None,
) -> tuple:
    key = (cart_speed, tuple(sorted((overrides or {}).items())), obstacle_speed)
    if key not in _RUNS:
        map_data, scenario = _scene(cart_speed)
        local = {**LOCAL_CONTROLLER_CONFIGS["dwa_balanced"], **(overrides or {})}
        _RUNS[key] = (
            scenario,
            run_stack(
                map_data,
                scenario,
                build_local_planner("astar+dwa", local),
                build_global_planner("astar+dwa", episode_seed=0),
                obstacle_speed=obstacle_speed,
            ),
            local["control_period"],
        )
    return _RUNS[key]


def required_gaps(speed: float, closing_speed: float, robot: RobotConfig, period: float) -> tuple:
    """``(static, moving)`` room the robot needs to stop, in metres.

    The **static** expression is what ``DWAPlanner._speed_that_stops_within``
    solves for today, rearranged: the robot covers ``v·T`` while a new
    command takes effect and ``v²/(2a)`` while braking.

    The **moving** expression adds what the obstacle covers meanwhile —
    ``u·T`` during the reaction step and ``u·v/a`` during the braking
    itself. With ``u = 0`` the two are the same expression, which is the
    property P1 depends on: a deployment that declares no closing traffic
    keeps today's behaviour exactly.
    """
    braking = stopping_distance(speed, robot)
    static = speed * period + braking
    # What the obstacle covers while the robot reacts, then while it brakes.
    closes = closing_speed * period + closing_speed * speed / robot.max_linear_acceleration
    return static, static + closes


def _closing_speed(obstacle: DynamicObstacle, time: float, seed: int, x: float, y: float) -> float:
    """How fast the obstacle is eating the gap, in m/s, from ground truth.

    Ground truth is legitimate here and only here: this is the test
    judging the controller, not the controller sensing the world. A
    controller reading this would be the privilege HĐ-4.1 exists to
    refuse — and estimating it from LiDAR instead is the whole of P5.

    Only the approaching component counts; an obstacle leaving does not
    hand back braking distance the robot has already spent.
    """
    step = 1e-3
    before = position_at(obstacle, max(0.0, time - step), seed)
    after = position_at(obstacle, time + step, seed)
    span = (time + step) - max(0.0, time - step)
    velocity_x = (after.x - before.x) / span
    velocity_y = (after.y - before.y) / span
    here = position_at(obstacle, time, seed)
    toward_x, toward_y = x - here.x, y - here.y
    distance = math.hypot(toward_x, toward_y)
    if distance <= 0.0:
        return 0.0
    return max(0.0, (velocity_x * toward_x + velocity_y * toward_y) / distance)


class Step:
    """One control step of the probe, with both bounds evaluated.

    Measured on the **true** pose and the obstacle's **true** centre. The
    robot brakes according to where it believes it is; a check run on the
    believed pose would be marking its own homework, which is the reading
    error phase 1b already had to correct once.
    """

    __slots__ = ("gap", "moving", "separation", "speed", "static", "time", "closing")

    def __init__(
        self,
        time: float,
        gap: float,
        speed: float,
        closing: float,
        bounds: tuple,
        separation: tuple[float, float],
    ):
        self.time = time
        self.gap = gap
        self.speed = speed
        self.closing = closing
        self.static, self.moving = bounds
        #: Robot centre minus cart centre. Kept as a **vector** and not
        #: only as ``gap`` because timing the contact inside a step means
        #: interpolating the separation and then taking its length; taking
        #: the length first and interpolating that is a different, and
        #: wrong, curve whenever the robot is moving sideways at all.
        #: (Only the *geometry* is interpolated across a step. The speed
        #: is not — see :func:`speed_at_first_contact`.)
        self.separation = separation

    @property
    def pinched(self) -> bool:
        """The controller called this step safe and the world did not."""
        return self.static <= self.gap < self.moving

    @property
    def static_broken(self) -> bool:
        return self.gap < self.static


def probe(
    cart_speed: float,
    overrides: dict | None = None,
    obstacle_speed: float | None = None,
) -> tuple:
    """``(status, steps)`` for one cart speed.

    ``obstacle_speed`` is what the *deployment declares*, which is a
    different thing from ``cart_speed``, what the cart *does*. P0 reads
    this probe with nothing declared; P1 reads the same probe with the
    bound declared, and the two readings are the before and after.
    """
    scenario, run, period = _run(cart_speed, overrides, obstacle_speed)
    cart = scenario.dynamic_obstacles[0]
    surface = CART_RADIUS + scenario.robot.radius
    steps = []
    for point in run.result.trajectory:
        snapshot = point.obstacles[0]
        # Surface to surface, not centre to centre. Getting this wrong
        # inflates every gap by 0.66 m and the table reads the other way.
        separation = (point.x - snapshot.x, point.y - snapshot.y)
        gap = math.hypot(*separation) - surface
        closing = _closing_speed(cart, point.time, scenario.random_seed, point.x, point.y)
        steps.append(
            Step(
                point.time,
                gap,
                point.linear_velocity,
                closing,
                required_gaps(point.linear_velocity, closing, scenario.robot, period),
                separation,
            )
        )
    return run.result.status, steps


class TestTheTwoExpressionsAreOneExpression:
    """``moving`` extends ``static``; it does not replace it.

    P1 makes ``v_obstacle_max`` optional and promises that a deployment
    which declares nothing keeps today's behaviour byte for byte. That
    promise is this identity, so it is checked here rather than assumed
    there.
    """

    @pytest.mark.parametrize("speed", [0.0, 0.1, 0.4, 0.8])
    def test_a_stationary_obstacle_asks_for_exactly_todays_bound(self, speed: float) -> None:
        static, moving = required_gaps(speed, 0.0, ROBOT, 0.05)
        assert moving == pytest.approx(static)

    def test_it_matches_the_speed_the_controller_would_pick(self) -> None:
        """The static half is not a restatement of the criterion in a test
        — it is the criterion. ``_speed_that_stops_within`` solves
        ``v·T + v²/(2a) = headroom``, so feeding its answer back in must
        return the headroom it was given."""
        from planbench_planning import DWAPlanner

        planner = DWAPlanner()
        headroom = 0.64
        speed = planner._speed_that_stops_within(headroom, ROBOT)
        static, _ = required_gaps(speed, 0.0, ROBOT, planner.control_period)
        assert static == pytest.approx(headroom, abs=1e-6)

    @pytest.mark.parametrize("closing", [0.1, 0.5, 1.0])
    def test_a_closing_obstacle_only_ever_asks_for_more(self, closing: float) -> None:
        static, moving = required_gaps(0.8, closing, ROBOT, 0.05)
        assert moving > static


class TestTheStepModelIsZeroOrderHold:
    """What velocity is in force **inside** a simulation step.

    This exists because getting it wrong produced a wrong number in a
    report, and nothing in the suite objected. ``kinematics.step``
    resolves the new velocity first — clamped to the limits, then to one
    step of acceleration — and integrates the whole ``dt`` with it. So a
    sample carries the velocity that applied from the *previous* sample
    onwards, and anything timing an event inside a step must use it as a
    constant rather than interpolate towards it.

    Pinned against the trace rather than against the docstring: a
    docstring is what somebody meant, and the reading error here was
    somebody's meaning too.
    """

    @pytest.mark.parametrize("cart_speed", [0.3, 1.0, 1.5])
    def test_displacement_matches_the_speed_recorded_at_the_step_end(
        self, cart_speed: float
    ) -> None:
        """Read off the robot's own trajectory, and it is exact.

        ``moved == after.speed × dt`` to a hair at every step, while
        ``before.speed`` is out by a whole deceleration step whenever the
        robot is braking — which is every step that matters here.
        """
        _, run, _ = _run(cart_speed, ADVERSARIAL, cart_speed)
        trajectory = run.result.trajectory
        braking = 0
        for before, after in zip(trajectory, trajectory[1:], strict=False):
            dt = after.time - before.time
            moved = math.hypot(after.x - before.x, after.y - before.y)
            assert moved == pytest.approx(after.linear_velocity * dt, abs=1e-9)
            if after.linear_velocity < before.linear_velocity - 1e-9:
                braking += 1
                assert moved != pytest.approx(before.linear_velocity * dt, abs=1e-9)
        assert braking > 10

    def test_a_step_that_reaches_zero_moves_the_robot_not_at_all(self) -> None:
        """The case the wrong reading turned into 5.8 mm/s of phantom
        motion. The step in which the robot's speed reaches zero covers
        no ground whatever, so an obstacle arriving inside that step
        arrives at a robot that is already stopped."""
        _, steps = probe(1.0, ADVERSARIAL, obstacle_speed=1.0)
        stopping = next(
            index
            for index in range(1, len(steps))
            if steps[index].speed == 0.0 and steps[index - 1].speed > 0.0
        )
        before, after = steps[stopping - 1], steps[stopping]
        # The cart is the only thing that moved: the whole change in
        # separation is its own travel over the step.
        travelled = abs(after.separation[0] - before.separation[0])
        assert travelled == pytest.approx(1.0 * (after.time - before.time), abs=1e-9)


class TestTheProbeIsCalibrated:
    """Before believing what the instrument says about moving carts.

    A probe that reported violations against a parked cart would be
    measuring its own arithmetic, not the controller — and the phase-1b
    suite already proves the parked case is sound, so the two must agree.
    """

    def test_a_parked_cart_breaches_neither_bound(self) -> None:
        status, steps = probe(PARKED, ADVERSARIAL)
        assert status is EpisodeStatus.SUCCESS
        assert [step.time for step in steps if step.static_broken] == []
        assert [step.time for step in steps if step.pinched] == []

    def test_a_parked_cart_is_still_seen(self) -> None:
        """Zero violations because the robot handled it, not because the
        cart was never in the way. Without this the calibration row would
        also pass on a probe that measured the wrong obstacle."""
        _, steps = probe(PARKED, ADVERSARIAL)
        assert min(step.gap for step in steps) < 2.0

    def test_a_slow_cart_is_still_inside_the_guarantee(self) -> None:
        """0.1 m/s: the fastest cart the current bound survives. Its
        closest approach is 0.584 m, so it is not passing by a hair."""
        status, steps = probe(0.1, ADVERSARIAL)
        assert status is EpisodeStatus.SUCCESS
        assert [step.time for step in steps if step.pinched] == []
        assert min(step.gap for step in steps) == pytest.approx(0.584, abs=0.01)


#: Cart speeds the hole is claimed for. 0.15 m/s is left out of the
#: assertion and kept in the module docstring instead: it is the boundary
#: row, and a boundary row is the one place a threshold assertion turns
#: into a coin toss.
BREACHING_SPEEDS = (0.2, 0.3, 0.6, 1.0, 1.5)


def bound_breaches(steps: Sequence[Step], declared: float | None, robot: RobotConfig) -> list:
    """Steps where the robot was going faster than it was allowed to.

    This is the invariant the controller **enforces**, read back off the
    trajectory: at every step, the speed must be within what the gap the
    robot could measure permits, given the deployment's declared closing
    speed. It is what "the robot can always still stop before what it can
    see" means as an arithmetic statement.

    **One deceleration step of slack, and it is physics rather than
    tolerance.** The bound is a limit on the *command*; the robot arrives
    at it at ``max_linear_acceleration``. When the gap shrinks the bound
    falls immediately and the robot cannot already be below it, so a step
    where the speed exceeds it by at most ``a · T`` is the robot obeying
    as fast as a robot can. Anything beyond that is a breach.

    Note which closing speed this uses: the one the deployment
    **declared**, which is what the controller was given and therefore
    what it can be held to. ``None`` means the deployment declared
    nothing, which the controller reads as zero — so an undeclared
    deployment is checked against exactly the promise it made, and P0's
    reading is a fair one rather than a rigged one.
    """
    slack = robot.max_linear_acceleration * CONTROL_PERIOD
    return [
        step
        for step in steps
        if step.speed
        > admissible_speed(step.gap, robot, CONTROL_PERIOD, declared or 0.0) + slack + 1e-9
    ]


def speed_at_first_contact(steps: Sequence[Step]) -> float | None:
    """How fast the robot was at the **instant** of contact, or ``None``.

    **Swept, not sampled, and the difference changed a conclusion.** The
    first version of this read the speed off the first *sample* whose gap
    was non-positive. That sample is taken at the **end** of a step, and
    contact happens **inside** it — so a robot still decelerating when the
    cart reached it was recorded at the zero it arrived at a few
    milliseconds later, and every declared run looked like a clean stop
    for a reason that had nothing to do with the controller.

    **The second draft then got it wrong the other way**, and that one is
    worth keeping written down. It interpolated the speed across the step
    — ``before + s·(after − before)`` — and reported the robot still
    moving at 5.8 mm/s where it was in fact stopped. The engine does not
    ramp velocity across a step: ``kinematics.step`` resolves the new
    velocity *first*, then integrates the whole ``dt`` with it. So the
    speed in force from ``t`` to ``t+dt`` is the one recorded at
    ``t+dt``, held constant, and interpolating towards it invents motion
    that never happened.

    Which leaves the measurement in two halves, one per mistake:

    * **when** — both bodies travel straight segments over the step, so
      centre-to-centre distance is a quadratic in the step fraction ``s``
      and contact is its first root inside ``[0, 1]``;
    * **how fast** — ``after.speed``, constant, not a function of ``s``.

    A gap already non-positive at the opening sample means contact
    happened earlier still; it is reported at that sample rather than
    skipped, because the alternative is a probe that misses the collision
    it exists to time.
    """
    radii = CART_RADIUS + ROBOT.radius
    for before, after in zip(steps, steps[1:], strict=False):
        if before.gap <= 0.0:
            return before.speed
        start = before.separation
        delta = (after.separation[0] - start[0], after.separation[1] - start[1])
        # |start + s·delta|² = radii², solved for the first root in [0, 1].
        quadratic = delta[0] * delta[0] + delta[1] * delta[1]
        linear = 2.0 * (start[0] * delta[0] + start[1] * delta[1])
        constant = start[0] * start[0] + start[1] * start[1] - radii * radii
        if quadratic <= 1e-18:
            continue
        discriminant = linear * linear - 4.0 * quadratic * constant
        if discriminant < 0.0:
            continue
        fraction = (-linear - math.sqrt(discriminant)) / (2.0 * quadratic)
        if not 0.0 <= fraction <= 1.0:
            continue
        # **The speed across the whole step is the one recorded at its
        # end**, and interpolating between the two samples would be a
        # second reading error on top of the one this function fixes.
        # ``kinematics.step`` resolves the new velocity *first* — clamped
        # to the limits, then to one step of acceleration — and integrates
        # the entire ``dt`` with it, so the sample at ``t+dt`` carries the
        # velocity that was in force from ``t`` onwards. Checked against
        # the trace rather than taken from the docstring: displacement
        # between two samples equals ``after.speed × dt`` to the last
        # float, at every step.
        return after.speed
    return None


class TestTheGuaranteeDoesNotCoverAnApproachingObstacle:
    """**The P0 finding: what an undeclared deployment gets.**

    These tests assert a defect, deliberately. It is not a defect waiting
    to be fixed — it is what a deployment that declares no
    ``v_obstacle_max`` is entitled to, and P1 left that behaviour byte for
    byte alone on purpose so no stored run was invalidated. The class
    below is the same probe with the bound declared.

    Do not "fix" this file by loosening it. If these go green on their
    own, something moved the probe, not the controller.
    """

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_the_controller_calls_steps_safe_that_are_not(self, cart_speed: float) -> None:
        _, steps = probe(cart_speed, ADVERSARIAL)
        pinched = [step for step in steps if step.pinched]
        assert pinched, f"no pinch state at {cart_speed} m/s — has P1 landed?"
        worst = min(pinched, key=lambda step: step.gap - step.moving)
        assert worst.gap < worst.moving
        assert worst.gap >= worst.static

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_and_the_episode_ends_in_contact(self, cart_speed: float) -> None:
        """Stronger evidence than the pinch state, and not the criterion:
        a hall wide enough to swerve in could hide the collision while the
        guarantee stayed just as broken."""
        status, steps = probe(cart_speed, ADVERSARIAL)
        assert status is EpisodeStatus.COLLISION
        assert min(step.gap for step in steps) < 0.0

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_the_shipped_weights_do_not_save_it(self, cart_speed: float) -> None:
        """The defect is not an artifact of the adversarial knobs.

        Before phase 1b, safety on ``sudden_stop`` was resting on
        ``weight_clearance`` being incidentally large. Here it rests on
        nothing: the shipped configuration collides at every one of these
        speeds, and at 0.15 m/s it collides where the adversarial one
        still scrapes through.
        """
        status, steps = probe(cart_speed)
        assert status is EpisodeStatus.COLLISION
        assert [step for step in steps if step.pinched]

    def test_the_controller_brakes_as_hard_as_it_can_and_still_arrives_late(self) -> None:
        """The mechanism, not the outcome — and it exonerates the code.

        Nothing malfunctions at the moment of the breach: the robot sheds
        speed at ``max_linear_acceleration`` from the first step its own
        criterion is violated. It is late because the criterion was
        measured against an obstacle that was only standing still inside
        the controller's model of the world.
        """
        _, steps = probe(1.0, ADVERSARIAL)
        breached = next(index for index, step in enumerate(steps) if step.static_broken)
        # It was cruising, unwarned, right up to the step before.
        assert steps[breached - 1].pinched
        assert steps[breached - 1].speed == pytest.approx(ROBOT.max_linear_velocity, abs=1e-3)
        # And from there it decelerates at the limit, every step.
        period = steps[breached].time - steps[breached - 1].time
        limit = ROBOT.max_linear_acceleration * period
        decelerating = [
            steps[index - 1].speed - steps[index].speed
            for index in range(breached + 1, len(steps))
            if steps[index].speed > 0.0
        ]
        assert decelerating
        assert all(delta == pytest.approx(limit, abs=1e-6) for delta in decelerating)

    def test_the_hole_opens_far_below_walking_pace(self) -> None:
        """The number that decides whether P1 is worth two days.

        A hole that only opened against a 1.5 m/s forklift would be a
        corner case. It opens between 0.10 and 0.20 m/s — slower than a
        person strolling, and below any ``v_obstacle_max`` a deployment
        author would think to declare.
        """
        assert probe(0.1, ADVERSARIAL)[0] is EpisodeStatus.SUCCESS
        assert probe(0.2, ADVERSARIAL)[0] is EpisodeStatus.COLLISION

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_it_was_still_moving_when_the_cart_reached_it(self, cart_speed: float) -> None:
        """The clean statement of the failure, and P1's mirror.

        Not "it collided" — a robot standing still can be collided with,
        and no controller prevents that. **It never stopped.** At every
        cart speed the robot was still driving when the gap closed.
        """
        _, steps = probe(cart_speed, ADVERSARIAL)
        assert speed_at_first_contact(steps) > 0.1

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_and_it_broke_the_bound_it_would_have_been_given(self, cart_speed: float) -> None:
        """Read against the bound a declaring deployment would impose, the
        undeclared runs breach it at every speed — which is the same
        finding as the pinch state, stated in the quantity P1 enforces so
        the two readings are directly comparable."""
        _, steps = probe(cart_speed, ADVERSARIAL)
        assert bound_breaches(steps, cart_speed, ROBOT)


class TestDeclaringTheBoundRestoresTheGuarantee:
    """**The P1 reading. Same probe, same seeds, bound declared.**

    The pair with the class above is the whole evidence of this phase: one
    instrument, two readings, and nothing between them but a number the
    deployment declares.
    """

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_the_robot_never_exceeds_what_it_can_stop_from(self, cart_speed: float) -> None:
        _, steps = probe(cart_speed, ADVERSARIAL, obstacle_speed=cart_speed)
        breaches = bound_breaches(steps, cart_speed, ROBOT)
        assert breaches == [], f"{len(breaches)} steps above the bound at {cart_speed} m/s"

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_it_is_at_rest_when_the_cart_arrives(self, cart_speed: float) -> None:
        """The guarantee, in one number: the robot stopped in time.

        Contrast the class above, where the same robot met the same cart
        at up to 0.638 m/s. What happens next — the cart driving into a
        stationary robot — is not something a speed bound reaches.

        **This assertion took three readings to get right, and the middle
        one was wrong in both directions.** Reading the sample after
        contact said rest (too strong). Interpolating the speed across the
        step said 5.8 mm/s (too weak, and wrong about the engine).
        ``kinematics.step`` holds one velocity for the whole step, so the
        speed during the step containing contact is the one recorded at
        its end — and it is zero. See
        :meth:`TestTheStepModelIsZeroOrderHold` for the pin.
        """
        _, steps = probe(cart_speed, ADVERSARIAL, obstacle_speed=cart_speed)
        assert speed_at_first_contact(steps) == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_the_shipped_weights_get_it_too(self, cart_speed: float) -> None:
        """Deployment-owned means every candidate, not the careful ones.

        The bound is not a soft term a configuration can turn down: the
        shipped weights and the adversarial ones are held to the identical
        limit, which is the entire reason it lives on the deployment.
        """
        _, steps = probe(cart_speed, obstacle_speed=cart_speed)
        assert bound_breaches(steps, cart_speed, ROBOT) == []
        assert speed_at_first_contact(steps) == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.parametrize("cart_speed", BREACHING_SPEEDS)
    def test_the_one_step_allowance_is_needed_and_never_exceeded(self, cart_speed: float) -> None:
        """The slack in :func:`bound_breaches` is load-bearing, not padding.

        The robot runs up to **99%** of one deceleration step above the
        bound its current gap implies, and never past it. Both halves
        matter: a smaller allowance would fail on physics the controller
        cannot beat, and a larger one would stop detecting a real breach.
        """
        _, steps = probe(cart_speed, ADVERSARIAL, obstacle_speed=cart_speed)
        one_step = ROBOT.max_linear_acceleration * CONTROL_PERIOD
        excess = max(
            step.speed - admissible_speed(step.gap, ROBOT, CONTROL_PERIOD, cart_speed)
            for step in steps
        )
        assert 0.8 * one_step < excess <= one_step

    def test_it_brakes_far_earlier_than_it_used_to(self) -> None:
        """Where the metres come from, rather than only that they do.

        **Both runs are read at the same reference point**, and that is
        the whole point of this test rather than an implementation note.
        Quoting one run's last full-speed sample against the other's first
        reduced one is an off-by-a-step that reads as a real difference:
        it put a wrong "1.16 s" into a report. Measured either way the
        answer is the same — 0.75 s and 1.574 m — because the difference
        is invariant and only the absolute marks move.
        """
        top = ROBOT.max_linear_velocity

        def braking_starts(declared: float | None, offset: int) -> Step:
            _, steps = probe(1.0, ADVERSARIAL, obstacle_speed=declared)
            last_cruising = max(
                index for index, step in enumerate(steps) if step.speed >= top - 1e-6
            )
            return steps[last_cruising + offset]

        for offset in (0, 1):  # last sample at v_max, then the first below it
            undeclared = braking_starts(None, offset)
            declared = braking_starts(1.0, offset)
            assert undeclared.time - declared.time == pytest.approx(0.75, abs=1e-9)
            assert declared.gap - undeclared.gap == pytest.approx(1.574, abs=1e-3)

    def test_a_deployment_that_declares_nothing_is_left_exactly_alone(self) -> None:
        """P1's other promise, and the one that protects every stored run.

        ``None`` must reproduce the previous behaviour, not merely
        resemble it: the same trajectory, float for float. Same shape of
        guard as ``NO_REPLANNING`` and ``NO_RECOVERY``.
        """
        for cart_speed in (PARKED, 0.3, 1.0):
            _, undeclared = probe(cart_speed, ADVERSARIAL, obstacle_speed=None)
            _, zeroed = probe(cart_speed, ADVERSARIAL, obstacle_speed=0.0)
            assert [(s.time, s.gap, s.speed) for s in undeclared] == [
                (s.time, s.gap, s.speed) for s in zeroed
            ]
