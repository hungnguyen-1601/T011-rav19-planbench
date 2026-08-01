"""Accounts, OAuth links, review requests; benchmark ownership.

Additive only. Existing benchmarks keep every column they had and gain
``owner_user_id`` as NULL, which the API reads as "created before
accounts existed" and falls back to matching ``created_by`` against the
signed-in nickname. Nothing is rewritten, so a downgrade loses only the
new tables and columns.

``users.nickname_key`` carries the unique index and holds the case-folded
nickname: a functional index on ``lower(nickname)`` exists on PostgreSQL
and not on SQLite, and this schema has to be the same on both.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(32)
TIMESTAMP = sa.String(40)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", ID, primary_key=True),
        sa.Column("nickname", sa.String(30), nullable=False),
        # Nullable so several accounts can sit in onboarding at once:
        # both backends treat multiple NULLs as distinct under a unique
        # index, an empty string would collide on the second one.
        sa.Column("nickname_key", sa.String(30), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("password_hash", sa.String(120), nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        sa.UniqueConstraint("nickname_key", name="uq_users_nickname_key"),
    )

    op.create_table(
        "oauth_accounts",
        sa.Column("id", ID, primary_key=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(200), nullable=False),
        sa.Column("provider_email", sa.String(320), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        # One provider identity, one PlanBench account.
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    op.create_table(
        "review_requests",
        sa.Column("id", ID, primary_key=True),
        sa.Column(
            "benchmark_id", ID, sa.ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("stage", sa.String(10), nullable=False),
        sa.Column("requested_by_user_id", ID, nullable=False),
        sa.Column("reviewer_user_id", ID, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("request_comment", sa.Text(), nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("reviewed_at", TIMESTAMP, nullable=True),
        sa.Column("cancelled_at", TIMESTAMP, nullable=True),
    )
    op.create_index("ix_review_requests_benchmark_id", "review_requests", ["benchmark_id"])
    op.create_index(
        "ix_review_requests_reviewer", "review_requests", ["reviewer_user_id", "status"]
    )
    op.create_index("ix_review_requests_requester", "review_requests", ["requested_by_user_id"])

    with op.batch_alter_table("benchmarks") as batch:
        batch.add_column(sa.Column("owner_user_id", ID, nullable=True))
    op.create_index("ix_benchmarks_owner", "benchmarks", ["owner_user_id"])

    with op.batch_alter_table("approvals") as batch:
        batch.add_column(sa.Column("user_id", ID, nullable=True))
        batch.add_column(sa.Column("review_request_id", ID, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("approvals") as batch:
        batch.drop_column("review_request_id")
        batch.drop_column("user_id")

    op.drop_index("ix_benchmarks_owner", table_name="benchmarks")
    with op.batch_alter_table("benchmarks") as batch:
        batch.drop_column("owner_user_id")

    op.drop_index("ix_review_requests_requester", table_name="review_requests")
    op.drop_index("ix_review_requests_reviewer", table_name="review_requests")
    op.drop_index("ix_review_requests_benchmark_id", table_name="review_requests")
    op.drop_table("review_requests")

    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")

    op.drop_table("users")
