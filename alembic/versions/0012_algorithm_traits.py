"""Algorithm natures get a table somebody can edit.

**Why a table at all.** ``TRAITS`` in ``planbench_benchmark.outcome`` was
written for the algorithms this platform shipped with. Since the import
feature landed the platform runs algorithms nobody here has heard of, and
a nature table that can only be extended by editing Python and
redeploying is a table that will simply have no row for them: the outcome
rules then pair a real number with an empty nature and say nothing at
all about it.

**`anchor` is NOT NULL, and that is the point.** A nature with nowhere
to check it is folklore, and folklore in a database column looks exactly
like a measurement to whoever reads it next. Every row names where the
claim can be checked — a registry flag, or the algorithm's defining
mechanics.

**The seed lands as `draft`, not `approved`.** The shipped table was
written by this project and reviewed by whoever merged it, which is not
the same as somebody signing it as a trait row. Only an approved row may
back a promoted claim, the same rule the knowledge base runs under, so
seeding as approved would grant that on nobody's signature.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-26
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def _seed_rows() -> list[dict[str, object]]:
    """The shipped natures, read from the module that already holds them.

    Imported here rather than copied into this file: a migration that
    restated the table would be a second list of natures, free to
    disagree with the one the rules read on any machine that has not run
    the migration yet.
    """
    from planbench_benchmark.outcome import TRAITS
    from planbench_benchmark.traits_store import entries_from_mapping

    return [
        {
            "algorithm_id": entry.algorithm_id,
            "kind": entry.kind,
            "strengths": json.dumps(list(entry.strengths), ensure_ascii=False),
            "weaknesses": json.dumps(list(entry.weaknesses), ensure_ascii=False),
            "anchor": entry.anchor,
            "review_status": "draft",
            "reviewed_by": "",
        }
        for entry in entries_from_mapping(TRAITS)
    ]


def upgrade() -> None:
    table = op.create_table(
        "algorithm_traits",
        sa.Column("algorithm_id", sa.String(120), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="other"),
        sa.Column("strengths", JSON_TYPE, nullable=False, server_default="[]"),
        sa.Column("weaknesses", JSON_TYPE, nullable=False, server_default="[]"),
        # Not nullable, and no default: a row that arrives without an
        # anchor is a row nobody can check, and the write is where that
        # has to be refused rather than at read time.
        sa.Column("anchor", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False, server_default="none"),
        sa.Column("reviewed_by", sa.String(120), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "review_status in ('none','draft','approved','withdrawn')",
            name="ck_algorithm_traits_review_status",
        ),
        sa.CheckConstraint("length(anchor) > 0", name="ck_algorithm_traits_anchor_present"),
    )
    op.bulk_insert(table, _seed_rows())


def downgrade() -> None:
    op.drop_table("algorithm_traits")
