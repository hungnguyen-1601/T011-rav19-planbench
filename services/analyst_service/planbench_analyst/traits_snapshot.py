"""The trait catalog a bundle was graded against, kept re-derivable — W1.8.

A checksum of the natures is not enough, and the reason is dull: the
table has a *current* state. An operator edits a row, the pointer moves,
and the revision the bundle was graded against is gone — leaving a
bundle that names a checksum nobody can produce a document for. It reads
as pinned and cannot be replayed, which is the failure mode the frozen
bundle exists to prevent, arriving through the one field nobody checked.

So a bundle carries **three** things about the traits and not one:

``traits_revision_id``
    Which revision of the catalog. A label an operator can talk about.

``traits_snapshot_checksum``
    The content hash. Recomputed by every reader from the bytes on hand
    — the :mod:`~planbench_explanation.packet_artifact` rule: a stored
    checksum is a claim, and a claim nobody recomputes is decoration.

``traits_snapshot_ref``
    Where the document is. **Content-addressed**: the checksum is in the
    path, so an artifact cannot be edited in place and stay findable, and
    two writes of one revision are the same file rather than a conflict.

Three properties this module enforces, each because its absence produced
a specific wrong answer somewhere in this platform before:

**The whole catalog is hashed, never the part one packet used.** A
subset that followed the packet would give one bundle two checksums on
two cases, and a gate would call the same system two systems.

**Canonical before hashing.** Sorted by ``(algorithm_id, kind, index)``
and every string through NFKC, using the same ``canonical`` the sanitiser
uses and the same ``artifact_checksum`` everything else uses. A second
hashing formula for one value is how ``packet_checksum`` drifted at A4-i.

**A referenced snapshot is not deletable.** Removing the document a
live bundle names is an operational error with a name, not a tidy-up.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path

from planbench_analyst.sanitize import canonical
from planbench_benchmark.traits_store import TraitEntry, TraitSource
from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "SnapshotRefusal",
    "TraitsSnapshot",
    "delete_snapshot",
    "read_snapshot",
    "snapshot_from",
    "snapshot_path",
    "write_snapshot",
]


class SnapshotRefusal(ValueError):
    """A trait snapshot this platform will not write, read or remove."""


@dataclass(frozen=True)
class TraitsSnapshot:
    """One revision of the whole trait catalog, as an artifact."""

    revision_id: str
    entries: tuple[TraitEntry, ...]

    @property
    def payload(self) -> dict[str, object]:
        """The document, canonical.

        Text goes through ``canonical`` — NFKC — for the reason the
        sanitiser does it: two strings that render identically and hash
        differently would make one revision two, and a reader comparing
        the checksums would be told the catalog changed when nothing
        about it did.
        """
        rows = [
            {
                "algorithm_id": canonical(entry.algorithm_id),
                "kind": entry.kind,
                "strengths": [canonical(item) for item in entry.strengths],
                "weaknesses": [canonical(item) for item in entry.weaknesses],
                "anchor": canonical(entry.anchor),
                "review_status": entry.review_status,
                "reviewed_by": canonical(entry.reviewed_by),
            }
            for entry in sorted(self.entries, key=lambda item: (item.algorithm_id, item.kind))
        ]
        return {"revision_id": self.revision_id, "entries": rows}

    @property
    def checksum(self) -> str:
        """Content, not the label. Two revisions that say the same thing
        checksum the same, and a revision id somebody forgot to bump does
        not hide an edit."""
        return artifact_checksum(self.payload)

    @property
    def source(self) -> TraitSource:
        """The snapshot as the thing a round actually reads."""
        return TraitSource(self.entries)

    #: ``updated_at`` is deliberately outside :attr:`payload`. It moves
    #: when a row is touched and not when it changes, so including it
    #: would make a re-save of identical content a different catalog.
    _EXCLUDED_FROM_CONTENT = ("updated_at",)


def snapshot_from(source: TraitSource, *, revision_id: str) -> TraitsSnapshot:
    """Everything the analyst could have reached, under one revision id."""
    if not revision_id:
        raise SnapshotRefusal(
            "a snapshot with no revision id is one nobody can ask an operator "
            "about; the checksum identifies the content and the id identifies "
            "the decision to publish it"
        )
    return TraitsSnapshot(revision_id=revision_id, entries=tuple(source.entries))


def snapshot_path(root: Path, checksum: str) -> Path:
    """Where a snapshot of this content lives. The checksum **is** the name."""
    return root / f"traits-{checksum}.json"


def write_snapshot(snapshot: TraitsSnapshot, root: Path) -> Path:
    """Write it once, content-addressed. Re-writing identical bytes is fine.

    An existing file whose content hashes to something else is refused
    rather than replaced: the path names the content, so a mismatch is
    either a collision or a corrupted artifact, and both are worse than
    a failed write.
    """
    root.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(root, snapshot.checksum)
    body = json.dumps(snapshot.payload, ensure_ascii=False, sort_keys=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != body:
            raise SnapshotRefusal(
                f"{path.name} already holds different bytes. The path names the "
                "content, so this is a corrupted artifact rather than an update, "
                "and overwriting it would leave every bundle that cites it "
                "pointing at something else."
            )
        return path
    path.write_text(body, encoding="utf-8")
    return path


def read_snapshot(path: Path, *, expected_checksum: str = "") -> TraitsSnapshot:
    """Load one, recomputing its checksum from the bytes on disk.

    ``expected_checksum`` is checked when given — a bundle names one, and
    the point of naming it is that a reader can disagree.
    """
    if not path.exists():
        raise SnapshotRefusal(
            f"no trait snapshot at {path}. A bundle that names a snapshot nobody "
            "can open is a bundle nobody can replay, however pinned it looks."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = tuple(
        TraitEntry(
            algorithm_id=row["algorithm_id"],
            kind=row.get("kind", "other"),
            strengths=tuple(row.get("strengths") or ()),
            weaknesses=tuple(row.get("weaknesses") or ()),
            anchor=row["anchor"],
            review_status=row.get("review_status", "none"),
            reviewed_by=row.get("reviewed_by", ""),
        )
        for row in payload.get("entries", ())
    )
    snapshot = TraitsSnapshot(revision_id=str(payload.get("revision_id", "")), entries=entries)
    if snapshot.checksum != _checksum_in_name(path):
        raise SnapshotRefusal(
            f"{path.name} does not hash to the name it is filed under; the content "
            "was edited in place, and every bundle citing it was graded against "
            "something else."
        )
    if expected_checksum and snapshot.checksum != expected_checksum:
        raise SnapshotRefusal(
            f"the snapshot at {path} hashes to {snapshot.checksum} and the bundle "
            f"names {expected_checksum}. A stored checksum is a claim; this is the "
            "reader disagreeing with it."
        )
    return snapshot


def delete_snapshot(path: Path, *, referenced_by: Collection[str] = ()) -> None:
    """Remove one, unless something still cites it."""
    if referenced_by:
        raise SnapshotRefusal(
            f"{path.name} is cited by {sorted(referenced_by)}. Deleting it leaves "
            "those bundles naming a document nobody can produce — an operational "
            "error with a name, not a tidy-up."
        )
    path.unlink(missing_ok=True)


def verify_snapshot(
    root: Path,
    *,
    revision_id: str,
    checksum: str,
    ref: str,
) -> TraitsSnapshot:
    """The triple, checked the way a gate has to check it.

    All three, because each one alone can be true while the pair is
    wrong: a ref that resolves to another revision, a checksum that
    matches a document the bundle does not name, an id that was reused.
    """
    snapshot = read_snapshot(root / Path(ref).name, expected_checksum=checksum)
    if snapshot.revision_id != revision_id:
        raise SnapshotRefusal(
            f"the snapshot at {ref} is revision {snapshot.revision_id!r} and the "
            f"bundle names {revision_id!r}; the content matched, which means the "
            "same rows were published twice under two decisions."
        )
    return snapshot


def _checksum_in_name(path: Path) -> str:
    name = path.name
    if not name.startswith("traits-") or not name.endswith(".json"):
        raise SnapshotRefusal(
            f"{name} is not a content-addressed snapshot name; the checksum has to "
            "be in the path, or an edit in place stays findable."
        )
    return name[len("traits-") : -len(".json")]


def entries_of(source: Iterable[TraitEntry]) -> tuple[TraitEntry, ...]:
    """Rows in the order the snapshot hashes them."""
    return tuple(sorted(source, key=lambda item: (item.algorithm_id, item.kind)))
