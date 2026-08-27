"""Algorithm natures as a table somebody can edit, not a dict in a file.

``TRAITS`` in :mod:`planbench_benchmark.outcome` was written for the
algorithms this platform shipped with. Since the import feature landed,
the platform runs algorithms nobody here has heard of — and a nature
table that can only be extended by editing Python and redeploying is a
table that will simply have no row for them. The outcome rules then pair
a real number with an empty nature and say nothing.

So the natures move into a table, and this module is the shape they
travel in. Three rules survive the move, and they are the reason the
table is worth having rather than a free-text field:

**Every trait names its anchor.** A registry flag, or the algorithm's
defining mechanics. A trait table with no anchors is the model's
folklore in a constant's clothing, and folklore is exactly what a reader
cannot check.

**Unreviewed is not absent, and absent is not "no weaknesses".**
``review_status`` starts at ``none`` for a row created by an import.
A row nobody has reviewed may inform a hypothesis and may not promote a
claim — the same rule the knowledge base runs under. And an algorithm
with no row at all is one nobody has described, which a reader must be
told rather than left to read as a clean bill of health.

**One source, two readers.** The advisory rules (Lane 1) and the analyst
(Lane 2) read the same rows. Two tables of natures would disagree, and
the disagreement would surface as two different explanations of one run.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "TraitEntry",
    "TraitRefusal",
    "TraitSource",
    "entries_from_mapping",
    "mapping_from_entries",
]


class TraitRefusal(ValueError):
    """A trait row this platform will not serve."""


ReviewStatus = Literal["none", "draft", "approved", "withdrawn"]


class TraitEntry(BaseModel):
    """What one algorithm is known for, and who says so."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm_id: str = Field(min_length=1)
    kind: Literal["global", "local", "other"] = "other"
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    #: Where the claim can be checked. **Required**: a nature with no
    #: anchor is folklore, and folklore in a table looks exactly like a
    #: measurement to whoever reads it next.
    anchor: str = Field(min_length=1)
    review_status: ReviewStatus = "none"
    reviewed_by: str = ""
    updated_at: str = ""

    @model_validator(mode="after")
    def _check(self) -> TraitEntry:
        if self.review_status == "approved" and not self.reviewed_by:
            raise TraitRefusal(
                f"trait row {self.algorithm_id!r} is approved and names nobody; an "
                "approval nobody signed is an approval nobody is accountable for"
            )
        if self.review_status == "approved" and not (self.strengths or self.weaknesses):
            raise TraitRefusal(
                f"trait row {self.algorithm_id!r} is approved and says nothing about "
                "the algorithm; there is nothing there to have reviewed"
            )
        return self

    @property
    def may_support_a_claim(self) -> bool:
        """Only an approved row may back a promoted claim.

        The same rule the knowledge base runs under, and for the same
        reason: a sentence somebody typed and nobody checked is a
        hypothesis, however true it happens to be.
        """
        return self.review_status == "approved"

    def as_source_block(self) -> dict[str, Any]:
        """The shape the advisory rules already cite paths into.

        Kept identical to the old dict so ``outcome.py`` and everything
        rendering its ``field_path`` values carry on working: a move
        between storage layers must not move the citations.
        """
        return {
            "kind": self.kind,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "anchor": self.anchor,
            "review_status": self.review_status,
        }


#: What a reader is handed for an algorithm nobody has described. Not an
#: empty dict: "nobody wrote this down" and "this algorithm has no
#: weaknesses" are different sentences, and only one of them is ever true.
UNDESCRIBED: dict[str, Any] = {
    "kind": "other",
    "strengths": [],
    "weaknesses": [],
    "anchor": "",
    "review_status": "undescribed",
    "note": "no trait row exists for this algorithm; nobody has described it here",
}


class TraitSource:
    """Rows in memory, however they were loaded.

    A plain object rather than a protocol with one implementation: the
    database reader builds one of these, the seed builds one of these,
    and both readers below take the same thing.
    """

    def __init__(self, entries: Iterable[TraitEntry] = ()) -> None:
        self._by_id = {entry.algorithm_id: entry for entry in entries}

    def __contains__(self, algorithm_id: object) -> bool:
        return isinstance(algorithm_id, str) and algorithm_id in self._by_id

    def get(self, algorithm_id: str) -> TraitEntry | None:
        return self._by_id.get(algorithm_id)

    def block(self, algorithm_id: str) -> dict[str, Any]:
        """The citable block for one algorithm, described or not."""
        entry = self._by_id.get(algorithm_id)
        return entry.as_source_block() if entry is not None else dict(UNDESCRIBED)

    @property
    def entries(self) -> tuple[TraitEntry, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))


def entries_from_mapping(mapping: Mapping[str, Mapping[str, Any]]) -> tuple[TraitEntry, ...]:
    """Read the shipped ``TRAITS`` dict as rows, for the migration's seed."""
    rows: list[TraitEntry] = []
    for algorithm_id, payload in sorted(mapping.items()):
        anchor = str(payload.get("anchor") or "")
        if not anchor:
            raise TraitRefusal(
                f"{algorithm_id!r} has no anchor; it cannot become a row, because a "
                "nature with nowhere to check it is folklore"
            )
        rows.append(
            TraitEntry(
                algorithm_id=algorithm_id,
                kind=payload.get("kind", "other"),  # type: ignore[arg-type]
                strengths=tuple(payload.get("strengths") or ()),
                weaknesses=tuple(payload.get("weaknesses") or ()),
                anchor=anchor,
                # The shipped table was written by this project and
                # reviewed by whoever merged it, which is not the same
                # as somebody signing it as a trait row. It seeds as
                # ``draft`` and a human moves it, exactly as KB v1 does.
                review_status="draft",
            )
        )
    return tuple(rows)


def mapping_from_entries(entries: Iterable[TraitEntry]) -> dict[str, dict[str, Any]]:
    """Rows back into the dict shape the advisory rules read."""
    return {entry.algorithm_id: entry.as_source_block() for entry in entries}
