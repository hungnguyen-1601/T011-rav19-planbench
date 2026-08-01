"""Tests for the built-in scenario library."""

from __future__ import annotations

import pytest

from planbench_benchmark import CURRICULUM_ORDER, HOLDOUT_SCENARIOS, SCENARIO_LIBRARY, build_scenario
from planbench_benchmark.scenarios import STANDARD_ROBOT
from planbench_benchmark.scenarios import scenario_split
from planbench_planning import DWAPlanner
from planbench_schemas.episode import EpisodeStatus
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.nav_stack import plan_global_path, run_stack

ALL_SCENARIOS = list(SCENARIO_LIBRARY)


class TestLibraryContract:
    def test_curriculum_covers_every_scenario(self) -> None:
        assert set(CURRICULUM_ORDER) == set(SCENARIO_LIBRARY)
        assert CURRICULUM_ORDER[0] == "open_space"
        assert CURRICULUM_ORDER[-1] == "dynamic_warehouse"

    def test_unknown_scenario_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown scenario"):
            build_scenario("mars_colony")

    @pytest.mark.parametrize("name", ALL_SCENARIOS)
    def test_shares_the_same_robot_and_sensor(self, name: str) -> None:
        """Only geometry and traffic may differ — that is what makes
        cross-scenario comparison meaningful."""
        _, scenario = build_scenario(name)
        assert scenario.robot == STANDARD_ROBOT
        assert scenario.lidar.num_rays == 72
        assert scenario.simulation_dt == 0.05

    @pytest.mark.parametrize("name", ALL_SCENARIOS)
    def test_start_and_goal_are_placeable(self, name: str) -> None:
        map_data, scenario = build_scenario(name)
        engine = SimulationEngine()
        engine.load_map(map_data)
        engine.load_scenario(scenario)  # raises if start/goal collide

    @pytest.mark.parametrize("name", ALL_SCENARIOS)
    def test_a_global_path_exists(self, name: str) -> None:
        """Every scenario must be solvable in principle; otherwise a
        planner failure would be a scenario bug, not an algorithm result."""
        map_data, scenario = build_scenario(name)
        plan, _ = plan_global_path(map_data, scenario)
        assert plan.success, f"{name}: {plan.failure_reason}"
        assert len(plan.path) >= 2

    @pytest.mark.parametrize("name", ALL_SCENARIOS)
    def test_map_is_walled(self, name: str) -> None:
        """Maps need a closed border (LiDAR treats outside as empty)."""
        map_data, _ = build_scenario(name)
        width, height = map_data.width, map_data.height
        cells = map_data.cells
        assert all(cells[col] == 100 for col in range(width))
        assert all(cells[(height - 1) * width + col] == 100 for col in range(width))
        assert all(cells[row * width] == 100 for row in range(height))
        assert all(cells[row * width + width - 1] == 100 for row in range(height))


class TestHeldOutSplit:
    """P05: dev/holdout split for final reporting (spec section 8.6e)."""

    def test_holdout_scenarios_are_a_subset_of_the_library(self) -> None:
        assert HOLDOUT_SCENARIOS <= set(SCENARIO_LIBRARY)
        assert HOLDOUT_SCENARIOS  # not empty — a split with nothing held out is not a split

    @pytest.mark.parametrize("name", sorted(HOLDOUT_SCENARIOS))
    def test_holdout_scenarios_report_as_holdout(self, name: str) -> None:
        assert scenario_split(name) == "holdout"

    @pytest.mark.parametrize("name", sorted(set(SCENARIO_LIBRARY) - HOLDOUT_SCENARIOS))
    def test_non_holdout_library_scenarios_report_as_dev(self, name: str) -> None:
        assert scenario_split(name) == "dev"

    def test_a_scenario_outside_the_library_is_dev_by_default(self) -> None:
        assert scenario_split("some-users-own-map") == "dev"


class TestDynamicScenarios:
    @pytest.mark.parametrize(
        "name",
        [
            "crossing_obstacle",
            "sudden_stop",
            "bidirectional_corridor",
            "intersection",
            "dynamic_warehouse",
        ],
    )
    def test_declares_moving_obstacles(self, name: str) -> None:
        _, scenario = build_scenario(name)
        assert scenario.dynamic_obstacles

    @pytest.mark.parametrize("name", ["open_space", "narrow_corridor", "doorway"])
    def test_static_scenarios_have_no_traffic(self, name: str) -> None:
        _, scenario = build_scenario(name)
        assert scenario.dynamic_obstacles == ()


class TestRunnableWithDWA:
    @pytest.mark.parametrize("name", ["open_space", "wide_corridor"])
    def test_dwa_solves_the_easy_scenarios(self, name: str) -> None:
        map_data, scenario = build_scenario(name)
        run = run_stack(map_data, scenario, DWAPlanner())
        assert run.result.status is EpisodeStatus.SUCCESS, run.result.reason

    def test_dynamic_scenario_runs_deterministically(self) -> None:
        map_data, scenario = build_scenario("crossing_obstacle")
        seeded = scenario.model_copy(update={"random_seed": 5})
        first = run_stack(map_data, seeded, DWAPlanner())
        second = run_stack(map_data, seeded, DWAPlanner())
        assert first.result.trajectory == second.result.trajectory
