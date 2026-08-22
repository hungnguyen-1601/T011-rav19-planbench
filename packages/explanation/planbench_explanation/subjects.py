"""Who a claim is *about*, and why it is never "the algorithm".

A candidate is a whole navigation stack (HĐ-1.1), so "RRT* is slow in
corridors" names nothing that was measured: the run also had a local
controller, a costmap inflation, a set of providers and a transport. The
subject taxonomy below is the list of things a claim may be attributed
to, and it deliberately borrows the ownership vocabulary the Algorithm
Host already uses (candidate / deployment / oracle, capability channels,
H3–H4) rather than inventing a parallel one — a claim about
``perception_provider`` has to line up with the accounting that says who
paid for that compute, and two vocabularies would line up by hand.

**The pre-H4 ceiling is a stated limitation, not a bug.** Until latency
and perception compute can be attributed between candidate, deployment
and transport, a claim naming ``perception_provider`` or
``runtime_transport`` as the responsible component is an attribution the
platform cannot make — so those two subjects are capped at ``observed``:
the symptom may be reported, the responsibility may not be assigned.
Lifting the cap is a promotion-matrix version bump after H4.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from planbench_explanation.levels import ClaimLevel

Subject = Literal[
    "global_planner",
    "local_controller",
    "costmap_inflation",
    "perception_provider",
    "candidate_preprocessing",
    "runtime_transport",
    "task_geometry",
    "preference_constraint",
]

KNOWN_SUBJECTS: tuple[Subject, ...] = (
    "global_planner",
    "local_controller",
    "costmap_inflation",
    "perception_provider",
    "candidate_preprocessing",
    "runtime_transport",
    "task_geometry",
    "preference_constraint",
)

#: Subjects whose attribution H4's accounting does not yet support.
PRE_H4_CAPPED_SUBJECTS: tuple[Subject, ...] = ("perception_provider", "runtime_transport")

#: Whether the platform can attribute latency and perception compute
#: between candidate, deployment and transport yet.
#:
#: **A constant, not a parameter.** It was briefly a keyword argument on
#: the ledger builder, which put the answer in the hands of whoever
#: called it — including the party whose candidate is being judged.
#: Whether the accounting exists is a fact about this repository, and
#: flipping it changes which claims the matrix will promote, so it is a
#: promotion-matrix version bump and a code change, made by the platform
#: and visible in a diff.
H4_ACCOUNTING_COMPLETE = False


class UnknownSubjectError(ValueError):
    """A subject outside :data:`KNOWN_SUBJECTS`."""


def canonical_subjects(values: Iterable[str]) -> tuple[Subject, ...]:
    """Validate, deduplicate and sort subjects."""
    cleaned = {value.strip() for value in values}
    unknown = sorted(cleaned - set(KNOWN_SUBJECTS))
    if unknown:
        raise UnknownSubjectError(
            f"unknown subject(s) {unknown}; known subjects are {list(KNOWN_SUBJECTS)}"
        )
    return tuple(sorted(cleaned))  # type: ignore[arg-type]


def subject_ceiling(subject: Subject, *, h4_accounting_complete: bool = False) -> ClaimLevel:
    """Strongest level a claim about ``subject`` may reach today.

    ``h4_accounting_complete`` is an argument rather than a constant so
    the day H4 lands is a one-line change with a test that already
    covers both sides, instead of an edit to a table nobody re-reads.
    """
    if subject not in KNOWN_SUBJECTS:
        raise UnknownSubjectError(
            f"unknown subject {subject!r}; known subjects are {list(KNOWN_SUBJECTS)}"
        )
    if not h4_accounting_complete and subject in PRE_H4_CAPPED_SUBJECTS:
        return "observed"
    return "intervention_supported"
