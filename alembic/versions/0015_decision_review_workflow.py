"""Review becomes claim-then-acknowledge, and stops being benchmark-only.

**Three separate problems, one table.**

*A request could only ever be about a benchmark.* ``benchmark_id`` was a
NOT NULL foreign key, so decision runs — the lane that replaced
benchmarks — had no way to be sent to anybody. ``subject_kind`` plus
``subject_id`` fixes that, at the cost of the database no longer
enforcing that the subject exists; the service does, inside the
transaction that creates the request. The trade is worth making because
the alternative was a second, near-identical table.

*"Who is this waiting on?" and "who did the engineer ask for?" were one
column.* ``reviewer_user_id`` meant both, so a reviewer who claimed a
request and then released it left the request looking as though it were
still addressed to them, and nobody else could pick it up. They are now
``requested_reviewer_user_id`` — what the engineer asked for, kept
forever because it is part of what they said — and ``claimed_by_user_id``,
which is where it is now.

*Neither said whether anybody else could take it.* A directed request
that its reviewer released, and a directed request whose reviewer left
the deployment, both need to become available without erasing who was
asked. ``available_to_pool`` is that answer, stated rather than inferred
from the other two — inferring it is what produced the stuck-request bug
in the first place.

**The benchmark lane keeps its old rules.** Rows backfill to
``subject_kind='benchmark'`` and ``available_to_pool=false``, and the
service refuses claim and takeover on them. Rewriting the rules a stored
benchmark was decided under would make its audit trail describe a
process that never happened.

SQLite cannot drop a NOT NULL foreign key in place, so the table is
recreated with ``batch_alter_table``.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(36)
TIMESTAMP = sa.String(40)


def upgrade() -> None:
    with op.batch_alter_table("review_requests", recreate="always") as batch:
        # The subject is no longer always a benchmark, so the column that
        # named one stops being mandatory. Kept rather than dropped: a
        # benchmark request still fills it, and it is still the foreign
        # key that makes deleting a benchmark take its requests with it.
        batch.alter_column("benchmark_id", existing_type=ID, nullable=True)
        batch.alter_column("reviewer_user_id", existing_type=ID, nullable=True)
        batch.add_column(
            sa.Column("subject_kind", sa.String(20), nullable=False, server_default="benchmark")
        )
        batch.add_column(sa.Column("subject_id", ID, nullable=True))
        batch.add_column(sa.Column("requested_reviewer_user_id", ID, nullable=True))
        batch.add_column(sa.Column("claimed_by_user_id", ID, nullable=True))
        batch.add_column(sa.Column("claimed_at", TIMESTAMP, nullable=True))
        batch.add_column(
            sa.Column(
                "available_to_pool", sa.Boolean(), nullable=False, server_default=sa.text("0")
            )
        )

    connection = op.get_bind()
    # The old columns keep their meaning where they had one: the subject
    # was always a benchmark, and the named reviewer was always what the
    # requester asked for.
    connection.execute(
        sa.text(
            "UPDATE review_requests SET subject_id = benchmark_id, "
            "requested_reviewer_user_id = reviewer_user_id, subject_kind = 'benchmark'"
        )
    )
    op.create_index(
        "ix_review_requests_subject", "review_requests", ["subject_kind", "subject_id", "status"]
    )

    op.add_column(
        "decision_runs", sa.Column("current_review_request_id", ID, nullable=True)
    )


def downgrade() -> None:
    op.drop_column("decision_runs", "current_review_request_id")
    op.drop_index("ix_review_requests_subject", table_name="review_requests")
    with op.batch_alter_table("review_requests", recreate="always") as batch:
        batch.drop_column("available_to_pool")
        batch.drop_column("claimed_at")
        batch.drop_column("claimed_by_user_id")
        batch.drop_column("requested_reviewer_user_id")
        batch.drop_column("subject_id")
        batch.drop_column("subject_kind")
        batch.alter_column("reviewer_user_id", existing_type=ID, nullable=False)
        batch.alter_column("benchmark_id", existing_type=ID, nullable=False)
