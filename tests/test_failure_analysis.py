"""Tests for evidence-based failure analysis."""

from __future__ import annotations

import pytest

from planbench_benchmark import FailureCategory, analyse_episode
from planbench_benchmark.failure import Confidence
from planbench_schemas.episode import (
    EpisodeEvent,
    EpisodeResult,
    EpisodeStatus,
    ObstacleSnapshot,
    TrajectoryPoint,
)
from planbench_schemas.geometry import Pose2D
from planbench_schemas.robot import RobotConfig
from planbench_schemas.scenario import Scenario


@pytest.fixture
def scenario() -> Scenario:
    return Scenario(
        name="analysis",
        robot=RobotConfig(
            radius=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=2.0,
            max_linear_acceleration=1.0,
            max_angular_acceleration=3.0,
        ),
        start_pose=Pose2D(x=1.0, y=1.0, theta=0.0),
        goal_pose=Pose2D(x=10.0, y=1.0, theta=0.0),
        goal_tolerance=0.3,
        timeout_seconds=30.0,
        simulation_dt=0.05,
    )


def point(
    time: float,
    x: float,
    y: float,
    *,
    w: float = 0.0,
    obstacles: tuple[ObstacleSnapshot, ...] = (),
) -> TrajectoryPoint:
    return TrajectoryPoint(
        time=time, x=x, y=y, theta=0.0, linear_velocity=1.0, angular_velocity=w, obstacles=obstacles
    )


def result(
    status: EpisodeStatus,
    points: list[TrajectoryPoint],
    reason: str = "",
    events: tuple[EpisodeEvent, ...] = (),
) -> EpisodeResult:
    return EpisodeResult(
        status=status,
        reason=reason,
        elapsed_time=points[-1].time if points else 0.0,
        steps=max(0, len(points) - 1),
        trajectory=tuple(points),
        events=events,
    )


class TestPrimaryClassification:
    def test_success(self, scenario: Scenario) -> None:
        report = analyse_episode(result(EpisodeStatus.SUCCESS, [point(0, 1, 1)]), scenario)
        assert report.primary.category is FailureCategory.NONE
        assert not report.failed

    def test_static_collision(self, scenario: Scenario) -> None:
        episode = result(
            EpisodeStatus.COLLISION,
            [point(0, 1, 1), point(1, 3, 1)],
            reason="collision with static obstacle at (3.000, 1.000) after 1.00s",
            events=(EpisodeEvent(time=1.0, type="collision", message="hit a wall"),),
        )
        report = analyse_episode(episode, scenario)
        assert report.primary.category is FailureCategory.STATIC_OBSTACLE_COLLISION
        assert report.primary.confidence is Confidence.HIGH
        assert any(e.kind == "final_pose" for e in report.primary.evidence)

    def test_dynamic_collision_names_the_obstacle(self, scenario: Scenario) -> None:
        snapshot = ObstacleSnapshot(name="pedestrian", x=3.4, y=1.0, radius=0.35)
        episode = result(
            EpisodeStatus.COLLISION,
            [point(0, 1, 1), point(1, 3, 1, obstacles=(snapshot,))],
            reason="collision with dynamic obstacle at (3.000, 1.000) after 1.00s",
        )
        report = analyse_episode(episode, scenario)
        assert report.primary.category is FailureCategory.DYNAMIC_OBSTACLE_COLLISION
        assert "pedestrian" in report.primary.summary
        nearest = next(e for e in report.primary.evidence if e.kind == "nearest_dynamic_obstacle")
        assert nearest.value == pytest.approx(0.4)

    def test_timeout_near_goal_is_distinguished(self, scenario: Scenario) -> None:
        near = analyse_episode(result(EpisodeStatus.TIMEOUT, [point(30, 9.5, 1.0)]), scenario)
        far = analyse_episode(result(EpisodeStatus.TIMEOUT, [point(30, 2.0, 1.0)]), scenario)
        assert near.primary.category is FailureCategory.TIMEOUT
        assert "close to the goal" in near.primary.summary
        assert "far from the goal" in far.primary.summary
        assert next(
            e for e in near.primary.evidence if e.kind == "goal_distance_at_end"
        ).value == pytest.approx(0.5)

    def test_stuck(self, scenario: Scenario) -> None:
        report = analyse_episode(result(EpisodeStatus.STUCK, [point(5, 2, 1)]), scenario)
        assert report.primary.category is FailureCategory.STUCK

    def test_no_progress_flags_the_euclidean_caveat(self, scenario: Scenario) -> None:
        report = analyse_episode(result(EpisodeStatus.NO_PROGRESS, [point(9, 2, 1)]), scenario)
        assert report.primary.category is FailureCategory.FAILURE_TO_PROGRESS
        assert report.primary.confidence is Confidence.MEDIUM
        assert "straight line" in report.primary.summary  # warns about detours

    def test_no_global_path(self, scenario: Scenario) -> None:
        episode = EpisodeResult(
            status=EpisodeStatus.NO_GLOBAL_PATH,
            reason="no path exists",
            elapsed_time=0.0,
            steps=0,
            trajectory=(),
            events=(EpisodeEvent(time=0.0, type="no_global_path", message="no path exists"),),
        )
        report = analyse_episode(episode, scenario)
        assert report.primary.category is FailureCategory.NO_GLOBAL_PATH
        assert report.primary.evidence

    def test_operator_stop_is_not_a_failure(self, scenario: Scenario) -> None:
        report = analyse_episode(result(EpisodeStatus.STOPPED, [point(2, 2, 1)]), scenario)
        assert report.primary.category is FailureCategory.NONE


class TestContributingFactors:
    def test_oscillation_detected(self, scenario: Scenario) -> None:
        points = [
            point(index * 0.2, 2.0 + 0.001 * index, 1.0, w=0.8 if index % 2 == 0 else -0.8)
            for index in range(20)
        ]
        report = analyse_episode(result(EpisodeStatus.TIMEOUT, points), scenario)
        oscillation = next(
            f for f in report.contributing if f.category is FailureCategory.OSCILLATION
        )
        assert oscillation.confidence is Confidence.MEDIUM
        assert any(e.kind == "angular_sign_flips" for e in oscillation.evidence)

    def test_straight_driving_is_not_oscillation(self, scenario: Scenario) -> None:
        points = [point(index * 0.2, 1.0 + index * 0.2, 1.0) for index in range(20)]
        report = analyse_episode(result(EpisodeStatus.TIMEOUT, points), scenario)
        assert all(f.category is not FailureCategory.OSCILLATION for f in report.contributing)

    def test_low_clearance_flagged(self, scenario: Scenario) -> None:
        report = analyse_episode(
            result(EpisodeStatus.SUCCESS, [point(1, 2, 1)]), scenario, min_clearance=0.1
        )
        finding = next(
            f for f in report.contributing if f.category is FailureCategory.LOW_CLEARANCE
        )
        assert finding.evidence[0].value == pytest.approx(0.1)

    def test_comfortable_clearance_not_flagged(self, scenario: Scenario) -> None:
        report = analyse_episode(
            result(EpisodeStatus.SUCCESS, [point(1, 2, 1)]), scenario, min_clearance=0.9
        )
        assert all(f.category is not FailureCategory.LOW_CLEARANCE for f in report.contributing)

    def test_local_planner_failures_reported(self, scenario: Scenario) -> None:
        events = tuple(
            EpisodeEvent(
                time=index * 0.5,
                type="local_planner_failure",
                message="all candidates collide; commanding stop",
            )
            for index in range(3)
        )
        report = analyse_episode(
            result(EpisodeStatus.STUCK, [point(5, 2, 1)], events=events), scenario
        )
        finding = next(
            f for f in report.contributing if f.category is FailureCategory.LOCAL_PLANNER_FAILURE
        )
        assert "3 failure(s)" in finding.summary
        assert len(finding.evidence) == 3

    def test_primary_cause_is_not_duplicated_as_contributing(self, scenario: Scenario) -> None:
        events = (EpisodeEvent(time=1.0, type="local_planner_failure", message="stop"),)
        report = analyse_episode(
            result(EpisodeStatus.STUCK, [point(5, 2, 1)], events=events),
            scenario,
            min_clearance=0.05,
        )
        categories = [f.category for f in report.contributing]
        assert report.primary.category not in categories


class TestEvidenceDiscipline:
    def test_every_finding_carries_evidence_or_says_why(self, scenario: Scenario) -> None:
        """Findings must be checkable: each one cites recorded data."""
        episode = result(
            EpisodeStatus.COLLISION,
            [point(0, 1, 1), point(1, 3, 1)],
            reason="collision with static obstacle",
            events=(EpisodeEvent(time=1.0, type="collision", message="hit"),),
        )
        report = analyse_episode(episode, scenario, min_clearance=-0.05)
        for finding in (report.primary, *report.contributing):
            assert finding.evidence, f"{finding.category} has no evidence"
