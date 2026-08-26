"""W1.6 — what approving a nature has to mean before it can back a claim.

An approved row may promote a claim, which makes the field the whole
risk in the table: "RRT* starves in narrow corridors" is either something
a reader can go and check or it is folklore in a table's clothing, and
from the outside the two look identical.

Three things are held here. That approval names a person and something
to have reviewed. That the anchor points *outside* the row — a row whose
anchor repeats its own claim, or appeals to what everybody knows, is one
nobody can check. And that a golden run which may promote on a nature
refuses to start while any row in its snapshot is unreviewed: approving
one after seeing which cases it would have helped is choosing an oracle
from the results, and nothing downstream can tell that apart from a
review done properly.
"""

from __future__ import annotations

import pytest

from planbench_benchmark.outcome import TRAITS
from planbench_benchmark.traits_review import (
    ReviewRefusal,
    approve,
    awaiting_review,
    independent_anchor,
    lock_for_golden,
    summarise,
)
from planbench_benchmark.traits_store import TraitEntry, TraitSource, entries_from_mapping

AT = "2026-08-26T12:00:00+00:00"


def entry(**overrides) -> TraitEntry:  # type: ignore[no-untyped-def]
    fields = {
        "algorithm_id": "rrtstar",
        "kind": "global",
        "weaknesses": ("needs samples in narrow corridors",),
        "anchor": "registry marks stochastic_global_planner=True; read across seeds",
    }
    fields.update(overrides)
    return TraitEntry(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Approval is a decision with three parts
# --------------------------------------------------------------------------


def test_an_approval_names_the_person_accountable_for_it() -> None:
    with pytest.raises(ReviewRefusal, match="nobody"):
        approve(entry(), reviewed_by="   ", at=AT)


def test_a_row_that_says_nothing_has_nothing_to_approve() -> None:
    with pytest.raises(ReviewRefusal, match="nothing"):
        approve(entry(weaknesses=(), strengths=()), reviewed_by="an", at=AT)


def test_an_approved_row_carries_the_reviewer_and_the_time() -> None:
    reviewed = approve(entry(), reviewed_by="An Tong", at=AT)
    assert reviewed.review_status == "approved"
    assert reviewed.reviewed_by == "An Tong"
    assert reviewed.updated_at == AT
    assert reviewed.may_support_a_claim


def test_the_timestamp_is_the_reviewers_and_not_the_clocks() -> None:
    """A function that stamped "now" would date an import as a review."""
    assert approve(entry(), reviewed_by="an", at="2020-01-01T00:00:00Z").updated_at.startswith(
        "2020"
    )


# --------------------------------------------------------------------------
# The anchor has to point outside the row
# --------------------------------------------------------------------------


def test_an_anchor_that_repeats_the_claim_is_not_one() -> None:
    circular = entry(anchor="needs samples in narrow corridors")
    assert not independent_anchor(circular)
    with pytest.raises(ReviewRefusal, match="anchor"):
        approve(circular, reviewed_by="an", at=AT)


@pytest.mark.parametrize(
    "anchor",
    [
        "well known behaviour of sampling planners",
        "self-evident from the algorithm",
        "as described above",
    ],
)
def test_an_appeal_to_common_knowledge_is_not_a_place_to_check(anchor: str) -> None:
    assert not independent_anchor(entry(anchor=anchor))


def test_an_anchor_naming_nothing_outside_the_row_is_refused() -> None:
    assert not independent_anchor(entry(anchor="rrtstar"))


@pytest.mark.parametrize(
    "anchor",
    [
        "registry marks requires_model=True",
        "planbench_planning.dwa: the sampled-rollout scoring loop",
        "measured on the warehouse_a_v1 sweep, report 2026-07-02",
        "docs/HĐ-6.md: the two node columns and what each counts",
    ],
)
def test_an_anchor_that_names_a_place_passes(anchor: str) -> None:
    assert independent_anchor(entry(anchor=anchor))


def test_every_shipped_nature_has_a_checkable_anchor() -> None:
    """The seed becomes the first thing anybody reviews; a row that
    could never be approved would make that review pointless."""
    unusable = [
        item.algorithm_id
        for item in entries_from_mapping(TRAITS)
        if not independent_anchor(item)
    ]
    assert unusable == []


# --------------------------------------------------------------------------
# Locked before golden
# --------------------------------------------------------------------------


def test_a_promoting_golden_run_refuses_while_a_row_is_unreviewed() -> None:
    source = TraitSource((entry(),))
    with pytest.raises(ReviewRefusal, match="rrtstar"):
        lock_for_golden(source, promoting=True)


def test_a_run_that_promotes_nothing_may_read_drafts() -> None:
    """An unapproved row widening the hypothesis space is the rule the
    knowledge base already runs under."""
    source = TraitSource((entry(),))
    assert lock_for_golden(source, promoting=False) == source.entries


def test_a_fully_reviewed_catalog_unlocks_the_promoting_run() -> None:
    source = TraitSource((approve(entry(), reviewed_by="an", at=AT),))
    assert lock_for_golden(source, promoting=True)


def test_what_is_waiting_is_a_list_rather_than_a_surprise_at_the_gate() -> None:
    source = TraitSource(
        (entry(), approve(entry(algorithm_id="dwa", kind="local"), reviewed_by="an", at=AT))
    )
    assert [item.algorithm_id for item in awaiting_review(source)] == ["rrtstar"]


def test_the_summary_says_which_anchors_a_reader_could_check() -> None:
    text = summarise((entry(), entry(algorithm_id="dwa", anchor="dwa")))
    assert "ANCHOR NOT CHECKABLE" in text
    assert "anchor ok" in text
