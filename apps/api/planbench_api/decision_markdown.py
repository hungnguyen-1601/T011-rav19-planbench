"""A selection run as one Markdown document.

**Why an export at all.** A Decision Card is read by people who are not
going to open the platform: somebody signing off a deployment, somebody
reviewing it six months later, somebody who needs it in a ticket. The
old flow had this for benchmarks and it retired with `/benchmarks`; the
capability is worth keeping even though the thing it describes changed.

**What it must not become.** A pretty summary that drops the caveats is
worse than no export, because it travels further than the screen it came
from. So three properties are structural here rather than stylistic:

1. **A run with no card still exports.** Fewer than two candidates
   through the gates means no ΔU (HĐ-7), and the gate table is then the
   whole deliverable — refusing to export it would make the ordinary
   outcome the one you cannot share.
2. **Null renders as "not measured", never as a blank.** HĐ-12 defines
   null that way, and a blank cell in a Markdown table reads as
   reassurance.
3. **The scope travels with the recommendation.** HĐ-1.4 limits it to
   one deployment, and a document that arrives without that line is a
   document somebody will apply somewhere else.
"""

from __future__ import annotations

from typing import Any

__all__ = ["decision_report_filename", "render_decision_markdown"]

#: What a missing number says. Spelled out rather than left blank
#: because HĐ-12 makes null "not measured", which is a finding.
NOT_MEASURED = "not measured"


def decision_report_filename(run_id: str) -> str:
    return f"decision-{run_id}.md"


def render_decision_markdown(run: Any) -> str:
    """The whole run as Markdown: gates first, card second, caveats attached."""
    report: dict[str, Any] = run.report or {}
    lines: list[str] = [f"# Selection run — {_text(run.task_profile_id)}", ""]
    lines += _provenance(run, report)
    lines += _sample(report)
    lines += _gates(report)
    lines += _card(run, report)
    lines += _human_state(run)
    return "\n".join(lines).rstrip() + "\n"


def _provenance(run: Any, report: dict[str, Any]) -> list[str]:
    """Where this came from, in enough detail to rebuild it (HĐ-13)."""
    identity = report.get("identity") or {}
    rows = [
        ("Run id", run.id),
        ("Deployment", run.task_profile_id),
        ("Experiment scope", identity.get("experiment_scope") or run.experiment_scope),
        ("Contracts version", run.contracts_version),
        ("Code version", identity.get("git_sha")),
        ("Anchor config", identity.get("anchor_config_version")),
        ("Run", identity.get("created_at") or run.created_at),
    ]
    lines = ["## Provenance", "", "| | |", "| --- | --- |"]
    lines += [f"| {label} | {_text(value)} |" for label, value in rows]
    warning = (report.get("measurement_environment") or {}).get("warning")
    if warning:
        # An unpinned host makes every latency number a measurement of
        # this machine as much as of the candidate, so it travels with
        # the document rather than staying on the screen.
        lines += ["", f"> **Measurement environment:** {_text(warning)}"]
    return lines + [""]


def _sample(report: dict[str, Any]) -> list[str]:
    """What was measured, and what was asked for.

    Both, because an interrupted run whose requested count is missing
    reads as a deliberately short one — and a short run is exactly the
    thing a collision bound must not be computed from.
    """
    sample = report.get("sample") or {}
    measured = sample.get("n_episodes")
    requested = sample.get("n_episodes_requested")
    lines = ["## Sample", "", "| | |", "| --- | --- |"]
    lines.append(f"| Episodes measured | {_text(measured)} |")
    if requested is not None and requested != measured:
        lines.append(f"| Episodes requested | {_text(requested)} |")
        lines.append("| Interrupted | yes |")
    lines.append(f"| Minimum required (HĐ-7.1) | {_text(sample.get('n_min_required'))} |")
    return lines + [""]


def _gates(report: dict[str, Any]) -> list[str]:
    """The gate table — a first-class section, not an appendix.

    Six feasibility gates run before anything is scored, so a candidate
    that failed one was never ranked at all. Leading with the
    recommendation and burying this would invert the contract on paper
    exactly as it once did on screen.

    ``Shown`` is here because a comparison between candidates given
    different inputs is measuring the inputs: the column is what lets a
    reader see that before believing the last one.
    """
    candidates = report.get("candidates") or []
    if not candidates:
        return []
    lines = [
        "## Gates",
        "",
        "Six feasibility gates run before anything is scored (HĐ-7). A candidate that",
        "failed one was never ranked, which is a result rather than an error.",
        "",
        "| Candidate | Config | Shown | Distinct episodes | Success | p99 latency | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidates:
        blocking = candidate.get("blocking_gates") or []
        verdict = "passed" if candidate.get("cleared_gates") else f"blocked: {', '.join(blocking)}"
        cells = [
            _text(candidate.get("stack_label")),
            _text(candidate.get("local_controller_config")),
            _text(candidate.get("local_observation_class")),
            _text(candidate.get("n_distinct_episodes")),
            _ratio(candidate.get("success_rate")),
            _number(candidate.get("pooled_p99_latency_ms"), "ms"),
            verdict,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += _mixed_observation(candidates)
    lines += _stopped_early(candidates)
    return lines + [""]


def _mixed_observation(candidates: list[dict[str, Any]]) -> list[str]:
    """Say so when the field was not shown the same world.

    Two stacks reading different inputs answer different questions, so
    ΔU between them measures the privilege as much as the planner. On
    paper this matters more than on screen: the reader cannot ask.
    """
    classes = {candidate.get("local_observation_class") for candidate in candidates}
    if len(classes) < 2:
        return []
    named = ", ".join(sorted(_text(entry) for entry in classes))
    return [
        "",
        f"> **These candidates were shown different things ({named}).** Most of the gap",
        "> between their numbers is the gap between their inputs, so any ranking below",
        "> is measuring the privilege as much as the planner.",
    ]


def _stopped_early(candidates: list[dict[str, Any]]) -> list[str]:
    """Name every retired candidate and the sample it actually got."""
    retired = [entry for entry in candidates if entry.get("stopped_early")]
    if not retired:
        return []
    lines = ["", "Retired before the sweep ended, so their rows rest on fewer episodes:", ""]
    for entry in retired:
        stop = entry["stopped_early"]
        lines.append(
            f"- **{_text(entry.get('stack_label'))}** — {_text(stop.get('gate'))} after "
            f"{_text(stop.get('episodes_run'))} of {_text(stop.get('episodes_planned'))} "
            f"episodes ({_text(stop.get('rule'))})"
        )
    return lines


def _card(run: Any, report: dict[str, Any]) -> list[str]:
    """The recommendation with its scope and its caveats, or why there is none."""
    card = run.card or report.get("decision_card")
    if not card:
        lines = ["## No Decision Card", ""]
        reason = report.get("why_no_card")
        gate_only = report.get("gate_only_deployment")
        if gate_only:
            # A property of the deployment, not of the field: no
            # candidate would ever change it (HĐ-8.4).
            lines += [f"This deployment cannot rank (HĐ-8.4): {_text(gate_only)}", ""]
        elif reason:
            lines += [_text(reason), ""]
        lines += [
            "Fewer than two candidates cleared the gates, so ΔU does not exist and no card",
            "was produced. The gate table above is the result.",
            "",
        ]
        return lines

    recommended = card.get("recommended") or {}
    evidence = card.get("evidence") or {}
    lines = ["## Decision Card", "", "| | |", "| --- | --- |"]
    lines.append(f"| Recommended | {_text(recommended.get('stack'))} |")
    lines.append(f"| Candidate id | {_text(recommended.get('candidate_id'))} |")
    alternative = card.get("alternative") or {}
    lines.append(f"| Alternative | {_text(alternative.get('stack'))} |")
    lines.append(f"| Status | {_text(card.get('status'))} |")
    lines.append(f"| Contracts version | {_text(card.get('contracts_version'))} |")
    scope = card.get("recommendation_scope") or run.task_profile_id
    lines += [
        "",
        f"> **Scope:** this recommendation applies to `{_text(scope)}` and to nothing else",
        "> (HĐ-1.4). Carrying it to another deployment is a claim this run did not make.",
        "",
    ]
    lines += _sensitivity(evidence)
    return lines


def _sensitivity(evidence: dict[str, Any]) -> list[str]:
    """The three margins, with null spelled out.

    HĐ-12 makes null "not measured". Rendered blank, a card that measured
    none of them would look exactly like one that measured all three.
    """
    rows = [
        ("Weight stability margin", evidence.get("weight_stability_margin")),
        ("Anchor stability", evidence.get("anchor_stability")),
        ("Robustness margin", evidence.get("robustness_margin")),
    ]
    if all(value is None for _, value in rows):
        return [
            "None of the sensitivity margins were measured. That is not the same as their",
            "being wide (HĐ-12).",
            "",
        ]
    lines = ["| Sensitivity | |", "| --- | --- |"]
    lines += [f"| {label} | {_number(value)} |" for label, value in rows]
    return lines + [""]


def _human_state(run: Any) -> list[str]:
    """Who read it and who approved it — two acts, kept apart (HĐ-14)."""
    return [
        "## Human record",
        "",
        "| | |",
        "| --- | --- |",
        f"| Review state | {_text(run.review_state)} |",
        f"| Reviewed by | {_text(run.reviewed_by)} |",
        f"| Reviewed at | {_text(run.reviewed_at)} |",
        f"| Configuration decision | {_text(run.config_state)} |",
        f"| Decided by | {_text(run.config_decided_by)} |",
        f"| Decided at | {_text(run.config_decided_at)} |",
        "",
        "Reading the evidence and approving the configuration are separate acts (HĐ-14).",
        "A run that was read and never approved is an ordinary state, not an omission.",
        "",
    ]


def _text(value: Any) -> str:
    """A cell that never comes out empty, and never breaks the table."""
    if value is None or value == "":
        return NOT_MEASURED
    return str(value).replace("|", "\\|").replace("\n", " ")


def _number(value: Any, unit: str = "") -> str:
    if value is None:
        return NOT_MEASURED
    if isinstance(value, (int, float)):
        return f"{value:.3g}{(' ' + unit) if unit else ''}"
    return _text(value)


def _ratio(value: Any) -> str:
    if value is None:
        return NOT_MEASURED
    return f"{float(value) * 100:.1f}%"
