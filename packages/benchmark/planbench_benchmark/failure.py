"""Evidence-based failure analysis.

Every diagnosis is derived from recorded episode data — trajectory,
events, obstacle snapshots, metrics — never guessed. Each finding
carries the evidence that produced it, so a reviewer (or the LLM report
writer, which may only cite evidence) can check the reasoning.

Confidence is deliberately coarse:
- ``high``: the engine itself recorded the cause (e.g. a collision event
  plus an obstacle overlapping the robot at that instant);
- ``medium``: derived from trajectory statistics that admit one clear
  reading (e.g. sustained rotation with no translation);
- ``low``: consistent with the data but other readings exist. A ``low``
  finding is a hypothesis, not a conclusion.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from planbench_schemas.episode import EpisodeResult, EpisodeStatus, TrajectoryPoint
from planbench_schemas.geometry import EPS
from planbench_schemas.scenario import Scenario


class FailureCategory(StrEnum):
    """Categories from spec section 22 that this analyser can decide."""

    STATIC_OBSTACLE_COLLISION = "static_obstacle_collision"
    DYNAMIC_OBSTACLE_COLLISION = "dynamic_obstacle_collision"
    TIMEOUT = "timeout"
    STUCK = "stuck"
    OSCILLATION = "oscillation"
    FAILURE_TO_PROGRESS = "failure_to_progress"
    NO_GLOBAL_PATH = "no_global_path"
    LOCAL_PLANNER_FAILURE = "local_planner_failure"
    GOAL_UNREACHABLE = "goal_unreachable"
    LOW_CLEARANCE = "low_clearance"
    NONE = "none"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Evidence(BaseModel):
    """One checkable fact backing a finding."""

    model_config = ConfigDict(frozen=True)

    kind: str
    detail: str
    time: float | None = None
    value: float | None = None


class Finding(BaseModel):
    """A diagnosed failure (or contributing factor) with its evidence."""

    model_config = ConfigDict(frozen=True)

    category: FailureCategory
    confidence: Confidence
    summary: str
    evidence: tuple[Evidence, ...]


class FailureReport(BaseModel):
    """Full analysis of one episode."""

    model_config = ConfigDict(frozen=True)

    status: EpisodeStatus
    primary: Finding
    contributing: tuple[Finding, ...] = ()

    @property
    def failed(self) -> bool:
        return self.primary.category is not FailureCategory.NONE


# Thresholds for the derived (non-engine) diagnoses. Named so the numbers
# never appear bare in the logic.
OSCILLATION_MIN_SIGN_FLIPS = 6
OSCILLATION_WINDOW_SECONDS = 4.0
OSCILLATION_MAX_DISPLACEMENT = 0.5
LOW_CLEARANCE_FRACTION_OF_RADIUS = 0.5


def analyse_episode(
    result: EpisodeResult,
    scenario: Scenario,
    *,
    min_clearance: float | None = None,
) -> FailureReport:
    """Classify why an episode ended, citing recorded evidence."""
    trajectory = result.trajectory
    contributing: list[Finding] = []

    oscillation = _detect_oscillation(trajectory)
    if oscillation is not None:
        contributing.append(oscillation)
    low_clearance = _detect_low_clearance(min_clearance, scenario)
    if low_clearance is not None:
        contributing.append(low_clearance)
    planner_failure = _detect_local_planner_failure(result)
    if planner_failure is not None:
        contributing.append(planner_failure)

    primary = _classify_primary(result, scenario, trajectory)
    # A contributing finding that *is* the primary cause is not repeated.
    contributing = [f for f in contributing if f.category is not primary.category]
    return FailureReport(status=result.status, primary=primary, contributing=tuple(contributing))


def _classify_primary(
    result: EpisodeResult, scenario: Scenario, trajectory: tuple[TrajectoryPoint, ...]
) -> Finding:
    status = result.status
    event_evidence = tuple(
        Evidence(kind="engine_event", detail=f"{event.type}: {event.message}", time=event.time)
        for event in result.events
    )

    if status is EpisodeStatus.SUCCESS:
        return Finding(
            category=FailureCategory.NONE,
            confidence=Confidence.HIGH,
            summary="Episode reached the goal.",
            evidence=event_evidence,
        )

    if status is EpisodeStatus.COLLISION:
        return _classify_collision(result, trajectory, event_evidence)

    if status is EpisodeStatus.NO_GLOBAL_PATH:
        return Finding(
            category=FailureCategory.NO_GLOBAL_PATH,
            confidence=Confidence.HIGH,
            summary=(
                "The global planner found no path, so the goal is unreachable "
                "on the inflated grid (map too tight, or start/goal enclosed)."
            ),
            evidence=event_evidence,
        )

    if status is EpisodeStatus.TIMEOUT:
        remaining = _goal_distance(trajectory[-1], scenario) if trajectory else None
        evidence = list(event_evidence)
        if remaining is not None:
            evidence.append(
                Evidence(
                    kind="goal_distance_at_end",
                    detail="Distance still separating robot and goal when time ran out.",
                    time=result.elapsed_time,
                    value=remaining,
                )
            )
        close = remaining is not None and remaining < 5 * scenario.goal_tolerance
        return Finding(
            category=FailureCategory.TIMEOUT,
            confidence=Confidence.HIGH,
            summary=(
                "Ran out of time close to the goal — too slow, not lost."
                if close
                else "Ran out of time while still far from the goal."
            ),
            evidence=tuple(evidence),
        )

    if status is EpisodeStatus.STUCK:
        return Finding(
            category=FailureCategory.STUCK,
            confidence=Confidence.HIGH,
            summary=(
                f"Robot stopped moving: displacement stayed under "
                f"{scenario.stuck_min_displacement} m for "
                f"{scenario.stuck_time_window} s."
            ),
            evidence=event_evidence,
        )

    if status is EpisodeStatus.NO_PROGRESS:
        return Finding(
            category=FailureCategory.FAILURE_TO_PROGRESS,
            confidence=Confidence.MEDIUM,
            summary=(
                "Goal distance stopped shrinking. Note this is measured in a "
                "straight line, so a long legitimate detour can trigger it — "
                "check the trajectory before concluding the planner failed."
            ),
            evidence=event_evidence,
        )

    if status is EpisodeStatus.STOPPED:
        return Finding(
            category=FailureCategory.NONE,
            confidence=Confidence.HIGH,
            summary="Episode was stopped by the operator.",
            evidence=event_evidence,
        )

    return Finding(
        category=FailureCategory.NONE,
        confidence=Confidence.LOW,
        summary=f"Unclassified terminal status {status.value!r}.",
        evidence=event_evidence,
    )


def _classify_collision(
    result: EpisodeResult,
    trajectory: tuple[TrajectoryPoint, ...],
    event_evidence: tuple[Evidence, ...],
) -> Finding:
    """Separate static from dynamic collisions using obstacle snapshots."""
    if not trajectory:
        return Finding(
            category=FailureCategory.STATIC_OBSTACLE_COLLISION,
            confidence=Confidence.LOW,
            summary="Collision recorded but no trajectory was captured.",
            evidence=event_evidence,
        )

    final = trajectory[-1]
    culprit = None
    culprit_distance = math.inf
    for snapshot in final.obstacles:
        distance = math.hypot(final.x - snapshot.x, final.y - snapshot.y)
        if distance < culprit_distance:
            culprit, culprit_distance = snapshot, distance

    evidence = [
        *event_evidence,
        Evidence(
            kind="final_pose",
            detail=f"Robot at ({final.x:.3f}, {final.y:.3f})",
            time=final.time,
        ),
    ]
    # The engine already reported which kind it was; snapshots let us name
    # the obstacle and quantify the overlap.
    dynamic_reported = "dynamic obstacle" in result.reason
    if culprit is not None:
        evidence.append(
            Evidence(
                kind="nearest_dynamic_obstacle",
                detail=f"{culprit.name} at ({culprit.x:.3f}, {culprit.y:.3f})",
                time=final.time,
                value=culprit_distance,
            )
        )
    if dynamic_reported:
        name = culprit.name if culprit else "an unnamed obstacle"
        return Finding(
            category=FailureCategory.DYNAMIC_OBSTACLE_COLLISION,
            confidence=Confidence.HIGH,
            summary=f"Collided with the moving obstacle {name!r}.",
            evidence=tuple(evidence),
        )
    return Finding(
        category=FailureCategory.STATIC_OBSTACLE_COLLISION,
        confidence=Confidence.HIGH,
        summary="Collided with static geometry (map cell or static obstacle).",
        evidence=tuple(evidence),
    )


def _detect_oscillation(trajectory: tuple[TrajectoryPoint, ...]) -> Finding | None:
    """Repeated angular-velocity sign flips with little net displacement."""
    if len(trajectory) < 3:
        return None
    end_time = trajectory[-1].time
    window = [p for p in trajectory if p.time >= end_time - OSCILLATION_WINDOW_SECONDS]
    if len(window) < 3:
        return None
    flips = sum(
        1
        for a, b in zip(window, window[1:], strict=False)
        if a.angular_velocity * b.angular_velocity < 0
        and abs(a.angular_velocity) > 0.1
        and abs(b.angular_velocity) > 0.1
    )
    displacement = math.hypot(window[-1].x - window[0].x, window[-1].y - window[0].y)
    if flips < OSCILLATION_MIN_SIGN_FLIPS or displacement > OSCILLATION_MAX_DISPLACEMENT:
        return None
    return Finding(
        category=FailureCategory.OSCILLATION,
        confidence=Confidence.MEDIUM,
        summary=(
            f"Controller oscillated: {flips} angular-velocity sign changes while "
            f"moving only {displacement:.3f} m in the last "
            f"{OSCILLATION_WINDOW_SECONDS:.0f} s."
        ),
        evidence=(
            Evidence(
                kind="angular_sign_flips",
                detail="Sign changes of commanded angular velocity in the window.",
                time=end_time,
                value=float(flips),
            ),
            Evidence(
                kind="window_displacement",
                detail="Net displacement over the same window.",
                time=end_time,
                value=displacement,
            ),
        ),
    )


def _detect_low_clearance(min_clearance: float | None, scenario: Scenario) -> Finding | None:
    if min_clearance is None:
        return None
    threshold = LOW_CLEARANCE_FRACTION_OF_RADIUS * scenario.robot.radius
    if min_clearance > threshold:
        return None
    return Finding(
        category=FailureCategory.LOW_CLEARANCE,
        confidence=Confidence.HIGH if min_clearance <= EPS else Confidence.MEDIUM,
        summary=(
            f"Robot passed within {min_clearance:.3f} m of an obstacle "
            f"(threshold {threshold:.3f} m = half the robot radius)."
        ),
        evidence=(
            Evidence(
                kind="min_clearance",
                detail="Smallest surface-to-surface distance along the trajectory.",
                value=min_clearance,
            ),
        ),
    )


def _detect_local_planner_failure(result: EpisodeResult) -> Finding | None:
    failures = [event for event in result.events if event.type == "local_planner_failure"]
    if not failures:
        return None
    return Finding(
        category=FailureCategory.LOCAL_PLANNER_FAILURE,
        confidence=Confidence.HIGH,
        summary=(
            f"The local planner reported {len(failures)} failure(s); it found no "
            "safe velocity and commanded a stop."
        ),
        evidence=tuple(
            Evidence(kind="local_planner_failure", detail=event.message, time=event.time)
            for event in failures[:5]
        ),
    )


def _goal_distance(point: TrajectoryPoint, scenario: Scenario) -> float:
    return math.hypot(point.x - scenario.goal_pose.x, point.y - scenario.goal_pose.y)
