"""Restore per-user role: an Engineer runs benchmarks, an Approver reviews them.

Additive only. ``server_default='engineer'`` means existing rows and any
insert that forgets the column get a valid, unprivileged role rather than
NULL — nobody is silently promoted to Approver by a migration.

``is_admin`` is untouched: it stays the separate operational-recovery
override it already was, not a third role.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "role",
                sa.String(20),
                nullable=False,
                server_default="engineer",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("role")
