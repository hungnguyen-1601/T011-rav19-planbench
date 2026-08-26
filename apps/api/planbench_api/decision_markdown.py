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

**The words come from `decision_text`, the shape from here.** A document
in a language the reader does not use is one whose caveats do not
travel, which is the whole failure this export exists to avoid. English
stays frozen byte for byte — `tests/golden/decision_report_en.md` is the
guard — because this is a document people keep and diff against the copy
already in the ticket.
"""

from __future__ import annotations

from typing import Any

from planbench_api.decision_export import (
    DEFAULT_LOCALE,
    Locale,
    as_text,
    card_rows,
    decision_evidence_rows,
    environment_warning,
    episode_columns,
    episode_rows,
    gate_columns,
    gate_rows,
    human_rows,
    mixed_observation,
    no_card_reason,
    outcome_columns,
    outcome_rows,
    provenance_rows,
    retired_candidates,
    sample_rows,
    scope_of,
    sensitivity_rows,
)
from planbench_api.decision_text import lines as text_lines
from planbench_api.decision_text import text

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


def _quote(key: str, locale: Locale, **fields: object) -> list[str]:
    """A paragraph as a blockquote, wrapped where the string wraps.

    The line breaks belong to the text rather than to this function: the
    spreadsheet joins the same paragraph with spaces, and a renderer
    re-wrapping it would be a second opinion about where the sentence
    should break.
    """
    return [f"> {line}" for line in text_lines(key, locale, **fields)]


def render_decision_markdown(run: Any, locale: Locale = DEFAULT_LOCALE) -> str:
    """The whole run as Markdown: gates first, card second, caveats attached."""
    report: dict[str, Any] = run.report or {}
    heading = text("heading.document", locale, profile=as_text(run.task_profile_id, locale))
    lines: list[str] = [f"# {heading}", ""]
    lines += _provenance(run, report, locale)
    lines += _sample(report, locale)
    lines += _gates(report, locale)
    lines += _outcomes(report, locale)
    lines += _card(run, report, locale)
    lines += _episodes(report, locale)
    lines += _human_state(run, locale)
    return "\n".join(lines).rstrip() + "\n"


def _provenance(run: Any, report: dict[str, Any], locale: Locale) -> list[str]:
    lines = [f"## {text('heading.provenance', locale)}", ""] + _pairs(
        provenance_rows(run, report, locale)
    )
    warning = environment_warning(report, locale)
    if warning:
        label = text("heading.measurement_environment", locale)
        lines += ["", f"> **{label}:** {warning}"]
    return lines + [""]


def _sample(report: dict[str, Any], locale: Locale) -> list[str]:
    return [f"## {text('heading.sample', locale)}", ""] + _pairs(sample_rows(report, locale)) + [""]


def _gates(report: dict[str, Any], locale: Locale) -> list[str]:
    candidates = report.get("candidates") or []
    if not candidates:
        return []
    columns = gate_columns(locale)
    lines = [
        f"## {text('heading.gates', locale)}",
        "",
        *text_lines("prose.gates", locale),
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in gate_rows(report, locale):
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")

    mixed = mixed_observation(candidates, locale)
    if mixed:
        lines += ["", f"> **{mixed.lead}** {mixed.body[0]}"]
        lines += [f"> {line}" for line in mixed.body[1:]]

    retired = retired_candidates(candidates, locale)
    if retired:
        lines += ["", text("prose.retired", locale), ""]
        lines += [f"- **{label}** — {detail}" for label, detail in retired]
    return lines + [""]


def _table(columns: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    return ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"] + [
        "| " + " | ".join(_cell(value) for value in row) + " |" for row in rows
    ]


def _outcomes(report: dict[str, Any], locale: Locale) -> list[str]:
    """What the sweep concluded about each candidate.

    Separate from the gate table: that one says who was eliminated
    where, this one says how each behaved. Most of these columns never
    left the screen before.

    **Kept wide here while the workbook transposed it.** A spreadsheet
    reader compares down a column and wanted one row per metric; a
    document is read top to bottom and a transposed table would put the
    candidate names in a header nobody scrolls back to. The two formats
    diverging in shape is not the two formats disagreeing — every value
    still comes from `outcome_rows`.
    """
    rows = outcome_rows(report, locale)
    if not rows:
        return []
    return (
        [
            f"## {text('heading.outcome', locale)}",
            "",
            *text_lines("prose.eligible", locale),
            "",
        ]
        + _table(outcome_columns(locale), rows)
        + [""]
    )


def _episodes(report: dict[str, Any], locale: Locale) -> list[str]:
    """Every episode, because the aggregate was never the whole answer.

    `success_rate: 0.70` does not say *which* thirty per cent failed,
    nor whether they were collisions or timeouts, and those two ask for
    different work.
    """
    rows = episode_rows(report, locale)
    if not rows:
        return []
    return (
        [f"## {text('heading.episodes', locale)}", ""]
        + _table(episode_columns(locale), rows)
        + [""]
    )


def _card(run: Any, report: dict[str, Any], locale: Locale) -> list[str]:
    rows = card_rows(run, report, locale)
    if rows is None:
        lines = [f"## {text('heading.no_card', locale)}", ""]
        reason = no_card_reason(report, locale)
        if reason:
            lines += [reason, ""]
        lines += [*text_lines("prose.no_card", locale), ""]
        return lines

    scope = scope_of(run, report, locale)
    lines = [f"## {text('heading.card', locale)}", ""] + _pairs(rows)
    scope_lines = text_lines("prose.scope", locale, scope=scope)
    lines += [
        "",
        f"> **{text('heading.scope', locale)}:** {scope_lines[0]}",
        *[f"> {line}" for line in scope_lines[1:]],
        "",
    ]

    evidence = decision_evidence_rows(run, report, locale)
    if evidence:
        lines += [f"| {text('heading.margin', locale)} | |", "| --- | --- |"]
        lines += [f"| {_cell(label)} | {_cell(value)} |" for label, value in evidence]
        lines += ["", *_quote("prose.delta_u", locale), ""]

    card = run.card or report.get("decision_card") or {}
    margins = sensitivity_rows(card.get("evidence") or {}, locale)
    if margins is None:
        lines += [*text_lines("prose.no_sensitivity", locale), ""]
    else:
        lines += [f"| {text('heading.sensitivity', locale)} | |", "| --- | --- |"]
        lines += [f"| {_cell(label)} | {_cell(value)} |" for label, value in margins]
        lines += [""]
    return lines


def _human_state(run: Any, locale: Locale) -> list[str]:
    return (
        [f"## {text('heading.human', locale)}", ""]
        + _pairs(human_rows(run, locale))
        + ["", *text_lines("prose.two_acts", locale), ""]
    )
