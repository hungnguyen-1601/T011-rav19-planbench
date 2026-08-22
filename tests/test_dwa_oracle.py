"""P4 — the oracle knows the present, and must not know the future.

Test 7.9a of the plan. The whole value of the oracle rests on one
distinction that is easy to state and easy to violate by accident:

* **knowing the present perfectly** is what it is for — it removes
  estimation error so the constant-velocity *model* can be priced on its
  own;
* **knowing the future** would make it a different instrument entirely.
  An oracle that read ``position_at(t + eps)`` would carry no model error
  either, so the gap between it and the P5 tracker would stop being "the
  cost of having to estimate" and become an unreadable mixture.

``sudden_stop`` is where the difference becomes visible, and the boundary
is **observation, not event**. Before the cart parks, a backward
difference cannot know the stop is coming, so the oracle must extrapolate
straight *through* it. Once the stop has become the past, the oracle must
report zero — concluding that from evidence is not clairvoyance, it is
what any perfect tracker would also conclude.

Round 4 of the plan asked for the pre-stop velocity to persist *after*
``stop_time``, and round 5 withdrew it: that contradicts the backward
difference itself, since an obstacle stationary for a full ``dt`` has a
difference of exactly zero by definition. The transition phase in between
is written down here rather than left to chance, because a test that
asserts nothing at the boundary is a test that goes flaky there.
"""

from __future__ import annotations

import math

import pytest

from planbench_planning.dwa_predictive import DWAPredictiveConfig
from planbench_planning.dwa_predictive.oracle import (
    GroundTruthObstacleProvider,
    build_oracle,
)
from planbench_schemas.dynamic import DynamicObstacle, SuddenStopMotion, WaypointMotion
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_schemas.sensor import LidarConfig

ROBOT = RobotConfig(
    radius=0.26,
    max_linear_velocity=0.8,
    max_angular_velocity=1.2,
    max_linear_acceleration=0.5,
    max_angular_acceleration=1.0,
)

STOP_TIME = 3.0
CART_SPEED = 1.0
DT = 0.05


def _scenario(*obstacles: DynamicObstacle) -> Scenario:
    return Scenario(
        name="oracle_probe",
        description="ground-truth provider probe",
        robot=ROBOT,
        start_pose=Pose2D(x=1.0, y=4.5, theta=0.0),
        goal_pose=Pose2D(x=10.0, y=4.5, theta=0.0),
        timeout_seconds=30.0,
        simulation_dt=DT,
        dynamic_obstacles=obstacles,
        lidar=LidarConfig(num_rays=72, max_range=6.0),
    )


def _stopping_cart() -> DynamicObstacle:
    """Drives along +x at 1 m/s, then parks dead at ``STOP_TIME``."""
    return DynamicObstacle(
        name="cart",
        radius=0.4,
        motion=SuddenStopMotion(
            start=Point2D(x=2.0, y=4.5),
            heading=0.0,
            speed=CART_SPEED,
            stop_time=STOP_TIME,
        ),
        seed_time_offset=0.0,
    )


class TestTheProviderReadsOnlyThePast:
    """Three phases around ``stop_time``, and the boundary is observation."""

    @pytest.fixture()
    def provider(self) -> GroundTruthObstacleProvider:
        return GroundTruthObstacleProvider(_scenario(_stopping_cart()), DT)

    @pytest.mark.parametrize("time", [0.5, 1.5, 2.5, STOP_TIME - DT])
    def test_before_the_stop_it_reports_the_real_speed(
        self, provider: GroundTruthObstacleProvider, time: float
    ) -> None:
        """Phase one. Nothing has happened yet, so the difference is the
        cart's actual velocity — and, crucially, it stays that way right
        up to the last sample before the stop."""
        (track,) = provider(time)
        assert track.velocity.x == pytest.approx(CART_SPEED, abs=1e-9)
        assert track.velocity.y == pytest.approx(0.0, abs=1e-9)
        assert track.confidence == 1.0

    def test_it_extrapolates_straight_through_the_stop(
        self, provider: GroundTruthObstacleProvider
    ) -> None:
        """**The proof that it cannot read the future.**

        Sampled just before ``stop_time`` and asked where the cart will be
        a second later, the oracle must answer *one metre further on* —
        which is wrong, and has to be. The cart will have parked. An
        oracle that predicted the true future position here would be
        reading a stop that has not been observed.
        """
        (track,) = provider(STOP_TIME - DT)
        predicted = track.position_at(1.0)
        truth_at_stop = 2.0 + CART_SPEED * STOP_TIME
        assert predicted.x == pytest.approx(2.0 + CART_SPEED * (STOP_TIME - DT) + 1.0)
        assert predicted.x > truth_at_stop, "it predicted the parking it could not have seen"

    def test_the_transition_sample_is_the_partial_difference(
        self, provider: GroundTruthObstacleProvider
    ) -> None:
        """Phase two, written down so the boundary is not flaky.

        Exactly at ``stop_time`` the backward window straddles the event:
        the cart moved for the whole interval, so the difference is still
        the full speed. One sample later the window contains part of the
        stop and the difference decays. Neither value is a mistake — they
        are what a one-sided difference *is*.
        """
        (at_stop,) = provider(STOP_TIME)
        assert at_stop.velocity.x == pytest.approx(CART_SPEED, abs=1e-9)

        (after,) = provider(STOP_TIME + DT / 2.0)
        assert 0.0 < after.velocity.x < CART_SPEED

    @pytest.mark.parametrize("delay", [DT, 2 * DT, 1.0, 5.0])
    def test_once_the_stop_is_the_past_it_reports_zero(
        self, provider: GroundTruthObstacleProvider, delay: float
    ) -> None:
        """Phase three, and the half people mistake for a violation.

        Reporting zero here is *not* reading the future — the cart has
        been stationary for a full interval and the difference says so.
        Any perfect tracker would conclude the same. What was forbidden is
        knowing about the stop *before* it happened, which phase one
        already proved this cannot do.
        """
        (track,) = provider(STOP_TIME + delay)
        assert track.velocity.x == pytest.approx(0.0, abs=1e-12)
        assert track.position_at(2.0).x == pytest.approx(track.center.x)

    def test_the_warm_up_refuses_to_invent_a_velocity(
        self, provider: GroundTruthObstacleProvider
    ) -> None:
        """Before one full interval has passed there is no past to
        difference against, so the answer is zero rather than a guess.
        The P5 tracker will refuse identically — the two have to agree
        wherever neither has information, or the gap between them stops
        being estimation error."""
        (track,) = provider(0.0)
        assert track.velocity.x == 0.0
        (barely,) = provider(DT / 2.0)
        assert barely.velocity.x == 0.0


class TestItReproducesWhatTheEngineSees:
    """The provider is only useful if it is the *same* ground truth."""

    def test_position_matches_the_motion_law_exactly(self) -> None:
        from planbench_schemas.dynamic import position_at

        scenario = _scenario(_stopping_cart())
        provider = GroundTruthObstacleProvider(scenario, DT)
        for time in (0.0, 0.35, 1.2, STOP_TIME, 4.4):
            (track,) = provider(time)
            truth = position_at(scenario.dynamic_obstacles[0], time, scenario.random_seed)
            assert (track.center.x, track.center.y) == (truth.x, truth.y)

    def test_a_constant_velocity_obstacle_is_read_exactly(self) -> None:
        """Where the model is *right*, the oracle carries no error at all
        — which is what makes it an upper bound on prediction's value."""
        walker = DynamicObstacle(
            name="walker",
            radius=0.35,
            motion=WaypointMotion(
                waypoints=(Point2D(x=9.0, y=4.5), Point2D(x=2.0, y=4.5)),
                speed=0.6,
                loop=False,
            ),
            seed_time_offset=0.0,
        )
        provider = GroundTruthObstacleProvider(_scenario(walker), DT)
        (track,) = provider(2.0)
        assert track.velocity.x == pytest.approx(-0.6, abs=1e-9)
        # Extrapolated a second out, it lands on the truth.
        assert track.position_at(1.0).x == pytest.approx(9.0 - 0.6 * 3.0, abs=1e-9)

    def test_every_obstacle_gets_a_track(self) -> None:
        scenario = _scenario(
            _stopping_cart(),
            DynamicObstacle(
                name="second",
                radius=0.3,
                motion=WaypointMotion(
                    waypoints=(Point2D(x=5.0, y=1.0), Point2D(x=5.0, y=8.0)),
                    speed=0.4,
                    loop=False,
                ),
                seed_time_offset=0.0,
            ),
        )
        assert len(GroundTruthObstacleProvider(scenario, DT)(1.0)) == 2

    def test_a_static_scene_yields_no_tracks(self) -> None:
        assert GroundTruthObstacleProvider(_scenario(), DT)(1.0) == ()


class TestItCannotBecomeACandidate:
    """The plan's structural guarantee, asserted rather than trusted."""

    def test_it_names_itself_something_no_candidate_is_called(self) -> None:
        oracle = build_oracle(_scenario(_stopping_cart()))
        assert oracle.name == "dwa_oracle_predictive"
        assert oracle.name != "dwa_predictive"

    def test_the_registry_does_not_know_it(self) -> None:
        """It is not registered, and it could not be: the factory
        signature is ``config -> LocalPlanner`` with no scenario to close
        a ground-truth provider over. Being impossible to register is the
        feature — there is no path from here to ``/candidates``."""
        from planbench_benchmark.registry import ALGORITHMS

        assert not any("oracle" in name for name in ALGORITHMS)
        assert any("dwa" in name for name in ALGORITHMS), "read the wrong registry"

    def test_it_needs_a_scenario_which_a_factory_does_not_have(self) -> None:
        import inspect

        parameters = inspect.signature(build_oracle).parameters
        assert "scenario" in parameters

    def test_the_ground_truth_never_reaches_the_observation(self) -> None:
        """The second forbidden path: a ground-truth field on
        ``Observation`` would be a leak every controller could read, and
        standardised. The contract stays what the robot senses."""
        from planbench_schemas.episode import Observation

        assert set(Observation.model_fields) == {
            "time",
            "pose",
            "linear_velocity",
            "angular_velocity",
            "goal_distance",
            "goal_bearing",
            "lidar_ranges",
        }


class TestTheOracleDrivesWithIt:
    """End to end: the wiring works and the prediction reaches the cost."""

    def test_it_runs_an_episode_and_uses_its_tracks(self) -> None:
        from planbench_benchmark.registry import build_global_planner
        from planbench_benchmark.scenarios import build_scenario
        from planbench_simulator.nav_stack import run_stack

        map_data, scenario = build_scenario("intersection")
        scenario = scenario.model_copy(update={"timeout_seconds": 20.0})
        oracle = build_oracle(scenario, DWAPredictiveConfig(control_period=0.05))
        run = run_stack(
            map_data,
            scenario,
            oracle,
            build_global_planner("astar+dwa", episode_seed=scenario.random_seed),
        )
        assert run.result.steps > 50
        assert run.algorithm.endswith("dwa_oracle_predictive")

    def test_the_predicted_terms_actually_fire(self) -> None:
        """A provider that was wired but never consulted would pass every
        test above. This asks the controller for a decision in a scene
        with traffic and requires the predictive cost to be non-zero."""
        from planbench_schemas.episode import Observation
        from planbench_schemas.robot import RobotState

        scenario = _scenario(_stopping_cart())
        oracle = build_oracle(scenario, DWAPredictiveConfig(control_period=DT))
        oracle.reset([Point2D(x=1.0, y=4.5), Point2D(x=10.0, y=4.5)], ROBOT)
        result = oracle.compute(
            RobotState(pose=Pose2D(x=1.0, y=4.5, theta=0.0), linear_velocity=0.4),
            Observation(
                time=1.0,
                pose=Pose2D(x=1.0, y=4.5, theta=0.0),
                linear_velocity=0.4,
                angular_velocity=0.0,
                goal_distance=9.0,
                goal_bearing=0.0,
                lidar_ranges=(6.0,) * 72,
            ),
        )
        assert result.cost_components
        assert math.isfinite(result.cost_components["predicted_clearance"])
