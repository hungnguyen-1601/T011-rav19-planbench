"""Render a BenchmarkReport as a downloadable Markdown document.

Plain f-strings, no templating engine — the repo has no Jinja
dependency and one document shape does not justify adding one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from planbench_benchmark import AlgorithmAggregate, BenchmarkReport, PairwiseComparison, RunRecord


def render_report_markdown(benchmark_name: str, benchmark_id: str, report: BenchmarkReport) -> str:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    parts = [
        f"# {benchmark_name}",
        "",
        f"- Benchmark id: `{benchmark_id}`",
        f"- Generated: {generated_at}",
        "",
        _fairness_section(report),
        "",
        _adequacy_section(report),
        "",
        _aggregates_section(report.aggregates),
        "",
        _comparisons_section(report.comparisons),
        "",
        _runs_section(report.runs),
        "",
    ]
    return "\n".join(parts)


def _fairness_section(report: BenchmarkReport) -> str:
    f = report.fairness
    rows = [
        ("Map", f.map_name),
        ("Scenario", f.scenario_name),
        ("Seeds", ", ".join(str(s) for s in f.seeds)),
        ("Timeout (s)", f"{f.timeout_seconds}"),
        ("Simulation dt (s)", f"{f.simulation_dt}"),
        ("Robot radius (m)", f"{f.robot_radius}"),
        ("Max linear velocity (m/s)", f"{f.max_linear_velocity}"),
        ("Max angular velocity (rad/s)", f"{f.max_angular_velocity}"),
        ("LiDAR rays / max range (m)", f"{f.lidar_num_rays} / {f.lidar_max_range}"),
        ("Conditions checksum", f"`{f.conditions_checksum}`"),
    ]
    lines = ["## Fairness / conditions", "", "| Field | Value |", "| --- | --- |"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(lines)


def _adequacy_section(report: BenchmarkReport) -> str:
    if report.statistically_adequate:
        return f"**Seed count:** {report.seed_count} (statistically adequate, spec 8.6a: ≥30)."
    return (
        f"**Seed count:** {report.seed_count} — **not statistically adequate** "
        "(spec 8.6a recommends ≥30 seeds per algorithm/scenario pair). "
        "Results below are still real, just narrower evidence than a full run."
    )


def _fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _fmt_pair(value: tuple[float, float] | None, digits: int = 3) -> str:
    return "—" if value is None else f"[{value[0]:.{digits}f}, {value[1]:.{digits}f}]"


def _aggregates_section(aggregates: tuple[AlgorithmAggregate, ...]) -> str:
    header = (
        "| Algorithm | Episodes | Success rate (95% CI) | Collision | Timeout | "
        "Travel time (median [IQR]) | Path efficiency (median [IQR]) | "
        "Smoothness/m | Min clearance | Local planning latency |"
    )
    separator = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    lines = ["## Aggregates by algorithm", "", header, separator]
    for a in aggregates:
        success_rate = f"{a.success_rate:.3f} ({_fmt_pair(a.success_rate_ci95)})"
        travel_time = f"{_fmt(a.median_travel_time_successful)} {_fmt_pair(a.iqr_travel_time_successful)}"
        path_efficiency = (
            f"{_fmt(a.median_path_efficiency_successful)} "
            f"{_fmt_pair(a.iqr_path_efficiency_successful)}"
        )
        lines.append(
            f"| {a.algorithm} | {a.episodes} | {success_rate} | "
            f"{a.collision_rate:.3f} | {a.timeout_rate:.3f} | "
            f"{travel_time} | {path_efficiency} | "
            f"{_fmt(a.mean_smoothness_per_metre_successful)} | "
            f"{_fmt(a.mean_min_clearance)} | {_fmt(a.mean_local_planning_latency)} |"
        )
    return "\n".join(lines)


def _comparisons_section(comparisons: tuple[PairwiseComparison, ...]) -> str:
    if not comparisons:
        return (
            "## Pairwise comparisons\n\n"
            "None — needs at least two algorithms and two seeds to pair."
        )
    lines = [
        "## Pairwise comparisons",
        "",
        "Wilcoxon signed-rank test on `success`, paired by seed, against the "
        "algorithm with the highest success rate.",
        "",
        "| Baseline | Compared | Metric | p-value | Effect size | Significant |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in comparisons:
        lines.append(
            f"| {c.baseline_algorithm} | {c.compared_algorithm} | {c.metric} | "
            f"{c.p_value:.4f} | {c.effect_size:.4f} | {'yes' if c.significant else 'no'} |"
        )
    return "\n".join(lines)


def _runs_section(runs: tuple[RunRecord, ...]) -> str:
    lines = [
        "## Runs",
        "",
        "| Algorithm | Seed | Status | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for r in runs:
        reason = r.reason[:120] + "…" if len(r.reason) > 120 else r.reason
        lines.append(f"| {r.algorithm} | {r.seed} | {r.status.value} | {reason} |")
    return "\n".join(lines)


__all__ = ["render_report_markdown"]
