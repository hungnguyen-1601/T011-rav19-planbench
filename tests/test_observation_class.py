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
from planbench_benchmark.observation import global_class_under_replanning
from planbench_planning.common.local_base import LocalPlanner
from planbench_schemas.episode import Observation
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig


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


def _fairness(
    seeds: tuple[int, ...] = (1, 2), checksum: str = "checksum-1", **kw
) -> FairnessRecord:
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
        conditions_checksum=checksum,
        **kw,
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


def _stored(
    *aggregates: AlgorithmAggregate,
    benchmark_id: str = "bench-1",
    fairness: FairnessRecord | None = None,
) -> StoredBenchmark:
    spec = BenchmarkSpec(
        name="b",
        algorithms=tuple(AlgorithmSpec(id=a.algorithm) for a in aggregates),
        seeds=(1, 2),
    )
    return StoredBenchmark(
        id=benchmark_id,
        spec=spec,
        map_id="map-1",
        scenario_id="scenario-1",
        created_by="alice",
        created_at="2026-01-01T00:00:00Z",
        state=BenchmarkState.ACCEPTED,
        report=BenchmarkReport(
            spec=spec,
            fairness=fairness or _fairness(),
            runs=(),
            aggregates=tuple(aggregates),
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


class TestReplanningUpgradesTheGlobalClass:
    """P02 under replanning: the declaration is a run-time fact, not a stack id.

    A replan is computed from ``engine.dynamic_obstacles_now()`` — the
    simulator's ground truth. A stack that is allowed to replan therefore
    sees strictly more than the same stack with replanning off, and the
    registry, which labels stack ids and not runs, cannot express that.
    Labelling both ``full_static_map`` would reproduce the exact flaw
    this platform was built to expose.
    """

    def test_disabled_leaves_the_declaration_alone(self) -> None:
        for declared in OBSERVATION_CLASSES:
            assert global_class_under_replanning(declared, replanning_enabled=False) == declared, (
                declared
            )

    def test_enabled_upgrades_every_known_class(self) -> None:
        """No declaration may fall through into an invented class name."""
        for declared in OBSERVATION_CLASSES:
            upgraded = global_class_under_replanning(declared, replanning_enabled=True)
            assert upgraded in OBSERVATION_CLASSES, declared
            assert "human_states" in str(upgraded), declared

    def test_the_shipped_stacks_land_on_the_named_class(self) -> None:
        assert (
            global_class_under_replanning("full_static_map", replanning_enabled=True)
            == "full_static_map+human_states"
        )

    def test_an_undeclared_stack_is_not_given_one(self) -> None:
        """Upgrading None would invent the label the nullable field prevents."""
        assert global_class_under_replanning(None, replanning_enabled=True) is None


class TestAggregateUnderReplanning:
    def _run(self):
        from planbench_benchmark.spec import RunRecord
        from planbench_metrics import EpisodeMetrics
        from planbench_schemas.episode import EpisodeStatus

        return RunRecord(
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

    def test_replanning_off_keeps_the_registry_label(self) -> None:
        """Every report ever written must keep the label it was written with."""
        from planbench_benchmark.runner import aggregate_algorithm

        for rule in (None, NO_REPLANNING, ReplanningConfig(enabled=False, max_replans=0)):
            aggregate = aggregate_algorithm("astar+dwa", [self._run()], replanning=rule)
            assert aggregate.global_observation_class == "full_static_map", rule
            assert aggregate.local_observation_class == "lidar_only", rule

    def test_replanning_on_upgrades_the_global_half_only(self) -> None:
        from planbench_benchmark.runner import aggregate_algorithm

        aggregate = aggregate_algorithm(
            "astar+dwa",
            [self._run()],
            replanning=ReplanningConfig(enabled=True, max_replans=2),
        )
        assert aggregate.global_observation_class == "full_static_map+human_states"
        # The controller still runs on LiDAR: replanning changes what the
        # *global* planner is handed, nothing below it.
        assert aggregate.local_observation_class == "lidar_only"

    def test_the_upgraded_label_is_a_snapshot(self) -> None:
        """Reading the report later must not resolve the label from the registry.

        The registry says ``full_static_map`` and always will. If the
        leaderboard re-derived the class on read, a replanning run would
        quietly lose its upgrade the moment it was displayed.
        """
        from planbench_benchmark.runner import aggregate_algorithm

        aggregate = aggregate_algorithm(
            "astar+dwa",
            [self._run()],
            replanning=ReplanningConfig(enabled=True, max_replans=2),
        )
        board = build_leaderboard([_stored(aggregate)])
        entry = board.groups[0].entries[0]
        assert entry.global_observation_class == "full_static_map+human_states"


class TestLeaderboardSeparatesReplanningRuns:
    def _pair(self) -> list[StoredBenchmark]:
        """The same stack, same conditions checksum, two global classes.

        The checksum is deliberately held equal. Replanning does change
        ``conditions_checksum`` in production, so these two rows would be
        separated anyway — but then the observation class would be
        decoration. Pinning the checksum proves the class alone keeps
        them apart, which is what P02 claims to do.
        """
        return [
            _stored(
                _aggregate(
                    "astar+dwa",
                    0.5,
                    global_observation_class="full_static_map",
                    local_observation_class="lidar_only",
                    requires_global_path=True,
                ),
                benchmark_id="bench-no-replan",
            ),
            _stored(
                _aggregate(
                    "astar+dwa",
                    0.9,
                    global_observation_class="full_static_map+human_states",
                    local_observation_class="lidar_only",
                    requires_global_path=True,
                ),
                benchmark_id="bench-replan",
            ),
        ]

    def test_they_do_not_share_a_default_group(self) -> None:
        board = build_leaderboard(self._pair())
        assert len(board.groups) == 2
        assert {group.global_observation_class for group in board.groups} == {
            "full_static_map",
            "full_static_map+human_states",
        }
        assert all(len(group.entries) == 1 for group in board.groups)
        assert not any(group.cross_observation_class_warning for group in board.groups)

    def test_forcing_them_together_raises_the_cross_class_warning(self) -> None:
        board = build_leaderboard(self._pair(), group_by_observation_class=False)
        assert len(board.groups) == 1
        group = board.groups[0]
        assert len(group.entries) == 2
        assert group.cross_observation_class_warning is True
        # The rows agree on the controller but not on the global planner,
        # so neither a shared global class nor a clean ranking exists.
        assert group.global_observation_class is None
        assert group.local_observation_class == "lidar_only"

    def test_a_pre_replanning_report_reads_as_full_static_map(self) -> None:
        """Old rows carry no snapshot and must not be guessed at.

        Everything stored before this change ran with replanning off — it
        did not exist — so the registry fallback is not a guess here, it
        is the recorded truth.
        """
        board = build_leaderboard([_stored(_aggregate("astar+dwa", 0.5))])
        entry = board.groups[0].entries[0]
        assert entry.global_observation_class == "full_static_map"
        assert entry.local_observation_class == "lidar_only"


def test_registry_and_api_expose_the_same_declaration() -> None:
    """The API's algorithm list is the registry, not a parallel copy."""
    for algorithm_id, entry in ALGORITHMS.items():
        assert entry.info.id == algorithm_id
        assert entry.info.local_observation_class in OBSERVATION_CLASSES
