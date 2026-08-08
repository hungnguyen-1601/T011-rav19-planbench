"""Tests for the RRT* global planner.

Mirrors ``test_astar.py`` for the shared contract, then adds the cases
that only matter for a sampling planner: reproducibility from a seed,
genuine randomness across seeds, and the anytime property that
separates RRT* from plain RRT.
"""

from __future__ import annotations

import pytest

from planbench_planning import RRTStarConfig, RRTStarPlanner, has_line_of_sight
from planbench_schemas.geometry import Point2D, euclidean_distance
from planbench_simulator.grid import OccupancyGrid


def p(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


def assert_path_valid(grid: OccupancyGrid, path: tuple[Point2D, ...]) -> None:
    """Every consecutive segment must stay in free space."""
    assert len(path) >= 2
    for a, b in zip(path, path[1:], strict=False):
        assert has_line_of_sight(grid, a, b), f"segment {a} -> {b} crosses an obstacle"


def planner(**overrides) -> RRTStarPlanner:
    """A planner with a budget small enough for fast tests."""
    options = {"max_iterations": 1500, "step_size": 1.0, "rewire_radius": 2.0}
    options.update(overrides)
    episode_seed = options.pop("episode_seed", 0)
    return RRTStarPlanner(RRTStarConfig(**options), episode_seed=episode_seed)


class TestRRTStarSuccess:
    def test_empty_map(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner().plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert result.success
        assert result.path[0] == p(1.5, 1.5)
        assert result.path[-1] == p(8.5, 8.5)
        assert result.path_length >= euclidean_distance(p(1.5, 1.5), p(8.5, 8.5)) - 1e-9
        assert result.expanded_nodes > 0
        assert_path_valid(grid, result.path)

    def test_goal_is_reached_within_tolerance(self, map_factory) -> None:
        # The tree only has to get within goal_tolerance; the final hop
        # to the exact goal is the last path segment and must be free.
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner(goal_tolerance=0.5).plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert result.success
        assert euclidean_distance(result.path[-2], p(8.5, 8.5)) <= 0.5
        assert has_line_of_sight(grid, result.path[-2], result.path[-1])

    def test_wall_with_gap(self, map_factory) -> None:
        # Wall col=5, gap at row 9 -> path must detour through the gap.
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        result = planner(max_iterations=4000).plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert result.success
        assert_path_valid(grid, result.path)
        assert result.path_length > euclidean_distance(p(2.5, 2.5), p(8.5, 2.5))

    def test_start_equals_goal_cell(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5))
        result = planner().plan(grid, p(2.2, 2.2), p(2.8, 2.8))  # same cell (2, 2)
        assert result.success
        assert result.path == (p(2.2, 2.2), p(2.8, 2.8))
        assert result.cost == 0.0

    def test_expanded_nodes_counts_tree_nodes(self, map_factory) -> None:
        # Comparable in meaning to A*'s expanded nodes: the search
        # effort actually spent. Bounded by the iteration budget.
        grid = OccupancyGrid(map_factory(10, 10))
        result = planner(max_iterations=300).plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert result.success
        assert 1 < result.expanded_nodes <= 301


class TestRRTStarFailures:
    def test_no_path(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(10))))
        result = planner(max_iterations=500).plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert not result.success
        assert result.failure_reason
        assert result.path == ()

    def test_start_outside_map(self, map_factory) -> None:
        result = planner().plan(OccupancyGrid(map_factory(5, 5)), p(-1.0, 2.5), p(2.5, 2.5))
        assert not result.success
        assert "start is outside" in result.failure_reason

    def test_goal_outside_map(self, map_factory) -> None:
        result = planner().plan(OccupancyGrid(map_factory(5, 5)), p(2.5, 2.5), p(7.0, 2.5))
        assert not result.success
        assert "goal is outside" in result.failure_reason

    def test_start_in_obstacle(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        result = planner().plan(grid, p(2.5, 2.5), p(4.5, 4.5))
        assert not result.success
        assert "start is inside an obstacle" in result.failure_reason

    def test_goal_in_obstacle(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(5, 5, occupied=((2, 2),)))
        result = planner().plan(grid, p(0.5, 0.5), p(2.5, 2.5))
        assert not result.success
        assert "goal is inside an obstacle" in result.failure_reason

    def test_unknown_cells_block_planning_by_default(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, unknown=tuple((row, 5) for row in range(10))))
        result = planner(max_iterations=500).plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert not result.success


class TestRRTStarDeterminism:
    def test_same_seed_gives_the_identical_path(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10, occupied=tuple((row, 5) for row in range(9))))
        first = planner().plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        second = planner().plan(grid, p(2.5, 2.5), p(8.5, 2.5))
        assert first.success and second.success
        assert first.path == second.path
        assert first.cost == second.cost
        assert first.expanded_nodes == second.expanded_nodes

    def test_replanning_with_one_instance_repeats_itself(self, map_factory) -> None:
        # The generator is rebuilt per plan() call, so a reused planner
        # cannot drift — this is what keeps a re-run reproducible.
        grid = OccupancyGrid(map_factory(10, 10))
        reused = planner()
        assert reused.plan(grid, p(1.5, 1.5), p(8.5, 8.5)).path == (
            reused.plan(grid, p(1.5, 1.5), p(8.5, 8.5)).path
        )

    def test_different_episode_seeds_give_different_paths(self, map_factory) -> None:
        # Guards the wiring bug the plan calls out: if the episode seed
        # never reaches the planner, every episode replays one tree.
        grid = OccupancyGrid(map_factory(10, 10))
        paths = {
            planner(episode_seed=seed).plan(grid, p(1.5, 1.5), p(8.5, 8.5)).path
            for seed in range(4)
        }
        assert len(paths) == 4

    def test_different_config_seeds_give_different_paths(self, map_factory) -> None:
        grid = OccupancyGrid(map_factory(10, 10))
        first = planner(seed=1).plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        second = planner(seed=2).plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert first.path != second.path

    def test_config_seed_and_episode_seed_do_not_collide(self, map_factory) -> None:
        # An XOR mix would make (1, 2) and (3, 0) the same draw.
        grid = OccupancyGrid(map_factory(10, 10))
        mixed = planner(seed=1, episode_seed=2).plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        other = planner(seed=3, episode_seed=0).plan(grid, p(1.5, 1.5), p(8.5, 8.5))
        assert mixed.path != other.path


class TestRRTStarOptimality:
    def test_more_iterations_never_lengthen_the_path(self, map_factory) -> None:
        """The property that separates RRT* from plain RRT.

        Plain RRT returns the first path it stumbles on, so a bigger
        budget just changes it arbitrarily. RRT* keeps rewiring, so the
        answer may only improve.
        """
        grid = OccupancyGrid(map_factory(20, 20, occupied=tuple((row, 10) for row in range(16))))
        short = planner(max_iterations=500).plan(grid, p(2.5, 2.5), p(17.5, 2.5))
        long = planner(max_iterations=5000).plan(grid, p(2.5, 2.5), p(17.5, 2.5))
        assert short.success and long.success
        assert long.path_length <= short.path_length + 1e-9
        assert_path_valid(grid, long.path)

    def test_rewiring_beats_the_first_solution_found(self, map_factory) -> None:
        # A rewired path on an open map should come close to the
        # straight line; a raw RRT path typically does not.
        grid = OccupancyGrid(map_factory(20, 20))
        result = planner(max_iterations=4000).plan(grid, p(2.5, 2.5), p(17.5, 17.5))
        assert result.success
        straight = euclidean_distance(p(2.5, 2.5), p(17.5, 17.5))
        assert result.path_length < straight * 1.25


class TestRRTStarConfigValidation:
    @pytest.mark.parametrize(
        "field, value",
        [
            ("max_iterations", 0),
            ("step_size", 0.0),
            ("goal_bias", 1.5),
            ("rewire_radius", -1.0),
            ("goal_tolerance", 0.0),
            ("seed", -1),
        ],
    )
    def test_rejects_impossible_values(self, field: str, value: float) -> None:
        with pytest.raises(ValueError):
            RRTStarConfig(**{field: value})

    def test_is_frozen(self) -> None:
        config = RRTStarConfig()
        with pytest.raises(ValueError):
            config.seed = 5  # type: ignore[misc]
