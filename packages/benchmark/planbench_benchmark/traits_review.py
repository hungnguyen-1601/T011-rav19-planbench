"""Approving a nature, and what approval has to mean — W1.6.

An approved trait row may back a promoted claim. That is the whole point
of the field and the whole risk in it: the sentence "RRT* starves in
narrow corridors" is either something a reader can go and check or it is
the model's folklore wearing a table's clothing, and from the outside
those two look the same.

So approval is a decision with three parts, and each one is refused
without the others:

**A person.** ``reviewed_by``. An approval nobody signed is an approval
nobody is accountable for — already enforced by
:class:`~planbench_benchmark.traits_store.TraitEntry`, restated here
because it is half of what this module is about.

**Something to have reviewed.** A row that says nothing about the
algorithm has nothing in it to approve.

**An anchor that is independent of the claim.** This is the part that is
new here. An anchor pointing back at the sentence it supports — "because
the description says so", the trait text repeated, an empty gesture at
the algorithm's own name — is not a place to check the claim, it is the
claim again. What counts is something outside the row: a registry flag,
a module and the mechanic inside it, a measurement somebody recorded.

**Locked before golden.** The last function here is the one the golden
suite calls. Approving a nature *after* seeing which cases it would have
helped is choosing an oracle from the results, so the review has to be
finished — and the snapshot taken — before a calibration or a gate run
starts. A round that finds a draft row in its snapshot is told to stop.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from planbench_benchmark.traits_store import TraitEntry, TraitRefusal, TraitSource

__all__ = [
    "ReviewRefusal",
    "approve",
    "awaiting_review",
    "independent_anchor",
    "lock_for_golden",
]


class ReviewRefusal(TraitRefusal):
    """An approval this platform will not record."""


#: What an anchor has to reach outside the row to be one. Deliberately
#: broad — the shipped natures point at registry flags and at the code
#: that implements the mechanic, and both are checkable — and
#: deliberately not "any non-empty string", which is what the column
#: constraint alone amounts to.
_ANCHOR_MARKERS: tuple[str, ...] = (
    "registry",
    "planbench_",
    "measurement",
    "measured",
    "trace",
    "report",
    "gate",
    "docs/",
    "http",
)

#: Words that make an anchor a restatement rather than a reference.
_CIRCULAR_MARKERS: tuple[str, ...] = (
    "because the description",
    "as described above",
    "see the weakness",
    "see the strength",
    "self-evident",
    "well known",
    "commonly known",
    "everyone knows",
)


def independent_anchor(entry: TraitEntry) -> bool:
    """Whether this row's anchor points somewhere a reader could go.

    Three ways an anchor fails, and all three were written down because
    a plausible-looking row can have any of them:

    * it repeats the claim (the trait text appears inside it),
    * it appeals to common knowledge rather than to a place,
    * it names nothing outside the row at all.
    """
    anchor = entry.anchor.strip().lower()
    if not anchor:
        return False
    if any(marker in anchor for marker in _CIRCULAR_MARKERS):
        return False
    for text in (*entry.strengths, *entry.weaknesses):
        stripped = text.strip().lower()
        if stripped and stripped in anchor:
            return False
    if anchor in {entry.algorithm_id.lower(), entry.kind.lower()}:
        return False
    return any(marker in anchor for marker in _ANCHOR_MARKERS)


def approve(entry: TraitEntry, *, reviewed_by: str, at: str) -> TraitEntry:
    """Record a review. Refuses rather than downgrading what it cannot honour.

    ``at`` is the reviewer's timestamp, passed in rather than read from
    the clock: the caller knows when the decision was made, and a
    function that stamped "now" would date an import as a review.
    """
    if not reviewed_by.strip():
        raise ReviewRefusal(
            f"an approval of {entry.algorithm_id!r} that names nobody is an approval "
            "nobody is accountable for"
        )
    if not (entry.strengths or entry.weaknesses):
        raise ReviewRefusal(
            f"trait row {entry.algorithm_id!r} says nothing about the algorithm; "
            "there is nothing here to have reviewed"
        )
    if not independent_anchor(entry):
        raise ReviewRefusal(
            f"trait row {entry.algorithm_id!r} has no anchor a reader could check: "
            f"{entry.anchor!r} either repeats the claim, appeals to common knowledge, "
            "or names nothing outside the row. An approved nature may back a promoted "
            "claim, and folklore in a table reads exactly like a measurement."
        )
    return entry.model_copy(
        update={"review_status": "approved", "reviewed_by": reviewed_by.strip(), "updated_at": at}
    )


def awaiting_review(source: TraitSource) -> tuple[TraitEntry, ...]:
    """Rows that may inform a hypothesis and may not back a claim.

    What an operator is shown before a golden run, so "nobody has
    approved these yet" is a list rather than a surprise at the gate.
    """
    return tuple(item for item in source.entries if item.review_status != "approved")


def lock_for_golden(source: TraitSource, *, promoting: bool) -> tuple[TraitEntry, ...]:
    """The rows a golden run may rely on, or a refusal.

    ``promoting`` says whether this run's claims may be promoted on a
    trait. When they may, every row in the snapshot has to be approved
    **before** the run: approving a nature after seeing which cases it
    would have helped is choosing an oracle from the results, and no
    checksum downstream can tell that apart from a review done properly.

    When they may not, drafts are allowed through and returned as they
    are — an unapproved row widening the hypothesis space is the rule
    the knowledge base already runs under.
    """
    pending = awaiting_review(source)
    if promoting and pending:
        raise ReviewRefusal(
            "a golden run that may promote a claim on a nature needs every row in "
            f"its snapshot reviewed first; {[item.algorithm_id for item in pending]} "
            "are not. Approving one after seeing which cases it would have helped is "
            "choosing an oracle from the results."
        )
    return source.entries


def summarise(entries: Iterable[TraitEntry]) -> str:
    """One line per row for whoever is doing the reviewing."""
    lines = []
    for entry in sorted(entries, key=lambda item: item.algorithm_id):
        marks = len(entry.strengths) + len(entry.weaknesses)
        checkable = "anchor ok" if independent_anchor(entry) else "ANCHOR NOT CHECKABLE"
        lines.append(
            f"{entry.algorithm_id:<16} {entry.review_status:<9} {marks} statement(s)  "
            f"{checkable}  {entry.anchor}"
        )
    return "\n".join(lines)


def _looks_like_a_path(anchor: str) -> bool:
    """Kept for readers: what a code anchor tends to look like here."""
    return bool(re.match(r"^[a-z_]+(\.[a-z_]+)+", anchor.strip()))
