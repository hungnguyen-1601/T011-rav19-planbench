"""Statistical rigor for comparing planners (P04): median/IQR over mean,
bootstrap confidence intervals, paired significance testing, and a
rank-based way to combine results across scenarios whose raw metrics
are not directly comparable.

Every function here is pure — no I/O, no framework types — so a caller
supplies plain floats and gets plain floats back. That is also what
makes them cheap to unit-test with hand-picked inputs whose answer is
known in advance.

Why median/IQR instead of mean/std: robot metrics (travel time, path
length) are typically right-skewed — a few slow or stuck episodes pull
the mean up without being "typical". The median is not moved by a
single outlier; the interquartile range describes spread without
assuming a normal distribution.

Why bootstrap instead of a closed-form CI: resampling the data itself
needs no distributional assumption, which matters here because success
rate (a proportion) and travel time (skewed) do not share one.
"""

from __future__ import annotations

import random
import statistics as _stdlib_statistics
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict
from scipy import stats as _scipy_stats

DEFAULT_BOOTSTRAP_RESAMPLES = 1000
DEFAULT_CONFIDENCE = 0.95
#: Below this many paired seeds, scipy's exact Wilcoxon table is thin
#: enough that the p-value is not trustworthy — callers should treat the
#: result as informational only. Not enforced here (this module has no
#: opinion on what a caller does with a result); see
#: ``BenchmarkReport.statistically_adequate`` for where seed count is
#: surfaced to the user.
MIN_SEEDS_FOR_WILCOXON = 6


def median_iqr(values: Sequence[float]) -> tuple[float, float, float]:
    """(median, Q1, Q3) — Q1/Q3 via linear interpolation (numpy's default
    "linear" method), the same convention most stats software reports.

    Raises ValueError on an empty sequence: there is no median of
    nothing, and returning a sentinel would let a caller silently plot
    a zero that means "no data" as if it were a real value.
    """
    if not values:
        raise ValueError("median_iqr requires at least one value")
    ordered = sorted(values)
    median = _stdlib_statistics.median(ordered)
    q1 = _percentile(ordered, 25.0)
    q3 = _percentile(ordered, 75.0)
    return median, q1, q3


def _percentile(ordered: list[float], pct: float) -> float:
    """Linear-interpolation percentile of an already-sorted sequence."""
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def percentile(values: Sequence[float], pct: float) -> float:
    """Linear-interpolation percentile (numpy's default "linear" method)
    of ``values`` in any order — sorts internally.

    Public entry point for a caller with a single percentile to compute
    on unsorted data (e.g. p95 latency from a raw sample list); code
    inside this module that already has a sorted list and wants several
    percentiles from it uses the private ``_percentile`` instead, to
    avoid re-sorting per call.
    """
    if not values:
        raise ValueError("percentile requires at least one value")
    return _percentile(sorted(values), pct)


def bootstrap_ci(
    values: Sequence[float],
    *,
    n_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
) -> tuple[float, float]:
    """95% (or ``confidence``) confidence interval for the mean, by
    resampling ``values`` with replacement ``n_resamples`` times.

    ``seed`` is fixed by default so the same input always reproduces the
    same interval — a CI that changes on every call would undermine the
    reproducibility this whole protocol suite exists to provide.

    A single value has no spread to resample from; both bounds equal
    that value rather than raising, since "one data point" is a valid
    (if statistically thin) input a caller may still want to display.
    """
    if not values:
        raise ValueError("bootstrap_ci requires at least one value")
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(_stdlib_statistics.fmean(resample))
    means.sort()
    alpha = 1.0 - confidence
    lower = _percentile(means, 100.0 * (alpha / 2.0))
    upper = _percentile(means, 100.0 * (1.0 - alpha / 2.0))
    return lower, upper


class ComparisonResult(BaseModel):
    """One paired comparison between two algorithms on one metric."""

    model_config = ConfigDict(frozen=True)

    p_value: float
    #: Rank-biserial effect size r = Z / sqrt(N), in [-1, 1]. Magnitude
    #: alone does not imply practical importance — see the module
    #: docstring on why p-value and effect size are reported together.
    effect_size: float
    #: p < 0.05, the conventional (not sacred) threshold. Reported
    #: alongside the raw p-value so a caller can apply a stricter bar.
    significant: bool
    n_pairs: int


def wilcoxon_compare(a: Sequence[float], b: Sequence[float]) -> ComparisonResult:
    """Wilcoxon signed-rank test between two paired samples.

    Positive ``effect_size`` means ``a`` tends larger than ``b``;
    negative means the reverse — so for a higher-is-better metric,
    calling ``wilcoxon_compare(baseline, other)`` gives a positive
    effect size when the baseline wins.

    ``a`` and ``b`` must be the same length and paired by position (the
    caller's responsibility — in this codebase, that means same-index
    entries share a seed, since :func:`planbench_benchmark.runner.run_benchmark`
    runs every algorithm against the identical seed list).

    When every pair is tied (``a == b`` elementwise, or all differences
    are zero), there is no rank sum to compute a direction from —
    reported as p=1.0, effect_size=0.0 here, since "no evidence of a
    difference" is exactly what a fully-tied result means. Checked
    explicitly rather than left to scipy: depending on version, scipy
    either raises or returns statistic=0 with a division-by-zero warning
    for this case, and the latter would silently corrupt the effect-size
    z-approximation below if not caught first.
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples must be equal length, got {len(a)} vs {len(b)}")
    if len(a) == 0:
        raise ValueError("wilcoxon_compare requires at least one pair")
    n = len(a)
    if all(x == y for x, y in zip(a, b, strict=True)):
        return ComparisonResult(p_value=1.0, effect_size=0.0, significant=False, n_pairs=n)
    try:
        _statistic, p_value = _scipy_stats.wilcoxon(a, b)
    except ValueError:
        return ComparisonResult(p_value=1.0, effect_size=0.0, significant=False, n_pairs=n)

    # scipy's returned "statistic" is min(W+, W-) — order-invariant by
    # design, which is correct for its two-sided p-value but useless for
    # a signed effect size: swapping a and b would not change it. W+
    # (rank sum of the positive differences) is computed here instead,
    # because it *is* order-sensitive — swapping a and b turns every
    # positive difference negative and vice versa.
    diffs = [x - y for x, y in zip(a, b, strict=True) if x != y]
    ranks = _scipy_stats.rankdata([abs(d) for d in diffs])
    w_plus = sum(rank for diff, rank in zip(diffs, ranks, strict=True) if diff > 0)
    m = len(diffs)  # ties in a/b (d == 0) are dropped, same as scipy's default
    mean_w = m * (m + 1) / 4.0
    std_w = (m * (m + 1) * (2 * m + 1) / 24.0) ** 0.5
    z = (w_plus - mean_w) / std_w if std_w > 0 else 0.0
    effect_size = z / (m**0.5)
    return ComparisonResult(
        p_value=float(p_value),
        effect_size=float(effect_size),
        significant=p_value < 0.05,
        n_pairs=n,
    )


def average_rank(entries_by_group: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """Average rank of each algorithm across groups (scenarios) whose raw
    scores are not directly comparable, but whose *within-group ranking*
    is.

    Each element of ``entries_by_group`` is one group: algorithm id ->
    score, higher-is-better. An algorithm's rank in a group is 1-based
    (1 = best); its average rank is the mean of its ranks over every
    group it appears in. An algorithm missing from a group does not
    count against it there — a planner untested on a scenario has no
    opinion on that scenario, which is different from having lost on it.
    """
    ranks: dict[str, list[int]] = {}
    for group in entries_by_group:
        if not group:
            continue
        ordered = sorted(group.items(), key=lambda item: item[1], reverse=True)
        for position, (algorithm, _score) in enumerate(ordered, start=1):
            ranks.setdefault(algorithm, []).append(position)
    return {algorithm: _stdlib_statistics.fmean(positions) for algorithm, positions in ranks.items()}


__all__ = [
    "DEFAULT_BOOTSTRAP_RESAMPLES",
    "DEFAULT_CONFIDENCE",
    "MIN_SEEDS_FOR_WILCOXON",
    "ComparisonResult",
    "average_rank",
    "bootstrap_ci",
    "median_iqr",
    "percentile",
    "wilcoxon_compare",
]
