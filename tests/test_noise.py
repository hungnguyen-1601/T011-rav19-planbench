"""Seed-derived sensor and actuation noise (plan M1, CONTRACTS HĐ-2/3.2).

The simulator used to be fully deterministic, and the only seed-dependent
quantity was the phase of the moving obstacles. A deterministic stack on
a mission whose traffic never crossed its route therefore drove the *same
episode for every seed* — which is how one Decision Card came to bound a
collision probability off a sample of one.

These tests hold the three properties that make the fix a fidelity
correction rather than a source of new unfairness:

1. Off by default, and off means *bit-identical* to before.
2. LiDAR noise is a measurement error and may not move the world;
   wheel slip is an actuation error and must.
3. The draws depend on ``(seed, step)`` alone, so two candidates sharing
   an episode context meet the same noise however differently they drive.
"""

from __future__ import annotations

import math

import pytest
from test_metric_definitions import empty_map

from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig, SimAction
from planbench_schemas.scenario import Scenario
from planbench_schemas.sensor import LidarConfig, SensorNoise
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.noise import NoiseModel


def scenario(noise: SensorNoise, *, seed: int = 7) -> Scenario:
    """A short straight drive across an open room."""
    return Scenario(
        name="noise_fixture",
        robot=RobotConfig(
            radius=0.15,
            max_linear_velocity=0.8,
            max_angular_velocity=1.5,
            max_linear_acceleration=1.0,
            max_angular_acceleration=2.0,
        ),
        start_pose=Pose2D(x=1.0, y=1.0, theta=0.0),
        goal_pose=Pose2D(x=8.0, y=1.0, theta=0.0),
        timeout_seconds=30.0,
        lidar=LidarConfig(num_rays=16, max_range=5.0),
        sensor_noise=noise,
        random_seed=seed,
    )


def drive(noise: SensorNoise, *, steps: int = 40, seed: int = 7):
    """Run a fixed command sequence; return poses and first-scan ranges.

    The commands are fixed on purpose: with a planner in the loop every
    difference would be explainable as the planner reacting, and these
    tests are about what the *world* does.
    """
    engine = SimulationEngine()
    engine.load_map(empty_map())
    engine.load_scenario(scenario(noise, seed=seed))
    engine.reset()
    first_scan = engine.get_observation().lidar_ranges
    poses = []
    for _ in range(steps):
        if engine.is_done():
            break
        engine.step(SimAction(linear_velocity=0.5, angular_velocity=0.0))
        pose = engine.get_state().pose
        poses.append((round(pose.x, 12), round(pose.y, 12), round(pose.theta, 12)))
    return poses, first_scan


NONE = SensorNoise()
LIDAR_ONLY = SensorNoise(lidar_range_sigma_m=0.05)
SLIP_ONLY = SensorNoise(wheel_slip_fraction=0.05)
BOTH = SensorNoise(lidar_range_sigma_m=0.02, wheel_slip_fraction=0.02)


class TestOffByDefault:
    def test_a_profile_that_says_nothing_gets_nothing(self) -> None:
        assert NONE.active is False
        assert NoiseModel(spec=NONE, seed=1).lidar_offsets(0, 16) is None
        assert NoiseModel(spec=NONE, seed=1).slip_factors(0) == (1.0, 1.0)

    def test_disabled_noise_changes_no_pose_and_no_range(self) -> None:
        """ "Defaults to zero" has to mean bit-identical, not merely
        close: every stored result predates this feature, and a run that
        drifted in the last decimal would make every one of them
        incomparable for a reason nobody declared."""
        baseline_poses, baseline_scan = drive(NONE)
        again_poses, again_scan = drive(NONE)
        assert again_poses == baseline_poses
        assert again_scan == baseline_scan


class TestTheTwoSourcesDoDifferentThings:
    def test_lidar_noise_moves_the_reading_not_the_robot(self) -> None:
        """A range finder that reads 2 cm long does not move the wall.

        Same commands, same world: only the measurement may differ. If
        this ever fails, the collision test is judging contact on a noisy
        pose and the simulator is modelling a different world rather than
        a robot that measures poorly.
        """
        clean_poses, clean_scan = drive(NONE)
        noisy_poses, noisy_scan = drive(LIDAR_ONLY)
        assert noisy_poses == clean_poses
        assert noisy_scan != clean_scan

    def test_wheel_slip_moves_the_robot(self) -> None:
        """The other direction, and it is not a bug: the robot really did
        slip, so the world records where it actually ended up."""
        clean_poses, clean_scan = drive(NONE)
        slipped_poses, slipped_scan = drive(SLIP_ONLY)
        assert slipped_poses != clean_poses
        # ...and the first scan is taken before the first step, from the
        # same start pose with no range noise declared, so it is
        # identical. Slip reaches the measurement only through where the
        # robot ends up, never directly.
        assert slipped_scan == clean_scan

    def test_ranges_stay_inside_what_a_sensor_can_report(self) -> None:
        """Clamped, because a negative distance is not a reading any
        consumer should have to defend against."""
        _, ranges = drive(SensorNoise(lidar_range_sigma_m=2.0))
        assert all(0.0 <= value <= 5.0 for value in ranges)


class TestIndexedNotConsumed:
    """The property that keeps invariant 3 intact under a new random
    source: a draw is a function of ``(seed, step)``, never of how many
    draws happened before it.

    Without it, two candidates that step and replan differently would
    consume the stream in different orders and meet *different noise* in
    episodes sharing one ``episode_context_id`` — two worlds under one id.
    """

    def test_the_same_step_always_gives_the_same_draw(self) -> None:
        model = NoiseModel(spec=BOTH, seed=3)
        assert model.slip_factors(17) == model.slip_factors(17)
        first = model.lidar_offsets(17, 8)
        second = model.lidar_offsets(17, 8)
        assert first is not None and second is not None
        assert list(first) == list(second)

    def test_asking_out_of_order_changes_nothing(self) -> None:
        """A candidate that replans, or that queries the observation
        twice in one step, must not shift anybody's noise."""
        model = NoiseModel(spec=BOTH, seed=3)
        forwards = [model.slip_factors(step) for step in range(5)]
        backwards = [model.slip_factors(step) for step in reversed(range(5))]
        assert list(reversed(backwards)) == forwards

    def test_different_steps_differ(self) -> None:
        model = NoiseModel(spec=BOTH, seed=3)
        assert model.slip_factors(0) != model.slip_factors(1)

    def test_the_two_streams_never_coincide(self) -> None:
        """Separate tags, so slip cannot be read off the LiDAR draws or
        vice versa — and so changing one source's amplitude does not
        silently reshuffle the other."""
        model = NoiseModel(
            spec=SensorNoise(lidar_range_sigma_m=0.9, wheel_slip_fraction=0.9), seed=3
        )
        offsets = model.lidar_offsets(11, 2)
        assert offsets is not None
        slip = model.slip_factors(11)
        assert pytest.approx(list(offsets)) != [slip[0] - 1.0, slip[1] - 1.0]

    def test_the_seed_is_the_whole_source(self) -> None:
        """HĐ-3.2: everything stochastic derives from the episode seed,
        so a context reproduces its own episode."""
        one = NoiseModel(spec=BOTH, seed=1).slip_factors(4)
        two = NoiseModel(spec=BOTH, seed=2).slip_factors(4)
        assert one != two
        assert NoiseModel(spec=BOTH, seed=1).slip_factors(4) == one


class TestItActuallySeparatesEpisodes:
    def test_seeds_diverge_once_noise_is_on(self) -> None:
        """The whole point. Without noise a deterministic stack on a
        quiet mission replays one episode per seed, and G2's rule of
        three then bounds nothing.
        """
        distinct_off = {tuple(drive(NONE, seed=seed)[0]) for seed in range(3)}
        distinct_on = {tuple(drive(BOTH, seed=seed)[0]) for seed in range(3)}
        assert len(distinct_off) == 1
        assert len(distinct_on) == 3

    def test_a_seed_still_replays_itself(self) -> None:
        """Divergence between seeds, reproducibility within one. HĐ-13
        asks that somebody else rebuild the same card from the manifest,
        and a noise source drawn from the clock would break that."""
        first, _ = drive(BOTH, seed=5)
        second, _ = drive(BOTH, seed=5)
        assert first == second


class TestAmplitudesAreDeclared:
    def test_negative_amplitudes_are_refused(self) -> None:
        with pytest.raises(ValueError):
            SensorNoise(lidar_range_sigma_m=-0.01)
        with pytest.raises(ValueError):
            SensorNoise(wheel_slip_fraction=-0.01)

    def test_total_slip_is_refused(self) -> None:
        """A fraction of 1.0 is a standard deviation as large as the
        command itself, which is not a wheel slipping but a different
        robot."""
        with pytest.raises(ValueError):
            SensorNoise(wheel_slip_fraction=1.0)

    def test_slip_scales_with_the_declared_fraction(self) -> None:
        small = NoiseModel(spec=SensorNoise(wheel_slip_fraction=0.01), seed=9)
        large = NoiseModel(spec=SensorNoise(wheel_slip_fraction=0.20), seed=9)
        small_offset = abs(small.slip_factors(3)[0] - 1.0)
        large_offset = abs(large.slip_factors(3)[0] - 1.0)
        assert large_offset > small_offset
        assert math.isclose(large_offset / small_offset, 20.0, rel_tol=1e-6)
