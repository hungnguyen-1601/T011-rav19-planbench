"""Tests for experiment tracking adapters."""

from __future__ import annotations

import pytest

from planbench_benchmark import (
    AlgorithmSpec,
    BenchmarkSpec,
    run_benchmark,
)
from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario
from planbench_tracking import NullTracker, build_tracker
from planbench_tracking.mlflow_tracker import _aggregate_metrics, _run_metrics


@pytest.fixture
def report(bordered_map_factory):
    robot = RobotConfig(
        radius=0.3,
        max_linear_velocity=1.0,
        max_angular_velocity=2.0,
        max_linear_acceleration=1.0,
        max_angular_acceleration=3.0,
    )
    scenario = Scenario(
        name="tracking-test",
        robot=robot,
        start_pose=Pose2D(x=2.5, y=2.5, theta=0.0),
        goal_pose=Pose2D(x=8.5, y=8.5, theta=0.0),
        goal_tolerance=0.4,
        timeout_seconds=60.0,
        simulation_dt=0.05,
    )
    spec = BenchmarkSpec(name="tracking", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1,))
    return run_benchmark(bordered_map_factory(12, 12), scenario, spec)


class TestNullTracker:
    def test_records_nothing_but_returns_a_reference(self, report) -> None:
        tracked = NullTracker().log_benchmark("b1", report)
        assert tracked.backend == "null"
        assert tracked.run_id == ""


class TestBuildTracker:
    def test_empty_uri_disables_tracking(self) -> None:
        assert isinstance(build_tracker(""), NullTracker)

    def test_unusable_backend_degrades_to_null(self, monkeypatch, report) -> None:
        """A broken tracking backend must never fail a benchmark."""
        import planbench_tracking.mlflow_tracker as module

        def explode(*args, **kwargs):
            raise RuntimeError("tracking server unreachable")

        monkeypatch.setattr(module, "MLflowTracker", explode)
        tracker = build_tracker("http://127.0.0.1:1/unreachable", "planbench-test")
        assert isinstance(tracker, NullTracker)
        # The benchmark path still works end to end.
        assert tracker.log_benchmark("b1", report).backend == "null"


class TestMetricExtraction:
    def test_aggregate_metrics_are_numeric_and_complete(self, report) -> None:
        metrics = _aggregate_metrics(report.aggregates[0])
        assert metrics["episodes"] == 1.0
        assert 0.0 <= metrics["success_rate"] <= 1.0
        assert all(isinstance(value, float) for value in metrics.values())
        # Optional values are omitted rather than logged as None.
        assert None not in metrics.values()

    def test_run_metrics_cover_the_per_seed_view(self, report) -> None:
        metrics = _run_metrics(report.runs[0].metrics)
        assert "seed_travel_time" in metrics
        assert "seed_trajectory_length" in metrics
        assert metrics["seed_success"] in (0.0, 1.0)
        assert all(isinstance(value, float) for value in metrics.values())
