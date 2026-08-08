"""Tests for the benchmark engine: registry, fairness, aggregation."""

from __future__ import annotations

import pytest

from planbench_benchmark import (
    AlgorithmSpec,
    BenchmarkSpec,
    FairnessRecord,
    build_global_planner,
    build_local_planner,
    list_algorithms,
    run_benchmark,
    validate_algorithm_config,
)
from planbench_benchmark.registry import AlgorithmConfigError, UnknownAlgorithmError
from planbench_benchmark.runner import aggregate_algorithm, run_single
from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario


@pytest.fixture
def robot() -> RobotConfig:
    return RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )


def make_scenario(robot: RobotConfig, **overrides) -> Scenario:
    defaults: dict = {
        "name": "benchmark-test",
        "robot": robot,
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=8.5, y=8.5, theta=0.0),
        "goal_tolerance": 0.4,
        "timeout_seconds": 60.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


class TestRegistry:
    def test_lists_stacks_with_benchmarkable_flags(self) -> None:
        infos = {info.id: info for info in list_algorithms()}
        assert infos["astar+dwa"].benchmarkable is True
        assert infos["astar+pure_pursuit"].benchmarkable is False
        assert infos["astar+dwa"].config_schema["properties"]["weight_clearance"]

    def test_builds_a_configured_planner(self) -> None:
        planner = build_local_planner("astar+dwa", {"weight_clearance": 3.0})
        assert planner.name == "dwa"
        assert planner.config.weight_clearance == 3.0  # type: ignore[attr-defined]

    def test_unknown_algorithm_rejected(self) -> None:
        with pytest.raises(UnknownAlgorithmError, match="unknown algorithm"):
            build_local_planner("astar+teleport")

    def test_invalid_config_rejected(self) -> None:
        with pytest.raises(AlgorithmConfigError, match="invalid config"):
            validate_algorithm_config("astar+dwa", {"velocity_samples": 0})

    def test_empty_config_uses_defaults(self) -> None:
        config = validate_algorithm_config("astar+dwa", None)
        assert config.velocity_samples == 9  # type: ignore[attr-defined]

    def test_two_stacks_are_benchmarkable_without_extra_installs(self) -> None:
        # The point of adding RRT*: a fresh clone can compare two real
        # stacks. astar+ppo does not count — it needs a trained model.
        ready = {
            info.id for info in list_algorithms() if info.benchmarkable and not info.requires_model
        }
        assert ready == {"astar+dwa", "rrtstar+dwa"}

    def test_declares_the_global_planner_of_every_stack(self) -> None:
        infos = {info.id: info for info in list_algorithms()}
        assert infos["astar+dwa"].global_planner == "astar"
        assert infos["astar+dwa"].stochastic_global_planner is False
        assert infos["rrtstar+dwa"].global_planner == "rrtstar"
        assert infos["rrtstar+dwa"].stochastic_global_planner is True
        assert infos["rrtstar+pure_pursuit"].benchmarkable is False
        for info in infos.values():
            assert info.global_planner == info.id.split("+", 1)[0]

    def test_builds_the_global_planner_for_a_stack(self) -> None:
        assert build_global_planner("astar+dwa").name == "astar"
        planner = build_global_planner("rrtstar+dwa", episode_seed=11)
        assert planner.name == "rrtstar"
        assert planner.episode_seed == 11  # type: ignore[attr-defined]

    def test_unknown_stack_has_no_global_planner(self) -> None:
        with pytest.raises(UnknownAlgorithmError, match="unknown algorithm"):
            build_global_planner("teleport+dwa")


class TestBenchmarkSpec:
    def test_rejects_duplicate_algorithms(self) -> None:
        with pytest.raises(ValueError, match="duplicate algorithms"):
            BenchmarkSpec(
                name="dup",
                algorithms=(AlgorithmSpec(id="astar+dwa"), AlgorithmSpec(id="astar+dwa")),
                seeds=(1,),
            )

    def test_rejects_duplicate_seeds(self) -> None:
        with pytest.raises(ValueError, match="seeds must be unique"):
            BenchmarkSpec(name="dup", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1, 1))

    def test_requires_at_least_one_algorithm_and_seed(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkSpec(name="empty", algorithms=(), seeds=(1,))
        with pytest.raises(ValueError):
            BenchmarkSpec(name="empty", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=())


class TestFairness:
    def test_identical_conditions_hash_identically(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        first = FairnessRecord.build(map_data, scenario, (1, 2, 3))
        second = FairnessRecord.build(map_data, scenario, (1, 2, 3))
        assert first.conditions_checksum == second.conditions_checksum

    def test_scenario_seed_does_not_change_identity(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        """The benchmark supplies seeds, so the scenario's own seed field
        must not affect the fairness identity."""
        map_data = bordered_map_factory(12, 12)
        base = make_scenario(robot, random_seed=0)
        reseeded = make_scenario(robot, random_seed=99)
        assert (
            FairnessRecord.build(map_data, base, (1,)).conditions_checksum
            == FairnessRecord.build(map_data, reseeded, (1,)).conditions_checksum
        )

    @pytest.mark.parametrize(
        "override",
        [
            {"timeout_seconds": 61.0},
            {"simulation_dt": 0.04},
            {"goal_tolerance": 0.5},
            {"goal_pose": Pose2D(x=8.0, y=8.5, theta=0.0)},
        ],
    )
    def test_changed_conditions_change_the_hash(
        self, bordered_map_factory, robot: RobotConfig, override: dict
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        base = FairnessRecord.build(map_data, make_scenario(robot), (1,))
        changed = FairnessRecord.build(map_data, make_scenario(robot, **override), (1,))
        assert base.conditions_checksum != changed.conditions_checksum

    def test_changed_map_changes_the_hash(self, bordered_map_factory, robot: RobotConfig) -> None:
        scenario = make_scenario(robot)
        base = FairnessRecord.build(bordered_map_factory(12, 12), scenario, (1,))
        changed = FairnessRecord.build(
            bordered_map_factory(12, 12, occupied=((5, 5),)), scenario, (1,)
        )
        assert base.conditions_checksum != changed.conditions_checksum

    def test_different_seed_list_changes_the_hash(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        assert (
            FairnessRecord.build(map_data, scenario, (1, 2)).conditions_checksum
            != FairnessRecord.build(map_data, scenario, (1, 3)).conditions_checksum
        )


class TestRunBenchmark:
    def test_runs_every_algorithm_seed_pair(self, bordered_map_factory, robot: RobotConfig) -> None:
        spec = BenchmarkSpec(
            name="pairs",
            algorithms=(AlgorithmSpec(id="astar+dwa"), AlgorithmSpec(id="astar+pure_pursuit")),
            seeds=(1, 2),
        )
        report = run_benchmark(bordered_map_factory(12, 12), make_scenario(robot), spec)
        assert len(report.runs) == 4
        assert {run.algorithm for run in report.runs} == {"astar+dwa", "astar+pure_pursuit"}
        assert {run.seed for run in report.runs} == {1, 2}
        assert len(report.aggregates) == 2
        assert [run.episode_index for run in report.runs] == [0, 1, 2, 3]

    def test_the_episode_seed_reaches_a_sampling_global_planner(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        # Without this wiring every episode would replay one tree, and
        # sweeping many seeds would measure nothing about RRT*.
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        algorithm = AlgorithmSpec(id="rrtstar+dwa")
        first = run_single(map_data, scenario, algorithm, seed=1)
        second = run_single(map_data, scenario, algorithm, seed=2)
        assert first.plan.success and second.plan.success
        assert first.plan.path != second.plan.path

    def test_the_same_seed_reproduces_a_sampling_stack(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        algorithm = AlgorithmSpec(id="rrtstar+dwa")
        first = run_single(map_data, scenario, algorithm, seed=5)
        second = run_single(map_data, scenario, algorithm, seed=5)
        assert first.plan.path == second.plan.path
        assert first.result.trajectory == second.result.trajectory

    def test_a_deterministic_stack_ignores_the_planner_seed(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        algorithm = AlgorithmSpec(id="astar+dwa")
        assert (
            run_single(map_data, scenario, algorithm, seed=1).plan.path
            == run_single(map_data, scenario, algorithm, seed=2).plan.path
        )

    def test_reports_progress_per_run(self, bordered_map_factory, robot: RobotConfig) -> None:
        seen: list[str] = []
        spec = BenchmarkSpec(
            name="progress", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1, 2)
        )
        run_benchmark(
            bordered_map_factory(12, 12),
            make_scenario(robot),
            spec,
            on_run=lambda record, run: seen.append(
                f"{record.algorithm}:{record.seed}:{len(run.result.trajectory)}"
            ),
        )
        assert [entry.rsplit(":", 1)[0] for entry in seen] == ["astar+dwa:1", "astar+dwa:2"]
        # The callback receives the full episode, enabling replay storage.
        assert all(int(entry.rsplit(":", 1)[1]) > 0 for entry in seen)

    def test_report_carries_the_fairness_proof(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        spec = BenchmarkSpec(name="fair", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(7,))
        report = run_benchmark(map_data, scenario, spec)
        assert report.fairness.map_checksum == map_data.checksum()
        assert report.fairness.seeds == (7,)
        assert report.fairness.timeout_seconds == scenario.timeout_seconds

    def test_per_algorithm_config_is_applied(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        spec = BenchmarkSpec(
            name="configured",
            algorithms=(
                AlgorithmSpec(id="astar+dwa", config={"weight_velocity": 0.0}),
                AlgorithmSpec(id="astar+pure_pursuit"),
            ),
            seeds=(1,),
        )
        report = run_benchmark(bordered_map_factory(12, 12), make_scenario(robot), spec)
        slow = next(r for r in report.runs if r.algorithm == "astar+dwa")
        fast = next(r for r in report.runs if r.algorithm == "astar+pure_pursuit")
        # Zero velocity reward makes DWA crawl compared to pure pursuit.
        assert slow.metrics.average_speed < fast.metrics.average_speed

    def test_deterministic_report(self, bordered_map_factory, robot: RobotConfig) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = make_scenario(robot)
        spec = BenchmarkSpec(
            name="determinism", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1, 2)
        )
        first = run_benchmark(map_data, scenario, spec)
        second = run_benchmark(map_data, scenario, spec)
        assert [r.metrics.trajectory_length for r in first.runs] == [
            r.metrics.trajectory_length for r in second.runs
        ]


class TestAggregation:
    def _record(self, status: EpisodeStatus, **metric_overrides):
        from planbench_benchmark.spec import RunRecord
        from planbench_metrics import EpisodeMetrics

        defaults: dict = {
            "status": status,
            "success": status is EpisodeStatus.SUCCESS,
            "collision": status is EpisodeStatus.COLLISION,
            "travel_time": 10.0,
            "steps": 200,
            "trajectory_length": 12.0,
            "average_speed": 1.2,
            "max_speed": 1.5,
            # `smoothness` is Σ|Δθ| over path length — the only one of the
            # two comparable across episodes of different length, and the
            # one the leaderboard scores. The spec-literal Σ(Δθ)² lives in
            # `smoothness_squared` and is left unset here.
            "smoothness": 0.025,
            "min_clearance": 0.4,
        }
        defaults.update(metric_overrides)
        return RunRecord(
            algorithm="astar+dwa",
            seed=1,
            status=status,
            reason="",
            metrics=EpisodeMetrics(**defaults),
            trajectory_points=201,
            episode_index=0,
        )

    def test_rates_cover_every_status(self) -> None:
        runs = [
            self._record(EpisodeStatus.SUCCESS),
            self._record(EpisodeStatus.COLLISION),
            self._record(EpisodeStatus.TIMEOUT),
            self._record(EpisodeStatus.STUCK),
        ]
        aggregate = aggregate_algorithm("astar+dwa", runs)
        assert aggregate.episodes == 4
        assert aggregate.success_rate == 0.25
        assert aggregate.collision_rate == 0.25
        assert aggregate.timeout_rate == 0.25
        assert aggregate.stuck_rate == 0.25
        assert aggregate.no_progress_rate == 0.0

    def test_means_use_successful_episodes_only(self) -> None:
        runs = [
            self._record(EpisodeStatus.SUCCESS, travel_time=10.0),
            self._record(EpisodeStatus.COLLISION, travel_time=1.0),  # fast failure
        ]
        aggregate = aggregate_algorithm("astar+dwa", runs)
        assert aggregate.mean_travel_time_successful == 10.0

    def test_clearance_uses_all_episodes(self) -> None:
        runs = [
            self._record(EpisodeStatus.SUCCESS, min_clearance=0.5),
            self._record(EpisodeStatus.COLLISION, min_clearance=-0.1),
        ]
        aggregate = aggregate_algorithm("astar+dwa", runs)
        assert aggregate.mean_min_clearance == pytest.approx(0.2)
        assert aggregate.worst_min_clearance == pytest.approx(-0.1)

    def test_empty_runs_rejected(self) -> None:
        with pytest.raises(ValueError, match="no runs"):
            aggregate_algorithm("astar+dwa", [])
