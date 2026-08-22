"""Episode trace recorder (CONTRACTS HĐ-5).

The trace is the only input the Metrics Engine ever gets, so these tests
are about one question: can every metric of HĐ-6 be recomputed from the
file alone, and does the recorder refuse the files where it could not?
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from planbench_schemas.episode import EpisodeStatus
from planbench_schemas.episode_context import EpisodeContext
from planbench_schemas.geometry import Point2D, Pose2D
from planbench_schemas.map import MapData
from planbench_schemas.robot import RobotState, SimAction
from planbench_schemas.scenario import CircleObstacle, Scenario
from planbench_simulator.collision import DEFAULT_CLEARANCE_WINDOW_M
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.grid import OccupancyGrid
from planbench_simulator.trace import (
    TRACE_COLUMNS,
    EpisodeTraceRecorder,
    TraceError,
    TraceMetadata,
    clearance_probe,
    event_for_status,
    iter_traces,
    process_rss_mb,
    read_trace,
    trace_path,
)


def context(seed: int = 1, **overrides: object) -> EpisodeContext:
    payload: dict[str, object] = {
        "task_profile_id": "warehouse_a_v1",
        "mission_id": "m1",
        "seed": seed,
    }
    payload.update(overrides)
    return EpisodeContext.model_validate(payload)


def state(x: float = 1.0, y: float = 2.0, theta: float = 0.0) -> RobotState:
    return RobotState(pose=Pose2D(x=x, y=y, theta=theta), linear_velocity=0.4, angular_velocity=0.1)


def recorder(tmp_path: Path, **overrides: object) -> EpisodeTraceRecorder:
    kwargs: dict[str, object] = {
        "clearance": lambda pose: 0.8,
        "root": tmp_path,
        "costmap_cells": 400_000,
    }
    kwargs.update(overrides)
    return EpisodeTraceRecorder(context(), "cand12345678", **kwargs)  # type: ignore[arg-type]


class TestRoundTrip:
    def test_columns_and_metadata_survive(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(0.0, state(), planner_latency_ms=12.5)
        rec.record(0.05, state(x=1.2), "replan", planner_latency_ms=9.0)
        rec.record(0.10, state(x=1.4), "goal_reached", planner_latency_ms=8.0)
        path = rec.close(peak_search_nodes=4123, peak_tree_nodes=0, global_plan_length_m=41.2)

        loaded = read_trace(path)
        assert tuple(loaded.table.column_names) == TRACE_COLUMNS
        assert loaded.row_count == 3
        assert loaded.column("t") == [0.0, 0.05, 0.10]
        assert loaded.column("event") == [None, "replan", "goal_reached"]
        assert loaded.column("planner_latency_ms")[0] == 12.5
        assert loaded.metadata.episode_context_id == context().episode_context_id
        assert loaded.metadata.candidate_id == "cand12345678"
        assert loaded.metadata.task_profile_id == "warehouse_a_v1"
        assert loaded.metadata.sample_set == "evaluation"
        assert loaded.metadata.peak_search_nodes == 4123
        assert loaded.metadata.costmap_cells == 400_000
        assert loaded.metadata.global_plan_length_m == 41.2

    def test_the_address_carries_class_and_conditions(self, tmp_path: Path) -> None:
        """**The address changed on purpose in H9A.**

        It used to be ``candidate/context`` — exactly the two ids HĐ-3.1
        leaves the environment out of — so an oracle run and a production
        run of one candidate wrote to the *same file* and the second
        replaced the first. The class and the conditions now come first,
        and the pairing rule stays visible underneath them: two
        candidates that ran the same contexts still hold two directories
        with identical file names.
        """
        ctx = context(seed=7)
        expected = (
            tmp_path
            / "production"
            / "abc123"
            / "cand12345678"
            / f"{ctx.episode_context_id}.parquet"
        )
        assert (
            trace_path(
                "cand12345678",
                ctx.episode_context_id,
                root=tmp_path,
                evidence_class="production",
                execution_fingerprint="abc123",
            )
            == expected
        )

    def test_two_classes_of_one_episode_cannot_share_a_file(self, tmp_path: Path) -> None:
        """The defect this address exists to close, stated as a test."""
        ctx = context(seed=7)
        common = {
            "root": tmp_path,
            "execution_fingerprint": "abc123",
        }
        production = trace_path(
            "cand", ctx.episode_context_id, evidence_class="production", **common
        )
        oracle = trace_path("cand", ctx.episode_context_id, evidence_class="oracle", **common)
        assert production != oracle

    def test_two_worlds_of_one_episode_cannot_share_a_file(self, tmp_path: Path) -> None:
        ctx = context(seed=7)
        common = {"root": tmp_path, "evidence_class": "production"}
        first = trace_path("cand", ctx.episode_context_id, execution_fingerprint="aaa", **common)
        second = trace_path("cand", ctx.episode_context_id, execution_fingerprint="bbb", **common)
        assert first != second

    def test_a_trace_without_conditions_is_filed_where_that_shows(self, tmp_path: Path) -> None:
        """An episode run outside the contract pipeline has no conditions
        hash. Reuse and scoring already refuse it; this puts the state in
        ``ls`` rather than only in an error message."""
        ctx = context(seed=7)
        path = trace_path(
            "cand",
            ctx.episode_context_id,
            root=tmp_path,
            evidence_class="production",
            execution_fingerprint="",
        )
        assert path.parent.parent.name == "unfingerprinted"

    def test_context_manager_writes_on_exit(self, tmp_path: Path) -> None:
        with recorder(tmp_path) as rec:
            rec.record(0.0, state())
            path = rec.path
        assert read_trace(path).row_count == 1

    def test_context_manager_writes_even_when_the_episode_raises(self, tmp_path: Path) -> None:
        """400 recorded samples of a crashed episode are evidence; a
        missing file is a hole in a paired comparison."""
        rec = recorder(tmp_path)
        with pytest.raises(RuntimeError), rec:
            rec.record(0.0, state())
            raise RuntimeError("simulated blow-up")
        assert read_trace(rec.path).row_count == 1

    def test_cpu_time_and_rss_are_recorded(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(0.0, state())
        loaded = read_trace(rec.close())
        assert loaded.metadata.cpu_time_s >= 0.0
        assert loaded.metadata.peak_rss_mb >= 0.0

    def test_iter_traces_finds_every_file(self, tmp_path: Path) -> None:
        for seed in (1, 2):
            rec = EpisodeTraceRecorder(
                context(seed=seed), "cand12345678", clearance=lambda _: 1.0, root=tmp_path
            )
            rec.record(0.0, state())
            rec.close()
        assert len({loaded.metadata.episode_context_id for loaded in iter_traces(tmp_path)}) == 2


class TestRefusals:
    """Each of these survives a run silently and only shows up as a
    strange number on a Decision Card, long after the episodes are gone."""

    def test_out_of_order_timestamp(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(1.0, state())
        with pytest.raises(TraceError, match="must increase"):
            rec.record(0.9, state())

    def test_repeated_timestamp(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(1.0, state())
        with pytest.raises(TraceError, match="must increase"):
            rec.record(1.0, state())

    def test_unknown_event(self, tmp_path: Path) -> None:
        """A consumer switching on the value would take its default
        branch and count this episode as something it was not."""
        rec = recorder(tmp_path)
        with pytest.raises(TraceError, match="unknown trace event"):
            rec.record(0.0, state(), "crashed")

    def test_non_finite_value(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path, clearance=lambda pose: math.nan)
        with pytest.raises(TraceError, match="must be finite"):
            rec.record(0.0, state())

    def test_empty_trace(self, tmp_path: Path) -> None:
        """An empty file would still be counted as one paired
        observation."""
        rec = recorder(tmp_path)
        with pytest.raises(TraceError, match="empty trace"):
            rec.close()
        assert not rec.path.exists()

    def test_recording_after_close(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(0.0, state())
        rec.close()
        with pytest.raises(TraceError, match="already written"):
            rec.record(0.1, state())

    def test_double_close(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(0.0, state())
        rec.close()
        with pytest.raises(TraceError, match="already written"):
            rec.close()

    def test_clearance_must_come_from_somewhere(self, tmp_path: Path) -> None:
        """It cannot be recovered later — that is the whole reason HĐ-5
        stores it per sample."""
        rec = recorder(tmp_path, clearance=None)
        with pytest.raises(TraceError, match="clearance"):
            rec.record(0.0, state())

    def test_trace_without_metadata_is_refused(self, tmp_path: Path) -> None:
        """A trace whose candidate is unknown cannot be paired, and
        guessing it from the directory name would make a misplaced file
        look valid."""
        pa = pytest.importorskip("pyarrow")
        pq = pytest.importorskip("pyarrow.parquet")
        path = tmp_path / "bare.parquet"
        pq.write_table(pa.table({name: [0.0] for name in TRACE_COLUMNS[:-1]}), path)
        with pytest.raises(TraceError, match="metadata"):
            read_trace(path)

    def test_unknown_column_is_refused(self, tmp_path: Path) -> None:
        rec = recorder(tmp_path)
        rec.record(0.0, state())
        loaded = read_trace(rec.close())
        with pytest.raises(TraceError, match="not an HĐ-5 column"):
            loaded.column("collision_count")


class TestClearanceProbe:
    """Clearance is measured while writing because the world moves."""

    @staticmethod
    def grid() -> OccupancyGrid:
        return OccupancyGrid(
            MapData(
                name="empty_10x10m",
                width=40,
                height=40,
                resolution=0.25,
                origin=Pose2D(x=0.0, y=0.0, theta=0.0),
                cells=(0,) * (40 * 40),
            )
        )

    def test_moving_obstacle_is_read_at_call_time(self) -> None:
        """A snapshot taken once would report the same clearance all
        episode, and near-miss counting would measure nothing."""
        positions = iter(
            [
                (CircleObstacle(center=Point2D(x=8.0, y=5.0), radius=0.2),),
                (CircleObstacle(center=Point2D(x=6.0, y=5.0), radius=0.2),),
            ]
        )
        probe = clearance_probe(self.grid(), (), 0.3, lambda: next(positions))
        far = probe(Pose2D(x=5.0, y=5.0, theta=0.0))
        near = probe(Pose2D(x=5.0, y=5.0, theta=0.0))
        assert far > near
        assert near == pytest.approx(1.0 - 0.3 - 0.2)

    def test_obstacle_free_world_still_measures_the_walls(self) -> None:
        """Clearance to an empty set of shapes is infinity, which no
        float column can hold and no percentile survives. The grid is
        what keeps the answer finite: the map boundary always replies.

        Far from everything the probe reports its search window rather
        than the true distance (``clearance_to_grid_within``): this pose
        is 5 m from the nearest wall and the answer is the 2 m window
        minus the radius. That is a floor, not a measurement, and it is
        deliberately on the pessimistic side — both safety anchors
        saturate well below 2 m, so nothing downstream can tell the
        difference, and the exhaustive alternative costs a whole-map scan
        per recorded control step.
        """
        probe = clearance_probe(self.grid(), (), 0.3)
        value = probe(Pose2D(x=5.0, y=5.0, theta=0.0))
        assert math.isfinite(value)
        assert value == pytest.approx(DEFAULT_CLEARANCE_WINDOW_M - 0.3)

    def test_near_field_clearance_is_exact(self) -> None:
        """Inside the window — where every safety metric lives — the
        probe still reports the true distance."""
        probe = clearance_probe(self.grid(), (), 0.3)
        value = probe(Pose2D(x=0.8, y=5.0, theta=0.0))
        assert value == pytest.approx(0.8 - 0.3)

    def test_recorder_uses_the_probe(self, tmp_path: Path) -> None:
        probe = clearance_probe(
            self.grid(),
            (CircleObstacle(center=Point2D(x=2.0, y=2.0), radius=0.5),),
            0.3,
        )
        rec = recorder(tmp_path, clearance=probe)
        rec.record(0.0, state(x=2.0, y=4.0))
        assert read_trace(rec.close()).column("clearance_m")[0] == pytest.approx(2.0 - 0.5 - 0.3)


class TestEventVocabulary:
    def test_statuses_map_onto_the_closed_vocabulary(self) -> None:
        assert event_for_status(EpisodeStatus.SUCCESS) == "goal_reached"
        assert event_for_status(EpisodeStatus.COLLISION) == "collision"
        assert event_for_status(EpisodeStatus.NO_GLOBAL_PATH) == "no_path"

    def test_no_progress_is_a_stuck_episode(self) -> None:
        """HĐ-5 and HĐ-6's failure_reason have one bucket for both."""
        assert event_for_status(EpisodeStatus.NO_PROGRESS) == "stuck"

    def test_non_verdicts_map_to_nothing(self) -> None:
        """An operator-stopped episode is not a failure of the
        candidate."""
        assert event_for_status(EpisodeStatus.STOPPED) is None
        assert event_for_status(EpisodeStatus.RUNNING) is None


class TestMetadata:
    def test_ids_come_from_the_context(self) -> None:
        ctx = context(seed=3)
        metadata = TraceMetadata.for_episode(ctx, "cand12345678")
        assert metadata.episode_context_id == ctx.episode_context_id
        assert metadata.sample_set == ctx.sample_set

    def test_neighborhood_sample_set_is_carried(self) -> None:
        """Pooling these into the collision bound would make 3/N far too
        optimistic (HĐ-11.4), so the set has to survive the write."""
        ctx = context(sample_set="neighborhood", environment_variant="v_max_minus_10")
        metadata = TraceMetadata.for_episode(ctx, "cand12345678")
        assert metadata.sample_set == "neighborhood"

    def test_unknown_field_refused(self) -> None:
        with pytest.raises(ValueError):
            TraceMetadata(
                episode_context_id="a",
                candidate_id="b",
                task_profile_id="c",
                sample_set="evaluation",
                peak_ram_mb=10.0,  # type: ignore[call-arg]
            )

    def test_rss_probe_never_raises(self) -> None:
        """It is a diagnostic; an episode must not fail over it."""
        assert process_rss_mb() >= 0.0


class TestRealEpisode:
    """One real episode end to end: engine -> trace file -> metrics inputs.

    The point of HĐ-5 is that the file alone answers every question, so
    this test asks the questions HĐ-6 will ask (path length, latency
    percentile, minimum clearance, terminal event) using nothing but what
    was read back from disk.
    """

    def test_engine_episode_produces_a_readable_trace(
        self, bordered_map_factory, robot_config, tmp_path: Path
    ) -> None:
        map_data = bordered_map_factory(12, 12)
        scenario = Scenario(
            name="trace-episode",
            robot=robot_config,
            start_pose=Pose2D(x=2.5, y=2.5, theta=0.0),
            goal_pose=Pose2D(x=8.5, y=2.5, theta=0.0),
            goal_tolerance=0.3,
            timeout_seconds=30.0,
            simulation_dt=0.05,
        )
        engine = SimulationEngine()
        engine.load_map(map_data)
        engine.load_scenario(scenario)
        engine.reset()

        grid = OccupancyGrid(map_data)
        probe = clearance_probe(
            grid, scenario.static_obstacles, robot_config.radius, engine.dynamic_obstacles_now
        )
        rec = EpisodeTraceRecorder(
            context(),
            "cand12345678",
            clearance=probe,
            root=tmp_path,
            costmap_cells=map_data.width * map_data.height,
        )
        action = SimAction(linear_velocity=1.0, angular_velocity=0.0)
        while not engine.is_done():
            state_now = engine.get_state()
            rec.record(engine.time, state_now, planner_latency_ms=1.0)
            engine.step(action)
        final = engine.get_state()
        rec.record(engine.time, final, event_for_status(engine.episode_status))
        cells = map_data.width * map_data.height
        path = rec.close(peak_search_nodes=cells // 2, costmap_cells=cells)

        loaded = read_trace(path)
        assert loaded.row_count > 10
        assert loaded.column("event")[-1] == "goal_reached"

        # Everything HĐ-6 needs, recomputed from the file alone.
        xs, ys = loaded.column("x"), loaded.column("y")
        path_length_m = sum(
            math.dist((xs[i], ys[i]), (xs[i + 1], ys[i + 1])) for i in range(len(xs) - 1)
        )
        assert path_length_m == pytest.approx(6.0, abs=0.5)
        assert min(loaded.column("clearance_m")) > 0.0
        assert max(loaded.column("planner_latency_ms")) == 1.0
        assert loaded.column("t") == sorted(loaded.column("t"))

        # HĐ-15.1 criterion 6, the check the vertical slice will make.
        assert loaded.metadata.peak_search_nodes <= loaded.metadata.costmap_cells
