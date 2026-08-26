"""W1.8 — the trait catalog a bundle was graded against stays re-derivable.

A checksum of the natures pins a value and not a document. The table has
a *current* state; an operator edits a row, the pointer moves, and the
revision the bundle was graded against is gone — leaving a bundle that
names a hash nobody can produce anything to match. It reads as pinned
and cannot be replayed, which is exactly what the frozen bundle exists
to prevent, arriving through the one field nobody checked.

So: three fields, a content-addressed artifact, a reader that recomputes
rather than trusts, and a delete that refuses while something still
cites the document.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from test_analyst_runner import bundle

from planbench_analyst.identity import runtime_config_checksum
from planbench_analyst.traits_snapshot import (
    SnapshotRefusal,
    delete_snapshot,
    read_snapshot,
    snapshot_from,
    snapshot_path,
    verify_snapshot,
    write_snapshot,
)
from planbench_benchmark.traits_store import TraitEntry, TraitSource
from planbench_explanation.bundle import AnalystBundle
from planbench_explanation.catalog import TOOL_CATALOG_VERSION


def source(*extra: TraitEntry) -> TraitSource:
    rows = (
        TraitEntry(
            algorithm_id="dwa",
            kind="local",
            strengths=("smooth near obstacles",),
            weaknesses=("concave pockets",),
            anchor="planbench_planning.dwa: the sampled-rollout scoring loop",
        ),
        TraitEntry(
            algorithm_id="rrtstar",
            kind="global",
            weaknesses=("needs samples in narrow corridors",),
            anchor="planbench_planning.rrtstar: the sampling loop and its budget",
        ),
        *extra,
    )
    return TraitSource(rows)


def snapshot(**overrides):  # type: ignore[no-untyped-def]
    fields = {"revision_id": "traits-r3"}
    fields.update(overrides)
    return snapshot_from(overrides.pop("source", source()), revision_id=fields["revision_id"])


# --------------------------------------------------------------------------
# The content hash is content's
# --------------------------------------------------------------------------


def test_the_whole_catalog_is_hashed_and_not_the_part_one_packet_used() -> None:
    """A subset that followed the packet would give one bundle two
    checksums on two cases, and a gate would call one system two."""
    everything = snapshot()
    smaller = snapshot_from(TraitSource(source().entries[:1]), revision_id="traits-r3")
    assert everything.checksum != smaller.checksum


def test_two_revisions_that_say_the_same_thing_hash_the_same() -> None:
    """The id identifies the decision to publish; the checksum
    identifies the content. A bump nobody meant is not an edit."""
    first = snapshot_from(source(), revision_id="traits-r3")
    again = snapshot_from(TraitSource(tuple(reversed(source().entries))), revision_id="traits-r3")
    assert first.checksum == again.checksum


def test_an_edited_row_changes_the_checksum() -> None:
    edited = TraitEntry(
        algorithm_id="dwa",
        kind="local",
        strengths=("smooth near obstacles",),
        weaknesses=("concave pockets", "doorways at an angle"),
        anchor="planbench_planning.dwa: the sampled-rollout scoring loop",
    )
    changed = snapshot_from(TraitSource((edited, source().entries[1])), revision_id="traits-r3")
    assert changed.checksum != snapshot().checksum


def test_a_revision_id_is_required() -> None:
    with pytest.raises(SnapshotRefusal, match="revision id"):
        snapshot_from(source(), revision_id="")


def test_text_is_normalised_before_hashing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Two strings that render identically and hash differently would
    make one revision two, and a reader comparing checksums would be
    told the catalog changed when nothing about it did."""
    composed = TraitEntry(
        algorithm_id="dwa",
        kind="local",
        weaknesses=("Á narrow corridor",),
        anchor="a",
    )
    decomposed = TraitEntry(
        algorithm_id="dwa",
        kind="local",
        weaknesses=("Á narrow corridor",),
        anchor="a",
    )
    left = snapshot_from(TraitSource((composed,)), revision_id="r1")
    right = snapshot_from(TraitSource((decomposed,)), revision_id="r1")
    assert left.checksum == right.checksum


# --------------------------------------------------------------------------
# The artifact is content-addressed and read back suspiciously
# --------------------------------------------------------------------------


def test_the_checksum_is_the_filename(tmp_path) -> None:  # type: ignore[no-untyped-def]
    built = snapshot()
    path = write_snapshot(built, tmp_path)
    assert built.checksum in path.name
    assert path == snapshot_path(tmp_path, built.checksum)


def test_writing_the_same_revision_twice_is_the_same_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first = write_snapshot(snapshot(), tmp_path)
    again = write_snapshot(snapshot(), tmp_path)
    assert first == again
    assert len(list(tmp_path.glob("traits-*.json"))) == 1


def test_a_snapshot_read_back_is_the_catalog_that_was_written(tmp_path) -> None:  # type: ignore[no-untyped-def]
    built = snapshot()
    path = write_snapshot(built, tmp_path)
    loaded = read_snapshot(path, expected_checksum=built.checksum)
    assert loaded.checksum == built.checksum
    assert loaded.revision_id == built.revision_id
    assert "dwa" in loaded.source


def test_a_file_edited_in_place_is_refused_rather_than_served(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Every bundle citing it was graded against something else."""
    path = write_snapshot(snapshot(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"][0]["weaknesses"] = ["nothing at all"]
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(SnapshotRefusal, match="hash"):
        read_snapshot(path)


def test_a_reader_may_disagree_with_the_checksum_a_bundle_names(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A stored checksum is a claim, and the point of naming it is that
    somebody can check it."""
    path = write_snapshot(snapshot(), tmp_path)
    with pytest.raises(SnapshotRefusal, match="names"):
        read_snapshot(path, expected_checksum="f" * 64)


def test_a_snapshot_nobody_can_open_is_refused_with_that_reason(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SnapshotRefusal, match="no trait snapshot"):
        read_snapshot(tmp_path / "traits-deadbeef.json")


# --------------------------------------------------------------------------
# The triple, checked as a triple
# --------------------------------------------------------------------------


def test_verify_takes_all_three_because_each_alone_can_be_true(tmp_path) -> None:  # type: ignore[no-untyped-def]
    built = snapshot()
    path = write_snapshot(built, tmp_path)
    verified = verify_snapshot(
        tmp_path,
        revision_id=built.revision_id,
        checksum=built.checksum,
        ref=path.name,
    )
    assert verified.checksum == built.checksum


def test_the_same_rows_published_under_two_decisions_is_caught(tmp_path) -> None:  # type: ignore[no-untyped-def]
    built = snapshot()
    path = write_snapshot(built, tmp_path)
    with pytest.raises(SnapshotRefusal, match="two decisions"):
        verify_snapshot(
            tmp_path,
            revision_id="traits-r4",
            checksum=built.checksum,
            ref=path.name,
        )


# --------------------------------------------------------------------------
# Deleting one that is still cited
# --------------------------------------------------------------------------


def test_a_referenced_snapshot_is_not_deletable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = write_snapshot(snapshot(), tmp_path)
    with pytest.raises(SnapshotRefusal, match="bundle-a4"):
        delete_snapshot(path, referenced_by=("bundle-a4",))
    assert path.exists()


def test_an_unreferenced_snapshot_can_go(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = write_snapshot(snapshot(), tmp_path)
    delete_snapshot(path)
    assert not path.exists()


# --------------------------------------------------------------------------
# The bundle carries the triple, and it is its identity
# --------------------------------------------------------------------------


def test_a_bundle_with_two_of_the_three_is_refused() -> None:
    with pytest.raises(ValidationError, match="revision id"):
        bundle(traits_revision_id="traits-r3", traits_snapshot_checksum="a" * 64)


def test_a_bundle_with_none_of_them_is_a_bundle_graded_without_traits() -> None:
    target = bundle()
    assert target.traits_snapshot_ref == ""
    assert isinstance(target, AnalystBundle)


def test_the_triple_changes_the_bundle_identity() -> None:
    """Two bundles graded against two revisions of the natures are two
    systems, and a gate decision names one of them."""
    plain = bundle()
    pinned = bundle(
        traits_revision_id="traits-r3",
        traits_snapshot_checksum="a" * 64,
        traits_snapshot_ref="traits-" + "a" * 64 + ".json",
    )
    assert plain.identity_checksum != pinned.identity_checksum


def test_a_checksum_that_is_not_a_digest_is_refused() -> None:
    with pytest.raises(ValidationError, match="sha-256"):
        bundle(
            traits_revision_id="traits-r3",
            traits_snapshot_checksum="not-a-digest",
            traits_snapshot_ref="traits-x.json",
        )


def test_the_dev_checksum_carries_the_triple_too() -> None:
    def checksum(triple: tuple[str, str, str] | None) -> str:
        return runtime_config_checksum(
            prompt_checksum="a" * 64,
            generation_config={"temperature": 0.0},
            catalog_version=TOOL_CATALOG_VERSION,
            source_manifest_hash="b" * 64,
            traits_snapshot=triple,
        )

    assert checksum(None) != checksum(("traits-r3", "c" * 64, "traits-c.json"))
