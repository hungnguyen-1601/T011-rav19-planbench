"""P02 — information parity: every stack declares what it sees.

Two things are being defended here.

The first is the declaration itself: it must exist for every registered
stack and must never appear by default, because a wrong label is worse
than a missing one — it makes an unfair comparison look checked.

The second is the leaderboard's refusal to rank across declarations.
That refusal is what turns the label into a guarantee rather than a
decoration.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from planbench_api.approval import BenchmarkState
from planbench_api.leaderboard import build_leaderboard
from planbench_api.repositories import StoredBenchmark
from planbench_benchmark import (
    ALGORITHMS,
    OBSERVATION_CLASSES,
    AlgorithmAggregate,
    AlgorithmInfo,
    AlgorithmSpec,
    BenchmarkReport,
    BenchmarkSpec,
    FairnessRecord,
    list_algorithms,
)
from planbench_planning.common.local_base import LocalPlanner
from planbench_schemas.episode import Observation


class TestRegistryDeclaration:
    def test_every_stack_declares_both_observation_classes(self) -> None:
        for info in list_algorithms():
            assert info.global_observation_class in OBSERVATION_CLASSES, info.id
            assert info.local_observation_class in OBSERVATION_CLASSES, info.id
            assert isinstance(info.requires_global_path, bool), info.id

    def test_declaration_has_no_default(self) -> None:
        """Adding a stack without stating what it sees must fail loudly."""
        with pytest.raises(ValidationError) as excinfo:
            AlgorithmInfo(
                id="new+stack",
                kind="stack",
                description="a planner someone forgot to label",
                benchmarkable=True,
                config_schema={},
            )
        missing = {error["loc"][0] for error in excinfo.value.errors()}
        assert missing == {
            "global_observation_class",
            "local_observation_class",
            "requires_global_path",
        }

    def test_unknown_class_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AlgorithmInfo(
                id="new+stack",
                kind="stack",
                description="",
                benchmarkable=True,
                config_schema={},
                global_observation_class="everything",  # type: ignore[arg-type]
                local_observation_class="lidar_only",
                requires_global_path=True,
            )

    def test_shipped_stacks_all_run_on_sensing_alone(self) -> None:
        """Today every controller is lidar_only; the leaderboard depends on it.

        If this ever changes the change is deliberate, and the row that
        changes must move into its own leaderboard group.
        """
        for info in list_algorithms():
            assert info.local_observation_class == "lidar_only", info.id
            assert info.global_observation_class == "full_static_map", info.id


class TestInformationParityGuards:
    def test_observation_carries_no_ground_truth_obstacles(self) -> None:
        """The controller gets sensor returns, not the simulator's truth."""
        forbidden = {
            "obstacles",
            "static_obstacles",
            "dynamic_obstacles",
            "human_states",
            "obstacle_positions",
            "obstacle_velocities",
            "grid",
            "occupancy_grid",
            "map",
            "map_data",
            "scenario",
        }
        assert forbidden.isdisjoint(Observation.model_fields)

    def test_local_planner_compute_sees_only_state_and_observation(self) -> None:
        """A wider signature would let a controller reach past its class."""
        parameters = list(inspect.signature(LocalPlanner.compute).parameters)
        assert parameters == ["self", "state", "observation"]


def _fairness(seeds: tuple[int, ...] = (1, 2)) -> FairnessRecord:
    """A fairness record built by hand: the leaderboard only reads it."""
    return FairnessRecord(
        map_name="m",
        map_checksum="mc",
        scenario_name="s",
        scenario_checksum="sc",
        seeds=seeds,
        timeout_seconds=60.0,
        simulation_dt=0.1,
        robot_radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=1.5,
        lidar_num_rays=16,
        lidar_max_range=5.0,
        conditions_checksum="checksum-1",
    )


def _aggregate(algorithm: str, success_rate: float, **kw) -> AlgorithmAggregate:
    return AlgorithmAggregate(
        algorithm=algorithm,
        episodes=2,
        success_rate=success_rate,
        collision_rate=0.0,
        timeout_rate=0.0,
        stuck_rate=0.0,
        no_progress_rate=0.0,
        no_global_path_rate=0.0,
        **kw,
    )


def _stored(*aggregates: AlgorithmAggregate) -> StoredBenchmark:
    spec = BenchmarkSpec(
        name="b",
        algorithms=tuple(AlgorithmSpec(id=a.algorithm) for a in aggregates),
        seeds=(1, 2),
    )
    return StoredBenchmark(
        id="bench-1",
        spec=spec,
        map_id="map-1",
        scenario_id="scenario-1",
        created_by="alice",
        created_at="2026-01-01T00:00:00Z",
        state=BenchmarkState.ACCEPTED,
        report=BenchmarkReport(
            spec=spec, fairness=_fairness(), runs=(), aggregates=tuple(aggregates)
        ),
    )


class TestLeaderboardGrouping:
    def test_different_local_classes_do_not_share_a_group(self) -> None:
        board = build_leaderboard(
            [
                _stored(
                    _aggregate(
                        "astar+dwa",
                        0.5,
                        global_observation_class="full_static_map",
                        local_observation_class="lidar_only",
                        requires_global_path=True,
                    ),
                    _aggregate(
                        "oracle+cheater",
                        1.0,
                        global_observation_class="full_static_map",
                        local_observation_class="lidar+human_states",
                        requires_global_path=True,
                    ),
                )
            ]
        )
        assert len(board.groups) == 2
        classes = {group.local_observation_class for group in board.groups}
        assert classes == {"lidar_only", "lidar+human_states"}
        assert all(len(group.entries) == 1 for group in board.groups)
        assert not any(group.cross_observation_class_warning for group in board.groups)

    def test_forced_mixed_view_ranks_together_and_warns(self) -> None:
        board = build_leaderboard(
            [
                _stored(
                    _aggregate(
                        "astar+dwa",
                        0.5,
                        global_observation_class="full_static_map",
                        local_observation_class="lidar_only",
                        requires_global_path=True,
                    ),
                    _aggregate(
                        "oracle+cheater",
                        1.0,
                        global_observation_class="full_static_map",
                        local_observation_class="lidar+human_states",
                        requires_global_path=True,
                    ),
                )
            ],
            group_by_observation_class=False,
        )
        assert len(board.groups) == 1
        group = board.groups[0]
        assert len(group.entries) == 2
        assert group.cross_observation_class_warning is True
        # No single class can be claimed for a mixed ranking.
        assert group.local_observation_class is None

    def test_same_class_still_shares_one_group(self) -> None:
        board = build_leaderboard(
            [
                _stored(
                    _aggregate(
                        "astar+dwa",
                        0.5,
                        global_observation_class="full_static_map",
                        local_observation_class="lidar_only",
                        requires_global_path=True,
                    ),
                    _aggregate(
                        "rrtstar+dwa",
                        0.75,
                        global_observation_class="full_static_map",
                        local_observation_class="lidar_only",
                        requires_global_path=True,
                    ),
                )
            ]
        )
        assert len(board.groups) == 1
        group = board.groups[0]
        assert group.local_observation_class == "lidar_only"
        assert group.cross_observation_class_warning is False
        assert [entry.algorithm for entry in group.entries] == ["rrtstar+dwa", "astar+dwa"]

    def test_pre_p02_report_falls_back_to_the_registry(self) -> None:
        """Old rows carry no snapshot; a still-registered stack keeps its label."""
        board = build_leaderboard([_stored(_aggregate("astar+dwa", 0.5))])
        entry = board.groups[0].entries[0]
        assert entry.local_observation_class == "lidar_only"
        assert entry.global_observation_class == "full_static_map"
        assert entry.requires_global_path is True

    def test_unlabelled_and_unregistered_stays_unknown(self) -> None:
        """Never invent a class for a stack the registry no longer knows."""
        board = build_leaderboard([_stored(_aggregate("retired+stack", 1.0))])
        entry = board.groups[0].entries[0]
        assert entry.local_observation_class is None
        assert entry.global_observation_class is None
        assert entry.requires_global_path is None


class TestAggregateSnapshot:
    def test_aggregate_snapshots_the_declaration(self) -> None:
        """Relabelling the registry must not relabel results already stored."""
        from planbench_benchmark.runner import aggregate_algorithm
        from planbench_benchmark.spec import RunRecord
        from planbench_metrics import EpisodeMetrics
        from planbench_schemas.episode import EpisodeStatus

        run = RunRecord(
            algorithm="astar+dwa",
            seed=1,
            status=EpisodeStatus.SUCCESS,
            reason="",
            metrics=EpisodeMetrics(
                status=EpisodeStatus.SUCCESS,
                success=True,
                collision=False,
                travel_time=1.0,
                steps=10,
                trajectory_length=1.0,
                average_speed=0.1,
                max_speed=0.2,
                smoothness=0.0,
            ),
            trajectory_points=2,
            episode_index=0,
        )
        aggregate = aggregate_algorithm("astar+dwa", [run])
        assert aggregate.local_observation_class == "lidar_only"
        assert aggregate.global_observation_class == "full_static_map"
        assert aggregate.requires_global_path is True

    def test_old_reports_still_deserialize(self) -> None:
        """Backward compatibility: the new fields are additive."""
        legacy = {
            "algorithm": "astar+dwa",
            "episodes": 2,
            "success_rate": 1.0,
            "collision_rate": 0.0,
            "timeout_rate": 0.0,
            "stuck_rate": 0.0,
            "no_progress_rate": 0.0,
            "no_global_path_rate": 0.0,
        }
        aggregate = AlgorithmAggregate.model_validate(legacy)
        assert aggregate.local_observation_class is None
        assert aggregate.requires_global_path is None


def test_registry_and_api_expose_the_same_declaration() -> None:
    """The API's algorithm list is the registry, not a parallel copy."""
    for algorithm_id, entry in ALGORITHMS.items():
        assert entry.info.id == algorithm_id
        assert entry.info.local_observation_class in OBSERVATION_CLASSES
