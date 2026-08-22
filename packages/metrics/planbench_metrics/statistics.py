"""Evaluation statistics (P04): medians, intervals, paired tests, effect size.

Why these and not means. A benchmark's per-seed numbers are skewed and
bounded below — one scenario where the robot dithers for the whole
timeout drags a mean far past anything that actually happened. The
median plus an interquartile range says what a typical run looked like
and how much the runs disagreed, which is the question a reader has.

Why SciPy and not our own arithmetic. A wrong Wilcoxon does not raise:
it returns a plausible p-value that is simply not the p-value. That
failure is invisible in review and invisible in production, and it would
be sitting under every conclusion this platform publishes. SciPy's
versions are checked by far more people than will ever read this file.

What this module refuses to do. Every function raises on input it cannot
honestly summarise — too few points, NaN, mismatched pairs — rather than
returning a number with a quiet caveat. Callers decide what to show when
there is not enough data; they are not handed a fabricated value that
looks like a result.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from math import isfinite

import numpy as np
from scipy import stats


class StatisticsInputError(ValueError):
    """Input that cannot be summarised honestly.

    One exception type rather than several: every case means the same
    thing to a caller — do not print a number here, say why not.
    """


def _clean(values: Sequence[float], *, name: str, minimum: int = 1) -> np.ndarray:
    """Validate and convert; reject anything that would poison a statistic."""
    array = np.asarray(list(values), dtype=float)
    if array.size < minimum:
        raise StatisticsInputError(f"{name} needs at least {minimum} value(s), got {array.size}")
    if not np.all(np.isfinite(array)):
        raise StatisticsInputError(f"{name} contains NaN or infinity")
    return array


def median_iqr(values: Sequence[float]) -> tuple[float, float, float]:
    """Return ``(median, q1, q3)`` using linear interpolation.

    Linear interpolation is NumPy's default and the convention most
    readers assume; stating it matters because with an even number of
    seeds the quartiles of a small sample differ noticeably between
    conventions, and a report that changes convention silently would
    show a different spread for the same runs.
    """
    array = _clean(values, name="median_iqr")
    q1, median, q3 = np.percentile(array, [25, 50, 75])
    return (float(median), float(q1), float(q3))


def bootstrap_ci(
    values: Sequence[float],
    *,
    statistic: Callable[[Sequence[float]], float] = np.median,
    n_resamples: int = 1000,
    level: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for ``statistic``.

    Percentile rather than BCa: BCa needs a jackknife that is unstable
    at the sample sizes a benchmark actually runs (often 30 seeds, and
    sometimes 5), and an interval that occasionally comes back as NaN is
    worse than a slightly conservative one that always means something.

    ``seed`` makes the interval reproducible: the same runs re-analysed
    must give the same interval, or two people reading one report will
    quote different numbers.

    A sample with no variation has no interval to estimate — every
    resample is identical — so the degenerate answer (the value itself,
    twice) is returned rather than letting SciPy warn and hand back NaN.
    """
    array = _clean(values, name="bootstrap_ci", minimum=2)
    if not 0.0 < level < 1.0:
        raise StatisticsInputError(f"confidence level must be in (0, 1), got {level}")
    if n_resamples < 1:
        raise StatisticsInputError(f"n_resamples must be positive, got {n_resamples}")

    if np.all(array == array[0]):
        point = float(statistic(array))
        return (point, point)

    result = stats.bootstrap(
        (array,),
        statistic,
        n_resamples=n_resamples,
        confidence_level=level,
        method="percentile",
        vectorized=False,
        rng=np.random.default_rng(seed),
    )
    low = float(result.confidence_interval.low)
    high = float(result.confidence_interval.high)
    if not (isfinite(low) and isfinite(high)):
        raise StatisticsInputError("bootstrap produced a non-finite interval")
    return (low, high)


def wilcoxon_compare(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test on paired samples: ``(statistic, p_value)``.

    Paired means element *i* of both sequences came from the same seed.
    This function cannot check that — it only sees numbers — so pairing
    is the caller's responsibility and is done in
    ``planbench_benchmark.comparison``, which has the seeds.

    Two samples that are identical everywhere have nothing to test: the
    signed-rank statistic is undefined and SciPy raises. That is not an
    error condition for a benchmark (two deterministic stacks can tie on
    every seed), so it is reported as "no difference": statistic 0, p 1.
    """
    left = _clean(a, name="wilcoxon a")
    right = _clean(b, name="wilcoxon b")
    if left.size != right.size:
        raise StatisticsInputError(
            f"wilcoxon needs paired samples of equal length, got {left.size} and {right.size}"
        )
    if np.all(left == right):
        return (0.0, 1.0)
    result = stats.wilcoxon(left, right)
    return (float(result.statistic), float(result.pvalue))


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Cliff's delta: how often a value from ``a`` exceeds one from ``b``.

    In ``[-1, 1]``. +1 means every ``a`` beats every ``b``, 0 means the
    two are interleaved, -1 the reverse.

    A p-value answers "could this be chance?" and nothing else — with
    enough seeds a difference far too small to care about becomes
    significant. This answers "how big?", which is the question anyone
    choosing a planner is actually asking. Non-parametric, so it does
    not assume the shape a p-value already declined to assume, and
    unpaired, so it stays meaningful when the two stacks succeeded on
    different subsets of seeds.
    """
    left = _clean(a, name="cliffs_delta a")
    right = _clean(b, name="cliffs_delta b")
    greater = int(np.sum(left[:, None] > right[None, :]))
    less = int(np.sum(left[:, None] < right[None, :]))
    return (greater - less) / (left.size * right.size)


def proportion_ci(successes: int, trials: int, *, level: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a success rate.

    Exact and deterministic, so it does not need a seed, and unlike the
    normal approximation it stays inside ``[0, 1]`` and stays sensible at
    0% and 100% — which is exactly where a benchmark's success rate
    tends to sit, and exactly where a naive interval would report
    "0.0 to 0.0" for five failures and imply certainty nobody has.
    """
    if trials < 1:
        raise StatisticsInputError(f"trials must be positive, got {trials}")
    if not 0 <= successes <= trials:
        raise StatisticsInputError(f"successes {successes} outside 0..{trials}")
    if not 0.0 < level < 1.0:
        raise StatisticsInputError(f"confidence level must be in (0, 1), got {level}")
    low, high = stats.binomtest(successes, trials).proportion_ci(
        confidence_level=level, method="wilson"
    )
    return (float(low), float(high))


def average_rank_score(per_algorithm_ranks: Mapping[str, Sequence[int]]) -> dict[str, float]:
    """Mean rank per algorithm across scenarios; lower is better.

    The input maps an algorithm to the rank it took in each scenario, in
    a consistent scenario order. Every algorithm must have been ranked in
    every scenario: averaging over different subsets would let a stack
    look good by having skipped the hard ones, which is the exact failure
    an aggregate score is supposed to prevent.
    """
    if not per_algorithm_ranks:
        raise StatisticsInputError("average_rank_score needs at least one algorithm")
    lengths = {len(ranks) for ranks in per_algorithm_ranks.values()}
    if len(lengths) != 1:
        raise StatisticsInputError(
            "every algorithm must be ranked in the same scenarios; got rank "
            f"counts {sorted(lengths)}"
        )
    if lengths == {0}:
        raise StatisticsInputError("average_rank_score needs at least one scenario")
    scores: dict[str, float] = {}
    for algorithm, ranks in per_algorithm_ranks.items():
        array = np.asarray(list(ranks), dtype=float)
        if np.any(array < 1):
            raise StatisticsInputError(f"ranks start at 1; {algorithm!r} has {ranks}")
        scores[algorithm] = float(array.mean())
    return scores


#: Below this many seeds a benchmark can still run, and its numbers are
#: still shown — but a paired test on a handful of episodes cannot
#: distinguish an algorithm from luck, so the report says so instead of
#: quietly presenting a p-value as if the sample supported it.
ADEQUATE_SEED_COUNT = 30


def statistically_adequate(seed_count: int) -> bool:
    """Whether ``seed_count`` supports a conclusion, not just a number."""
    return seed_count >= ADEQUATE_SEED_COUNT
