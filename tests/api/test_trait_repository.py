"""W1.4 — the trait table becomes something both lanes can read.

M3 built the table and the shape; nothing joined them. Every reader
still took ``SHIPPED_TRAITS``, the constant the migration seeded *from*,
so a row written for an imported algorithm was stored and then read by
nobody — the feature looked present and was not connected at either end.

What is held here: the rows come back as the same ``TraitSource`` the
advisory rules and the analyst already take, a row that will not parse
stops the load instead of vanishing from it, the order is content's and
not the database's, and a seed never overwrites the one thing in this
table a person did by hand.
"""

from __future__ import annotations

import pytest

from planbench_api.db import SessionFactory, create_all, create_db_engine
from planbench_api.db.models import AlgorithmTraitRow
from planbench_api.db.traits_repositories import SqlTraitRepository, entry_from_row
from planbench_benchmark.outcome import TRAITS
from planbench_benchmark.traits_store import TraitEntry, TraitRefusal, entries_from_mapping


@pytest.fixture
def traits(tmp_path) -> SqlTraitRepository:  # type: ignore[no-untyped-def]
    engine = create_db_engine(f"sqlite:///{tmp_path / 'planbench.db'}")
    create_all(engine)
    return SqlTraitRepository(SessionFactory(engine))


def entry(algorithm_id: str = "dwa", **overrides) -> TraitEntry:  # type: ignore[no-untyped-def]
    fields = {
        "algorithm_id": algorithm_id,
        "kind": "local",
        "strengths": ("smooth near obstacles",),
        "weaknesses": ("concave pockets",),
        "anchor": "planbench_planning.dwa: the sampled-rollout scoring loop",
    }
    fields.update(overrides)
    return TraitEntry(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The join that was missing
# --------------------------------------------------------------------------


def test_a_written_row_comes_back_as_the_source_both_lanes_take(
    traits: SqlTraitRepository,
) -> None:
    traits.save(entry())
    source = traits.load()
    assert "dwa" in source
    block = source.block("dwa")
    assert block["weaknesses"] == ["concave pockets"]
    assert block["anchor"]


def test_an_algorithm_with_no_row_reads_as_undescribed_and_not_as_clean(
    traits: SqlTraitRepository,
) -> None:
    """ "Nobody wrote this down" and "this algorithm has no weaknesses"
    are different sentences, and only one of them is ever true."""
    block = traits.load().block("an-imported-planner")
    assert block["review_status"] == "undescribed"
    assert block["weaknesses"] == []
    assert block["note"]


def test_the_review_status_survives_the_round_trip(traits: SqlTraitRepository) -> None:
    """An unreviewed row may inform a hypothesis and may not promote a
    claim, so the status is the field the promotion rule reads."""
    traits.save(entry(review_status="approved", reviewed_by="an"))
    stored = traits.get("dwa")
    assert stored is not None
    assert stored.may_support_a_claim
    assert not entry().may_support_a_claim


def test_saving_the_same_algorithm_twice_leaves_one_row(traits: SqlTraitRepository) -> None:
    traits.save(entry())
    traits.save(entry(weaknesses=("narrow doorways",)))
    assert len(traits.load().entries) == 1
    assert traits.load().block("dwa")["weaknesses"] == ["narrow doorways"]


# --------------------------------------------------------------------------
# Order is content's
# --------------------------------------------------------------------------


def test_the_rows_come_back_in_one_order_whatever_they_were_written_in(
    traits: SqlTraitRepository,
) -> None:
    """W1.8 hashes this catalog. A content hash whose input order depends
    on the database's mood is a checksum that moves for no reason."""
    for algorithm_id in ("rrtstar", "astar", "dwa"):
        traits.save(entry(algorithm_id))
    assert [item.algorithm_id for item in traits.load().entries] == ["astar", "dwa", "rrtstar"]


def test_the_load_is_the_whole_table(traits: SqlTraitRepository) -> None:
    """Not a per-packet subset: what a bundle is graded against is
    everything the analyst could have reached, and a subset would give
    one bundle two checksums on two packets."""
    traits.seed(entries_from_mapping(TRAITS))
    assert len(traits.load().entries) == len(TRAITS)


# --------------------------------------------------------------------------
# A broken row stops the load
# --------------------------------------------------------------------------


def test_a_row_whose_anchor_was_emptied_refuses_the_whole_load(
    traits: SqlTraitRepository,
) -> None:
    """Skipping it would read downstream as "nobody described this
    algorithm", which is the more flattering of the two sentences."""
    traits.save(entry())
    with traits._sessions.begin() as session:  # noqa: SLF001 - editing round the model
        session.get(AlgorithmTraitRow, "dwa").anchor = ""
    with pytest.raises(TraitRefusal, match="dwa"):
        traits.load()


def test_a_row_with_a_status_nobody_enumerated_refuses_too(
    traits: SqlTraitRepository,
) -> None:
    traits.save(entry())
    with traits._sessions.begin() as session:  # noqa: SLF001
        session.get(AlgorithmTraitRow, "dwa").review_status = "blessed"
    with pytest.raises(TraitRefusal):
        traits.load()


def test_a_value_that_is_not_a_sentence_is_coerced_rather_than_carried(
    traits: SqlTraitRepository,
) -> None:
    """A number in the column would otherwise arrive in a prompt as a
    nature."""
    traits.save(entry())
    with traits._sessions.begin() as session:  # noqa: SLF001
        session.get(AlgorithmTraitRow, "dwa").weaknesses = [7]
    assert traits.load().block("dwa")["weaknesses"] == ["7"]


# --------------------------------------------------------------------------
# The seed
# --------------------------------------------------------------------------


def test_the_seed_writes_the_shipped_natures_once(traits: SqlTraitRepository) -> None:
    written = traits.seed(entries_from_mapping(TRAITS))
    assert written == len(TRAITS)
    assert traits.seed(entries_from_mapping(TRAITS)) == 0


def test_the_seed_does_not_undo_a_review(traits: SqlTraitRepository) -> None:
    """The review is the one thing in this table a person did by hand."""
    shipped = entries_from_mapping(TRAITS)
    first = shipped[0]
    traits.save(first.model_copy(update={"review_status": "approved", "reviewed_by": "an"}))
    traits.seed(shipped)
    stored = traits.get(first.algorithm_id)
    assert stored is not None
    assert stored.review_status == "approved"
    assert stored.reviewed_by == "an"


def test_the_shipped_seed_arrives_as_draft_rather_than_approved(
    traits: SqlTraitRepository,
) -> None:
    """Whoever merged the constant is not the same as somebody signing a
    trait row, so nothing seeded may back a claim until a person moves
    it."""
    traits.seed(entries_from_mapping(TRAITS))
    assert all(not item.may_support_a_claim for item in traits.load().entries)


def test_a_row_read_back_matches_the_row_that_was_written(
    traits: SqlTraitRepository,
) -> None:
    written = entry(review_status="draft", updated_at="2026-08-26T00:00:00Z")
    traits.save(written)
    with traits._sessions.begin() as session:  # noqa: SLF001
        assert entry_from_row(session.get(AlgorithmTraitRow, "dwa")) == written
