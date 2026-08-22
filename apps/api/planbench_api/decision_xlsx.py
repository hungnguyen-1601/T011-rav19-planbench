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


def render_decision_xlsx(run: Any) -> bytes:
    """The whole run as a workbook, one sheet per section."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    report: dict[str, Any] = run.report or {}
    workbook = Workbook()
    workbook.remove(workbook.active)

    bold = Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    def sheet(title: str):
        return workbook.create_sheet(_sheet_name(title))

    def write_pairs(target, rows: list[tuple[str, str]], start: int) -> int:
        for offset, (label, value) in enumerate(rows):
            target.cell(row=start + offset, column=1, value=label).font = bold
            target.cell(row=start + offset, column=2, value=value)
        return start + len(rows)

    def write_caveat(target, label: str, text: str, at: int) -> int:
        """A caveat, on the sheet holding what it qualifies.

        Labelled rather than merged into the surrounding rows: a reader
        copying a range out should take the warning with the numbers or
        leave both.
        """
        target.cell(row=at, column=1, value=label).font = bold
        cell = target.cell(row=at, column=2, value=text)
        cell.alignment = wrap
        return at + 1

    # --- Provenance -------------------------------------------------------
    provenance = sheet("Provenance")
    heading = provenance.cell(
        row=1, column=1, value=f"Selection run — {as_text(run.task_profile_id)}"
    )
    heading.font = bold
    cursor = write_pairs(provenance, provenance_rows(run, report), 3)
    warning = environment_warning(report)
    if warning:
        write_caveat(provenance, "Measurement environment", warning, cursor + 1)
    provenance.column_dimensions["A"].width = 26
    provenance.column_dimensions["B"].width = 82

    # --- Sample -----------------------------------------------------------
    sample = sheet("Sample")
    write_pairs(sample, sample_rows(report), 1)
    sample.column_dimensions["A"].width = 30
    sample.column_dimensions["B"].width = 20

    # --- Gates ------------------------------------------------------------
    candidates = report.get("candidates") or []
    if candidates:
        gates = sheet("Gates")
        for column, label in enumerate(GATE_COLUMNS, start=1):
            gates.cell(row=1, column=column, value=label).font = bold
        for index, row in enumerate(gate_rows(report), start=2):
            for column, value in enumerate(row, start=1):
                gates.cell(row=index, column=column, value=value)
        # The header stays put while a reader scrolls a long field.
        gates.freeze_panes = "A2"
        for column, width in zip("ABCDEFGH", (22, 16, 18, 18, 12, 14, 12, 34), strict=False):
            gates.column_dimensions[column].width = width

        cursor = len(candidates) + 3
        mixed = mixed_observation(candidates)
        if mixed:
            cursor = write_caveat(gates, "Unlike inputs", mixed.sentence(), cursor)
        retired = retired_candidates(candidates)
        if retired:
            gates.cell(row=cursor + 1, column=1, value="Retired early").font = bold
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

    outcomes = outcome_rows(report)
    if outcomes:
        sheet_outcomes = sheet("Outcome by candidate")
        write_table(
            sheet_outcomes, OUTCOME_COLUMNS, outcomes,
            (22, 16) + (11,) * 5 + (12, 11, 18, 15, 15, 14, 13, 15, 16, 12, 20),
        )
        write_caveat(
            sheet_outcomes,
            "Eligible to recommend",
            "Stated rather than left to be read off the gate column. A gate failure can "
            "leave no mark on the utility at all — collisions are excluded from U_S by "
            "contract (HĐ-6) so that they cannot be traded against speed — so the mark "
            "does not compare across that line.",
            len(outcomes) + 3,
        )

    # --- The recommendation, or why there is none -------------------------
    decision = sheet("Decision Card")
    rows = card_rows(run, report)
    if rows is None:
        decision.cell(row=1, column=1, value="No Decision Card").font = bold
        reason = no_card_reason(report)
        at = 3
        if reason:
            at = write_caveat(decision, "Reason", reason, at)
        write_caveat(
            decision,
            "What this means",
            "Fewer than two candidates cleared the gates, so ΔU does not exist and no "
            "card was produced. The gate table is the result.",
            at,
        )
    else:
        cursor = write_pairs(decision, rows, 1)
        cursor = write_caveat(
            decision,
            "Scope",
            f"This recommendation applies to {scope_of(run, report)} and to nothing else "
            "(HĐ-1.4). Carrying it to another deployment is a claim this run did not make.",
            cursor + 1,
        )
        evidence = decision_evidence_rows(run, report)
        if evidence:
            decision.cell(row=cursor + 1, column=1, value="The margin").font = bold
            cursor = write_pairs(decision, evidence, cursor + 2)
            cursor = write_caveat(
                decision,
                "Reading ΔU",
                "Printed with its interval and never without it: a margin whose interval "
                "includes zero is consistent with the two candidates being equal.",
                cursor + 1,
            )

        card = run.card or report.get("decision_card") or {}
        margins = sensitivity_rows(card.get("evidence") or {})
        if margins is None:
            write_caveat(
                decision,
                "Sensitivity",
                "None of the sensitivity margins were measured. That is not the same as "
                "their being wide (HĐ-12).",
                cursor + 1,
            )
        else:
            decision.cell(row=cursor + 1, column=1, value="Sensitivity").font = bold
            write_pairs(decision, margins, cursor + 2)
    decision.column_dimensions["A"].width = 26
    decision.column_dimensions["B"].width = 82

    # --- Every episode ----------------------------------------------------
    episodes = episode_rows(report)
    if episodes:
        write_table(
            sheet("Episodes"), EPISODE_COLUMNS, episodes,
            (30, 20, 16, 11, 14, 12, 13, 10, 15),
        )

    # --- Human record -----------------------------------------------------
    human = sheet("Human record")
    cursor = write_pairs(human, human_rows(run), 1)
    write_caveat(
        human,
        "Two acts",
        "Reading the evidence and approving the configuration are separate acts (HĐ-14). "
        "A run that was read and never approved is an ordinary state, not an omission.",
        cursor + 1,
    )
    human.column_dimensions["A"].width = 26
    human.column_dimensions["B"].width = 82

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
