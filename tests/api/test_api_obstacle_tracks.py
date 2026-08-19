"""Traffic on the trace canvas — the positions the browser is handed.

The map a trace is drawn on is static and the trace records only the
robot, so a route that bent around a cart was bending around nothing:
the one thing on screen that explained the bend was the thing missing
from it.

These guard the half that can be wrong without anybody noticing: the
positions come from the platform's own motion model at the platform's
own seed, there is exactly one per timestamp, and a context that cannot
be rebuilt yields no obstacles rather than obstacles somewhere else.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from planbench_api.decision_service import _context_for, _obstacle_tracks
from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_schemas.task_profile import TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[2]
WITH_TRAFFIC = REPO_ROOT / "artifacts" / "runs" / "profiles" / "sudden_stop.yaml"


@pytest.fixture(scope="module")
def profile() -> TaskProfile:
    if not WITH_TRAFFIC.exists():  # pragma: no cover - fixture profile removed
        pytest.skip(f"{WITH_TRAFFIC} is not in this checkout")
    return TaskProfile.model_validate(yaml.safe_load(WITH_TRAFFIC.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def context(profile: TaskProfile):  # type: ignore[no-untyped-def]
    return build_evaluation_contexts(profile)[0]


def test_the_fixture_actually_declares_traffic(profile: TaskProfile) -> None:
    """Otherwise every assertion below passes by having nothing to check."""
    assert profile.environment.dynamic_obstacles


def test_one_position_per_timestamp(profile: TaskProfile, context) -> None:  # type: ignore[no-untyped-def]
    """Indexed in lockstep with the trace, so both are the same instant.

    A track sampled on a grid of its own would drift against the robot,
    and the drift would look like the robot passing through the cart.
    """
    times = [0.0, 0.5, 1.0, 1.5, 2.0]
    (track,) = _obstacle_tracks(profile, context, times)
    assert len(track["x"]) == len(times)
    assert len(track["y"]) == len(times)
    assert track["radius_m"] > 0


def test_the_obstacle_actually_moves_and_then_stops(profile: TaskProfile, context) -> None:  # type: ignore[no-untyped-def]
    """The profile is named for its motion; the track should show it.

    Measured rather than asserted loosely: the cart travels early and is
    parked later, which is the whole premise of the episodes this
    deployment produces.
    """
    (track,) = _obstacle_tracks(profile, context, [0.0, 2.0, 6.0, 20.0])
    early = abs(track["y"][1] - track["y"][0])
    late = abs(track["y"][3] - track["y"][2])
    assert early > 0.5
    assert late == pytest.approx(0.0, abs=1e-9)


def test_the_seed_is_the_run_s_own(profile: TaskProfile, context) -> None:  # type: ignore[no-untyped-def]
    """Drawing another seed's traffic would put a cart where none was.

    `position_at` shifts each obstacle's clock by a hash of the seed, so
    two seeds are two different episodes — and a canvas that used the
    wrong one would be showing a plausible picture of a run that never
    happened.
    """
    from planbench_schemas.dynamic import position_at

    obstacle = profile.environment.dynamic_obstacles[0]
    (track,) = _obstacle_tracks(profile, context, [3.0])
    expected = position_at(obstacle, 3.0, context.seed)
    assert track["x"][0] == pytest.approx(expected.x)
    assert track["y"][0] == pytest.approx(expected.y)


def test_a_context_that_could_not_be_rebuilt_yields_no_obstacles(profile: TaskProfile) -> None:
    """Absent beats wrong: a misplaced cart reads as evidence."""
    assert _obstacle_tracks(profile, None, [0.0, 1.0]) == []


def test_a_trace_with_no_samples_yields_no_obstacles(profile: TaskProfile, context) -> None:  # type: ignore[no-untyped-def]
    assert _obstacle_tracks(profile, context, []) == []


def test_an_unknown_episode_id_resolves_to_nothing(profile: TaskProfile) -> None:
    """The id is a content hash, so a miss is a miss — never a near match."""
    assert _context_for(profile, "not-a-real-context-id") is None


def test_a_known_episode_id_resolves_to_its_context(profile: TaskProfile, context) -> None:
    """The other half of the pair, so the test above cannot pass by vacancy."""
    found = _context_for(profile, context.episode_context_id)
    assert found is not None
    assert found.seed == context.seed


# --------------------------------------------------------------------------
# The routes the planner asked for, placed against the trace's own steps
# --------------------------------------------------------------------------


def sidecar_with(tmp_path, outcomes):  # type: ignore[no-untyped-def]
    """One episode's sidecar, written the way a run writes one."""
    from planbench_explanation.sidecar_writer import GridSnapshot, PlanningInputRecorder
    from planbench_schemas.geometry import Pose2D

    path = tmp_path / "ep-001.parquet"
    sidecar = path.with_suffix(".planning_inputs.jsonl")
    recorder = PlanningInputRecorder.to_path(
        sidecar,
        run_id="run",
        episode_context_id="ep-001",
        candidate_id="cand_a",
        execution_environment_ref="git:" + "c" * 40,
    )
    grid = GridSnapshot.from_cells(
        [0] * 16, width=4, height=4, resolution=0.5, origin_x=0.0, origin_y=0.0
    )
    for index, points in enumerate(outcomes):
        common = {
            "simulation_tick": index * 100,
            "start_pose": Pose2D(x=0.0, y=0.0, theta=0.0),
            "goal_pose": Pose2D(x=1.5, y=1.5, theta=0.0),
            "grid": grid,
            "planner_name": "astar",
        }
        if points:
            recorder.record(
                **common,
                outcome="path",
                output_plan_checksum=f"{index:064d}",
                output_path=points,
            )
        else:
            recorder.record(**common, outcome="no_path", failure_code="no_global_path")
    recorder.close(expected_attempts=len(outcomes))
    return path


def test_the_initial_plan_starts_at_the_first_row(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from planbench_api.decision_service import _planned_routes

    path = sidecar_with(tmp_path, [[(0.0, 0.0), (1.0, 1.0)]])
    (route,) = _planned_routes(path, [])
    assert route["from_index"] == 0
    assert len(route["points"]) == 2


def test_each_replan_takes_over_on_the_row_it_was_recorded_on(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The handover comes from the trace's events, not the tick counter.

    The record counts simulation ticks and the trace counts control
    steps; converting between them would be a third opinion about the
    episode's timeline.
    """
    from planbench_api.decision_service import _planned_routes

    path = sidecar_with(
        tmp_path,
        [[(0.0, 0.0), (1.0, 0.0)], [(0.5, 0.0), (0.5, 1.0)], [(0.7, 1.0), (1.5, 1.5)]],
    )
    events = [
        {"index": 12, "event": "replan"},
        {"index": 40, "event": "goal_reached"},
        {"index": 31, "event": "replan"},
    ]
    routes = _planned_routes(path, events)
    assert [route["from_index"] for route in routes] == [0, 12, 31]


def test_a_refused_replan_is_a_route_with_no_points(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """At that step the robot had no plan, which is worth drawing as nothing."""
    from planbench_api.decision_service import _planned_routes

    path = sidecar_with(tmp_path, [[(0.0, 0.0), (1.0, 0.0)], []])
    routes = _planned_routes(path, [{"index": 20, "event": "replan"}])
    assert routes[1]["points"] == []
    assert routes[1]["from_index"] == 20


def test_attempts_and_replan_events_that_disagree_draw_nothing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A route placed at the wrong moment is a decision nobody made."""
    from planbench_api.decision_service import _planned_routes

    path = sidecar_with(tmp_path, [[(0.0, 0.0), (1.0, 0.0)], [(0.5, 0.0), (0.5, 1.0)]])
    # Three attempts' worth of events for a two-attempt sidecar.
    events = [{"index": 5, "event": "replan"}, {"index": 9, "event": "replan"}]
    assert _planned_routes(path, events) == []


def test_a_run_with_no_sidecar_draws_nothing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Recorded before E4.5: the lengths were kept, the polylines were not."""
    from planbench_api.decision_service import _planned_routes

    assert _planned_routes(tmp_path / "nothing-here.parquet", []) == []
