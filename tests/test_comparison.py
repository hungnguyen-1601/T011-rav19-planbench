"""P04 — head-to-head comparison, paired by seed.

The single thing these tests exist to protect: the pairing. A signed-rank
test on two lists that were never matched up by seed is not a weaker
test, it is a different test that answers no question anyone asked — and
it produces a perfectly normal-looking p-value while doing so. So the
cases below check that pairing happens by seed rather than by position,
that seeds where either stack failed drop out, and that everything
dropped is disclosed on the result.
"""

from __future__ import annotations

import pytest

from planbench_benchmark.comparison import (
    MIN_PAIRS_FOR_TEST,
    build_comparisons,
    compare_pair,
    leader,
)
from planbench_benchmark.runner import aggregate_algorithm
from planbench_benchmark.spec import AlgorithmAggregate, BenchmarkReport, RunRecord
from planbench_metrics import EpisodeMetrics
from planbench_schemas.episode import EpisodeStatus


def run(
    algorithm: str,
    seed: int,
    travel_time: float,
    *,
    status: EpisodeStatus = EpisodeStatus.SUCCESS,
    efficiency: float | None = 0.9,
) -> RunRecord:
    """One episode. Only the fields the comparison reads are meaningful."""
    return RunRecord(
        algorithm=algorithm,
        seed=seed,
        status=status,
        reason="",
        metrics=EpisodeMetrics(
            status=status,
            success=status is EpisodeStatus.SUCCESS,
            collision=status is EpisodeStatus.COLLISION,
            travel_time=travel_time,
            steps=int(travel_time * 10),
            trajectory_length=travel_time,
            average_speed=1.0,
            max_speed=1.2,
            smoothness=0.1,
            path_efficiency=efficiency,
        ),
        trajectory_points=2,
        episode_index=seed,
    )


def both(seeds: dict[int, tuple[float, float]]) -> list[RunRecord]:
    """``seed -> (a's travel time, b's travel time)`` for two stacks."""
    runs: list[RunRecord] = []
    for seed, (a_value, b_value) in seeds.items():
        runs.append(run("a", seed, a_value))
        runs.append(run("b", seed, b_value))
    return runs


class TestPairingIsBySeed:
    def test_shuffled_storage_order_gives_the_same_result(self) -> None:
        """The decisive test: order in the list must not matter, seeds must."""
        values = {1: (10.0, 12.0), 2: (11.0, 15.0), 3: (9.0, 9.5), 4: (12.0, 14.0), 5: (8.0, 9.0)}
        ordered = both(values)
        shuffled = [*ordered[::-1]]
        assert compare_pair(ordered, "a", "b") == compare_pair(shuffled, "a", "b")

    def test_mismatched_pairing_would_change_the_answer(self) -> None:
        """Proves the previous test is not vacuous.

        Pairing a's seed 1 with b's seed 2 is a different comparison. If
        it were not, nothing above would be worth checking.
        """
        aligned = compare_pair(
            both(
                {
                    1: (10.0, 11.0),
                    2: (20.0, 21.0),
                    3: (30.0, 31.0),
                    4: (40.0, 41.0),
                    5: (50.0, 51.0),
                }
            ),
            "a",
            "b",
        )
        crossed = compare_pair(
            both(
                {
                    1: (10.0, 51.0),
                    2: (20.0, 41.0),
                    3: (30.0, 31.0),
                    4: (40.0, 21.0),
                    5: (50.0, 11.0),
                }
            ),
            "a",
            "b",
        )
        assert aligned.statistic != crossed.statistic

    def test_seeds_where_one_stack_failed_are_dropped_and_disclosed(self) -> None:
        runs = [
            run("a", 1, 10.0),
            run("b", 1, 12.0),
            run("a", 2, 11.0),
            run("b", 2, 0.0, status=EpisodeStatus.TIMEOUT),
            run("a", 3, 9.0),
            run("b", 3, 9.5),
            run("a", 4, 12.0),
            run("b", 4, 13.0),
            run("a", 5, 8.0),
            run("b", 5, 9.0),
            run("a", 6, 7.0),
            run("b", 6, 8.0),
        ]
        result = compare_pair(runs, "a", "b")
        assert result.paired_seed_count == 5
        assert result.warning is not None
        assert "1 of 6 shared seeds" in result.warning

    def test_different_seed_sets_are_flagged_as_a_fairness_problem(self) -> None:
        runs = [
            *both({1: (10.0, 12.0), 2: (11.0, 13.0), 3: (9.0, 10.0), 4: (8.0, 9.0), 5: (7.0, 8.0)}),
            run("a", 6, 6.0),
        ]
        result = compare_pair(runs, "a", "b")
        assert result.warning is not None
        assert "did not run the same seeds" in result.warning


class TestTestIsOnlyRunWhenItMeansSomething:
    def test_too_few_pairs_returns_no_statistic(self) -> None:
        result = compare_pair(both({1: (10.0, 12.0), 2: (11.0, 13.0)}), "a", "b")
        assert result.statistic is None
        assert result.p_value is None
        assert result.effect_size is None
        assert result.significant is False
        assert result.paired_seed_count == 2
        assert result.warning is not None
        assert str(MIN_PAIRS_FOR_TEST) in result.warning

    def test_no_shared_successes_returns_no_statistic(self) -> None:
        runs = [
            run("a", 1, 10.0),
            run("b", 1, 0.0, status=EpisodeStatus.COLLISION),
            run("a", 2, 11.0),
            run("b", 2, 0.0, status=EpisodeStatus.COLLISION),
        ]
        result = compare_pair(runs, "a", "b")
        assert result.paired_seed_count == 0
        assert result.p_value is None

    def test_a_clear_consistent_difference_is_significant(self) -> None:
        # Ranges kept disjoint (a: 11..22, b: 101..112) so the effect
        # size is exactly -1 and the assertion below is unambiguous.
        values = {seed: (10.0 + seed, 100.0 + seed) for seed in range(1, 13)}
        result = compare_pair(both(values), "a", "b")
        assert result.p_value is not None
        assert result.p_value < 0.05
        assert result.significant is True
        # a is faster on every seed, so its values are lower throughout.
        assert result.effect_size == -1.0
        assert result.paired_seed_count == 12
        assert result.warning is None

    def test_identical_stacks_are_not_significant(self) -> None:
        values = {seed: (10.0 + seed, 10.0 + seed) for seed in range(1, 9)}
        result = compare_pair(both(values), "a", "b")
        assert result.p_value == 1.0
        assert result.significant is False
        assert result.effect_size == 0.0

    def test_a_metric_other_than_travel_time_can_be_compared(self) -> None:
        runs = both(dict.fromkeys(range(1, 8), (10.0, 12.0)))
        result = compare_pair(runs, "a", "b", metric="path_efficiency")
        assert result.metric == "path_efficiency"
        # Both stacks were given the same efficiency, so no difference.
        assert result.p_value == 1.0


class TestBuildComparisons:
    def _aggregates(self, runs: list[RunRecord]) -> tuple:
        algorithms = sorted({record.algorithm for record in runs})
        return tuple(
            aggregate_algorithm(name, [r for r in runs if r.algorithm == name])
            for name in algorithms
        )

    def test_baseline_is_the_most_successful_stack(self) -> None:
        runs = [
            *[run("a", seed, 10.0) for seed in range(1, 6)],
            *[run("b", seed, 9.0) for seed in range(1, 5)],
            run("b", 5, 0.0, status=EpisodeStatus.TIMEOUT),
        ]
        aggregates = self._aggregates(runs)
        assert leader(aggregates) == "a"
        comparisons = build_comparisons(runs, aggregates)
        assert [c.algorithm_a for c in comparisons] == ["a"]
        assert [c.algorithm_b for c in comparisons] == ["b"]

    def test_ties_break_on_name_so_the_table_is_stable(self) -> None:
        runs = both(dict.fromkeys(range(1, 6), (10.0, 10.0)))
        forward = build_comparisons(runs, self._aggregates(runs))
        backward = build_comparisons(runs[::-1], self._aggregates(runs[::-1]))
        assert forward[0].algorithm_a == backward[0].algorithm_a == "a"

    def test_single_algorithm_has_nothing_to_compare(self) -> None:
        runs = [run("a", seed, 10.0) for seed in range(1, 6)]
        assert build_comparisons(runs, self._aggregates(runs)) == ()

    def test_no_aggregates_returns_nothing(self) -> None:
        assert build_comparisons([], ()) == ()
        assert leader(()) is None

    def test_every_other_stack_gets_a_row(self) -> None:
        runs = [
            *[run("a", seed, 10.0) for seed in range(1, 7)],
            *[run("b", seed, 11.0) for seed in range(1, 7)],
            *[run("c", seed, 12.0) for seed in range(1, 7)],
        ]
        comparisons = build_comparisons(runs, self._aggregates(runs))
        assert [c.algorithm_b for c in comparisons] == ["b", "c"]
        assert all(c.algorithm_a == "a" for c in comparisons)


class TestReportSeedAdequacy:
    def _report(self, seeds: tuple[int, ...]) -> BenchmarkReport:
        from planbench_benchmark.spec import AlgorithmSpec, BenchmarkSpec, FairnessRecord

        spec = BenchmarkSpec(name="b", algorithms=(AlgorithmSpec(id="a"),), seeds=seeds)
        fairness = FairnessRecord(
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
            conditions_checksum="c",
        )
        return BenchmarkReport(spec=spec, fairness=fairness, runs=(), aggregates=())

    def test_seed_count_comes_from_the_spec(self) -> None:
        assert self._report(tuple(range(7))).seed_count == 7

    def test_small_benchmark_is_marked_inadequate(self) -> None:
        assert self._report((1, 2, 3)).statistically_adequate is False

    def test_thirty_seeds_is_adequate(self) -> None:
        assert self._report(tuple(range(30))).statistically_adequate is True

    def test_both_fields_are_serialised(self) -> None:
        """Computed, so old stored reports get them too — but only if the
        API actually emits them."""
        payload = self._report((1, 2)).model_dump(mode="json")
        assert payload["seed_count"] == 2
        assert payload["statistically_adequate"] is False

    def test_report_without_comparisons_still_loads(self) -> None:
        report = self._report((1, 2))
        assert report.comparisons == ()


class TestAggregateRobustSummaries:
    def _aggregate(self, travel_times: list[float]):
        runs = [run("a", seed, value) for seed, value in enumerate(travel_times)]
        return aggregate_algorithm("a", runs)

    def test_median_and_iqr_are_computed_from_successful_runs(self) -> None:
        aggregate = self._aggregate([10.0, 12.0, 14.0, 16.0, 18.0])
        assert aggregate.median_travel_time_successful == 14.0
        assert aggregate.iqr_travel_time_successful == (12.0, 16.0)

    def test_median_resists_an_outlier_the_mean_does_not(self) -> None:
        aggregate = self._aggregate([10.0, 11.0, 12.0, 13.0, 600.0])
        assert aggregate.median_travel_time_successful == 12.0
        assert aggregate.mean_travel_time_successful is not None
        assert aggregate.mean_travel_time_successful > 100.0

    def test_confidence_interval_brackets_the_median(self) -> None:
        aggregate = self._aggregate([10.0, 12.0, 14.0, 16.0, 18.0])
        interval = aggregate.ci95_travel_time_successful
        assert interval is not None
        assert interval[0] <= 14.0 <= interval[1]

    def test_same_runs_give_the_same_interval(self) -> None:
        values = [10.0, 12.5, 9.0, 14.0, 11.0, 13.0]
        assert (
            self._aggregate(values).ci95_travel_time_successful
            == self._aggregate(values).ci95_travel_time_successful
        )

    def test_one_success_has_a_median_but_no_interval(self) -> None:
        aggregate = self._aggregate([10.0])
        assert aggregate.median_travel_time_successful == 10.0
        assert aggregate.ci95_travel_time_successful is None

    def test_no_success_leaves_every_summary_none(self) -> None:
        runs = [run("a", seed, 0.0, status=EpisodeStatus.TIMEOUT) for seed in range(5)]
        aggregate = aggregate_algorithm("a", runs)
        assert aggregate.median_travel_time_successful is None
        assert aggregate.iqr_travel_time_successful is None
        assert aggregate.ci95_travel_time_successful is None
        assert aggregate.median_path_efficiency_successful is None
        assert aggregate.median_smoothness_successful is None

    def test_success_rate_interval_is_always_present(self) -> None:
        """Even at 0% and 100%, where a naive interval implies certainty."""
        perfect = self._aggregate([10.0] * 5)
        assert perfect.ci95_success_rate is not None
        assert perfect.ci95_success_rate[0] < 1.0

        runs = [run("a", seed, 0.0, status=EpisodeStatus.TIMEOUT) for seed in range(5)]
        hopeless = aggregate_algorithm("a", runs)
        assert hopeless.ci95_success_rate is not None
        assert hopeless.ci95_success_rate[1] > 0.0

    def test_old_reports_without_the_new_fields_still_load(self) -> None:
        """Additive only: a report stored before P04 must stay readable."""
        legacy = {
            "algorithm": "astar+dwa",
            "episodes": 2,
            "success_rate": 1.0,
            "collision_rate": 0.0,
            "timeout_rate": 0.0,
            "stuck_rate": 0.0,
            "no_progress_rate": 0.0,
            "no_global_path_rate": 0.0,
            "mean_travel_time_successful": 9.5,
        }
        aggregate = AlgorithmAggregate.model_validate(legacy)
        assert aggregate.mean_travel_time_successful == 9.5
        assert aggregate.median_travel_time_successful is None
        assert aggregate.ci95_success_rate is None

    def test_efficiency_summary_skips_runs_without_the_metric(self) -> None:
        runs = [
            run("a", 0, 10.0, efficiency=0.8),
            run("a", 1, 11.0, efficiency=None),
            run("a", 2, 12.0, efficiency=0.9),
        ]
        aggregate = aggregate_algorithm("a", runs)
        assert aggregate.median_path_efficiency_successful == pytest.approx(0.85)
