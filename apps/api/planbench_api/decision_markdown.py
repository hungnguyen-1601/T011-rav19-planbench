"""A selection run as one Markdown document.

**Why an export at all.** A Decision Card is read by people who are not
going to open the platform: somebody signing off a deployment, somebody
reviewing it six months later, somebody who needs it in a ticket. The
old flow had this for benchmarks and it retired with `/benchmarks`; the
capability is worth keeping even though the thing it describes changed.

**What it must not become.** A pretty summary that drops the caveats is
worse than no export, because it travels further than the screen it came
from.

The properties that guarantee that — a run with no card still exports,
null renders as "not measured" rather than blank, and the scope travels
with the recommendation — are properties of the *content*, so they moved
to `decision_export` when Excel became a second format. This module owns
the layout and nothing else: every value below is read from there, and
the two exports cannot disagree about a number because there is only one
place that decides what the number is.
"""

from __future__ import annotations

from typing import Any

from planbench_api.decision_export import (
    EPISODE_COLUMNS,
    GATE_COLUMNS,
    OUTCOME_COLUMNS,
    as_text,
    card_rows,
    decision_evidence_rows,
    environment_warning,
    episode_rows,
    gate_rows,
    human_rows,
    mixed_observation,
    no_card_reason,
    outcome_rows,
    provenance_rows,
    retired_candidates,
    sample_rows,
    scope_of,
    sensitivity_rows,
)

__all__ = ["decision_report_filename", "render_decision_markdown"]


def decision_report_filename(run_id: str) -> str:
    return f"decision-{run_id}.md"


def _cell(value: str) -> str:
    """A value as a Markdown table cell.

    The pipe escaping lives here rather than in `decision_export`: it is
    a fact about Markdown tables, and a spreadsheet fed the escaped form
    would show the backslashes.
    """
    return value.replace("|", "\\|")


def _pairs(rows: list[tuple[str, str]]) -> list[str]:
    """A headless two-column table, which is how this document states facts."""
    return ["| | |", "| --- | --- |"] + [
        f"| {_cell(label)} | {_cell(value)} |" for label, value in rows
    ]


def render_decision_markdown(run: Any) -> str:
    """The whole run as Markdown: gates first, card second, caveats attached."""
    report: dict[str, Any] = run.report or {}
    lines: list[str] = [f"# Selection run — {as_text(run.task_profile_id)}", ""]
    lines += _provenance(run, report)
    lines += _sample(report)
    lines += _gates(report)
    lines += _outcomes(report)
    lines += _card(run, report)
    lines += _episodes(report)
    lines += _human_state(run)
    return "\n".join(lines).rstrip() + "\n"


def _provenance(run: Any, report: dict[str, Any]) -> list[str]:
    lines = ["## Provenance", ""] + _pairs(provenance_rows(run, report))
    warning = environment_warning(report)
    if warning:
        lines += ["", f"> **Measurement environment:** {warning}"]
    return lines + [""]


def _sample(report: dict[str, Any]) -> list[str]:
    return ["## Sample", ""] + _pairs(sample_rows(report)) + [""]


def _gates(report: dict[str, Any]) -> list[str]:
    candidates = report.get("candidates") or []
    if not candidates:
        return []
    lines = [
        "## Gates",
        "",
        "Six feasibility gates run before anything is scored (HĐ-7). A candidate that",
        "failed one was never ranked, which is a result rather than an error.",
        "",
        "| " + " | ".join(GATE_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in GATE_COLUMNS) + " |",
    ]
    for row in gate_rows(report):
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")

    mixed = mixed_observation(candidates)
    if mixed:
        lines += ["", f"> **{mixed.lead}** {mixed.body[0]}"]
        lines += [f"> {line}" for line in mixed.body[1:]]

    retired = retired_candidates(candidates)
    if retired:
        lines += ["", "Retired before the sweep ended, so their rows rest on fewer episodes:", ""]
        lines += [f"- **{label}** — {detail}" for label, detail in retired]
    return lines + [""]


def _table(columns: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    return (
        ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
        + ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    )


def _outcomes(report: dict[str, Any]) -> list[str]:
    """What the sweep concluded about each candidate.

    Separate from the gate table: that one says who was eliminated
    where, this one says how each behaved. Most of these columns never
    left the screen before.
    """
    rows = outcome_rows(report)
    if not rows:
        return []
    return (
        [
            "## Outcome by candidate",
            "",
            "`Eligible to recommend` is stated rather than left to be read off the gate",
            "column: a gate failure can leave no mark on the utility at all — collisions are",
            "excluded from `U_S` by contract (HĐ-6), so that they cannot be traded against",
            "speed — and the mark alone therefore does not compare across that line.",
            "",
        ]
        + _table(OUTCOME_COLUMNS, rows)
        + [""]
    )


def _episodes(report: dict[str, Any]) -> list[str]:
    """Every episode, because the aggregate was never the whole answer.

    `success_rate: 0.70` does not say *which* thirty per cent failed,
    nor whether they were collisions or timeouts, and those two ask for
    different work.
    """
    rows = episode_rows(report)
    if not rows:
        return []
    return ["## Episodes", ""] + _table(EPISODE_COLUMNS, rows) + [""]


def _card(run: Any, report: dict[str, Any]) -> list[str]:
    rows = card_rows(run, report)
    if rows is None:
        lines = ["## No Decision Card", ""]
        reason = no_card_reason(report)
        if reason:
            lines += [reason, ""]
        lines += [
            "Fewer than two candidates cleared the gates, so ΔU does not exist and no card",
            "was produced. The gate table above is the result.",
            "",
        ]
        return lines

    scope = scope_of(run, report)
    lines = ["## Decision Card", ""] + _pairs(rows)
    lines += [
        "",
        f"> **Scope:** this recommendation applies to `{scope}` and to nothing else",
        "> (HĐ-1.4). Carrying it to another deployment is a claim this run did not make.",
        "",
    ]

    evidence = decision_evidence_rows(run, report)
    if evidence:
        lines += ["| The margin | |", "| --- | --- |"]
        lines += [f"| {_cell(label)} | {_cell(value)} |" for label, value in evidence]
        lines += [
            "",
            "> ΔU is printed with its interval and never without it. A margin whose interval",
            "> includes zero is consistent with the two candidates being equal.",
            "",
        ]

    card = run.card or report.get("decision_card") or {}
    margins = sensitivity_rows(card.get("evidence") or {})
    if margins is None:
        lines += [
            "None of the sensitivity margins were measured. That is not the same as their",
            "being wide (HĐ-12).",
            "",
        ]
    else:
        lines += ["| Sensitivity | |", "| --- | --- |"]
        lines += [f"| {_cell(label)} | {_cell(value)} |" for label, value in margins]
        lines += [""]
    return lines


def _human_state(run: Any) -> list[str]:
    return (
        ["## Human record", ""]
        + _pairs(human_rows(run))
        + [
            "",
            "Reading the evidence and approving the configuration are separate acts (HĐ-14).",
            "A run that was read and never approved is an ordinary state, not an omission.",
            "",
        ]
    )
