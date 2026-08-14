"""P3 — the space-time rollout, before any tracker exists.

Velocities are **injected** here rather than estimated, which is the
point of the phase: it isolates "does rolling the world forward work" from
"can we tell how fast anything is moving", so a regression later has one
place to be.

The file is organised around the three ways this phase can be wrong, and
only the first is the one people expect:

1. **The prediction is off by a step.** ``rollout_batch`` returns column
   ``k`` as the pose after ``k+1`` steps, so obstacles must advance by
   ``(k+1)·horizon_dt``. Using ``k·horizon_dt`` gives a controller that
   reacts one beat late — and *no aggregate metric shows it*, because a
   stale prediction is still a prediction.
2. **A predictive term leaks into a hard constraint.** Contract L2 says a
   candidate parameter may not narrow the hard feasible set. The refusal
   and the speed bound therefore have to match ``dwa`` exactly, which is
   asserted on the refused ``(v, ω)`` set itself rather than on outcomes.
3. **The new terms do not switch off.** With no tracks this controller
   must *be* ``dwa`` — not resemble it. Every later comparison between
   the two rests on that, so it is checked as byte equality of commands
   over whole episodes rather than as a tolerance on one step.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.registry import build_global_planner
from planbench_benchmark.scenarios import build_scenario
from planbench_planning import DWAPlanner
from planbench_planning.common.dwa_core import rollout_times
from planbench_planning.dwa.planner import DWAConfig
from planbench_planning.dwa_predictive import (
    DWAPredictiveConfig,
    DWAPredictivePlanner,
    ObstacleTrack,
)
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig, RobotState
from planbench_simulator.nav_stack import run_stack

ROBOT = RobotConfig(
    radius=0.26,
    max_linear_velocity=0.8,
    max_angular_velocity=1.2,
    max_linear_acceleration=0.5,
    max_angular_acceleration=1.0,
)


def _tracks(*specs: tuple[float, float, float, float, float]) -> tuple[ObstacleTrack, ...]:
    """``(x, y, vx, vy, radius)`` tuples as tracks, for readable tests."""
    return tuple(
        ObstacleTrack(
            center=Point2D(x=x, y=y),
            velocity=Point2D(x=vx, y=vy),
            radius=radius,
        )
        for x, y, vx, vy, radius in specs
    )


class TestTheTimeAxisLinesUpWithTheRollout:
    """The off-by-one-step failure, checked directly rather than inferred.

    A prediction one step stale still moves, still points the right way,
    and still improves the metrics slightly. Nothing downstream would
    report it, so it is checked here against arithmetic done by hand.
    """

    def test_the_first_column_is_already_one_step_ahead(self) -> None:
        """``rollout_batch`` never returns the starting pose: its column 0
        is the pose after one integration step. An obstacle clock starting
        at zero would therefore compare step 1 of the robot against step 0
        of the world."""
        times = rollout_times(1.0, 0.1)
        assert times[0] == pytest.approx(0.1)
        assert times[-1] == pytest.approx(1.0)
        assert len(times) == 10

    def test_a_track_is_where_hand_arithmetic_puts_it(self) -> None:
        track = _tracks((5.0, 0.0, -1.0, 0.0, 0.4))[0]
        assert track.position_at(0.0).x == pytest.approx(5.0)
        assert track.position_at(0.5).x == pytest.approx(4.5)
        assert track.position_at(1.5).x == pytest.approx(3.5)

    def test_the_predicted_distance_matches_the_closed_form(self) -> None:
        """A stationary robot and one track closing head-on, so the answer
        is arithmetic: at column ``k`` the surface gap must be
        ``|x0 - v·(k+1)·dt| - radius``, and the minimum over the horizon
        is the value at the last column."""
        config = DWAPredictiveConfig(horizon_seconds=1.0, horizon_dt=0.1)
        planner = DWAPredictivePlanner(config)
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)], ROBOT)

        # One candidate, standing still: every rollout column is the origin.
        rollouts = np.zeros((1, 10, 2))
        tracks = _tracks((5.0, 0.0, -1.0, 0.0, 0.4))
        predicted, _ = planner._predict(rollouts, tracks)

        # Last column is 1.0 s ahead: the track has closed to x = 4.0.
        assert float(predicted[0]) == pytest.approx(4.0 - 0.4)

    def test_the_stale_clock_is_wrong_by_exactly_one_step_of_travel(self) -> None:
        """How big the off-by-one is, and that the implementation is on
        the right side of it.

        A clock of ``k·dt`` instead of ``(k+1)·dt`` leaves the world one
        column behind, which for a track closing at ``u`` is ``u·dt`` of
        missing approach — 0.1 m here. Small enough to look like rounding
        in any aggregate, which is why it is pinned against the closed
        form rather than eyeballed.
        """
        closing, dt, steps, radius, start = 1.0, 0.1, 10, 0.4, 5.0
        stale = start - closing * ((steps - 1) * dt) - radius
        correct = start - closing * (steps * dt) - radius
        assert stale - correct == pytest.approx(closing * dt)

        planner = DWAPredictivePlanner(
            DWAPredictiveConfig(horizon_seconds=steps * dt, horizon_dt=dt)
        )
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)], ROBOT)
        measured, _ = planner._predict(
            np.zeros((1, steps, 2)), _tracks((start, 0.0, -closing, 0.0, radius))
        )
        assert float(measured[0]) == pytest.approx(correct)
        assert float(measured[0]) != pytest.approx(stale)


class TestTheTensorHasTheShapeTheDocstringClaims:
    """Shape asserted, not eyeballed — the plan asked for exactly this."""

    def test_prediction_returns_one_value_per_candidate(self) -> None:
        planner = DWAPredictivePlanner(DWAPredictiveConfig(horizon_seconds=1.0, horizon_dt=0.1))
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0)], ROBOT)
        rollouts = np.zeros((7, 10, 2))
        predicted, ttc = planner._predict(rollouts, _tracks((3.0, 0.0, -0.5, 0.0, 0.3)))
        assert predicted.shape == (7,)
        assert ttc.shape == (7,)

    def test_several_tracks_reduce_to_the_nearest(self) -> None:
        """The minimum is over both axes — horizon *and* obstacles — so a
        second, further track must not change the answer."""
        planner = DWAPredictivePlanner(DWAPredictiveConfig(horizon_seconds=1.0, horizon_dt=0.1))
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0)], ROBOT)
        rollouts = np.zeros((1, 10, 2))
        near = _tracks((5.0, 0.0, -1.0, 0.0, 0.4))
        both = _tracks((5.0, 0.0, -1.0, 0.0, 0.4), (9.0, 0.0, 0.0, 0.0, 0.4))
        assert float(planner._predict(rollouts, both)[0][0]) == pytest.approx(
            float(planner._predict(rollouts, near)[0][0])
        )


class TestWithoutTracksItIsExactlyDWA:
    """The switch everything else rests on.

    Not "close to ``dwa``" — identical. Every later comparison of the two
    candidates reads their difference as the value of prediction, and a
    controller that already differed on an empty scene would put a
    constant offset into that reading.
    """

    @staticmethod
    def _episode(planner, scenario_name: str, seed: int = 0):
        map_data, scenario = build_scenario(scenario_name)
        scenario = scenario.model_copy(update={"timeout_seconds": 20.0, "random_seed": seed})
        run = run_stack(
            map_data,
            scenario,
            planner,
            build_global_planner("astar+dwa", episode_seed=seed),
        )
        return [(p.linear_velocity, p.angular_velocity) for p in run.result.trajectory]

    @pytest.mark.parametrize("scenario", ["doorway", "static_obstacles", "narrow_corridor"])
    def test_the_commands_are_identical_when_no_tracks_arrive(self, scenario: str) -> None:
        """The switch itself: no tracks, no predictive cost, no difference.

        Stated with an **explicit empty provider** since P5, because the
        default is no longer "no tracks" — it is the LiDAR tracker, which
        is the real candidate. This still pins the property everything
        rests on: each of the tracker's failure modes returns no velocity,
        and this is what no velocity has to mean.
        """
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        plain = self._episode(DWAPlanner(DWAConfig(**shared)), scenario)
        predictive = self._episode(
            DWAPredictivePlanner(DWAPredictiveConfig(**shared), provider=lambda _t: ()),
            scenario,
        )
        assert predictive == plain

    def test_the_predictive_terms_are_exactly_zero(self) -> None:
        """Not merely small. A term that was ``1e-17`` rather than zero
        would break ties differently on some later scene, and tie-breaking
        is what picks the command."""
        planner = DWAPredictivePlanner(DWAPredictiveConfig())
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0)], ROBOT)
        components = planner._score(
            velocity=0.5,
            omega=0.0,
            trajectory=(Point2D(x=0.0, y=0.0), Point2D(x=0.5, y=0.0)),
            clearance=1.0,
            predicted_clearance=math.inf,
            time_to_collision=math.inf,
            local_goal=Point2D(x=5.0, y=0.0),
        )
        assert components["predicted_clearance"] == 0.0
        assert components["time_to_collision"] == 0.0

    def test_the_cost_keys_are_dwa_plus_exactly_two(self) -> None:
        """A third term would be a third weight, and the plan's argument
        against one is in the ``_score`` docstring. If this list grows,
        the reason should be written down beside it."""
        predictive = DWAPredictivePlanner(DWAPredictiveConfig())
        predictive.reset([Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0)], ROBOT)
        plain = DWAPlanner(DWAConfig())
        plain.reset([Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0)], ROBOT)
        trajectory = (Point2D(x=0.0, y=0.0), Point2D(x=0.5, y=0.0))
        goal = Point2D(x=5.0, y=0.0)
        theirs = set(plain._score(0.5, 0.0, trajectory, 1.0, goal))
        ours = set(predictive._score(0.5, 0.0, trajectory, 1.0, math.inf, math.inf, goal))
        assert ours - theirs == {"predicted_clearance", "time_to_collision"}
        assert theirs - ours == set()


class TestTheHardConstraintsAreUntouched:
    """Contract L2, checked on the constraint rather than on an outcome.

    Test 7.4 of the plan, and it is split in two because the plan's own
    round-2 review found that stating only the first left the second free
    to drift.
    """

    @staticmethod
    def _state(x: float, v: float, w: float = 0.0) -> RobotState:
        return RobotState(pose=Pose2D(x=x, y=0.0, theta=0.0), linear_velocity=v, angular_velocity=w)

    @pytest.mark.parametrize(("speed", "omega"), [(0.0, 0.0), (0.4, 0.3), (0.8, -0.6), (0.75, 1.1)])
    def test_the_sampled_window_is_the_same_set(self, speed: float, omega: float) -> None:
        """(a) and (b) at once: the window this returns is built from the
        reachable set *and* the admissible-speed bound, so an equal window
        means neither moved."""
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        plain = DWAPlanner(DWAConfig(**shared))
        plain.reset(path, ROBOT)
        predictive = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
        predictive.reset(path, ROBOT)

        obstacles = np.array([[4.0, 0.0], [4.0, 0.6]])
        state = self._state(1.0, speed, omega)
        assert predictive._dynamic_window(state, obstacles) == plain._dynamic_window(
            state, obstacles
        )

    @pytest.mark.parametrize("declared", [None, 0.5, 1.5])
    def test_the_speed_bound_reads_the_same_declared_number(self, declared) -> None:
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        plain = DWAPlanner(DWAConfig(**shared))
        plain.reset(path, ROBOT, obstacle_speed=declared)
        predictive = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
        predictive.reset(path, ROBOT, obstacle_speed=declared)
        for headroom in (0.0, 0.25, 1.0, 4.0, math.inf):
            assert predictive._speed_that_stops_within(
                headroom, ROBOT
            ) == plain._speed_that_stops_within(headroom, ROBOT)

    @staticmethod
    def _observation(time: float, ranges: tuple[float, ...]) -> Observation:
        return Observation(
            time=time,
            pose=Pose2D(x=1.0, y=0.0, theta=0.0),
            linear_velocity=0.4,
            angular_velocity=0.0,
            goal_distance=9.0,
            goal_bearing=0.0,
            lidar_ranges=ranges,
        )

    def test_a_predicted_collision_does_not_refuse_a_measured_clear_command(self) -> None:
        """**The refusal itself, not the window around it.**

        This test exists because a mutation survived without it. Feeding
        ``min(measured, predicted)`` into ``if clearances[index] <=
        keep_out`` passed every other assertion in this class: the window
        tests read ``_dynamic_window``, which the refusal is not part of,
        and the equality-with-``dwa`` tests run with **no tracks**, where
        the predicted clearance is infinite and the mutation is invisible.
        A test named after a constraint has to touch the constraint.

        The scene separates the two clearances on purpose: the scan is
        empty, so every candidate is measured as wide open, while a track
        sits close and closing fast, so every candidate is *predicted* to
        breach. Prediction may make all of them expensive. It may not make
        any of them refused.
        """
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        planner = DWAPredictivePlanner(
            DWAPredictiveConfig(**shared),
            provider=lambda _t: _tracks((1.6, 0.0, -2.0, 0.0, 0.4)),
        )
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)], ROBOT)
        # Every ray at the same range reads as "nothing returned", so the
        # measured point cloud is empty and nothing can be refused.
        result = planner.compute(self._state(1.0, 0.4), self._observation(0.0, (6.0,) * 72))

        assert result.failure_reason == ""
        assert result.predicted_trajectory, "no command chosen, so something refused it"
        # And the prediction did fire — otherwise this proves nothing.
        assert result.cost_components["predicted_clearance"] > 0.0

    def test_a_measured_breach_is_refused_by_both_alike(self) -> None:
        """The other direction: prediction must not *rescue* a command
        the measurement refuses. Tracks that say the obstacle is leaving
        do not make a currently-blocked trajectory admissible."""
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        # A wall of returns right in front of the robot.
        blocked = tuple(0.28 if index < 6 else 6.0 for index in range(72))
        observation = self._observation(0.0, blocked)
        state = self._state(1.0, 0.4)

        plain = DWAPlanner(DWAConfig(**shared))
        plain.reset(path, ROBOT)
        fleeing = DWAPredictivePlanner(
            DWAPredictiveConfig(**shared),
            provider=lambda _t: _tracks((1.3, 0.0, 9.0, 0.0, 0.2)),
        )
        fleeing.reset(path, ROBOT)

        theirs = plain.compute(state, observation)
        ours = fleeing.compute(state, observation)
        assert (ours.failure_reason == "") == (theirs.failure_reason == "")
        assert ours.action.linear_velocity == theirs.action.linear_velocity

    def test_tracks_do_not_widen_the_window(self) -> None:
        """The temptation the plan spends a whole section refusing: a
        track proving an obstacle is *leaving* must not buy any extra
        speed. The window is built from measured points alone, so
        providing tracks — of any velocity — changes nothing about it."""
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]
        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        obstacles = np.array([[3.0, 0.0]])
        state = self._state(1.0, 0.8)

        without = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
        without.reset(path, ROBOT)
        fleeing = DWAPredictivePlanner(
            DWAPredictiveConfig(**shared),
            provider=lambda _t: _tracks((3.0, 0.0, 5.0, 0.0, 0.4)),
        )
        fleeing.reset(path, ROBOT)
        assert fleeing._dynamic_window(state, obstacles) == without._dynamic_window(
            state, obstacles
        )


class TestPredictionActuallyChangesTheScore:
    """A switch that never switches on would pass every test above."""

    def test_an_approaching_track_costs_more_than_a_departing_one(self) -> None:
        """The asymmetry the whole phase exists to produce, on one
        rollout: same geometry now, opposite futures."""
        config = DWAPredictiveConfig(horizon_seconds=1.0, horizon_dt=0.1)
        planner = DWAPredictivePlanner(config)
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)], ROBOT)
        # Robot creeping forward along +x.
        rollouts = np.stack([np.stack([np.linspace(0.05, 0.5, 10), np.zeros(10)], axis=1)])
        approaching = planner._predict(rollouts, _tracks((3.0, 0.0, -2.0, 0.0, 0.4)))
        departing = planner._predict(rollouts, _tracks((3.0, 0.0, 2.0, 0.0, 0.4)))
        assert float(approaching[0][0]) < float(departing[0][0])

    def test_time_to_collision_is_finite_only_when_one_is_coming(self) -> None:
        config = DWAPredictiveConfig(horizon_seconds=1.0, horizon_dt=0.1)
        planner = DWAPredictivePlanner(config)
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)], ROBOT)
        rollouts = np.zeros((1, 10, 2))
        _, hitting = planner._predict(rollouts, _tracks((1.0, 0.0, -2.0, 0.0, 0.4)))
        _, missing = planner._predict(rollouts, _tracks((9.0, 0.0, 0.0, 0.0, 0.4)))
        assert math.isfinite(float(hitting[0]))
        assert not math.isfinite(float(missing[0]))

    def test_a_breach_after_the_horizon_is_not_reported_at_its_edge(self) -> None:
        """**Regression.** A shorter prediction horizon must produce *no
        claim*, never an urgent one.

        The first implementation clamped the time axis with
        ``np.minimum`` instead of dropping columns, which is not "stop
        predicting" — it parks the track at its last predicted position
        and leaves it there for the rest of the rollout. Two things went
        wrong at once, and the second is the dangerous one: the clamped
        array was also what the time-to-collision indexed, so an
        intersection late in the rollout was reported as happening
        **exactly at the horizon edge**.

        Measured on this scene before the fix: a 2.0 s rollout with a
        0.2 s prediction horizon returned ``ttc = 0.2`` for a geometric
        intersection at 1.425 s. ``urgency`` scores that at 0.9 of
        maximum — near-certain imminent collision, for an event seven
        times further away, against a phantom obstacle that had stopped
        only inside the arithmetic.
        """
        config = DWAPredictiveConfig(
            horizon_seconds=2.0, horizon_dt=0.1, prediction_horizon_seconds=0.2
        )
        planner = DWAPredictivePlanner(config)
        planner.reset([Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)], ROBOT)

        # Robot creeps forward; the track closes from ahead. Nothing they
        # do together lands inside 0.2 seconds.
        forward = np.linspace(0.08, 1.6, 20)
        rollouts = np.stack([np.stack([forward, np.zeros(20)], axis=1)])
        track = _tracks((2.0, 0.0, -1.0, 0.0, 0.4))

        predicted, ttc = planner._predict(rollouts, track)
        assert not math.isfinite(float(ttc[0])), "a breach past the horizon was given a time"
        # And no phantom: the clearance is the honest minimum over the two
        # columns actually predicted, not a negative number invented by a
        # parked ghost.
        assert float(predicted[0]) > 0.0

    def test_a_longer_horizon_only_ever_confirms_the_shorter_one(self) -> None:
        """Truncation makes the horizons nest: the columns a short horizon
        evaluates are the *same* columns a long one evaluates first. So a
        short horizon either agrees with the long one about when the first
        breach happens, or says nothing at all. Clamping broke this — it
        reported a different, earlier time."""
        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        forward = np.linspace(0.08, 1.6, 20)
        rollouts = np.stack([np.stack([forward, np.zeros(20)], axis=1)])
        track = _tracks((2.0, 0.0, -1.0, 0.0, 0.4))

        def ttc_for(horizon: float) -> float:
            planner = DWAPredictivePlanner(
                DWAPredictiveConfig(
                    horizon_seconds=2.0, horizon_dt=0.1, prediction_horizon_seconds=horizon
                )
            )
            planner.reset(path, ROBOT)
            return float(planner._predict(rollouts, track)[1][0])

        full = ttc_for(2.0)
        assert math.isfinite(full)
        for shorter in (0.2, 0.5, 0.9, 1.5):
            answer = ttc_for(shorter)
            assert not math.isfinite(answer) or answer == pytest.approx(full)

    def test_the_prediction_horizon_bounds_how_far_it_looks(self) -> None:
        """A short horizon must not see a collision a long one does —
        otherwise the field is decoration."""
        path = [Point2D(x=0.0, y=0.0), Point2D(x=10.0, y=0.0)]
        rollouts = np.zeros((1, 20, 2))
        far = DWAPredictivePlanner(
            DWAPredictiveConfig(horizon_seconds=2.0, horizon_dt=0.1, prediction_horizon_seconds=2.0)
        )
        near = DWAPredictivePlanner(
            DWAPredictiveConfig(horizon_seconds=2.0, horizon_dt=0.1, prediction_horizon_seconds=0.2)
        )
        far.reset(path, ROBOT)
        near.reset(path, ROBOT)
        track = _tracks((3.0, 0.0, -1.5, 0.0, 0.4))
        assert float(far._predict(rollouts, track)[0][0]) < float(
            near._predict(rollouts, track)[0][0]
        )


class TestItIsDeterministic:
    """Same inputs, same bytes — and the reset has to mean it.

    The tracker of P5 is the first thing in this controller to hold state
    between steps, so the habit is established here while there is almost
    none to clear.
    """

    def test_two_episodes_on_one_instance_match_two_instances(self) -> None:
        shared = LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]

        def episode(planner, seed: int):
            map_data, scenario = build_scenario("doorway")
            scenario = scenario.model_copy(update={"timeout_seconds": 15.0, "random_seed": seed})
            run = run_stack(
                map_data,
                scenario,
                planner,
                build_global_planner("astar+dwa", episode_seed=seed),
            )
            return [(p.linear_velocity, p.angular_velocity) for p in run.result.trajectory]

        reused = DWAPredictivePlanner(DWAPredictiveConfig(**shared))
        first_reused = episode(reused, 0)
        second_reused = episode(reused, 1)

        first_fresh = episode(DWAPredictivePlanner(DWAPredictiveConfig(**shared)), 0)
        second_fresh = episode(DWAPredictivePlanner(DWAPredictiveConfig(**shared)), 1)

        assert first_reused == first_fresh
        assert second_reused == second_fresh
