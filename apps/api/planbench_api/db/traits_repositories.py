"""Algorithm natures, from the table into the shape both lanes read — W1.4.

M3 gave the natures a table (``algorithm_traits``, migration 0012) and
:mod:`planbench_benchmark.traits_store` gave them a shape. Nothing joined
the two: every reader still got ``SHIPPED_TRAITS``, the constant seeded
*from* Python, so an imported algorithm's row could be written through
the API and then read by nobody. A table one half of the platform writes
and the other half cannot see is worse than no table — it looks like the
feature is there.

Three properties this reader has to keep, because they are the reasons
the rows are worth having:

**One source, two readers.** The advisory rules (Lane 1) and the analyst
(Lane 2) take the same :class:`TraitSource`. Two loaders with two
filters would be two tables again, disagreeing in the one place a reader
would never look — the explanation.

**A row that will not parse is refused, not skipped.** A row whose
anchor was emptied, or whose ``review_status`` is a word nobody
enumerated, is a row somebody edited into a state the platform does not
model. Dropping it quietly turns "this algorithm is described" into
"nobody has described it", which is the sentence the store exists to
keep separable.

**The catalog is the whole table.** :meth:`SqlTraitRepository.load` takes
no filter on purpose: what a bundle is graded against, and what W1.8
will hash into a snapshot, is *everything the analyst could have
reached*. A per-packet subset would give one bundle two checksums on two
packets.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planbench_api.db.models import AlgorithmTraitRow
from planbench_api.db.session import SessionFactory
from planbench_benchmark.traits_store import TraitEntry, TraitRefusal, TraitSource

__all__ = ["SqlTraitRepository", "entry_from_row", "row_from_entry"]


def entry_from_row(row: AlgorithmTraitRow) -> TraitEntry:
    """One stored row as the entry both lanes read.

    ``strengths`` and ``weaknesses`` are JSON columns, so what comes back
    is whatever was written. They are coerced to strings here rather than
    trusted: a number that reached the column would otherwise arrive in a
    prompt as a nature, and ``extra="forbid"`` on the model would raise
    somewhere far from the row that caused it.
    """
    return TraitEntry(
        algorithm_id=row.algorithm_id,
        kind=row.kind,  # type: ignore[arg-type]
        strengths=tuple(str(item) for item in (row.strengths or ())),
        weaknesses=tuple(str(item) for item in (row.weaknesses or ())),
        anchor=row.anchor,
        review_status=row.review_status,  # type: ignore[arg-type]
        reviewed_by=row.reviewed_by,
        updated_at=row.updated_at,
    )


def row_from_entry(entry: TraitEntry) -> AlgorithmTraitRow:
    """The entry as a row, for a seed or a write."""
    return AlgorithmTraitRow(
        algorithm_id=entry.algorithm_id,
        kind=entry.kind,
        strengths=list(entry.strengths),
        weaknesses=list(entry.weaknesses),
        anchor=entry.anchor,
        review_status=entry.review_status,
        reviewed_by=entry.reviewed_by,
        updated_at=entry.updated_at,
    )


class SqlTraitRepository:
    """The ``algorithm_traits`` table, as a :class:`TraitSource`."""

    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def load(self) -> TraitSource:
        """Every row in the table, in one source.

        Sorted by ``algorithm_id`` so two loads of one revision produce
        the same order — the snapshot W1.8 hashes is over content, and a
        content hash whose input order depends on the database's mood is
        a checksum that changes for no reason anybody can name.
        """
        with self._sessions.begin() as session:
            return TraitSource(self._entries(session))

    def get(self, algorithm_id: str) -> TraitEntry | None:
        with self._sessions.begin() as session:
            row = session.get(AlgorithmTraitRow, algorithm_id)
            return None if row is None else entry_from_row(row)

    def save(self, entry: TraitEntry) -> TraitEntry:
        """Write one row, replacing what was there under that id.

        Validation is the entry's, and it has already happened by the
        time this is called: an approved row with nobody named on it, or
        with nothing said in it, cannot be constructed. What is enforced
        here is only that the write lands as one row per algorithm.
        """
        with self._sessions.begin() as session:
            row = session.get(AlgorithmTraitRow, entry.algorithm_id)
            if row is None:
                session.add(row_from_entry(entry))
            else:
                row.kind = entry.kind
                row.strengths = list(entry.strengths)
                row.weaknesses = list(entry.weaknesses)
                row.anchor = entry.anchor
                row.review_status = entry.review_status
                row.reviewed_by = entry.reviewed_by
                row.updated_at = entry.updated_at
        return entry

    def seed(self, entries: tuple[TraitEntry, ...]) -> int:
        """Insert the rows that are not there yet. Returns how many.

        Existing rows are left alone — a seed that overwrote them would
        undo a review, which is the one thing in this table a person did
        by hand.
        """
        written = 0
        with self._sessions.begin() as session:
            present = {
                row.algorithm_id for row in session.execute(select(AlgorithmTraitRow)).scalars()
            }
            for entry in entries:
                if entry.algorithm_id in present:
                    continue
                session.add(row_from_entry(entry))
                written += 1
        return written

    @staticmethod
    def _entries(session: Session) -> tuple[TraitEntry, ...]:
        rows = (
            session.execute(select(AlgorithmTraitRow).order_by(AlgorithmTraitRow.algorithm_id))
            .scalars()
            .all()
        )
        entries: list[TraitEntry] = []
        for row in rows:
            try:
                entries.append(entry_from_row(row))
            except (TraitRefusal, ValueError) as refusal:
                # Refused rather than skipped: a dropped row reads
                # downstream as "nobody has described this algorithm",
                # which is a different and more flattering sentence than
                # "somebody described it and the description is broken".
                raise TraitRefusal(
                    f"trait row {row.algorithm_id!r} cannot be read: {refusal}. A row "
                    "left out here would be read as an algorithm nobody described."
                ) from refusal
        return tuple(entries)
