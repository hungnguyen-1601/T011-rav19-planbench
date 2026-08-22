"""Four more ways a real robot is worse than this simulator was.

Added 2026-08-13: localisation error, LiDAR dropout, systematic odometry
bias, control latency. Every one defaults to zero, so a profile written
before them behaves identically to the last float.

**The line these tests exist to hold** is the one ``noise.py`` was
written around: a *measurement* error must never reach the collision
test. A collision judged on a believed pose simulates a different world
rather than a robot that does not know where it is — and it would let a
badly localised robot pass through walls it truly hit.
"""

from __future__ import annotations

import inspect

import pytest

from planbench_schemas.geometry import Pose2D
from planbench_schemas.map import CellState, MapData
from planbench_schemas.robot import RobotConfig, SimAction
from planbench_schemas.scenario import Scenario
from planbench_schemas.sensor import LidarConfig, SensorNoise
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.noise import NoiseModel


def open_map() -> MapData:
    """A walled 10 x 10 m room at 0.5 m, so a scan always returns something."""
    width = height = 20
    cells = [
        CellState.OCCUPIED.value
        if (r in (0, height - 1) or c in (0, width - 1))
        else CellState.FREE.value
        for r in range(height)
        for c in range(width)
    ]
    return MapData(
        name="noise-room",
        width=width,
        height=height,
        resolution=0.5,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )


def scenario_with(noise: SensorNoise, **overrides) -> Scenario:
    return Scenario(
        name="noise-scenario",
        robot=RobotConfig(
            radius=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=2.0,
            max_linear_acceleration=1.0,
            max_angular_acceleration=3.0,
        ),
        start_pose=Pose2D(x=2.0, y=2.0, theta=0.0),
        goal_pose=Pose2D(x=8.0, y=8.0, theta=0.0),
        goal_tolerance=0.4,
        timeout_seconds=60.0,
        simulation_dt=0.05,
        lidar=LidarConfig(num_rays=36, max_range=6.0),
        sensor_noise=noise,
        random_seed=7,
        **overrides,
    )


def engine_for(noise: SensorNoise) -> SimulationEngine:
    engine = SimulationEngine()
    engine.load_map(open_map())
    engine.load_scenario(scenario_with(noise))
    engine.reset()
    return engine


class TestNothingChangesWhenNothingIsDeclared:
    """Every field defaults to zero. A profile written before these
    existed must behave identically, or adding them silently re-ran every
    measurement this project has taken."""

    def test_the_default_spec_is_inactive(self) -> None:
        assert SensorNoise().active is False

    def test_the_observation_is_the_true_pose(self) -> None:
        engine = engine_for(SensorNoise())
        engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        assert engine.get_observation().pose == engine.get_state().pose

    def test_a_command_takes_effect_at_once(self) -> None:
        engine = engine_for(SensorNoise())
        engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        assert engine.get_state().linear_velocity > 0.0


class TestLocalisationErrorIsMeasurementOnly:
    """The rule LiDAR range noise already follows, applied to the pose."""

    def test_the_robot_believes_it_is_somewhere_it_is_not(self) -> None:
        engine = engine_for(SensorNoise(localization_drift_m=0.5))
        for _ in range(20):
            engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        believed = engine.get_observation().pose
        true = engine.get_state().pose
        assert (believed.x, believed.y) != (true.x, true.y)

    def test_the_collision_test_never_consults_the_noise_model(self) -> None:
        """Asserted on the code rather than on an outcome: a collision
        judged on a believed pose would let a badly localised robot pass
        through a wall it truly hit, and no episode-level assertion
        catches that reliably."""
        source = inspect.getsource(SimulationEngine._check_termination)
        assert "_noise" not in source
        assert "_believed_pose" not in source

    def test_the_trajectory_records_the_true_pose(self) -> None:
        """HĐ-5's trace is what every metric is computed from. Recording
        a believed pose would make ``path_length`` and every clearance a
        measurement of the robot's opinion."""
        engine = engine_for(SensorNoise(localization_drift_m=0.5))
        for _ in range(10):
            engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        true = engine.get_state().pose
        engine.stop()
        last = engine.get_result().trajectory[-1]
        assert (last.x, last.y) == (true.x, true.y)

    def test_the_goal_distance_is_the_one_the_robot_can_work_out(self) -> None:
        """Reporting the true distance beside a believed pose would hand
        back a cross-check no robot has — a controller could recover the
        true pose from the pair."""
        engine = engine_for(SensorNoise(localization_drift_m=0.8))
        for _ in range(15):
            engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        observation = engine.get_observation()
        true = engine.get_state().pose
        believed_gap = ((8.0 - observation.pose.x) ** 2 + (8.0 - observation.pose.y) ** 2) ** 0.5
        true_gap = ((8.0 - true.x) ** 2 + (8.0 - true.y) ** 2) ** 0.5
        assert observation.goal_distance == pytest.approx(believed_gap)
        assert observation.goal_distance != pytest.approx(true_gap)

    def test_drift_is_correlated_rather_than_per_step_jitter(self) -> None:
        """A controller averages jitter away and cannot average away an
        estimate wrong in the same direction for twenty seconds. If this
        were per-step noise the error would change sign constantly."""
        model = NoiseModel(spec=SensorNoise(localization_drift_m=1.0), seed=3)
        errors = [model.pose_error(step)[0] for step in range(30)]
        sign_changes = sum(1 for a, b in zip(errors, errors[1:], strict=False) if a * b < 0)
        assert sign_changes <= 3, "drift that flips sign every step is jitter, not drift"

    def test_a_jump_persists_rather_than_spiking(self) -> None:
        """The danger of a bad fix is that it *stays*. A one-step spike
        is something a controller never notices."""
        model = NoiseModel(spec=SensorNoise(localization_jump_probability=1.0), seed=5)
        within_one_window = [model.pose_error(step) for step in range(0, 40)]
        assert len(set(within_one_window)) == 1


class TestLidarDropoutReadsAsEmptySpace:
    def test_a_dropped_ray_reports_maximum_range_not_zero(self) -> None:
        """Zero reads as an obstacle touching the sensor — the opposite
        of what happened, and it would make dropout the safest event a
        planner can meet instead of the one that drives robots into
        glass.

        ``lt=1.0`` on the field is deliberate and mirrors
        ``wheel_slip_fraction``: a scanner that drops every ray is a
        broken sensor, not a noise amplitude. So this drops nearly all of
        them and checks every ray that *moved* moved to the ceiling.
        """
        clean = engine_for(SensorNoise()).get_observation().lidar_ranges
        dropped = engine_for(SensorNoise(lidar_dropout_probability=0.99))
        noisy = dropped.get_observation().lidar_ranges
        changed = [after for before, after in zip(clean, noisy, strict=True) if before != after]
        assert changed, "a 99% dropout rate that changed nothing is not a dropout"
        assert set(changed) == {6.0}

    def test_no_dropout_when_it_is_not_declared(self) -> None:
        engine = engine_for(SensorNoise())
        assert min(engine.get_observation().lidar_ranges) < 6.0

    def test_the_mask_is_bernoulli_and_seed_indexed(self) -> None:
        model = NoiseModel(spec=SensorNoise(lidar_dropout_probability=0.5), seed=11)
        first = model.dropout_mask(4, 36)
        again = model.dropout_mask(4, 36)
        assert first is not None
        assert list(first) == list(again), "a repeated query must give the same answer"
        assert list(first) != list(model.dropout_mask(5, 36))


class TestOdometryBiasAccumulates:
    """The half of actuation error that wheel slip does not model."""

    def test_it_is_drawn_once_and_held(self) -> None:
        """Slip is zero-mean per step so it averages out; a wheel worn
        smaller than its partner is wrong in one direction every step."""
        model = NoiseModel(spec=SensorNoise(odometry_bias_fraction=0.05), seed=2)
        assert model.odometry_bias() == model.odometry_bias()

    def test_it_is_off_by_default(self) -> None:
        assert NoiseModel(spec=SensorNoise(), seed=2).odometry_bias() == (1.0, 1.0)

    def test_it_changes_the_real_motion(self) -> None:
        """Actuation error, not measurement: the robot really did travel
        further than it was told to."""
        # Commanded below the envelope on purpose. At full throttle a
        # positive bias is clipped by `max_linear_velocity` and the two
        # runs land in the same place — correct behaviour (a worn wheel
        # does not lend the robot a larger envelope) that would make this
        # test read as "bias does nothing".
        clean = engine_for(SensorNoise())
        biased = engine_for(SensorNoise(odometry_bias_fraction=0.2))
        for _ in range(20):
            clean.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
            biased.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        assert clean.get_state().pose.x != biased.get_state().pose.x


class TestCommandLatency:
    def test_the_robot_holds_still_until_the_pipe_fills(self) -> None:
        """What a drive does before the first command reaches it.
        Inventing a zero-latency first command would give away exactly
        the head start being modelled."""
        engine = engine_for(SensorNoise(command_latency_steps=3))
        for _ in range(3):
            engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        assert engine.get_state().linear_velocity == pytest.approx(0.0)

    def test_the_command_arrives_after_the_declared_delay(self) -> None:
        engine = engine_for(SensorNoise(command_latency_steps=3))
        for _ in range(5):
            engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        assert engine.get_state().linear_velocity > 0.0

    def test_the_queue_is_emptied_between_episodes(self) -> None:
        """A re-run must start with an empty pipe rather than the tail of
        the last one, or the second episode of a pair is not the same
        episode as the first."""
        engine = engine_for(SensorNoise(command_latency_steps=2))
        for _ in range(6):
            engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        engine.reset()
        engine.step(SimAction(linear_velocity=1.0, angular_velocity=0.0))
        assert engine.get_state().linear_velocity == pytest.approx(0.0)


class TestEveryDrawStaysIndexedByStep:
    """The property the whole module is built on (HĐ-3.2).

    Two candidates run different numbers of steps and replan at different
    moments. If noise were consumed sequentially, the order of
    consumption would depend on candidate behaviour and the two would
    meet *different noise* in episodes sharing one ``episode_context_id``
    — two worlds under one id.
    """

    @pytest.mark.parametrize(
        "spec",
        [
            SensorNoise(localization_drift_m=0.5),
            SensorNoise(localization_jump_probability=0.5),
            SensorNoise(lidar_dropout_probability=0.3),
            SensorNoise(odometry_bias_fraction=0.05),
        ],
    )
    def test_asking_twice_gives_the_same_answer(self, spec: SensorNoise) -> None:
        model = NoiseModel(spec=spec, seed=13)
        for step in (0, 7, 41):
            assert model.pose_error(step) == model.pose_error(step)
            mask, again = model.dropout_mask(step, 12), model.dropout_mask(step, 12)
            assert (mask is None and again is None) or list(mask) == list(again)  # type: ignore[arg-type]

    def test_two_seeds_give_two_worlds(self) -> None:
        spec = SensorNoise(localization_drift_m=0.5)
        assert NoiseModel(spec=spec, seed=1).pose_error(10) != NoiseModel(
            spec=spec, seed=2
        ).pose_error(10)

    def test_each_source_draws_from_its_own_stream(self) -> None:
        """Frozen stream tags keep two sources from ever drawing the same
        numbers. Reusing one would correlate, say, a dropped ray with a
        slipped wheel for no physical reason."""
        from planbench_simulator import noise as noise_module

        tags = {
            name: value for name, value in vars(noise_module).items() if name.endswith("_STREAM")
        }
        assert len(tags) == len(set(tags.values())), f"stream tags collide: {tags}"
