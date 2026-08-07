"""Unit tests for the P04 statistics module — hand-picked inputs whose
answer is known in advance, so a broken implementation cannot pass by
accident."""

from __future__ import annotations

import pytest

from planbench_metrics.statistics import (
    average_rank,
    bootstrap_ci,
    median_iqr,
    wilcoxon_compare,
)


class TestMedianIqr:
    def test_odd_count(self) -> None:
        median, q1, q3 = median_iqr([1, 2, 3, 4, 5])
        assert median == 3
        assert q1 == 2
        assert q3 == 4

    def test_single_value(self) -> None:
        median, q1, q3 = median_iqr([7.0])
        assert median == q1 == q3 == 7.0

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one value"):
            median_iqr([])

    def test_order_does_not_matter(self) -> None:
        assert median_iqr([5, 1, 3, 2, 4]) == median_iqr([1, 2, 3, 4, 5])


class TestBootstrapCi:
    def test_reproducible_with_fixed_seed(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]  # skewed, on purpose
        first = bootstrap_ci(values, n_resamples=200, seed=42)
        second = bootstrap_ci(values, n_resamples=200, seed=42)
        assert first == second

    def test_interval_contains_the_sample_mean(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        low, high = bootstrap_ci(values, n_resamples=500, seed=0)
        assert low <= 3.0 <= high

    def test_single_value_returns_a_degenerate_interval(self) -> None:
        assert bootstrap_ci([5.0]) == (5.0, 5.0)

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one value"):
            bootstrap_ci([])

    def test_wider_data_gives_a_wider_interval(self) -> None:
        tight = bootstrap_ci([1.0, 1.1, 0.9, 1.0, 1.05], n_resamples=500, seed=1)
        wide = bootstrap_ci([1.0, 50.0, -20.0, 30.0, 5.0], n_resamples=500, seed=1)
        assert (wide[1] - wide[0]) > (tight[1] - tight[0])


class TestWilcoxonCompare:
    def test_identical_samples_are_not_significant(self) -> None:
        result = wilcoxon_compare([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert result.p_value == 1.0
        assert result.effect_size == 0.0
        assert result.significant is False

    def test_no_warnings_on_a_fully_tied_pair(self, recwarn) -> None:
        wilcoxon_compare([0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        assert not recwarn.list

    def test_a_consistent_difference_is_significant(self) -> None:
        a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        b = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]  # b is a+1 every time
        result = wilcoxon_compare(a, b)
        assert result.significant is True
        assert result.p_value < 0.05
        # a is consistently smaller, so a-vs-b effect size is negative
        # (see the sign-convention note in wilcoxon_compare's docstring).
        assert result.effect_size < 0

    def test_reversing_the_arguments_flips_the_sign(self) -> None:
        a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        b = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        forward = wilcoxon_compare(a, b)
        backward = wilcoxon_compare(b, a)
        assert forward.effect_size == pytest.approx(-backward.effect_size)

    def test_mismatched_lengths_rejected(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            wilcoxon_compare([1.0, 2.0], [1.0])

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one pair"):
            wilcoxon_compare([], [])

    def test_n_pairs_reported(self) -> None:
        result = wilcoxon_compare([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
        assert result.n_pairs == 3


class TestAverageRank:
    def test_single_group_ranks_by_score(self) -> None:
        ranks = average_rank([{"a": 0.9, "b": 0.5, "c": 0.7}])
        assert ranks == {"a": 1.0, "c": 2.0, "b": 3.0}

    def test_averages_across_groups(self) -> None:
        # a wins group 1, loses group 2; b the opposite. Both average 1.5.
        ranks = average_rank([{"a": 0.9, "b": 0.5}, {"a": 0.4, "b": 0.8}])
        assert ranks == {"a": 1.5, "b": 1.5}

    def test_missing_from_a_group_does_not_count_against_it(self) -> None:
        """An algorithm not run on a scenario has no opinion recorded
        for that scenario — its average is over the groups it actually
        appeared in, not penalised for absence."""
        ranks = average_rank([{"a": 0.9, "b": 0.5}, {"a": 0.9}])
        assert ranks["a"] == 1.0  # won both groups it was in
        assert ranks["b"] == 2.0  # only appeared once, came second

    def test_empty_groups_are_skipped(self) -> None:
        assert average_rank([{}, {"a": 0.5}]) == {"a": 1.0}

    def test_no_groups_at_all(self) -> None:
        assert average_rank([]) == {}
