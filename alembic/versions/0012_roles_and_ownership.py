"""Roles come back, as capability packages rather than as a rank.

**What this replaces.** Authority used to be ownership alone, with one
boolean — ``users.is_admin`` — bolted beside it for two unrelated jobs
(importing a plugin, writing an API key). Ownership answers *which
record*; nothing answered *which kind of action*, and the visible cost
was that any signed-in account could approve somebody else's decision
run. HĐ-14 as of contract 7.0.0 defines three packages that do not nest,
so this table is a set per user, not a column.

**Why a table and not a column.** A column forces a rank, and there is
no rank here: an administrator holds no business capability at all, and
a reviewer is not an engineer with extras. Somebody doing two jobs holds
two rows, and each audit entry records which capability authorised the
act rather than the caller's "highest" role, because highest is not a
thing.

``demo_owner`` gets a partial unique index rather than a check in
service code alone. It carries every capability at once, so "exactly one
of these exists" has to be a guarantee the database makes, not one a
race can slip past.

**Backfill is deliberately narrow.** Every existing account becomes an
engineer, and the admins become admins as well — that is what the old
boolean meant. Nobody is made a reviewer: the whole point of the package
is that somebody decided to grant it, and inventing reviewers from a
column that never meant that would put signatures on a queue nobody
agreed to hold. Deployments that need one grant it (a desktop install
does so on every launch, from its profile).

``users.is_admin`` is left in place and stops being read or written. It
goes in a later migration, once nothing in a rolled-back copy of the app
would look for it.

The ownership and archive columns land here too, because they answer the
second question in the same check: ``resource.write`` says an engineer
may edit maps, ``owner_user_id`` says which ones. ``archived_at``
exists so "remove this from my list" stops being a DELETE — an audit
trail that points at rows somebody deleted is a trail with holes.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(36)
TIMESTAMP = sa.String(32)


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        # Who granted it, and why. Empty for the backfill and for grants
        # a deployment profile reconciles on every launch; an
        # administrator acting through the UI must supply a reason.
        sa.Column("granted_by_user_id", ID, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("granted_at", TIMESTAMP, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role", name="pk_user_roles"),
    )
    op.create_index("ix_user_roles_role", "user_roles", ["role"])
    # One demo owner per database, enforced where a race cannot get past
    # it. SQLite and PostgreSQL both support partial indexes.
    op.create_index(
        "uq_single_demo_owner",
        "user_roles",
        ["role"],
        unique=True,
        sqlite_where=sa.text("role = 'demo_owner'"),
        postgresql_where=sa.text("role = 'demo_owner'"),
    )

    op.add_column("users", sa.Column("disabled_at", TIMESTAMP, nullable=True))
    op.add_column("users", sa.Column("last_sign_in_at", TIMESTAMP, nullable=True))

    op.create_table(
        "account_events",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        # The account acted upon, and the account that acted. They differ
        # for every grant and every disable, which is the point.
        sa.Column("user_id", ID, nullable=False),
        sa.Column("actor_user_id", ID, nullable=True),
        # A snapshot, comma separated: the caller's roles at the time.
        # Stored rather than joined because a role revoked next week must
        # not rewrite what last week's entry says.
        sa.Column("actor_roles", sa.String(120), nullable=False, server_default=""),
        sa.Column("authorized_capability", sa.String(40), nullable=False, server_default=""),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("previous", sa.Text(), nullable=False, server_default=""),
        sa.Column("new", sa.Text(), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("override", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_account_events_user", "account_events", ["user_id"])

    op.add_column("maps", sa.Column("owner_user_id", ID, nullable=True))
    op.add_column("maps", sa.Column("archived_at", TIMESTAMP, nullable=True))
    op.add_column("scenarios", sa.Column("owner_user_id", ID, nullable=True))
    op.add_column("scenarios", sa.Column("archived_at", TIMESTAMP, nullable=True))
    op.add_column("task_profiles", sa.Column("archived_at", TIMESTAMP, nullable=True))
    # A reference deployment is one a reviewer validates a plugin
    # against. It has no owner and refuses to be edited, and neither of
    # those follows from ``owner_user_id IS NULL`` — that already means
    # "made before accounts existed", which is shared, not immutable.
    op.add_column(
        "task_profiles",
        sa.Column("is_reference", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    connection = op.get_bind()
    stamp = datetime.now(UTC).isoformat()
    rows = connection.execute(sa.text("SELECT id, is_admin FROM users")).fetchall()
    for user_id, is_admin in rows:
        grants = ["engineer"]
        if is_admin:
            grants.append("admin")
        for role in grants:
            connection.execute(
                sa.text(
                    "INSERT INTO user_roles (user_id, role, granted_by_user_id, reason, granted_at)"
                    " VALUES (:user_id, :role, NULL, :reason, :granted_at)"
                ),
                {
                    "user_id": user_id,
                    "role": role,
                    "reason": "granted by migration 0012 from the pre-role account model",
                    "granted_at": stamp,
                },
            )


def downgrade() -> None:
    op.drop_column("task_profiles", "is_reference")
    op.drop_column("task_profiles", "archived_at")
    op.drop_column("scenarios", "archived_at")
    op.drop_column("scenarios", "owner_user_id")
    op.drop_column("maps", "archived_at")
    op.drop_column("maps", "owner_user_id")
    op.drop_index("ix_account_events_user", table_name="account_events")
    op.drop_table("account_events")
    op.drop_column("users", "last_sign_in_at")
    op.drop_column("users", "disabled_at")
    op.drop_index("uq_single_demo_owner", table_name="user_roles")
    op.drop_index("ix_user_roles_role", table_name="user_roles")
    op.drop_table("user_roles")
