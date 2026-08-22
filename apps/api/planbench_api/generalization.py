"""API adapter for the dev/held-out generalization gap (P05).

The gap itself is computed in ``planbench_benchmark.generalization``,
which knows nothing about stored benchmarks. This module supplies the two
things only the API has: which reports are allowed to count, and the
identity and timing of each held-out run for the audit trail.

Acceptance filtering mirrors the leaderboard: by default only ACCEPTED
benchmarks contribute, because a generalization claim built from
unreviewed runs is exactly the claim nobody checked.
"""

from __future__ import annotations

from collections.abc import Sequence

from planbench_api.approval import BenchmarkState
from planbench_api.repositories import StoredBenchmark
from planbench_benchmark import BenchmarkReport, GeneralizationSummary, HoldoutUse
from planbench_benchmark.generalization import build_generalization


def _holdout_use(stored: StoredBenchmark, report: BenchmarkReport) -> HoldoutUse:
    return HoldoutUse(
        benchmark_id=stored.id,
        benchmark_name=stored.spec.name,
        scenario_name=report.fairness.scenario_name,
        algorithms=tuple(algorithm.id for algorithm in report.spec.algorithms),
        seed_count=report.seed_count,
        finished_at=stored.finished_at,
    )


def build_generalization_summary(
    benchmarks: Sequence[StoredBenchmark],
    *,
    accepted_only: bool = True,
    algorithm: str | None = None,
) -> GeneralizationSummary:
    """Gap across stored benchmarks, with a held-out usage audit trail.

    ``algorithm`` narrows the entries but never the audit: a held-out run
    happened whether or not the reader is currently looking at the stack
    that made it happen.
    """
    reports: list[BenchmarkReport] = []
    usage: list[HoldoutUse] = []
    for stored in benchmarks:
        report = stored.report
        if report is None:
            continue
        if accepted_only and stored.state is not BenchmarkState.ACCEPTED:
            continue
        reports.append(report)
        if report.scenario_split == "holdout":
            usage.append(_holdout_use(stored, report))

    summary = build_generalization(reports, holdout_usage=usage)
    if algorithm is None:
        return summary
    return summary.model_copy(
        update={"entries": tuple(e for e in summary.entries if e.algorithm == algorithm)}
    )
