"""A selection run as one workbook.

The Markdown export goes in a ticket; this one goes to somebody who
works in a spreadsheet. Same content, same words, different container —
`decision_export` decides every value, and this module only decides
where it sits.

**What a spreadsheet gets wrong that a page does not.** Two of the
export's structural properties are sharper here:

- *Null renders as "not measured", never as a blank.* On a page a blank
  cell is merely unhelpful. In a spreadsheet it sorts to the top, sums
  as zero, and averages as though it were measured.
- *The caveats travel.* A workbook is the format most likely to be
  pulled apart — one sheet copied into a slide, one column pasted into
  an email — so each caveat sits on the sheet holding the numbers it
  qualifies rather than in a preamble somebody will leave behind.

**Values are written as the strings the Markdown export shows**, not as
raw floats. It costs sorting and summing, and it buys the one property
worth more: the two documents cannot quote different numbers for the
same run. `7.35 ms` here and `7.3479809999` in the other file would be
the same value and a reader would have no way to know it.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any

from planbench_api.decision_export import (
    DEFAULT_LOCALE,
    Locale,
    Quantity,
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
    summary_rows,
)
from planbench_api.decision_text import text

__all__ = ["decision_workbook_filename", "render_decision_xlsx"]

#: Excel refuses these in a sheet name and truncates past 31 characters.
#: Enforced rather than assumed: a name that trips either rule makes the
#: whole file unopenable, and the failure arrives at the reader, not here.
_ILLEGAL_IN_SHEET_NAME = re.compile(r"[\[\]:*?/\\]")
_SHEET_NAME_LIMIT = 31

#: Anything outside this becomes a hyphen. Deliberately narrower than
#: what any one filesystem forbids: the file is downloaded by a browser,
#: saved on whatever the reader runs, and mailed on from there, so the
#: safe set is the intersection rather than the union.
_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

#: Long enough for two stack names and a deployment, short enough that
#: the whole path stays inside the Windows limit after it lands in a
#: nested Downloads folder.
_FILENAME_STEM_LIMIT = 120


def _slug(value: Any) -> str:
    """A filename-safe fragment, or the empty string when there is none."""
    return _UNSAFE_IN_FILENAME.sub("-", str(value or "")).strip("-")


def _comparison_slug(report: dict[str, Any]) -> str:
    """What was compared, named in the filename.

    Two candidates are named; more are counted. `a-vs-b-vs-c-vs-d` is a
    filename nobody reads to the end, and the count is the part that
    tells a reader which download this is.
    """
    labels = [_slug(entry.get("stack_label")) for entry in report.get("candidates") or []]
    labels = [label for label in labels if label]
    if not labels:
        return "no-candidates"
    if len(labels) > 2:
        return f"{len(labels)}-candidates"
    return "-vs-".join(labels)


def _when(run: Any, report: dict[str, Any]) -> str:
    """When the run happened, or nothing at all.

    **Not the moment the button was pressed.** Two exports of one run
    have to produce one filename, or a reader with both in a folder has
    two files and no way to see they are the same document.

    An unparseable timestamp drops the segment rather than substituting
    now(): a name that states the wrong time is worse than one that
    states no time, because only the first is believed.
    """
    identity = report.get("identity") or {}
    raw = identity.get("created_at") or getattr(run, "created_at", None)
    if not raw:
        return ""
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return ""
    return stamp.strftime("%Y-%m-%d_%H-%M")


def decision_workbook_filename(run: Any) -> str:
    """``<project>_<comparison>_<YYYY-MM-DD_HH-mm>.xlsx``.

    Named for what the file is about rather than for the id it was
    fetched by. `decision-8f3a1c.xlsx` is unambiguous and says nothing;
    a reader with six of them in a Downloads folder needs the deployment
    and the pair, and needs them without opening anything.
    """
    report: dict[str, Any] = getattr(run, "report", None) or {}
    parts = [
        _slug(getattr(run, "task_profile_id", None)) or "decision",
        _comparison_slug(report),
    ]
    when = _when(run, report)
    if when:
        parts.append(when)
    return f"{'_'.join(parts)[:_FILENAME_STEM_LIMIT]}.xlsx"


def _sheet_name(title: str) -> str:
    return _ILLEGAL_IN_SHEET_NAME.sub("-", title)[:_SHEET_NAME_LIMIT]


def render_decision_xlsx(run: Any, locale: Locale = DEFAULT_LOCALE) -> bytes:
    """The whole run as a workbook, one sheet per section."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    report: dict[str, Any] = run.report or {}
    workbook = Workbook()
    workbook.remove(workbook.active)

    bold = Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    def sheet(key: str):
        """A sheet named from the text table.

        Named by key rather than by literal because Vietnamese runs
        longer than English and Excel truncates a sheet name at 31
        characters — a limit that has to be checked in whichever
        language the reader asked for, not only the default.
        """
        return workbook.create_sheet(_sheet_name(text(key, locale)))

    def write_value(target, row: int, column: int, value: str | Quantity):
        """One cell, as a number where the value is one.

        A :class:`Quantity` reaches the sheet as a float with a format,
        not as the string a reader would see. That is what makes the
        column sortable and summable — and it is why a missing value
        leaves the cell genuinely **empty** rather than carrying the
        words "not measured": text in a numeric column takes sorting
        away from every other row in it, and 0 would be read as a
        measurement.
        """
        cell = target.cell(row=row, column=column)
        if isinstance(value, Quantity):
            if not value.missing:
                cell.value = value.value
            cell.number_format = value.unit.excel_format
        else:
            cell.value = value
        return cell

    def write_pairs(target, rows, start: int) -> int:
        for offset, (label, value) in enumerate(rows):
            target.cell(row=start + offset, column=1, value=label).font = bold
            write_value(target, start + offset, 2, value)
        return start + len(rows)

    def write_caveat(target, label: str, body: str, at: int) -> int:
        """A caveat, on the sheet holding what it qualifies.

        Labelled rather than merged into the surrounding rows: a reader
        copying a range out should take the warning with the numbers or
        leave both.

        The parameter is `body` and not `text`: this module now imports a
        function by that name, and a parameter shadowing it would leave
        the next line added inside here calling a string.
        """
        target.cell(row=at, column=1, value=label).font = bold
        cell = target.cell(row=at, column=2, value=body)
        cell.alignment = wrap
        return at + 1

    # --- Summary ----------------------------------------------------------
    #
    # First, and the only sheet that answers "what came out of this?"
    # without the reader assembling it from three others: the run's
    # identity was on `Provenance`, the winner and the margin on
    # `Decision Card`, and which stacks were compared only on the tables
    # underneath. A reader who opens the file to check one number should
    # not have to know which tab it lives on.
    summary = sheet("heading.summary")
    cursor = write_pairs(summary, summary_rows(run, report, locale), 1)
    write_caveat(
        summary,
        text("heading.precision", locale),
        text("prose.summary_precision", locale),
        cursor + 1,
    )
    summary.column_dimensions["A"].width = 26
    summary.column_dimensions["B"].width = 82

    # --- Provenance -------------------------------------------------------
    provenance = sheet("heading.provenance")
    heading = provenance.cell(
        row=1,
        column=1,
        value=text(
            "heading.document", locale, profile=as_text(run.task_profile_id, locale)
        ),
    )
    heading.font = bold
    cursor = write_pairs(provenance, provenance_rows(run, report, locale), 3)
    warning = environment_warning(report, locale)
    if warning:
        write_caveat(
            provenance,
            text("heading.measurement_environment", locale),
            warning,
            cursor + 1,
        )
    provenance.column_dimensions["A"].width = 26
    provenance.column_dimensions["B"].width = 82

    # --- Sample -----------------------------------------------------------
    sample = sheet("heading.sample")
    write_pairs(sample, sample_rows(report, locale), 1)
    sample.column_dimensions["A"].width = 30
    sample.column_dimensions["B"].width = 20

    # --- Gates ------------------------------------------------------------
    candidates = report.get("candidates") or []
    if candidates:
        gates = sheet("heading.gates")
        for column, label in enumerate(gate_columns(locale), start=1):
            gates.cell(row=1, column=column, value=label).font = bold
        for index, row in enumerate(gate_rows(report, locale), start=2):
            for column, value in enumerate(row, start=1):
                gates.cell(row=index, column=column, value=value)
        # The header stays put while a reader scrolls a long field.
        gates.freeze_panes = "A2"
        for column, width in zip("ABCDEFGH", (22, 16, 18, 18, 12, 14, 12, 34), strict=False):
            gates.column_dimensions[column].width = width

        cursor = len(candidates) + 3
        mixed = mixed_observation(candidates, locale)
        if mixed:
            cursor = write_caveat(
                gates, text("heading.unlike_inputs", locale), mixed.sentence(), cursor
            )
        retired = retired_candidates(candidates, locale)
        if retired:
            gates.cell(
                row=cursor + 1, column=1, value=text("heading.retired_early", locale)
            ).font = bold
            for offset, (label, detail) in enumerate(retired):
                gates.cell(row=cursor + 1 + offset, column=2, value=f"{label} — {detail}")

    # --- What the sweep concluded about each candidate --------------------
    def write_table(target, columns, rows, widths) -> None:  # noqa: ANN001, ANN202
        for column, label in enumerate(columns, start=1):
            target.cell(row=1, column=column, value=label).font = bold
        for index, row in enumerate(rows, start=2):
            for column, value in enumerate(row, start=1):
                target.cell(row=index, column=column, value=value)
        # The header stays put while a reader scrolls a long field.
        target.freeze_panes = "A2"
        for offset, width in enumerate(widths):
            target.column_dimensions[get_column_letter(offset + 1)].width = width

    outcomes = outcome_rows(report, locale)
    if outcomes:
        sheet_outcomes = sheet("heading.outcome")
        write_table(
            sheet_outcomes, outcome_columns(locale), outcomes,
            (22, 16) + (11,) * 5 + (12, 11, 18, 15, 15, 14, 13, 15, 16, 12, 20),
        )
        write_caveat(
            sheet_outcomes,
            text("column.outcome.eligible", locale),
            text("prose.eligible_sheet", locale),
            len(outcomes) + 3,
        )

    # --- The recommendation, or why there is none -------------------------
    decision = sheet("heading.card")
    rows = card_rows(run, report, locale)
    if rows is None:
        decision.cell(
            row=1, column=1, value=text("heading.no_card", locale)
        ).font = bold
        reason = no_card_reason(report, locale)
        at = 3
        if reason:
            at = write_caveat(decision, text("heading.reason", locale), reason, at)
        write_caveat(
            decision,
            text("heading.what_this_means", locale),
            text("prose.no_card_sheet", locale),
            at,
        )
    else:
        cursor = write_pairs(decision, rows, 1)
        cursor = write_caveat(
            decision,
            text("heading.scope", locale),
            text("prose.scope_sheet", locale, scope=scope_of(run, report, locale)),
            cursor + 1,
        )
        evidence = decision_evidence_rows(run, report, locale)
        if evidence:
            decision.cell(
                row=cursor + 1, column=1, value=text("heading.margin", locale)
            ).font = bold
            cursor = write_pairs(decision, evidence, cursor + 2)
            cursor = write_caveat(
                decision,
                text("heading.reading_delta_u", locale),
                text("prose.delta_u_sheet", locale),
                cursor + 1,
            )

        card = run.card or report.get("decision_card") or {}
        margins = sensitivity_rows(card.get("evidence") or {}, locale)
        if margins is None:
            write_caveat(
                decision,
                text("heading.sensitivity", locale),
                text("prose.no_sensitivity_sheet", locale),
                cursor + 1,
            )
        else:
            decision.cell(
                row=cursor + 1, column=1, value=text("heading.sensitivity", locale)
            ).font = bold
            write_pairs(decision, margins, cursor + 2)
    decision.column_dimensions["A"].width = 26
    decision.column_dimensions["B"].width = 82

    # --- Every episode ----------------------------------------------------
    episodes = episode_rows(report, locale)
    if episodes:
        write_table(
            sheet("heading.episodes"), episode_columns(locale), episodes,
            (30, 20, 16, 11, 14, 12, 13, 10, 15),
        )

    # --- Human record -----------------------------------------------------
    human = sheet("heading.human")
    cursor = write_pairs(human, human_rows(run, locale), 1)
    write_caveat(
        human,
        text("heading.two_acts", locale),
        text("prose.two_acts_sheet", locale),
        cursor + 1,
    )
    human.column_dimensions["A"].width = 26
    human.column_dimensions["B"].width = 82

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
