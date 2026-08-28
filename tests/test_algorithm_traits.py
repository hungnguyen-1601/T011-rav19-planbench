"""M3 — algorithm natures as rows, and the rules that survive the move.

The natures were a dict in ``planbench_benchmark.outcome``. That worked
while the platform only ran algorithms it shipped with; since the import
feature landed it runs algorithms nobody here has heard of, and a nature
somebody can only add by editing Python is a nature an imported
algorithm will never have.

Three things are held here, and each is the reason the table is worth
having rather than a free-text field: every row names where its claim
can be checked, an unreviewed row cannot promote a claim, and an
algorithm nobody described reads as *undescribed* rather than as one
with no weaknesses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planbench_benchmark.outcome import SHIPPED_TRAITS, TRAITS, build_outcome
from planbench_benchmark.traits_store import (
    UNDESCRIBED,
    TraitEntry,
    TraitRefusal,
    TraitSource,
    entries_from_mapping,
    mapping_from_entries,
)


def entry(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "algorithm_id": "mppi",
        "kind": "local",
        "strengths": ("samples whole trajectories rather than one step",),
        "weaknesses": ("cost is paid every tick, whatever the map looks like",),
        "anchor": "defining mechanics: sampling-based receding-horizon control",
    }
    fields.update(overrides)
    return TraitEntry(**fields)  # type: ignore[arg-type]


def report(stack: str = "astar+dwa"):  # type: ignore[no-untyped-def]
    return {
        "candidates": [
            {"candidate_id": "cand_a", "stack_label": stack, "success_rate": 1.0},
        ]
    }


# --------------------------------------------------------------------------
# A row has to be checkable
# --------------------------------------------------------------------------


def test_a_trait_with_no_anchor_is_not_a_row() -> None:
    """A nature with nowhere to check it is folklore, and folklore in a
    column reads exactly like a measurement."""
    with pytest.raises((TraitRefusal, ValidationError)):
        entry(anchor="")


def test_an_approval_nobody_signed_is_refused() -> None:
    with pytest.raises((TraitRefusal, ValidationError), match="accountable"):
        entry(review_status="approved")


def test_an_approved_row_that_says_nothing_is_refused() -> None:
    with pytest.raises((TraitRefusal, ValidationError), match="nothing there"):
        entry(review_status="approved", reviewed_by="An", strengths=(), weaknesses=())


# --------------------------------------------------------------------------
# Review gates promotion, not visibility
# --------------------------------------------------------------------------


def test_an_unreviewed_row_may_be_read_and_may_not_promote() -> None:
    """The same rule the knowledge base runs under: a sentence somebody
    typed and nobody checked is a hypothesis, however true it is."""
    unreviewed = entry(review_status="draft")
    assert unreviewed.may_support_a_claim is False
    assert unreviewed.as_source_block()["weaknesses"]


def test_an_approved_row_may_promote() -> None:
    assert entry(review_status="approved", reviewed_by="An").may_support_a_claim is True


def test_the_shipped_table_seeds_as_draft() -> None:
    """It was written by this project and reviewed by whoever merged it,
    which is not the same as somebody signing it as a trait row."""
    assert SHIPPED_TRAITS.entries
    assert all(item.review_status == "draft" for item in SHIPPED_TRAITS.entries)
    assert not any(item.may_support_a_claim for item in SHIPPED_TRAITS.entries)


def test_every_shipped_row_names_its_anchor() -> None:
    assert all(item.anchor for item in SHIPPED_TRAITS.entries)


# --------------------------------------------------------------------------
# Undescribed is a state, not an absence
# --------------------------------------------------------------------------


def test_an_algorithm_nobody_described_says_so() -> None:
    """ "Nobody wrote this down" and "this algorithm has no weaknesses"
    are different sentences, and only one of them is ever true."""
    block = TraitSource().block("mppi")
    assert block["review_status"] == "undescribed"
    assert block["note"]
    assert block == UNDESCRIBED


def test_an_imported_algorithm_reads_as_undescribed_in_the_outcome_source() -> None:
    """The failure this table exists to fix: the rules paired a real
    number with an empty nature and said nothing about it."""
    source = build_outcome(report("mppi+dwa"))
    traits = source["report"]["candidates"][0]["traits"]
    assert traits["global"]["review_status"] == "undescribed"
    assert traits["local"]["strengths"]


def test_a_described_import_reaches_the_rules() -> None:
    described = TraitSource([*SHIPPED_TRAITS.entries, entry(algorithm_id="mppi")])
    source = build_outcome(report("mppi+dwa"), traits=described)
    traits = source["report"]["candidates"][0]["traits"]
    assert traits["global"]["weaknesses"]
    assert traits["global"]["anchor"]


# --------------------------------------------------------------------------
# One list of natures, not two
# --------------------------------------------------------------------------


def test_the_dict_and_the_rows_hold_the_same_algorithms() -> None:
    """A migration that restated the table would be a second list, free
    to disagree with the one the rules read."""
    assert {item.algorithm_id for item in entries_from_mapping(TRAITS)} == set(TRAITS)


def test_rows_render_back_into_the_shape_the_rules_cite() -> None:
    """A move between storage layers must not move the citations."""
    rendered = mapping_from_entries(SHIPPED_TRAITS.entries)
    for algorithm_id, block in rendered.items():
        assert set(block) >= {"kind", "strengths", "weaknesses", "anchor"}
        assert list(block["strengths"]) == list(TRAITS[algorithm_id].get("strengths", ()))


def test_the_default_source_is_the_shipped_one() -> None:
    """A caller with no database still gets natures, and they are the
    same rows the migration seeds."""
    assert build_outcome(report())["report"]["candidates"][0]["traits"]["global"]["anchor"]
