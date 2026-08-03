#!/usr/bin/env python3
"""Headless demo: A* + pure-pursuit episode in a small warehouse map.

Run from the repository root with the project virtualenv:

    PYTHONPATH= .venv/bin/python scripts/demo_astar_episode.py

Prints real episode metrics and writes trajectory/plan/metrics JSON to
``artifacts/demo/astar_episode.json`` (git-ignored).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for relative in ("packages/schemas", "packages/planning", "packages/metrics", "services/simulator"):
    sys.path.insert(0, str(REPO_ROOT / relative))

from planbench_schemas.geometry import Point2D, Pose2D  # noqa: E402
from planbench_schemas.map import CellState, MapData  # noqa: E402
from planbench_schemas.robot import RobotConfig  # noqa: E402
from planbench_schemas.scenario import CircleObstacle, RectangleObstacle, Scenario  # noqa: E402
from planbench_simulator.episode_runner import run_episode  # noqa: E402


def build_demo_map() -> MapData:
    """12 m x 9 m warehouse (0.25 m cells) with border walls and shelves."""
    resolution = 0.25
    width, height = 48, 36
    free, occupied = CellState.FREE.value, CellState.OCCUPIED.value
    cells = [free] * (width * height)

    def set_occupied(row: int, col: int) -> None:
        cells[row * width + col] = occupied

    for col in range(width):
        set_occupied(0, col)
        set_occupied(height - 1, col)
    for row in range(height):
        set_occupied(row, 0)
        set_occupied(row, width - 1)
    # Two shelf rows (in cells): y bands at rows 12-14 and 22-24 with a gap.
    for row in (12, 13, 14, 22, 23, 24):
        for col in range(8, 40):
            if 20 <= col <= 25:  # aisle gap
                continue
            set_occupied(row, col)

    return MapData(
        name="demo-warehouse",
        width=width,
        height=height,
        resolution=resolution,
        origin=Pose2D(x=0.0, y=0.0, theta=0.0),
        cells=tuple(cells),
    )


def build_demo_scenario() -> Scenario:
    return Scenario(
        name="demo-astar-pure-pursuit",
        description="Cross two shelf rows through the central aisle.",
        robot=RobotConfig(
            radius=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=2.0,
            max_linear_acceleration=1.0,
            max_angular_acceleration=3.0,
        ),
        start_pose=Pose2D(x=1.5, y=1.5, theta=0.0),
        goal_pose=Pose2D(x=10.5, y=7.5, theta=0.0),
        goal_tolerance=0.3,
        timeout_seconds=120.0,
        simulation_dt=0.05,
        static_obstacles=(
            CircleObstacle(center=Point2D(x=4.0, y=1.8), radius=0.4),
            RectangleObstacle(min_x=7.0, min_y=1.2, max_x=8.0, max_y=2.0),
        ),
    )


def main() -> int:
    map_data = build_demo_map()
    scenario = build_demo_scenario()
    run = run_episode(map_data, scenario)

    print(f"map: {map_data.name} ({map_data.width}x{map_data.height} @ {map_data.resolution} m)")
    print(f"scenario: {scenario.name}")
    print(
        f"plan: success={run.plan.success} waypoints={len(run.plan.path)} "
        f"length={run.plan.path_length:.2f} m expanded={run.plan.expanded_nodes} "
        f"time={run.plan.planning_time_seconds * 1000:.1f} ms"
    )
    print(f"episode: status={run.result.status.value} reason={run.result.reason!r}")
    print(f"  steps={run.result.steps} sim_time={run.result.elapsed_time:.2f} s")
    metrics = run.metrics
    print("metrics:")
    print(f"  trajectory_length = {metrics.trajectory_length:.2f} m")
    print(f"  path_efficiency   = {metrics.path_efficiency}")
    print(f"  average_speed     = {metrics.average_speed:.2f} m/s")
    print(f"  max_speed         = {metrics.max_speed:.2f} m/s")
    print(f"  smoothness        = {metrics.smoothness:.3f} rad/m")
    print(f"  min_clearance     = {metrics.min_clearance:.3f} m")
    print(f"  mean_clearance    = {metrics.mean_clearance:.3f} m")

    output_dir = REPO_ROOT / "artifacts" / "demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "astar_episode.json"
    output_file.write_text(
        json.dumps(
            {
                "map_checksum": map_data.checksum(),
                "scenario": scenario.model_dump(),
                "plan": run.plan.model_dump(),
                "result": run.result.model_dump(),
                "metrics": run.metrics.model_dump(),
            },
            indent=2,
        )
    )
    print(f"artifact: {output_file.relative_to(REPO_ROOT)}")
    return 0 if run.result.status.value == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
