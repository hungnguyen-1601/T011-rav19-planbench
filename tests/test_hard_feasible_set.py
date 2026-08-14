"""Phase 1 — one hard feasible set, owned by the deployment.

The defect this closes is measured in
``docs/antongduy/notes/2026-08-13/tongduyan_hai-vung-cam-mot-con-robot.md``:
two layers held two different answers to *"may the robot be here"* —
0.31 m for the controller, 0.61 m for the planner — and the whole 0.30 m
difference was a grid-quantisation term.

Three layers of boundary, and **"who owns it" is a different axis from
"hard or soft"**:

* **collision footprint** — hard, robot;
* **safety envelope** — hard, *deployment*: how wrong the pose estimate
  may be;
* **comfort margin** — soft, *candidate*: room it would rather have.

The contract that follows:

* **L1** global may only return paths inside the hard set local can drive;
* **L2** local may be more cautious by *cost*, never by narrowing the
  hard set with a parameter global cannot see;
* **L3** every layer shares the footprint and the envelope;
* **L4** an integration check drives both stacks and requires every
  global path to pass local's feasibility test.

Two live violations existed when this was written, and both are fixed
here:

1. ``safety_margin`` was a **candidate** parameter acting as a **hard**
   refusal — L2 broken in one direction.
2. The admissible-velocity criterion measured the distance to the
   **goal** rather than to the nearest obstacle, so nothing forbade a
   speed the robot could not brake from. Safety rested on
   ``weight_clearance``, another candidate parameter — L2 broken in the
   other direction, with a reproducible collision behind it.
"""

from __future__ import annotations

import copy
import inspect
import math
from pathlib import Path

import pytest
import yaml

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.episode import scenario_for
from planbench_benchmark.registry import build_global_planner, build_local_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_planning import DWAPlanner
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.feasibility import (
    SafetyEnvelope,
    hard_clearance,
    reaction_distance,
    stopping_distance,
)
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import CircleObstacle
from planbench_schemas.sensor import MIN_JUMP_MAGNITUDE_M, SensorNoise
from planbench_schemas.task_profile import TaskProfile
from planbench_simulator.drivable import path_is_drivable
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.nav_stack import _inflation_radius, run_stack

REPO_ROOT = Path(__file__).resolve().parents[1]


def _executable_source(path: Path) -> str:
    """The module's source with comments and docstrings removed.

    Every guard here scans code for a pattern that must or must not be
    there, and the file it scans *explains* the pattern in prose right
    beside it. Twice already a test in this repo has matched its own
    documentation and reported the opposite of the truth, so the scans
    read tokens rather than text.
    """
    import io
    import tokenize

    source = path.read_text(encoding="utf-8")
    kept: list[str] = []
    previous = tokenize.INDENT
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        # A string alone on a logical line is a docstring, never a value.
        if token.type == tokenize.STRING and previous in (
            tokenize.INDENT,
            tokenize.NEWLINE,
            tokenize.NL,
        ):
            continue
        if token.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            kept.append(token.string)
        previous = token.type
    return " ".join(kept)


def _uses(path: Path, expression: str) -> bool:
    """Is ``expression`` present in the file's *code*, ignoring layout?

    Whitespace is dropped from both sides so a needle can be written the
    way a person would write it while the haystack stays a token stream.
    """
    haystack = "".join(_executable_source(path).split())
    return "".join(expression.split()) in haystack


DWA_SOURCE = (
    REPO_ROOT / "packages" / "planning" / "planbench_planning" / "dwa" / "planner.py"
)
NAV_STACK_SOURCE = REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "nav_stack.py"
NOISE_SOURCE = REPO_ROOT / "services" / "simulator" / "planbench_simulator" / "noise.py"


ROBOT = RobotConfig(
    radius=0.26,
    max_linear_velocity=0.8,
    max_angular_velocity=1.2,
    max_linear_acceleration=0.5,
    max_angular_acceleration=1.0,
)

#: Both stacks the platform ships. L4 is a claim about the *contract*
#: between the layers, so proving it for one global planner would prove
#: only that A* happens to be conservative.
STACKS = ("astar+dwa", "rrtstar+dwa")


class TestTheEnvelopeIsDerivedRatherThanChosen:
    """Every input is something the deployment already declares.

    An envelope that asked for its own number would be one more "somebody
    chose this" — the class of knob removed when ``max_replans`` stopped
    being a cap.
    """

    def test_no_declared_noise_means_no_envelope(self) -> None:
        """The footprint alone is right for an exact pose estimate, so
        every profile that declares no noise keeps its behaviour."""
        envelope = SafetyEnvelope.for_noise(SensorNoise())
        assert envelope.position_uncertainty_m == 0.0
        assert hard_clearance(ROBOT, envelope) == pytest.approx(ROBOT.radius)

    def test_drift_bounds_both_axes_at_once(self) -> None:
        """The drift weights are a Dirichlet draw, so they sum to one:
        each axis is bounded by the declared amplitude and the pair by
        ``amplitude × √2``."""
        envelope = SafetyEnvelope.for_noise(SensorNoise(localization_drift_m=0.1))
        assert envelope.position_uncertainty_m == pytest.approx(0.1 * math.sqrt(2.0))

    def test_a_possible_jump_is_counted_as_a_certainty(self) -> None:
        """"Unlikely per window" is "it happens" across an episode of many
        windows, and a hard bound exceeded sometimes is not hard."""
        envelope = SafetyEnvelope.for_noise(
            SensorNoise(localization_drift_m=0.1, localization_jump_probability=0.02)
        )
        assert envelope.position_uncertainty_m == pytest.approx(
            0.1 * math.sqrt(2.0) + MIN_JUMP_MAGNITUDE_M
        )

    def test_wheel_slip_does_not_widen_it(self) -> None:
        """Slip moves the robot *for real*, so it is already inside the
        true pose the collision test reads. It opens no gap between truth
        and belief, and that gap is the only thing here."""
        envelope = SafetyEnvelope.for_noise(SensorNoise(wheel_slip_fraction=0.5))
        assert envelope.position_uncertainty_m == 0.0

    def test_braking_is_not_in_it(self) -> None:
        """Stopping distance is quadratic in speed. Folding it into a
        static envelope would forbid a robot creeping past at 0.1 m/s
        exactly as hard as one charging at 0.8 — 0.64 m of margin against
        a real need of 0.01 m."""
        assert stopping_distance(0.8, ROBOT) == pytest.approx(0.64)
        assert stopping_distance(0.1, ROBOT) == pytest.approx(0.01)

    def test_the_jump_magnitude_has_one_definition(self) -> None:
        """It lives beside the field it belongs to and the noise model
        imports it. Two copies is how two layers drift apart — which is
        the entire subject of this file."""
        assert _uses(NOISE_SOURCE, "max(drift, MIN_JUMP_MAGNITUDE_M)")
        assert not _uses(NOISE_SOURCE, "max(drift, 0.25)")

    def test_reaction_distance_counts_the_declared_latency(self) -> None:
        """Braking from the instant of decision assumes a robot that
        reacts instantly, which is the assumption ``command_latency_steps``
        exists to remove."""
        assert reaction_distance(0.8, 0.05, 0) == pytest.approx(0.04)
        assert reaction_distance(0.8, 0.05, 2) == pytest.approx(0.12)


class TestL2IsEnforcedByTheSignature:
    """A rule nobody *can* break beats a rule nobody *may* break."""

    def test_the_hard_set_cannot_see_a_candidate_config(self) -> None:
        """``hard_clearance`` takes the robot and the deployment's
        envelope and nothing else, so a controller that wanted to narrow
        the set has no argument to do it with."""
        assert set(inspect.signature(hard_clearance).parameters) == {"robot", "envelope"}
        assert set(inspect.signature(path_is_drivable).parameters) == {
            "path",
            "robot",
            "envelope",
            "obstacles",
            "grid",
        }

    def test_the_controller_no_longer_hard_rejects_on_its_own_margin(self) -> None:
        """``safety_margin`` used to *be* the hard threshold, which let a
        candidate silently shrink the set the planner planned against."""
        assert _uses(DWA_SOURCE, "keep_out = hard_clearance(robot, self._envelope)")
        assert not _uses(DWA_SOURCE, "robot.radius + config.safety_margin")

    def test_the_wish_for_extra_room_survives_as_a_cost(self) -> None:
        """Demoting the margin must not delete the preference: wanting
        five more centimetres is a legitimate thing for a candidate to
        want, and it still has to separate two of them."""
        assert "comfort" in inspect.getsource(DWAPlanner._score)
        timid = _run("astar+dwa", {"safety_margin": 0.45})
        bold = _run("astar+dwa", {"safety_margin": 0.01})
        assert _closest_approach(timid) > _closest_approach(bold), (
            "safety_margin no longer changes how close the robot drives, "
            "so demoting it to a cost deleted it instead of moving it"
        )

    def test_every_layer_quotes_the_same_clearance(self) -> None:
        """L3. The planner's inflation is the shared clearance plus a
        quantisation term — and that term appears exactly once in the
        codebase, because it is a property of the map's resolution rather
        than of the world."""
        assert _uses(NAV_STACK_SOURCE, "hard_clearance(scenario.robot, envelope)")
        code = "".join(_executable_source(NAV_STACK_SOURCE).split())
        assert code.count("math.sqrt(2.0)*map_data.resolution") == 1


def _scene(noise: dict | None = None):
    """`sudden_stop` as a deployment, the way the form builds one."""
    map_data, library = build_scenario("sudden_stop")
    raw = copy.deepcopy(
        yaml.safe_load(
            (REPO_ROOT / "profiles" / "open_hall_v2.yaml").read_text(encoding="utf-8")
        )
    )
    raw["id"] = "feasible_probe"
    raw["replanning"] = {"enabled": True}
    raw["missions"] = [
        {
            "id": "m",
            "start": [library.start_pose.x, library.start_pose.y, 0.0],
            "goal": [library.goal_pose.x, library.goal_pose.y, 0.0],
            "probability": 1.0,
        }
    ]
    raw["environment"]["dynamic_obstacles"] = [
        obstacle.model_dump(mode="json") for obstacle in library.dynamic_obstacles
    ]
    raw["environment"]["sensor_noise"] = noise or {
        "lidar_range_sigma_m": 0.02,
        "wheel_slip_fraction": 0.02,
    }
    profile = TaskProfile.model_validate(raw)
    scenario = scenario_for(
        profile, EpisodeContext(task_profile_id=profile.id, mission_id="m", seed=0)
    )
    return map_data, profile, scenario


#: Episodes here run to a 120-second timeout and several tests ask about
#: the same one, so they are simulated once and reused. Safe because a
#: run is a pure function of its inputs — the whole platform rests on
#: that — and the results are read, never mutated.
_RUNS: dict[tuple, tuple] = {}


def _run(stack: str, overrides: dict | None = None, noise: dict | None = None):
    key = (stack, tuple(sorted((overrides or {}).items())), tuple(sorted((noise or {}).items())))
    if key not in _RUNS:
        map_data, profile, scenario = _scene(noise)
        local = {**LOCAL_CONTROLLER_CONFIGS["dwa_balanced"], **(overrides or {})}
        _RUNS[key] = (
            map_data,
            scenario,
            run_stack(
                map_data,
                scenario,
                build_local_planner(stack, local),
                build_global_planner(stack, episode_seed=0),
                profile.replanning,
            ),
        )
    return _RUNS[key]


def _closest_approach(run_tuple) -> float:
    """Nearest the robot's *surface* ever came to the cart."""
    _, scenario, run = run_tuple
    surface = 0.4 + scenario.robot.radius
    return min(
        math.hypot(point.x - 7.0, point.y - 4.5) - surface for point in run.result.trajectory
    )


class TestL4EveryGlobalPathIsOneTheControllerCouldDrive:
    """The most important fence in phase 1.

    It takes **every** path the global planner returns — the first plan
    *and* every replan — measures it **continuously** rather than on the
    grid, and runs for **both** shipped stacks. Checking only the first
    plan would miss the interesting half: replans are planned from a
    believed pose over a *relaxed* grid, which is exactly where a path
    outside the hard set would come from.

    **What it checks against, and what it deliberately does not.** The
    world here is the map plus the static obstacles — the geometry the
    global planner is answerable for. Dynamic obstacles are excluded on
    purpose: at t=0 the planner cannot see the cart, so a first plan
    running straight through where the cart will later be is correct
    behaviour and the controller's problem, not a contract breach. The
    validator's own ability to reject a path through a *circle* is proved
    below on constructed geometry rather than on a live episode, because
    recovering where the cart stood at the instant of replan *k* is not
    something a finished ``StackRun`` can answer.
    """

    @pytest.mark.parametrize("stack", STACKS)
    def test_the_first_plan_is_drivable(self, stack: str) -> None:
        map_data, scenario, run = _run(stack)
        envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
        assert run.plans, f"{stack} planned nothing, so there is nothing to check"
        report = path_is_drivable(
            run.plans[0].path,
            scenario.robot,
            envelope,
            scenario.static_obstacles,
            OccupancyGrid(map_data),
        )
        assert report.drivable, f"{stack}: {report.describe()}"

    @pytest.mark.parametrize("stack", STACKS)
    def test_every_replan_is_drivable_too(self, stack: str) -> None:
        """A replan may legitimately run *closer* than the first plan —
        that is what the room-to-leave bubble is for. It may not run
        inside the hard boundary, which is the line the bubble was
        written never to cross.
        """
        map_data, scenario, run = _run(stack)
        envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
        grid = OccupancyGrid(map_data)
        for index, plan in enumerate(run.plans[1:], start=1):
            report = path_is_drivable(
                plan.path, scenario.robot, envelope, scenario.static_obstacles, grid
            )
            assert report.drivable, f"{stack} replan {index}: {report.describe()}"

    def test_the_validator_rejects_a_path_that_clips_a_wall(self) -> None:
        """The guard against a validator that passes everything.

        Aimed at a cell the map actually marks, rather than at a hand-made
        number, so it stays a real rejection if the clearance definition
        changes.
        """
        map_data, scenario, _ = _run("astar+dwa")
        envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
        grid = OccupancyGrid(map_data)
        blocked = [index for index, cell in enumerate(map_data.cells) if cell == 100]
        assert blocked, "the map has no obstacles, so this proves nothing"
        row, col = divmod(blocked[0], map_data.width)
        centre = Point2D(
            x=map_data.origin.x + (col + 0.5) * map_data.resolution,
            y=map_data.origin.y + (row + 0.5) * map_data.resolution,
        )
        report = path_is_drivable([centre, centre], scenario.robot, envelope, (), grid)
        assert not report.drivable
        assert report.shortfall > 0.0

    def test_a_violation_between_two_legal_waypoints_is_caught(self) -> None:
        """Sampling only the waypoints would pass a straight line whose
        ends are clear and whose middle goes through the cart — the exact
        shape a two-waypoint global path has.

        Written against a constructed circle standing in for the cart:
        the live scene keeps its cart in the *dynamic* set, which this
        fence excludes by design, so borrowing it would test nothing.
        """
        cart = CircleObstacle(center=Point2D(x=7.0, y=4.5), radius=0.4)
        envelope = SafetyEnvelope.for_noise(SensorNoise(localization_drift_m=0.1))
        ends = [Point2D(x=4.0, y=4.5), Point2D(x=10.0, y=4.5)]
        for end in ends:
            clear = path_is_drivable([end], ROBOT, envelope, [cart])
            assert clear.drivable, f"the endpoint ({end.x}, {end.y}) is already blocked"
        report = path_is_drivable(ends, ROBOT, envelope, [cart])
        assert not report.drivable, report.describe()
        assert report.worst_point is not None
        assert report.worst_point.x == pytest.approx(cart.center.x, abs=0.1)

    def test_the_line_a_hair_outside_the_boundary_still_passes(self) -> None:
        """The other side of the same edge. A validator that rejected
        everything near an obstacle would make L4 unsatisfiable and the
        contract would have to be loosened to get any work done.
        """
        cart = CircleObstacle(center=Point2D(x=7.0, y=4.5), radius=0.4)
        envelope = SafetyEnvelope.for_noise(SensorNoise(localization_drift_m=0.1))
        offset = cart.radius + ROBOT.radius + envelope.position_uncertainty_m + 1e-3
        past = [Point2D(x=4.0, y=4.5 + offset), Point2D(x=10.0, y=4.5 + offset)]
        report = path_is_drivable(past, ROBOT, envelope, [cart])
        assert report.drivable, report.describe()
        assert report.worst_clearance == pytest.approx(envelope.position_uncertainty_m, abs=2e-3)

    def test_it_measures_metres_and_not_cells(self) -> None:
        """The threshold must carry no term proportional to cell size.

        The planner's inflation does carry one — ``√2 × resolution`` — and
        that is the difference this whole phase exists to keep straight: a
        path the *grid* would refuse is not thereby infeasible, it is
        coarsely rasterised. Asserted against the two numbers directly, so
        it fails the moment somebody reaches for ``_inflation_radius``
        here for convenience.
        """
        map_data, scenario, _ = _run("astar+dwa")
        envelope = SafetyEnvelope.for_noise(scenario.sensor_noise)
        report = path_is_drivable([Point2D(x=1.5, y=4.5)], scenario.robot, envelope)
        assert report.required_clearance == pytest.approx(envelope.position_uncertainty_m)
        assert _inflation_radius(map_data, scenario) == pytest.approx(
            hard_clearance(scenario.robot, envelope) + math.sqrt(2.0) * map_data.resolution
        )
        assert _inflation_radius(map_data, scenario) > hard_clearance(scenario.robot, envelope)


def _stopping_violations(scenario, run) -> list[tuple[float, float]]:
    """Steps where the robot could not have stopped before the cart.

    Measured on the **true** pose, not the believed one. With drift the
    robot brakes according to where it *thinks* it is, and that gap is
    precisely what the deployment's envelope exists to cover — so a check
    run on the believed pose would be marking its own homework.
    """
    period = scenario.simulation_dt
    surface = 0.4 + scenario.robot.radius
    out = []
    for point in run.result.trajectory:
        gap = math.hypot(point.x - 7.0, point.y - 4.5) - surface
        speed = point.linear_velocity
        if stopping_distance(speed, scenario.robot) + speed * period > gap:
            out.append((round(gap, 4), round(speed, 4)))
    return out


class TestAdmissibleStoppingIsAGuaranteeNotAWeight:
    """The criterion measured the wrong distance, and it cost a collision.

    ``sudden_stop`` with the shipped weights is **green**: the robot slows
    because the clearance term is expensive, not because anything forbids
    the speed. So a scenario test proves nothing here — the claim has to
    be a property over the whole trajectory, checked with the soft terms
    turned off.

    "Dynamic Window" is not itself the guarantee. The window bounds what
    the *actuators* can reach in one control period; the admissibility
    condition (Fox, Burgard and Thrun, 1997) is separate and reads the
    distance to the **nearest obstacle**. The implementation read the
    distance to the **goal**, which is a goal-arrival device wearing a
    safety name.
    """

    def test_it_holds_with_the_shipped_weights(self) -> None:
        _, scenario, run = _run("astar+dwa")
        assert _stopping_violations(scenario, run) == []

    def test_it_holds_with_the_clearance_term_switched_off(self) -> None:
        """A hard guarantee has to survive every soft term being zeroed;
        otherwise it is not a guarantee, it is a habit."""
        _, scenario, run = _run("astar+dwa", {"weight_clearance": 0.0})
        assert _stopping_violations(scenario, run) == []

    def test_the_case_that_used_to_collide(self) -> None:
        """Regression. ``weight_clearance=0`` with a half-second horizon
        gave **collision, closest approach −0.002 m, 23 steps unable to
        stop**. Both are ordinary candidate knobs, which is the point: no
        legal configuration may reach through to the hard set.
        """
        _, scenario, run = _run(
            "astar+dwa", {"weight_clearance": 0.0, "horizon_seconds": 0.5}
        )
        assert run.result.status is not EpisodeStatus.COLLISION
        assert _stopping_violations(scenario, run) == []

    def test_the_speed_bound_reads_the_obstacle_and_not_only_the_goal(self) -> None:
        assert _uses(DWA_SOURCE, "to_obstacle = self._nearest_obstacle_distance(obstacles, state)")
        assert _uses(DWA_SOURCE, "headroom = max(0.0, min(to_goal, to_obstacle))")

    def test_an_empty_room_is_not_slowed_down(self) -> None:
        """With nothing in range the goal is the only bound, which is what
        the criterion always did and stays correct."""
        planner = DWAPlanner()
        assert planner._speed_that_stops_within(math.inf, ROBOT) == ROBOT.max_linear_velocity
        assert planner._speed_that_stops_within(0.0, ROBOT) == 0.0

    def test_the_bound_is_the_speed_that_exactly_fits(self) -> None:
        """Solved rather than sampled: ``v·t + v²/(2a) = headroom``. A
        robot 0.64 m from a cart may not do the naive ``√(2·a·d)``,
        because it also has to cover the step it spends reacting."""
        planner = DWAPlanner()
        headroom = 0.64
        speed = planner._speed_that_stops_within(headroom, ROBOT)
        period = planner.control_period
        assert stopping_distance(speed, ROBOT) + speed * period == pytest.approx(
            headroom, abs=1e-6
        )
        assert speed < math.sqrt(2.0 * ROBOT.max_linear_acceleration * headroom)
