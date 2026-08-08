"""Generalization gap: dev results against held-out results (P05).

A benchmark runs one scenario, so a single report is entirely one split
and has nothing to compare against. The gap therefore lives here, across
reports: group each algorithm's reports by the split each one *recorded
when it ran*, summarise both sides, and subtract.

Three rules the numbers depend on:

- **Only snapshots count.** The split comes from the report, never from
  today's protocol file. Re-classifying a scenario changes what future
  benchmarks are, not what past ones were.
- **Unassigned is excluded, not folded into dev.** A scenario nobody has
  classified supports no claim about generalization in either direction.
- **A gap without both sides is None.** Not zero, not "no gap".

Scenarios are weighted equally: each side averages per scenario first and
then over scenarios, so running ``doorway`` ten times and ``open_space``
once does not make the dev side mostly ``doorway``. The scenario names
behind every number travel with it, because a gap between three dev
scenarios and one holdout scenario is a different claim from a gap
between three and three, and the reader is the one who has to discount it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from statistics import fmean

from pydantic import BaseModel, ConfigDict

from planbench_benchmark.scenario_protocol import ScenarioSplit
from planbench_benchmark.spec import AlgorithmAggregate, BenchmarkReport


class GapMetric(BaseModel):
    """One metric the gap is computed on, and how to read its sign."""

    model_config = ConfigDict(frozen=True)

    name: str
    #: True when a larger value is a better result. The gap is always
    #: ``dev - holdout``; whether that being positive is bad depends on
    #: this flag, and a UI that ignores it will colour half the table
    #: backwards.
    higher_is_better: bool


#: Metrics compared across splits. Success rate is the headline; the two
#: medians describe the runs that did arrive. Means are deliberately not
#: used (P04) — a single dithering episode would move the gap more than
#: any real difference in behaviour.
GAP_METRICS: tuple[GapMetric, ...] = (
    GapMetric(name="success_rate", higher_is_better=True),
    GapMetric(name="median_travel_time_successful", higher_is_better=False),
    GapMetric(name="median_path_efficiency_successful", higher_is_better=True),
)

_EXTRACTORS: dict[str, Callable[[AlgorithmAggregate], float | None]] = {
    "success_rate": lambda a: a.success_rate,
    "median_travel_time_successful": lambda a: a.median_travel_time_successful,
    "median_path_efficiency_successful": lambda a: a.median_path_efficiency_successful,
}

#: Splits that can appear on either side of a gap. ``unassigned`` cannot.
COMPARABLE_SPLITS: tuple[ScenarioSplit, ...] = ("dev", "holdout")


class SplitSummary(BaseModel):
    """One algorithm's results on one split, summarised over scenarios."""

    model_config = ConfigDict(frozen=True)

    split: ScenarioSplit
    #: Which scenarios contributed, sorted. The gap means little without
    #: them: two algorithms compared on different holdout scenarios were
    #: not asked the same question.
    scenarios: tuple[str, ...]
    #: How many reports fed this side (a scenario may have been run more
    #: than once; repeats are averaged before the scenarios are).
    report_count: int
    episodes: int
    #: Metric name -> value, averaged over scenarios. A metric is absent
    #: when no scenario on this side produced it, which is normal: a
    #: stack that never reached the goal has no median travel time.
    metrics: dict[str, float]
    #: Scenarios that contributed to each metric. Not always all of
    #: ``scenarios`` — see above.
    metric_scenario_counts: dict[str, int]
    #: True when every contributing report had enough seeds (P04). False
    #: does not invalidate the gap; it means the gap inherits the same
    #: caveat the underlying reports carry.
    statistically_adequate: bool


class GeneralizationEntry(BaseModel):
    """One algorithm's dev-versus-holdout standing."""

    model_config = ConfigDict(frozen=True)

    algorithm: str
    dev: SplitSummary | None = None
    holdout: SplitSummary | None = None
    #: ``dev - holdout`` per metric, only for metrics present on both
    #: sides. None when either side is missing entirely. Read the sign
    #: against :data:`GAP_METRICS`: for success rate a positive gap means
    #: the stack did worse on held-out scenarios; for travel time a
    #: positive gap means it was *faster* on dev, which is the same story
    #: with the opposite sign.
    gap: dict[str, float] | None = None
    #: Everything that should make the reader hesitate before quoting the
    #: gap: a missing side, lopsided scenario coverage, thin seed counts.
    warnings: tuple[str, ...] = ()


class HoldoutUse(BaseModel):
    """A record that held-out scenarios were looked at.

    A held-out set stops being held out once it has been consulted often
    enough to tune against, and that erosion is invisible unless it is
    written down. This is the audit trail: it does not block anything,
    it just makes "we only checked once" a checkable claim.
    """

    model_config = ConfigDict(frozen=True)

    benchmark_name: str
    scenario_name: str
    algorithms: tuple[str, ...]
    seed_count: int
    #: Populated by callers that know it (the API); the benchmark package
    #: has no notion of stored benchmarks or time.
    benchmark_id: str | None = None
    finished_at: str | None = None


class GeneralizationSummary(BaseModel):
    """Dev-versus-holdout for every algorithm seen in the given reports."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[GeneralizationEntry, ...] = ()
    metrics: tuple[GapMetric, ...] = GAP_METRICS
    #: Protocol versions the contributing reports ran under. More than
    #: one means the split definition changed mid-flight, and the two
    #: sides may not be answering the same question.
    protocol_versions: tuple[str, ...] = ()
    dev_scenarios: tuple[str, ...] = ()
    holdout_scenarios: tuple[str, ...] = ()
    #: Reports left out because their scenario is unassigned. Reported
    #: rather than dropped quietly: it is usually the explanation for an
    #: empty answer.
    unassigned_report_count: int = 0
    holdout_usage: tuple[HoldoutUse, ...] = ()
    warnings: tuple[str, ...] = ()


def _mean_over_scenarios(
    collected: dict[str, dict[str, list[float]]],
) -> tuple[dict[str, float], dict[str, int]]:
    """Average within each scenario, then across scenarios.

    Two stages, not one, so a scenario that happens to have been run ten
    times does not outvote the other nine scenarios on the same side.
    """
    values: dict[str, float] = {}
    counts: dict[str, int] = {}
    for metric in GAP_METRICS:
        scenario_values = [fmean(samples) for samples in collected[metric.name].values()]
        if scenario_values:
            values[metric.name] = fmean(scenario_values)
            counts[metric.name] = len(scenario_values)
    return values, counts


def _summarise(
    split: ScenarioSplit, reports: Sequence[tuple[BenchmarkReport, AlgorithmAggregate]]
) -> SplitSummary:
    # metric -> scenario -> values from each report of that scenario.
    collected: dict[str, dict[str, list[float]]] = {metric.name: {} for metric in GAP_METRICS}
    scenarios: set[str] = set()
    episodes = 0
    adequate = True
    for report, aggregate in reports:
        scenario = report.fairness.scenario_name
        scenarios.add(scenario)
        episodes += aggregate.episodes
        adequate = adequate and report.statistically_adequate
        for metric in GAP_METRICS:
            value = _EXTRACTORS[metric.name](aggregate)
            if value is not None:
                collected[metric.name].setdefault(scenario, []).append(value)
    values, counts = _mean_over_scenarios(collected)
    return SplitSummary(
        split=split,
        scenarios=tuple(sorted(scenarios)),
        report_count=len(reports),
        episodes=episodes,
        metrics=values,
        metric_scenario_counts=counts,
        statistically_adequate=adequate,
    )


def _entry_warnings(dev: SplitSummary | None, holdout: SplitSummary | None) -> tuple[str, ...]:
    warnings: list[str] = []
    if dev is None:
        warnings.append("no results on dev scenarios; nothing to compare the held-out runs against")
    if holdout is None:
        warnings.append("no results on held-out scenarios; generalization is untested")
    if dev is None or holdout is None:
        return tuple(warnings)
    if len(dev.scenarios) != len(holdout.scenarios):
        warnings.append(
            f"uneven coverage: {len(dev.scenarios)} dev scenario(s) against "
            f"{len(holdout.scenarios)} held-out scenario(s); the two averages "
            "are over different amounts of evidence"
        )
    for metric in GAP_METRICS:
        in_dev = metric.name in dev.metrics
        in_holdout = metric.name in holdout.metrics
        if in_dev != in_holdout:
            missing = "held-out" if in_dev else "dev"
            warnings.append(
                f"{metric.name} has no value on the {missing} side, so no gap was computed for it"
            )
    if not dev.statistically_adequate or not holdout.statistically_adequate:
        warnings.append(
            "at least one contributing benchmark ran too few seeds to support "
            "a conclusion; the gap inherits that limit"
        )
    return tuple(warnings)


def build_generalization(
    reports: Iterable[BenchmarkReport],
    *,
    holdout_usage: Sequence[HoldoutUse] | None = None,
) -> GeneralizationSummary:
    """Dev-versus-holdout gap per algorithm, from stored reports.

    ``holdout_usage`` lets a caller that knows benchmark identities and
    timestamps supply a richer audit trail; without it the records are
    derived from the reports themselves.
    """
    reports = list(reports)
    by_algorithm: dict[str, dict[str, list[tuple[BenchmarkReport, AlgorithmAggregate]]]] = {}
    protocol_versions: set[str] = set()
    dev_scenarios: set[str] = set()
    holdout_scenarios: set[str] = set()
    unassigned = 0
    derived_usage: list[HoldoutUse] = []

    for report in reports:
        split = report.scenario_split
        if split not in COMPARABLE_SPLITS:
            unassigned += 1
            continue
        if report.protocol_version:
            protocol_versions.add(report.protocol_version)
        scenario = report.fairness.scenario_name
        if split == "dev":
            dev_scenarios.add(scenario)
        else:
            holdout_scenarios.add(scenario)
            derived_usage.append(
                HoldoutUse(
                    benchmark_name=report.spec.name,
                    scenario_name=scenario,
                    algorithms=tuple(algorithm.id for algorithm in report.spec.algorithms),
                    seed_count=report.seed_count,
                )
            )
        for aggregate in report.aggregates:
            by_algorithm.setdefault(aggregate.algorithm, {}).setdefault(split, []).append(
                (report, aggregate)
            )

    entries: list[GeneralizationEntry] = []
    for algorithm in sorted(by_algorithm):
        sides = by_algorithm[algorithm]
        dev = _summarise("dev", sides["dev"]) if sides.get("dev") else None
        holdout = _summarise("holdout", sides["holdout"]) if sides.get("holdout") else None
        gap: dict[str, float] | None = None
        if dev is not None and holdout is not None:
            shared = {
                metric.name: dev.metrics[metric.name] - holdout.metrics[metric.name]
                for metric in GAP_METRICS
                if metric.name in dev.metrics and metric.name in holdout.metrics
            }
            gap = shared or None
        entries.append(
            GeneralizationEntry(
                algorithm=algorithm,
                dev=dev,
                holdout=holdout,
                gap=gap,
                warnings=_entry_warnings(dev, holdout),
            )
        )

    warnings: list[str] = []
    if len(protocol_versions) > 1:
        warnings.append(
            "results span protocol versions "
            f"{', '.join(sorted(protocol_versions))}; the dev/held-out split "
            "was not the same for all of them"
        )
    if unassigned:
        warnings.append(
            f"{unassigned} report(s) excluded: their scenario is not assigned "
            "to a split, so they support no generalization claim"
        )
    if len(derived_usage) > 1 or (holdout_usage and len(holdout_usage) > 1):
        warnings.append(
            "held-out scenarios have been run more than once; each look "
            "erodes how held-out they still are"
        )

    return GeneralizationSummary(
        entries=tuple(entries),
        protocol_versions=tuple(sorted(protocol_versions)),
        dev_scenarios=tuple(sorted(dev_scenarios)),
        holdout_scenarios=tuple(sorted(holdout_scenarios)),
        unassigned_report_count=unassigned,
        holdout_usage=tuple(holdout_usage) if holdout_usage is not None else tuple(derived_usage),
        warnings=tuple(warnings),
    )
