"""Publishing an imported algorithm becomes an act somebody performs.

**What was wrong.** A bundle that validated was immediately in every
engineer's picker, and `_retire_previous()` disabled the revision it
replaced the moment the new one passed — so what the platform actually
ran changed because a *check* succeeded, with nobody deciding. That is
the failure the reviewer package exists to end: importing code and
vouching for it are two jobs, and only one of them is mechanical.

**Publications are a history, not a pointer.** The obvious shape is one
row per plugin holding "the current revision", upserted on publish. It
cannot answer the question that matters afterwards: an approval made
against revision 2 needs to know whether 2 was *retired by a newer
revision* — which says nothing about whether it was any good — or
*withdrawn* by a reviewer, which does. Upserting flattens both into the
same absence. So a publish inserts a row, supersedes the previous one by
stamping it, and an unpublish stamps a different column; "current" is the
row with neither stamp, guaranteed unique by a partial index.

`operational_status` gains a third value rather than a second column.
`held` is a reviewer pulling a bundle back temporarily; `disabled` is
terminal, because "turn it back on" and "upload the fixed one" should not
both exist — the second is honest about what changed. Adding a value to
the column that already answers "may this be picked?" keeps one answer in
one place; a parallel column would be a second one, free to disagree.

Nothing is backfilled into `plugin_publications`. Every bundle already
imported stays exactly as runnable as it is today — the resolver only
starts consulting publications when `PLANBENCH_ALGORITHM_GOVERNANCE` is
turned on — and at that point a reviewer publishes the revisions worth
keeping. Inventing publication rows here would forge a signature: the
table records that a person vouched for a revision, and a migration is
not a person.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(36)
TIMESTAMP = sa.String(40)


def upgrade() -> None:
    op.create_table(
        "plugin_publications",
        sa.Column("id", ID, primary_key=True),
        sa.Column("plugin_id", sa.String(200), nullable=False),
        sa.Column(
            "bundle_id",
            ID,
            sa.ForeignKey("plugin_bundles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("published_by_user_id", ID, nullable=True),
        sa.Column("published_at", TIMESTAMP, nullable=False),
        # Stamped when a *different* revision was published in its place.
        # Says nothing about the quality of this one.
        sa.Column("superseded_at", TIMESTAMP, nullable=True),
        # Stamped when a reviewer pulled this revision back. Does say
        # something about it, which is why the two are separate columns.
        sa.Column("unpublished_at", TIMESTAMP, nullable=True),
        sa.Column("unpublished_by_user_id", ID, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_plugin_publications_bundle", "plugin_publications", ["bundle_id"])
    # "Current" is the row with neither stamp. Unique per plugin, in the
    # database rather than in a service check, because two reviewers
    # publishing at once is exactly when it would matter.
    op.create_index(
        "uq_plugin_publication_current",
        "plugin_publications",
        ["plugin_id"],
        unique=True,
        sqlite_where=sa.text("superseded_at IS NULL AND unpublished_at IS NULL"),
        postgresql_where=sa.text("superseded_at IS NULL AND unpublished_at IS NULL"),
    )

    op.create_table(
        "plugin_events",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bundle_id", ID, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actor_user_id", ID, nullable=True),
        sa.Column("actor_roles", sa.String(120), nullable=False, server_default=""),
        sa.Column("authorized_capability", sa.String(40), nullable=False, server_default=""),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_plugin_events_bundle", "plugin_events", ["bundle_id"])

    op.add_column("plugin_bundles", sa.Column("disabled_at", TIMESTAMP, nullable=True))
    op.add_column("plugin_bundles", sa.Column("disabled_by_user_id", ID, nullable=True))
    op.add_column(
        "plugin_bundles", sa.Column("disabled_reason", sa.Text(), nullable=False, server_default="")
    )


def downgrade() -> None:
    op.drop_column("plugin_bundles", "disabled_reason")
    op.drop_column("plugin_bundles", "disabled_by_user_id")
    op.drop_column("plugin_bundles", "disabled_at")
    op.drop_index("ix_plugin_events_bundle", table_name="plugin_events")
    op.drop_table("plugin_events")
    op.drop_index("uq_plugin_publication_current", table_name="plugin_publications")
    op.drop_index("ix_plugin_publications_bundle", table_name="plugin_publications")
    op.drop_table("plugin_publications")
