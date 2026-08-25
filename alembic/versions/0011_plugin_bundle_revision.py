"""An imported bundle is identified by its archive, not by its label.

**What was wrong with keying on the manifest's version.** `0010` made
`(plugin_id, plugin_version)` unique, reasoning that two uploads claiming
one plugin version are two answers to "what produced this result?". The
reasoning was right and the column was wrong: the thing a candidate
actually hashes on is the **checksum of the archive**, and the manifest's
version is a label its author maintains by hand.

So the constraint refused the case it should have accepted — changed code
whose author had not bumped a number — and it made every edit begin with
opening `plugin.json`. That is the "a number a person maintains is a
number a person forgets" failure the source-checksum work elsewhere in
this repository exists to end, reappearing one table over.

Keyed on `(plugin_id, checksum)` instead, the rule says what it means:
the same bytes twice are one bundle, and different bytes are different
controllers whatever their manifests call themselves.

**`revision` replaces the version as the readable one.** Assigned by the
platform, counting the uploads of one plugin. Nothing hashes on it, so it
is free to be the legible thing the manifest version kept failing to be.
Existing rows are numbered by their creation order, which is what they
would have been given had this column existed when they arrived.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plugin_bundles",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )

    # Number what is already there by arrival order, per plugin. A single
    # UPDATE with a window function would not run on SQLite's older
    # builds, and this table is small enough that the readable form costs
    # nothing.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, plugin_id FROM plugin_bundles ORDER BY plugin_id, created_at")
    ).fetchall()
    counters: dict[str, int] = {}
    for row_id, plugin_id in rows:
        counters[plugin_id] = counters.get(plugin_id, 0) + 1
        connection.execute(
            sa.text("UPDATE plugin_bundles SET revision = :n WHERE id = :id"),
            {"n": counters[plugin_id], "id": row_id},
        )

    # SQLite cannot drop a constraint in place, so the table is rebuilt.
    with op.batch_alter_table("plugin_bundles") as batch:
        batch.drop_constraint("uq_plugin_bundles_identity", type_="unique")
        batch.create_unique_constraint(
            "uq_plugin_bundles_identity", ["plugin_id", "checksum"]
        )


def downgrade() -> None:
    with op.batch_alter_table("plugin_bundles") as batch:
        batch.drop_constraint("uq_plugin_bundles_identity", type_="unique")
        batch.create_unique_constraint(
            "uq_plugin_bundles_identity", ["plugin_id", "plugin_version"]
        )
    op.drop_column("plugin_bundles", "revision")
