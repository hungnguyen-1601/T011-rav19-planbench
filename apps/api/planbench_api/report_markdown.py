"""Markdown export of a benchmark report (F09).

The point of the export is not convenience. Everything the platform
computed — the fairness record, the observation classes, the medians and
their intervals, the paired tests, the split — lives behind a login, in a
page nobody can paste into a review thread. A report that cannot leave
the system cannot be checked by anyone outside it.

So the document is written to be read on its own, months later, by
somebody who does not have the database:

- **Provenance before results.** Which commit, which conditions checksum,
  which seeds, which protocol version, which calibration. A number whose
  conditions are missing is not evidence.
- **Nothing is inferred to fill a blank.** A missing observation class
  prints as unknown, an uncomputed interval prints as ``—``. The document
  never converts "we do not know" into a value.
- **Every caveat travels with the number it qualifies.** The seed count
  sits in the same row as the p-value; the warnings section is a summary,
  not the only place a limitation appears.

The generalization gap is the one number this document cannot compute
from its own report: a benchmark runs one scenario, so a single report is
entirely one split. When the caller supplies the cross-benchmark summary
it is rendered here, labelled as what it is — computed across other
accepted benchmarks, not from this run.
"""

from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

from planbench_api.leaderboard import _observation_classes
from planbench_api.repositories import StoredBenchmark
from planbench_benchmark import (
    BenchmarkReport,
    FairnessRecord,
    GeneralizationSummary,
    RunRecord,
    calibration_version,
    get_difficulty,
)
from planbench_benchmark.generalization import GAP_METRICS

REPO_ROOT = Path(__file__).resolve().parents[3]

DASH = "—"


@lru_cache(maxsize=1)
def git_sha() -> str:
    """Commit the API is running at, or ``"unknown"``.

    Deliberately the same shape of answer as the calibration script's:
    never guessed, and ``unknown`` when the tree is not a git checkout —
    a report from a container built off a tarball is still a valid
    report, it just cannot claim to be reproducible from a commit.

    Cached because it cannot change while the process lives, and shelling
    out per download would be a subprocess on a read path.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else "unknown"


def report_filename(stored: StoredBenchmark) -> str:
    """Download name: readable, and safe as a filename on any platform.

    The benchmark name is user-supplied, so it is reduced to a
    conservative slug rather than escaped. The id is appended and never
    dropped: two benchmarks may legitimately share a name, and the file
    on the reviewer's disk has to say which run it is.
    """
    slug = "".join(
        char if char.isalnum() or char in "-_" else "-" for char in stored.spec.name.strip()
    ).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug[:60].strip("-").lower()
    return f"benchmark-{slug}-{stored.id}.md" if slug else f"benchmark-{stored.id}.md"


# -- formatting -------------------------------------------------------


def _cell(value: object) -> str:
    """One table cell, safe inside a GitHub-flavoured Markdown table.

    A pipe in a benchmark name, an algorithm id or a failure reason would
    otherwise split the row into extra columns and shift every value one
    place left — a corrupted table that still looks like a table, which
    is worse than an obviously broken one. Newlines end the row entirely,
    so they collapse to a space.
    """
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    text = " ".join(text.split())
    return text or DASH


def _num(value: float | None, digits: int = 3, suffix: str = "") -> str:
    return DASH if value is None else f"{value:.{digits}f}{suffix}"


def _pct(value: float | None) -> str:
    return DASH if value is None else f"{value * 100:.1f}%"


def _interval(bounds: tuple[float, float] | None, digits: int = 3) -> str:
    return DASH if bounds is None else f"{bounds[0]:.{digits}f}–{bounds[1]:.{digits}f}"


def _bool(value: bool | None) -> str:
    return DASH if value is None else ("yes" if value else "no")


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


# -- sections ---------------------------------------------------------


def _provenance(stored: StoredBenchmark, report: BenchmarkReport) -> list[str]:
    fairness = report.fairness
    difficulty = get_difficulty(fairness.scenario_name)
    rows = [
        ["Benchmark ID", f"`{_cell(stored.id)}`"],
        ["Name", _cell(stored.spec.name)],
        ["State", _cell(stored.state.value)],
        ["Created by", _cell(stored.created_by)],
        ["Created at", _cell(stored.created_at)],
        ["Started at", _cell(stored.started_at)],
        ["Finished at", _cell(stored.finished_at)],
        ["Git SHA", f"`{_cell(git_sha())}`"],
        ["Benchmark spec version", _cell(stored.spec.spec_version)],
        ["Map", _cell(fairness.map_name)],
        ["Scenario", _cell(fairness.scenario_name)],
        ["Conditions checksum", f"`{_cell(fairness.conditions_checksum)}`"],
        ["Map checksum", f"`{_cell(fairness.map_checksum)}`"],
        ["Scenario checksum", f"`{_cell(fairness.scenario_checksum)}`"],
        ["Seeds", _cell(", ".join(str(seed) for seed in fairness.seeds))],
        ["Seed count", str(report.seed_count)],
        ["Protocol version (P05)", _cell(report.protocol_version)],
        ["Scenario split (P05)", _cell(report.scenario_split)],
    ]
    if difficulty is None:
        rows.append(
            [
                "Scenario difficulty (P03)",
                f"{DASH} (not calibrated; calibration in force: {_cell(calibration_version())})",
            ]
        )
    else:
        note = (
            " · **stale**: the scenario has changed since it was measured"
            if difficulty.stale
            else ""
        )
        adequacy = "" if difficulty.adequate else f" · provisional, {difficulty.seed_count} seeds"
        rows.append(
            [
                "Scenario difficulty (P03)",
                f"{difficulty.value:.3f} (CI95 {_interval(difficulty.ci95)}, band "
                f"{difficulty.band}){adequacy}{note}",
            ]
        )
        rows.append(["Difficulty calibration version", _cell(difficulty.calibration_version)])
        rows.append(["Difficulty baseline", f"`{_cell(difficulty.baseline_algorithm)}`"])
    return ["## Provenance", "", *_table(["Field", "Value"], rows), ""]


def _replanning(fairness: FairnessRecord) -> str:
    """How the replanning rule reads in the conditions table.

    Reports written before replanning existed carry the field defaults,
    which describe exactly what those runs did: nothing replanned.
    """
    if not fairness.replanning_enabled:
        return "disabled (a blocked robot stays blocked)"
    return f"enabled, up to {fairness.max_replans} replan(s) per episode"


def _conditions(report: BenchmarkReport) -> list[str]:
    fairness = report.fairness
    rows = [
        ["Timeout", _num(fairness.timeout_seconds, 1, " s")],
        ["Simulation dt", _num(fairness.simulation_dt, 3, " s")],
        ["Robot radius", _num(fairness.robot_radius, 3, " m")],
        ["Max linear velocity", _num(fairness.max_linear_velocity, 2, " m/s")],
        ["Max angular velocity", _num(fairness.max_angular_velocity, 2, " rad/s")],
        ["LiDAR rays", str(fairness.lidar_num_rays)],
        ["LiDAR max range", _num(fairness.lidar_max_range, 2, " m")],
        ["Replanning", _replanning(fairness)],
    ]
    return [
        "## Conditions",
        "",
        "Every algorithm below ran under exactly these conditions; that is",
        "what the conditions checksum attests. Results carrying a different",
        "checksum are not comparable with these.",
        "",
        *_table(["Field", "Value"], rows),
        "",
    ]


def _replanning_observation_note(report: BenchmarkReport) -> list[str]:
    """Why the global class below differs from the one in the registry.

    A reader who looks up ``astar+dwa`` in the algorithm registry finds
    ``full_static_map`` and finds this table saying something else. That
    discrepancy is the honest answer, not a bug, and a report that shows
    the upgraded label without explaining it invites the reader to
    assume the opposite.
    """
    if not report.fairness.replanning_enabled:
        return []
    return [
        "",
        "The global observation class here is **higher than the registry",
        "declares**, and deliberately so: replanning was enabled, and a",
        "replan is computed from the ground-truth positions of the dynamic",
        "obstacles at that instant — information no sensor on this robot",
        "produces. The registry declaration describes a stack that plans",
        "once on the static map; these runs are not that. The controller",
        "class is unchanged, because the controller still sees only LiDAR.",
    ]


def _algorithms(report: BenchmarkReport) -> list[str]:
    by_id = {aggregate.algorithm: aggregate for aggregate in report.aggregates}
    rows = []
    for spec in report.spec.algorithms:
        aggregate = by_id.get(spec.id)
        global_class, local_class, needs_path = (
            _observation_classes(aggregate) if aggregate else (None, None, None)
        )
        rows.append(
            [
                f"`{_cell(spec.id)}`",
                f"`{_cell(json.dumps(spec.config, sort_keys=True))}`"
                if spec.config
                else "defaults",
                _cell(global_class),
                _cell(local_class),
                _bool(needs_path),
            ]
        )
    return [
        "## Algorithms under test",
        "",
        "The observation classes (P02) are the snapshot taken when this",
        "benchmark ran. Stacks that were shown different things are not",
        "ranked against each other, and an unknown class is printed as such",
        "rather than assumed to match the others.",
        *_replanning_observation_note(report),
        "",
        *_table(
            [
                "Stack",
                "Config",
                "Global observation",
                "Local observation",
                "Needs global path",
            ],
            rows,
        ),
        "",
    ]


def _outcomes(report: BenchmarkReport) -> list[str]:
    rows = [
        [
            f"`{_cell(a.algorithm)}`",
            str(a.episodes),
            f"{_pct(a.success_rate)} (CI95 {_interval(a.ci95_success_rate)})",
            _pct(a.collision_rate),
            _pct(a.timeout_rate),
            _pct(a.stuck_rate),
            _pct(a.no_progress_rate),
            _pct(a.no_global_path_rate),
        ]
        for a in report.aggregates
    ]
    return [
        "## Outcomes",
        "",
        *_table(
            [
                "Stack",
                "Episodes",
                "Success",
                "Collision",
                "Timeout",
                "Stuck",
                "No progress",
                "No global path",
            ],
            rows,
        ),
        "",
    ]


def _metric_block(
    title: str,
    report: BenchmarkReport,
    median: str,
    iqr: str,
    ci: str,
    digits: int,
    unit: str = "",
) -> list[str]:
    rows = []
    for aggregate in report.aggregates:
        rows.append(
            [
                f"`{_cell(aggregate.algorithm)}`",
                _num(getattr(aggregate, median), digits, unit),
                _interval(getattr(aggregate, iqr), digits),
                _interval(getattr(aggregate, ci), digits),
            ]
        )
    return [f"### {title}", "", *_table(["Stack", "Median", "IQR", "CI95"], rows), ""]


def _distributions(report: BenchmarkReport) -> list[str]:
    lines = [
        "## Distributions (P04)",
        "",
        "Medians, not means: one episode that dithered until the timeout",
        "drags a mean past anything that actually happened. The IQR says how",
        "much the runs varied; the CI95 says how well this many seeds pin the",
        "median down. They answer different questions and neither replaces",
        "the other. Values marked `successful` use only episodes that reached",
        "the goal — travel time is undefined for a robot that never arrived,",
        "and averaging it in would reward fast failures. `—` means not",
        "computed, never zero.",
        "",
    ]
    lines += _metric_block(
        "Travel time (successful episodes)",
        report,
        "median_travel_time_successful",
        "iqr_travel_time_successful",
        "ci95_travel_time_successful",
        2,
        " s",
    )
    lines += _metric_block(
        "Path efficiency (successful episodes)",
        report,
        "median_path_efficiency_successful",
        "iqr_path_efficiency_successful",
        "ci95_path_efficiency_successful",
        3,
    )
    lines += _metric_block(
        "Smoothness (successful episodes)",
        report,
        "median_smoothness_successful",
        "iqr_smoothness_successful",
        "ci95_smoothness_successful",
        3,
    )
    rows = [
        [
            f"`{_cell(a.algorithm)}`",
            _num(a.worst_min_clearance, 3, " m"),
            _num(a.mean_min_clearance, 3, " m"),
            _num(_ms(a.mean_local_planning_latency), 2, " ms"),
            _num(_ms(a.max_local_planning_latency), 2, " ms"),
            _num(a.mean_global_planning_time, 4, " s"),
        ]
        for a in report.aggregates
    ]
    lines += [
        "### Clearance and latency",
        "",
        *_table(
            [
                "Stack",
                "Worst clearance",
                "Mean clearance",
                "Mean local latency",
                "Max local latency",
                "Mean global planning",
            ],
            rows,
        ),
        "",
    ]
    return lines


def _ms(seconds: float | None) -> float | None:
    return None if seconds is None else seconds * 1000.0


def _comparisons(report: BenchmarkReport) -> list[str]:
    lines = [
        "## Head-to-head tests (P04)",
        "",
        "Wilcoxon signed-rank, paired seed by seed: each pair is the same",
        "seed run by both stacks, so a seed that only one of them survived",
        "contributes to neither. Cliff's delta is the effect size — how large",
        "the difference is, not only how unlikely. The paired seed count is",
        'printed beside every p-value because "A was faster on the four seeds',
        'where both arrived" is a different claim from "A was faster".',
        "",
    ]
    if not report.comparisons:
        lines += [
            "No head-to-head test was run: a benchmark with a single algorithm",
            "has nothing to compare against.",
            "",
        ]
        return lines
    rows = []
    for comparison in report.comparisons:
        if comparison.p_value is None:
            verdict = "no test"
        elif comparison.significant and report.statistically_adequate:
            verdict = "difference found"
        else:
            verdict = "no conclusion"
        rows.append(
            [
                f"`{_cell(comparison.algorithm_a)}` vs `{_cell(comparison.algorithm_b)}`",
                _cell(comparison.metric),
                str(comparison.paired_seed_count),
                _num(comparison.statistic, 3),
                DASH if comparison.p_value is None else f"{comparison.p_value:.4f}",
                _num(comparison.effect_size, 3),
                verdict,
                _cell(comparison.warning),
            ]
        )
    lines += _table(
        [
            "Pair",
            "Metric",
            "Paired seeds",
            "Statistic",
            "p-value",
            "Effect size",
            "Verdict",
            "Warning",
        ],
        rows,
    )
    lines += [
        "",
        "In the benchmark set and conditions recorded above, the rows marked",
        '"difference found" showed a difference at the chosen test level. That',
        "is not a claim that one stack is better in general.",
        "",
    ]
    return lines


def _generalization(report: BenchmarkReport, summary: GeneralizationSummary | None) -> list[str]:
    lines = [
        "## Generalization gap (P05)",
        "",
        "This benchmark ran one scenario, so it is entirely one split and has",
        "nothing of its own to subtract. The gap below is computed *across*",
        "accepted benchmarks and is reproduced here for context; it is not a",
        "result of this run.",
        "",
    ]
    if report.generalization_gap:
        lines += _table(
            ["Metric", "Gap recorded on this report"],
            [
                [_cell(name), _num(value, 4)]
                for name, value in sorted(report.generalization_gap.items())
            ],
        )
        lines.append("")
    algorithms = {spec.id for spec in report.spec.algorithms}
    entries = (
        [entry for entry in summary.entries if entry.algorithm in algorithms] if summary else []
    )
    if not entries:
        lines += [
            "No cross-benchmark gap is available for these stacks: it needs",
            "accepted results on both a dev and a held-out scenario. A missing",
            "side means the gap is not computable, which is not the same as a",
            "gap of zero.",
            "",
        ]
        return lines
    rows = []
    for entry in entries:
        for metric in GAP_METRICS:
            gap = (entry.gap or {}).get(metric.name)
            rows.append(
                [
                    f"`{_cell(entry.algorithm)}`",
                    _cell(metric.name),
                    _num((entry.dev.metrics.get(metric.name) if entry.dev else None), 4),
                    _num((entry.holdout.metrics.get(metric.name) if entry.holdout else None), 4),
                    _num(gap, 4),
                    "higher is better" if metric.higher_is_better else "lower is better",
                ]
            )
    lines += _table(
        ["Stack", "Metric", "Dev", "Held-out", "Gap (dev − held-out)", "Direction"], rows
    )
    lines.append("")
    for entry in entries:
        for warning in entry.warnings:
            lines.append(f"- `{_cell(entry.algorithm)}`: {_cell(warning)}")
    if summary and summary.warnings:
        lines.extend(f"- {_cell(warning)}" for warning in summary.warnings)
    lines.append("")
    return lines


def _runs(report: BenchmarkReport) -> list[str]:
    # The replan column earns its width only when replanning was on. With
    # it off the column is a wall of zeroes that says the same thing the
    # conditions table already said once.
    show_replans = report.fairness.replanning_enabled
    rows = [
        [
            f"`{_cell(run.algorithm)}`",
            str(run.seed),
            _cell(run.status.value if hasattr(run.status, "value") else run.status),
            _num(run.metrics.travel_time, 2, " s"),
            _num(run.metrics.trajectory_length, 2, " m"),
            _num(run.metrics.path_efficiency, 3),
            _num(run.metrics.min_clearance, 3, " m"),
            DASH if run.metrics.near_miss_count is None else str(run.metrics.near_miss_count),
            DASH if run.metrics.stop_and_go_count is None else str(run.metrics.stop_and_go_count),
            *(
                [DASH if run.metrics.replan_count is None else str(run.metrics.replan_count)]
                if show_replans
                else []
            ),
            _cell(run.reason),
        ]
        for run in _sorted_runs(report.runs)
    ]
    return [
        "## Runs",
        "",
        *_table(
            [
                "Stack",
                "Seed",
                "Status",
                "Travel time",
                "Path length",
                "Efficiency",
                "Min clearance",
                "Near misses",
                "Stop-and-go",
                *(["Replans"] if show_replans else []),
                "Reason",
            ],
            rows,
        ),
        "",
        *_metric_thresholds(report),
    ]


def _metric_thresholds(report: BenchmarkReport) -> list[str]:
    """State the thresholds behind the counts — a count without its
    threshold is a number nobody can reproduce or dispute."""
    configs = {
        run.metrics.metric_config.version: run.metrics.metric_config
        for run in report.runs
        if run.metrics.metric_config is not None
    }
    if not configs:
        return [
            "Near-miss and stop-and-go counts were not computed for this report "
            "(recorded before metric config v1).",
            "",
        ]
    lines = []
    for config in configs.values():
        lines.append(
            f"Metric thresholds (config v{_cell(config.version)}): a near miss is a "
            f"trajectory point with clearance below "
            f"{_num(config.near_miss_clearance_threshold, 2)} m (collisions are not "
            f"double-counted); a stop-and-go is a drop below "
            f"{_num(config.stop_speed_threshold, 2)} m/s followed by a recovery above "
            f"{_num(config.resume_speed_threshold, 2)} m/s, after the robot first moved."
        )
    lines.append("")
    return lines


def _sorted_runs(runs: tuple[RunRecord, ...]) -> list[RunRecord]:
    return sorted(runs, key=lambda run: (run.algorithm, run.seed))


def _limitations(stored: StoredBenchmark, report: BenchmarkReport) -> list[str]:
    warnings: list[str] = []
    if not report.statistically_adequate:
        warnings.append(
            f"Only {report.seed_count} seed(s). Below 30 the intervals are wide and a "
            "significant p-value is a reason to look further, not a result. Every number "
            "above inherits this caveat."
        )
    if report.scenario_split == "unassigned":
        warnings.append(
            "The scenario was not classified as dev or held-out when this ran, so these "
            "results support no claim about generalization in either direction."
        )
    if report.scenario_split == "holdout":
        warnings.append(
            "This is a held-out scenario. Every look at held-out results erodes what "
            "makes them held out; this run is part of that record."
        )
    difficulty = get_difficulty(report.fairness.scenario_name)
    if difficulty is None:
        warnings.append(
            "The scenario has no measured difficulty, so there is no way to tell whether "
            "a high success rate here means a capable stack or an easy scenario."
        )
    elif difficulty.stale:
        warnings.append(
            "The scenario has been edited since its difficulty was measured; the "
            "difficulty above describes an older version of it."
        )
    elif not difficulty.adequate:
        warnings.append(
            f"The difficulty above was measured over {difficulty.seed_count} seed(s) and is "
            "provisional rather than a calibrated scale."
        )
    unknown = [
        aggregate.algorithm
        for aggregate in report.aggregates
        if _observation_classes(aggregate)[1] is None
    ]
    if unknown:
        warnings.append(
            "No observation class is recorded for "
            + ", ".join(f"`{_cell(name)}`" for name in unknown)
            + ". What those stacks were shown is unknown, so they cannot be ranked "
            "against the others on the information-parity argument (P02)."
        )
    if stored.state.value != "accepted":
        warnings.append(
            f"This benchmark is in state `{_cell(stored.state.value)}`. Only accepted "
            "results reach the leaderboard; these numbers have not passed that gate."
        )
    for comparison in report.comparisons:
        if comparison.warning:
            warnings.append(
                f"`{_cell(comparison.algorithm_a)}` vs `{_cell(comparison.algorithm_b)}` on "
                f"{_cell(comparison.metric)}: {_cell(comparison.warning)}"
            )
    lines = ["## Known limitations", ""]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append(
            "- Nothing specific to this run. The platform-wide limitations still "
            "apply — see `docs/KNOWN_LIMITATIONS.md`."
        )
    lines.append("")
    return lines


def render_report_markdown(
    stored: StoredBenchmark,
    *,
    generalization: GeneralizationSummary | None = None,
) -> str:
    """The whole report as one Markdown document.

    Raises ``ValueError`` when the benchmark has no report: an export of a
    run that has not happened would be a document full of blanks that
    reads like a result.
    """
    report = stored.report
    if report is None:
        raise ValueError("benchmark has no report yet")
    lines: list[str] = [
        f"# Benchmark report — {_cell(stored.spec.name)}",
        "",
    ]
    if stored.spec.description:
        lines += [_cell(stored.spec.description), ""]
    lines += _provenance(stored, report)
    lines += _conditions(report)
    lines += _algorithms(report)
    lines += _outcomes(report)
    lines += _distributions(report)
    lines += _comparisons(report)
    lines += _generalization(report, generalization)
    lines += _runs(report)
    lines += _limitations(stored, report)
    return "\n".join(lines).rstrip() + "\n"
