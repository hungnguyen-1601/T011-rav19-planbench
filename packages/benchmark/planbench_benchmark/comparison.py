"""Pairwise comparison of stacks, paired by seed (P04).

A benchmark runs every algorithm on the same seed list, which means the
comparison can be *paired*: seed 7 gave both stacks the same obstacle
motion, so the difference at seed 7 is a difference between algorithms
and not between episodes. Pairing is what makes a signed-rank test
appropriate here, and throwing it away by handing two loose lists to
SciPy in whatever order they happened to be stored would silently turn
a strong test into a meaningless one.

So the pairing is done here, where the seeds are, and it is done
explicitly: build seed -> value for each side, intersect, sort, and
report how many pairs actually survived. A seed where either stack
failed has no travel time to compare, so it drops out — and the count of
what dropped travels with the result, because "A was faster on the four
seeds where both arrived" is a very different claim from "A was faster".
"""

from __future__ import annotations

from collections.abc import Sequence

from planbench_benchmark.spec import AlgorithmAggregate, PairwiseComparison, RunRecord
from planbench_metrics.statistics import (
    StatisticsInputError,
    cliffs_delta,
    wilcoxon_compare,
)
from planbench_schemas.episode import EpisodeStatus

#: Default metric to compare. Travel time on successful episodes is the
#: number people quote, and it is undefined for a robot that never
#: arrived — which is why pairing has to drop seeds rather than
#: substitute a timeout value and reward fast failures.
DEFAULT_COMPARISON_METRIC = "travel_time"

#: A p-value below this is called significant. Stated as a constant so a
#: report can quote the threshold it used rather than implying there is
#: one obvious choice.
SIGNIFICANCE_LEVEL = 0.05

#: Fewer pairs than this and the test is not worth running: with two or
#: three seeds the smallest possible p-value is still large, so a "not
#: significant" verdict would say more about the sample size than about
#: the algorithms.
MIN_PAIRS_FOR_TEST = 5


def _metric_by_seed(runs: Sequence[RunRecord], algorithm: str, metric: str) -> dict[int, float]:
    """Successful episodes of one algorithm as ``seed -> metric value``.

    Only successful episodes: travel time and path efficiency have no
    meaning for a robot that stopped early, and including them would let
    a stack that fails quickly look fast.
    """
    values: dict[int, float] = {}
    for run in runs:
        if run.algorithm != algorithm or run.status is not EpisodeStatus.SUCCESS:
            continue
        value = getattr(run.metrics, metric, None)
        if value is None:
            continue
        values[run.seed] = float(value)
    return values


def _seeds_attempted(runs: Sequence[RunRecord], algorithm: str) -> set[int]:
    return {run.seed for run in runs if run.algorithm == algorithm}


def compare_pair(
    runs: Sequence[RunRecord],
    algorithm_a: str,
    algorithm_b: str,
    *,
    metric: str = DEFAULT_COMPARISON_METRIC,
    significance_level: float = SIGNIFICANCE_LEVEL,
) -> PairwiseComparison:
    """Compare two stacks on ``metric``, paired seed by seed."""
    attempted_a = _seeds_attempted(runs, algorithm_a)
    attempted_b = _seeds_attempted(runs, algorithm_b)
    values_a = _metric_by_seed(runs, algorithm_a, metric)
    values_b = _metric_by_seed(runs, algorithm_b, metric)

    paired_seeds = sorted(set(values_a) & set(values_b))
    notes: list[str] = []

    # A mismatched seed list means the two did not face the same
    # conditions at all — a fairness problem, not a sampling one.
    if attempted_a != attempted_b:
        notes.append(
            f"{algorithm_a} and {algorithm_b} did not run the same seeds "
            f"({len(attempted_a)} vs {len(attempted_b)}); the comparison is not paired "
            "across the whole benchmark"
        )

    attempted_together = len(attempted_a & attempted_b)
    dropped = attempted_together - len(paired_seeds)
    if dropped > 0:
        notes.append(
            f"{dropped} of {attempted_together} shared seeds contributed no pair because "
            f"at least one stack has no {metric} there (it did not reach the goal)"
        )

    if len(paired_seeds) < MIN_PAIRS_FOR_TEST:
        notes.append(
            f"only {len(paired_seeds)} paired seed(s); fewer than {MIN_PAIRS_FOR_TEST} "
            "cannot support a significance test, so none was run"
        )
        return PairwiseComparison(
            algorithm_a=algorithm_a,
            algorithm_b=algorithm_b,
            metric=metric,
            paired_seed_count=len(paired_seeds),
            warning="; ".join(notes) or None,
        )

    ordered_a = [values_a[seed] for seed in paired_seeds]
    ordered_b = [values_b[seed] for seed in paired_seeds]

    try:
        statistic, p_value = wilcoxon_compare(ordered_a, ordered_b)
        effect = cliffs_delta(ordered_a, ordered_b)
    except StatisticsInputError as exc:
        notes.append(f"no test: {exc}")
        return PairwiseComparison(
            algorithm_a=algorithm_a,
            algorithm_b=algorithm_b,
            metric=metric,
            paired_seed_count=len(paired_seeds),
            warning="; ".join(notes),
        )

    return PairwiseComparison(
        algorithm_a=algorithm_a,
        algorithm_b=algorithm_b,
        metric=metric,
        statistic=statistic,
        p_value=p_value,
        effect_size=effect,
        significant=p_value < significance_level,
        paired_seed_count=len(paired_seeds),
        warning="; ".join(notes) or None,
    )


def leader(aggregates: Sequence[AlgorithmAggregate]) -> str | None:
    """The stack every other one is compared against.

    Highest success rate, ties broken by algorithm id. The tie-break is
    not cosmetic: without it the comparison table would depend on dict
    ordering, and re-running the same benchmark could quietly swap which
    stack is the baseline.
    """
    if not aggregates:
        return None
    return min(aggregates, key=lambda a: (-a.success_rate, a.algorithm)).algorithm


def build_comparisons(
    runs: Sequence[RunRecord],
    aggregates: Sequence[AlgorithmAggregate],
    *,
    metric: str = DEFAULT_COMPARISON_METRIC,
) -> tuple[PairwiseComparison, ...]:
    """Compare the most successful stack against each of the others.

    Leader-against-the-rest rather than every pair: with two or three
    stacks the two are the same thing, and the shape of the result — a
    list of independent pairs — extends to full pairwise without any
    consumer changing. What it deliberately does not do is apply a
    multiple-comparison correction it has not been told the family of
    tests for; that decision belongs with whoever asks for full pairwise.
    """
    baseline = leader(aggregates)
    if baseline is None:
        return ()
    return tuple(
        compare_pair(runs, baseline, aggregate.algorithm, metric=metric)
        for aggregate in sorted(aggregates, key=lambda a: a.algorithm)
        if aggregate.algorithm != baseline
    )
