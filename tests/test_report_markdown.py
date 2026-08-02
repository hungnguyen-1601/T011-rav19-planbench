"""Tests for the Markdown benchmark-report export (F09)."""

from __future__ import annotations

import pytest

from planbench_api.report_markdown import render_report_markdown
from planbench_benchmark import AlgorithmSpec, BenchmarkSpec, run_benchmark
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
        "name": "report-export-test",
        "robot": robot,
        "start_pose": Pose2D(x=2.5, y=2.5, theta=0.0),
        "goal_pose": Pose2D(x=8.5, y=8.5, theta=0.0),
        "goal_tolerance": 0.4,
        "timeout_seconds": 60.0,
        "simulation_dt": 0.05,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


def _two_algorithm_report(bordered_map_factory, robot: RobotConfig):
    spec = BenchmarkSpec(
        name="report-export-benchmark",
        algorithms=(AlgorithmSpec(id="astar+dwa"), AlgorithmSpec(id="astar+pure_pursuit")),
        seeds=(1, 2),
    )
    return run_benchmark(bordered_map_factory(12, 12), make_scenario(robot), spec)


class TestRenderReportMarkdown:
    def test_includes_title_and_id(self, bordered_map_factory, robot: RobotConfig) -> None:
        report = _two_algorithm_report(bordered_map_factory, robot)
        markdown = render_report_markdown("My Benchmark", "bench-123", report)
        assert markdown.startswith("# My Benchmark")
        assert "bench-123" in markdown

    def test_includes_every_algorithm(self, bordered_map_factory, robot: RobotConfig) -> None:
        report = _two_algorithm_report(bordered_map_factory, robot)
        markdown = render_report_markdown("bench", "id", report)
        assert "astar+dwa" in markdown
        assert "astar+pure_pursuit" in markdown

    def test_includes_fairness_conditions(self, bordered_map_factory, robot: RobotConfig) -> None:
        report = _two_algorithm_report(bordered_map_factory, robot)
        markdown = render_report_markdown("bench", "id", report)
        assert report.fairness.map_name in markdown
        assert report.fairness.scenario_name in markdown
        assert report.fairness.conditions_checksum in markdown

    def test_warns_when_not_statistically_adequate(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        report = _two_algorithm_report(bordered_map_factory, robot)
        assert report.statistically_adequate is False  # only 2 seeds
        markdown = render_report_markdown("bench", "id", report)
        assert "not statistically adequate" in markdown
        assert str(report.seed_count) in markdown

    def test_includes_comparisons_when_present(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        report = _two_algorithm_report(bordered_map_factory, robot)
        assert len(report.comparisons) == 1
        markdown = render_report_markdown("bench", "id", report)
        comparison = report.comparisons[0]
        assert comparison.baseline_algorithm in markdown
        assert comparison.compared_algorithm in markdown
        assert f"{comparison.p_value:.4f}" in markdown

    def test_no_comparisons_section_is_explicit_when_empty(
        self, bordered_map_factory, robot: RobotConfig
    ) -> None:
        spec = BenchmarkSpec(
            name="solo",
            algorithms=(AlgorithmSpec(id="astar+dwa"),),
            seeds=(1, 2),
        )
        report = run_benchmark(bordered_map_factory(12, 12), make_scenario(robot), spec)
        assert report.comparisons == ()
        markdown = render_report_markdown("bench", "id", report)
        assert "None — needs at least two algorithms" in markdown

    def test_includes_every_run(self, bordered_map_factory, robot: RobotConfig) -> None:
        report = _two_algorithm_report(bordered_map_factory, robot)
        markdown = render_report_markdown("bench", "id", report)
        for run in report.runs:
            assert f"| {run.algorithm} | {run.seed} |" in markdown
