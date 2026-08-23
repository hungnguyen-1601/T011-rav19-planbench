"""A map can be pinned against the orphan sweep.

**What the sweep is for.** Maps arrive faster than anyone deletes them:
importing a library scenario stores a fresh map every call, so one
database held 198 map rows carrying 41 distinct checksums, 117 of them
the same `static-obstacles` grid stored over and over. Almost none of
them were reachable — 165 were held alive only by a scenario that
nothing simulated or benchmarked — but "unreachable" is not the same
claim as "unwanted", and a sweep that cannot tell them apart is a sweep
nobody will run twice.

**So the column, and so its default.** `kept` is the author saying this
map matters regardless of what currently points at it — a hall they
drew, a case they will come back to. The sweep skips those and takes the
rest.

The default is `false`, and that is the decision worth writing down.
Marking every existing row as kept would be the cautious-looking choice
and would make the first sweep delete nothing at all, leaving a column
that only ever describes what somebody has already lost. Nothing is
destroyed by defaulting to `false` either: the sweep runs dry unless a
caller asks for the delete, and pinning is one click on a map that is
still there.

`server_default` rather than a Python-side default, because the rows
already on disk need a value and the schema has to give them one: a
NOT NULL column added to a populated table with no server default does
not apply.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maps",
        sa.Column("kept", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("maps", "kept")
