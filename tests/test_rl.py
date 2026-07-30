"""Tests for the RL layer: observation encoding, rewards, Gym environment."""

from __future__ import annotations

import math

import numpy as np
import pytest

from planbench_benchmark import build_scenario
from planbench_rl import ObservationConfig, PlanBenchNavEnv, RewardConfig, encode, step_reward
from planbench_rl.observation import cross_track_error, downsample_lidar, lookahead_waypoints
from planbench_schemas.episode import EpisodeStatus, Observation
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.robot import RobotConfig


def p(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


ROBOT = RobotConfig(
    radius=0.3,
    max_linear_velocity=1.0,
    max_angular_velocity=2.0,
    max_linear_acceleration=1.0,
    max_angular_acceleration=3.0,
)


class TestLidarDownsampling:
    def test_takes_the_minimum_not_the_mean(self) -> None:
        """A single close ray must survive: averaging would hide it."""
        ranges = tuple([6.0] * 11 + [0.5])  # one ray sees an obstacle
        binned = downsample_lidar(ranges, bins=2, max_range=6.0)
        assert binned[1] == pytest.approx(0.5 / 6.0)
        assert binned[0] == pytest.approx(1.0)

    def test_handles_ray_count_not_divisible_by_bins(self) -> None:
        assert len(downsample_lidar(tuple([1.0] * 7), bins=3, max_range=2.0)) == 3

    def test_empty_scan_reads_as_free_space(self) -> None:
        assert np.all(downsample_lidar((), bins=4, max_range=5.0) == 1.0)


class TestWaypointEncoding:
    def test_waypoints_are_in_the_robot_frame(self) -> None:
        """Facing +y, a path along +x must appear to the robot's right."""
        path = (p(0, 0), p(10, 0))
        points = lookahead_waypoints(path, p(0, 0), math.pi / 2, ObservationConfig())
        first_x, first_y = points[0]
        assert first_x == pytest.approx(0.0, abs=1e-9)  # nothing straight ahead
        assert first_y < 0  # the path is to the right

    def test_waypoints_advance_along_the_path(self) -> None:
        config = ObservationConfig(num_waypoints=3, waypoint_spacing=1.0)
        points = lookahead_waypoints((p(0, 0), p(10, 0)), p(0, 0), 0.0, config)
        assert [round(x, 6) for x, _ in points] == [1.0, 2.0, 3.0]

    def test_short_path_clamps_to_the_end(self) -> None:
        config = ObservationConfig(num_waypoints=3, waypoint_spacing=5.0)
        points = lookahead_waypoints((p(0, 0), p(1, 0)), p(0, 0), 0.0, config)
        assert all(x == pytest.approx(1.0) for x, _ in points)


class TestCrossTrackError:
    def test_zero_on_the_path(self) -> None:
        assert cross_track_error((p(0, 0), p(10, 0)), p(5, 0)) == pytest.approx(0.0)

    def test_sign_distinguishes_the_two_sides(self) -> None:
        left = cross_track_error((p(0, 0), p(10, 0)), p(5, 1))
        right = cross_track_error((p(0, 0), p(10, 0)), p(5, -1))
        assert left > 0 and right < 0
        assert abs(left) == pytest.approx(1.0)


class TestObservationEncoding:
    def observation(self, **kw) -> Observation:
        defaults: dict = {
            "time": 0.0,
            "pose": Pose2D(x=1.0, y=1.0, theta=0.0),
            "linear_velocity": 0.5,
            "angular_velocity": -0.2,
            "goal_distance": 3.0,
            "goal_bearing": 0.4,
            "lidar_ranges": tuple([4.0] * 72),
        }
        defaults.update(kw)
        return Observation(**defaults)

    def test_size_matches_the_declared_layout(self) -> None:
        config = ObservationConfig()
        vector = encode(self.observation(), (p(0, 0), p(10, 0)), ROBOT, 6.0, config)
        assert vector.shape == (config.size,)
        assert vector.dtype == np.float32

    def test_always_bounded_and_finite(self) -> None:
        vector = encode(self.observation(), (p(0, 0), p(10, 0)), ROBOT, 6.0, ObservationConfig())
        assert np.all(np.isfinite(vector))
        assert vector.min() >= -1.0 and vector.max() <= 1.0

    def test_far_goal_is_clipped_not_wrapped(self) -> None:
        vector = encode(
            self.observation(goal_distance=1000.0),
            (p(0, 0), p(10, 0)),
            ROBOT,
            6.0,
            ObservationConfig(num_lidar_bins=8),
        )
        assert vector[8] == pytest.approx(1.0)

    def test_ground_truth_obstacles_are_not_included(self) -> None:
        """The policy must not see anything a real robot could not sense."""
        config = ObservationConfig()
        assert config.size == config.num_lidar_bins + 4 + 2 * config.num_waypoints + 1


class TestRewards:
    def test_progress_dominates_the_time_penalty(self) -> None:
        config = RewardConfig()
        moving = step_reward(
            config,
            progress_metres=0.05,
            path_deviation=0.0,
            clearance=1.0,
            linear_velocity=1.0,
            angular_velocity=0.0,
            previous_angular_velocity=0.0,
            status=EpisodeStatus.RUNNING,
        )
        idle = step_reward(
            config,
            progress_metres=0.0,
            path_deviation=0.0,
            clearance=1.0,
            linear_velocity=0.0,
            angular_velocity=0.0,
            previous_angular_velocity=0.0,
            status=EpisodeStatus.RUNNING,
        )
        assert moving.total > idle.total

    def test_reaching_the_goal_outweighs_any_shaping(self) -> None:
        config = RewardConfig()
        success = step_reward(
            config,
            progress_metres=0.0,
            path_deviation=5.0,
            clearance=0.05,
            linear_velocity=0.0,
            angular_velocity=0.0,
            previous_angular_velocity=0.0,
            status=EpisodeStatus.SUCCESS,
        )
        assert success.total > 0
        assert success.components["terminal"] == config.goal_reached

    def test_collision_is_heavily_penalised(self) -> None:
        breakdown = step_reward(
            RewardConfig(),
            progress_metres=1.0,
            path_deviation=0.0,
            clearance=0.0,
            linear_velocity=1.0,
            angular_velocity=0.0,
            previous_angular_velocity=0.0,
            status=EpisodeStatus.COLLISION,
        )
        assert breakdown.total < 0  # progress cannot buy off a crash

    def test_low_clearance_penalty_scales_with_the_deficit(self) -> None:
        config = RewardConfig()
        near = step_reward(
            config,
            progress_metres=0.0,
            path_deviation=0.0,
            clearance=0.05,
            linear_velocity=0.0,
            angular_velocity=0.0,
            previous_angular_velocity=0.0,
            status=EpisodeStatus.RUNNING,
        )
        comfortable = step_reward(
            config,
            progress_metres=0.0,
            path_deviation=0.0,
            clearance=0.34,
            linear_velocity=0.0,
            angular_velocity=0.0,
            previous_angular_velocity=0.0,
            status=EpisodeStatus.RUNNING,
        )
        assert near.components["clearance"] < comfortable.components["clearance"] < 0

    def test_oscillation_only_on_a_sign_flip(self) -> None:
        config = RewardConfig()
        flip = step_reward(
            config,
            progress_metres=0.0,
            path_deviation=0.0,
            clearance=1.0,
            linear_velocity=0.0,
            angular_velocity=0.5,
            previous_angular_velocity=-0.5,
            status=EpisodeStatus.RUNNING,
        )
        steady = step_reward(
            config,
            progress_metres=0.0,
            path_deviation=0.0,
            clearance=1.0,
            linear_velocity=0.0,
            angular_velocity=0.5,
            previous_angular_velocity=0.5,
            status=EpisodeStatus.RUNNING,
        )
        assert "oscillation" in flip.components
        assert "oscillation" not in steady.components

    def test_version_is_recorded(self) -> None:
        assert RewardConfig().version == "v1"


class TestEnvironment:
    def env(self, names=("open_space",), **kw) -> PlanBenchNavEnv:
        return PlanBenchNavEnv([build_scenario(name) for name in names], **kw)

    def test_spaces_match_the_configuration(self) -> None:
        config = ObservationConfig(num_lidar_bins=16, num_waypoints=2)
        env = self.env(observation_config=config)
        assert env.observation_space.shape == (config.size,)
        assert env.action_space.shape == (2,)

    def test_reset_returns_a_valid_observation(self) -> None:
        observation, info = self.env().reset(seed=1)
        assert np.all(np.isfinite(observation))
        assert info["scenario"] == "open_space"
        assert info["observation_version"] == "v1"

    def test_step_before_reset_is_rejected(self) -> None:
        with pytest.raises(RuntimeError, match="reset"):
            self.env().step(np.zeros(2, dtype=np.float32))

    @pytest.mark.parametrize(
        "action",
        [
            np.array([float("nan"), 0.0], dtype=np.float32),
            np.array([float("inf"), float("-inf")], dtype=np.float32),
        ],
    )
    def test_invalid_actions_stop_the_robot_and_are_counted(self, action) -> None:
        """A broken policy must not be able to command garbage velocities."""
        env = self.env()
        env.reset(seed=1)
        observation, reward, terminated, truncated, info = env.step(action)
        assert info["invalid_actions"] == 1
        assert math.isfinite(reward)
        assert np.all(np.isfinite(observation))

    def test_actions_are_clipped_to_the_robot_limits(self) -> None:
        env = self.env()
        env.reset(seed=1)
        env.step(np.array([50.0, -50.0], dtype=np.float32))
        state = env._engine.get_state()  # noqa: SLF001 - white-box limit check
        assert abs(state.linear_velocity) <= ROBOT.max_linear_velocity + 1e-9
        assert abs(state.angular_velocity) <= ROBOT.max_angular_velocity + 1e-9

    def test_same_seed_replays_identically(self) -> None:
        def rollout(seed: int) -> list[float]:
            env = self.env(("crossing_obstacle",))
            env.reset(seed=seed)
            rewards = []
            for _ in range(25):
                _, reward, terminated, truncated, _ = env.step(
                    np.array([0.6, 0.1], dtype=np.float32)
                )
                rewards.append(round(reward, 9))
                if terminated or truncated:
                    break
            return rewards

        assert rollout(11) == rollout(11)

    def test_different_seeds_change_a_dynamic_scenario(self) -> None:
        """Seeds must actually vary traffic, otherwise multi-seed
        benchmarking reports a fake variance of zero."""

        def obstacle_y(seed: int) -> float:
            env = self.env(("crossing_obstacle",))
            env.reset(seed=seed)
            for _ in range(10):
                env.step(np.array([0.5, 0.0], dtype=np.float32))
            return env._engine._trajectory[-1].obstacles[0].y  # noqa: SLF001

        assert obstacle_y(1) != obstacle_y(4)

    def test_truncates_at_max_episode_steps(self) -> None:
        env = self.env(max_episode_steps=5)
        env.reset(seed=1)
        for _ in range(5):
            _, _, terminated, truncated, _ = env.step(np.array([0.1, 0.0], dtype=np.float32))
        assert truncated and not terminated

    def test_reaching_the_goal_terminates_with_success(self) -> None:
        env = self.env(max_episode_steps=3000)
        env.reset(seed=1)
        for _ in range(3000):
            _, _, terminated, truncated, info = env.step(np.array([1.0, 0.0], dtype=np.float32))
            if terminated or truncated:
                break
        assert info["status"] == "success"
        assert info["is_success"] is True

    def test_requires_at_least_one_scenario(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            PlanBenchNavEnv([])

    def test_cycles_through_scenarios_across_episodes(self) -> None:
        env = self.env(("open_space", "wide_corridor"))
        first = env.reset(seed=1)[1]["scenario"]
        second = env.reset(seed=1)[1]["scenario"]
        assert {first, second} == {"open_space", "wide_corridor"}
