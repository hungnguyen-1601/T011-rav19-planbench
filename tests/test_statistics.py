"""P04 — the statistics under every conclusion this platform publishes.

These tests check three separate things, and the third is the one that
matters most.

1. The wrappers agree with hand-computed values on small samples, so a
   reader can verify the layer by eye.
2. They refuse bad input instead of returning a plausible number. A
   statistic that quietly summarises three points, or silently drops a
   NaN, is worse than one that raises: nobody reviews a number that
   looks fine.
3. They agree with SciPy called directly. This is the point of the
   module — the platform must not have its own arithmetic drifting
   underneath a published p-value.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from planbench_metrics.statistics import (
    ADEQUATE_SEED_COUNT,
    StatisticsInputError,
    average_rank_score,
    bootstrap_ci,
    cliffs_delta,
    median_iqr,
    proportion_ci,
    statistically_adequate,
    wilcoxon_compare,
)


class TestMedianAndIqr:
    def test_odd_sample_is_the_middle_value(self) -> None:
        median, q1, q3 = median_iqr([1.0, 2.0, 3.0, 4.0, 5.0])
        assert median == 3.0
        assert (q1, q3) == (2.0, 4.0)

    def test_even_sample_interpolates(self) -> None:
        median, q1, q3 = median_iqr([1.0, 2.0, 3.0, 4.0])
        assert median == 2.5
        assert (q1, q3) == (1.75, 3.25)

    def test_a_single_outlier_does_not_move_the_median(self) -> None:
        """The reason the report quotes medians at all."""
        typical = [10.0, 11.0, 12.0, 13.0, 14.0]
        with_timeout = [*typical[:-1], 600.0]
        assert median_iqr(typical)[0] == median_iqr(with_timeout)[0]
        assert np.mean(typical) != np.mean(with_timeout)

    def test_skewed_sample_keeps_the_quartiles_apart(self) -> None:
        median, q1, q3 = median_iqr([1.0, 1.0, 1.0, 2.0, 60.0])
        assert median == 1.0
        assert q1 == 1.0
        assert q3 == 2.0

    def test_empty_input_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            median_iqr([])

    def test_nan_raises_instead_of_propagating(self) -> None:
        with pytest.raises(StatisticsInputError):
            median_iqr([1.0, float("nan"), 3.0])

    def test_infinity_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            median_iqr([1.0, float("inf")])


class TestBootstrapCi:
    SAMPLE = [12.0, 13.5, 11.0, 14.2, 12.8, 15.0, 11.9, 13.1, 12.2, 16.4]

    def test_same_seed_gives_the_same_interval(self) -> None:
        first = bootstrap_ci(self.SAMPLE, seed=7)
        second = bootstrap_ci(self.SAMPLE, seed=7)
        assert first == second

    def test_interval_brackets_the_statistic(self) -> None:
        low, high = bootstrap_ci(self.SAMPLE, seed=0)
        median = float(np.median(self.SAMPLE))
        assert low <= median <= high

    def test_matches_scipy_called_directly(self) -> None:
        """The wrapper must not be doing arithmetic of its own."""
        low, high = bootstrap_ci(self.SAMPLE, seed=3, n_resamples=500)
        expected = stats.bootstrap(
            (np.asarray(self.SAMPLE),),
            np.median,
            n_resamples=500,
            confidence_level=0.95,
            method="percentile",
            vectorized=False,
            rng=np.random.default_rng(3),
        ).confidence_interval
        assert low == pytest.approx(float(expected.low))
        assert high == pytest.approx(float(expected.high))

    def test_a_wider_level_gives_a_wider_interval(self) -> None:
        narrow = bootstrap_ci(self.SAMPLE, level=0.80, seed=0)
        wide = bootstrap_ci(self.SAMPLE, level=0.99, seed=0)
        assert wide[0] <= narrow[0]
        assert wide[1] >= narrow[1]

    def test_constant_sample_returns_the_value_not_nan(self) -> None:
        assert bootstrap_ci([4.0, 4.0, 4.0], seed=0) == (4.0, 4.0)

    def test_single_value_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            bootstrap_ci([1.0])

    @pytest.mark.parametrize("level", [0.0, 1.0, -0.5, 1.5])
    def test_invalid_confidence_level_raises(self, level: float) -> None:
        with pytest.raises(StatisticsInputError):
            bootstrap_ci(self.SAMPLE, level=level)

    def test_non_positive_resamples_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            bootstrap_ci(self.SAMPLE, n_resamples=0)

    def test_nan_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            bootstrap_ci([1.0, 2.0, float("nan")])


class TestWilcoxon:
    def test_matches_scipy_on_a_textbook_sample(self) -> None:
        a = [125.0, 115.0, 130.0, 140.0, 140.0, 115.0, 140.0, 125.0, 140.0, 135.0]
        b = [110.0, 122.0, 125.0, 120.0, 140.0, 124.0, 123.0, 137.0, 135.0, 145.0]
        statistic, p_value = wilcoxon_compare(a, b)
        expected = stats.wilcoxon(np.asarray(a), np.asarray(b))
        assert statistic == pytest.approx(float(expected.statistic))
        assert p_value == pytest.approx(float(expected.pvalue))

    def test_detects_a_consistent_shift(self) -> None:
        a = [float(i) for i in range(1, 21)]
        b = [value + 5.0 for value in a]
        _, p_value = wilcoxon_compare(a, b)
        assert p_value < 0.01

    def test_order_does_not_change_the_p_value(self) -> None:
        a = [3.0, 5.0, 2.0, 8.0, 6.0, 7.0, 4.0]
        b = [4.0, 4.0, 3.0, 6.0, 9.0, 5.0, 5.0]
        assert wilcoxon_compare(a, b)[1] == pytest.approx(wilcoxon_compare(b, a)[1])

    def test_identical_samples_report_no_difference(self) -> None:
        """Two stacks can tie on every seed; that is a result, not a crash."""
        sample = [1.0, 2.0, 3.0, 4.0]
        assert wilcoxon_compare(sample, sample) == (0.0, 1.0)

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(StatisticsInputError):
            wilcoxon_compare([1.0, 2.0, 3.0], [1.0, 2.0])

    def test_empty_input_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            wilcoxon_compare([], [])


class TestCliffsDelta:
    def test_identical_samples_are_zero(self) -> None:
        sample = [1.0, 2.0, 3.0, 4.0]
        assert cliffs_delta(sample, sample) == 0.0

    def test_strictly_greater_is_one(self) -> None:
        assert cliffs_delta([10.0, 11.0, 12.0], [1.0, 2.0]) == 1.0

    def test_strictly_smaller_is_minus_one(self) -> None:
        assert cliffs_delta([1.0, 2.0], [10.0, 11.0, 12.0]) == -1.0

    def test_partial_overlap_is_computed_by_hand(self) -> None:
        # a = [1, 3]; b = [2, 4]. Pairs greater: (3>2). Pairs less:
        # (1<2), (1<4), (3<4). delta = (1 - 3) / 4.
        assert cliffs_delta([1.0, 3.0], [2.0, 4.0]) == -0.5

    def test_works_on_unequal_sample_sizes(self) -> None:
        """Unpaired by design: two stacks rarely succeed on the same seeds."""
        assert cliffs_delta([5.0, 6.0, 7.0, 8.0], [1.0]) == 1.0


class TestProportionCi:
    def test_brackets_the_observed_rate(self) -> None:
        low, high = proportion_ci(15, 30)
        assert low <= 0.5 <= high

    def test_all_successes_does_not_claim_certainty(self) -> None:
        low, high = proportion_ci(5, 5)
        assert high == pytest.approx(1.0)
        assert low < 1.0

    def test_no_successes_does_not_claim_certainty(self) -> None:
        low, high = proportion_ci(0, 5)
        assert low == pytest.approx(0.0)
        assert high > 0.0

    def test_more_trials_narrow_the_interval(self) -> None:
        small = proportion_ci(5, 10)
        large = proportion_ci(50, 100)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_matches_scipy_called_directly(self) -> None:
        expected = stats.binomtest(7, 20).proportion_ci(confidence_level=0.95, method="wilson")
        assert proportion_ci(7, 20) == (
            pytest.approx(float(expected.low)),
            pytest.approx(float(expected.high)),
        )

    def test_impossible_counts_raise(self) -> None:
        with pytest.raises(StatisticsInputError):
            proportion_ci(6, 5)
        with pytest.raises(StatisticsInputError):
            proportion_ci(1, 0)


class TestAverageRank:
    def test_hand_computed_table(self) -> None:
        # Three scenarios; a is 1st, 1st, 2nd — b is the mirror.
        scores = average_rank_score({"a": [1, 1, 2], "b": [2, 2, 1]})
        assert scores == {"a": pytest.approx(4 / 3), "b": pytest.approx(5 / 3)}

    def test_lower_is_better(self) -> None:
        scores = average_rank_score({"winner": [1, 1], "loser": [2, 2]})
        assert scores["winner"] < scores["loser"]

    def test_ranking_over_different_scenario_counts_raises(self) -> None:
        """Skipping the hard scenarios must not improve a stack's score."""
        with pytest.raises(StatisticsInputError):
            average_rank_score({"a": [1, 1, 1], "b": [2]})

    def test_empty_input_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            average_rank_score({})
        with pytest.raises(StatisticsInputError):
            average_rank_score({"a": []})

    def test_zero_rank_raises(self) -> None:
        with pytest.raises(StatisticsInputError):
            average_rank_score({"a": [0, 1]})


class TestSeedAdequacy:
    def test_threshold_is_stated_not_hidden(self) -> None:
        assert ADEQUATE_SEED_COUNT == 30

    def test_below_threshold_is_inadequate(self) -> None:
        assert statistically_adequate(29) is False
        assert statistically_adequate(1) is False

    def test_at_or_above_threshold_is_adequate(self) -> None:
        assert statistically_adequate(30) is True
        assert statistically_adequate(100) is True
