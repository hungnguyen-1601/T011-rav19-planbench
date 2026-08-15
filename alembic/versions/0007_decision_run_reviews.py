"""Two human acts, kept apart: reading a run, and deploying its answer.

Phase 6.3 wires HĐ-14's approval flow to the decision layer. The obvious
shape — one ``approved`` flag on ``decision_runs`` — is the one that
cannot be right, and the reason is the same one that turned ``0005``
around at ``0006``: **most runs produce no recommendation.**

Four of the first five comparisons ended with no Decision Card. A single
approval column forces one of two answers for those rows, and both are
wrong:

* let them be approved — and ``approved`` now means "somebody read the
  gate table" on one row and "this is the configuration we deploy" on the
  next, with nothing in the column to say which;
* forbid them entirely — and a run that eliminated four candidates has
  nowhere to record that anybody ever looked at it, which is exactly how
  it becomes the artifact nobody remembers.

So two columns, answering two questions:

* ``review_state`` — has a human read this run's evidence? Applies to
  **every** run, ranked or not.
* ``config_state`` — is this run's recommendation the configuration we
  deploy? ``not_applicable`` where there is no card, and that value is
  the structural refusal: approving an unranked run is not blocked by a
  check somewhere, it is unreachable from the state it starts in.

Both NOT NULL with the conservative default, so a row written by any path
that has not heard of these columns lands unreviewed and unapprovable
rather than the reverse.

``decision_run_reviews`` is a new table rather than a widened
``approvals``: that table's ``benchmark_id`` is a NOT NULL foreign key
into ``benchmarks``, and making it nullable to fit both kinds would leave
every historical audit row unable to say which kind it described.

**Backfill.** Existing rows get ``config_state = 'pending'`` where a card
is present and ``'not_applicable'`` where it is not — the same rule the
application applies on insert, so old rows and new ones mean the same
thing. Nothing is backfilled into ``review_state``: nobody has reviewed
anything yet, and stamping rows as read would be inventing an audit
record.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_LENGTH = 32
TIMESTAMP_LENGTH = 40


def upgrade() -> None:
    op.add_column(
        "decision_runs",
        sa.Column("review_state", sa.String(20), nullable=False, server_default="unreviewed"),
    )
    op.add_column("decision_runs", sa.Column("reviewed_by", sa.String(ID_LENGTH), nullable=True))
    op.add_column(
        "decision_runs", sa.Column("reviewed_at", sa.String(TIMESTAMP_LENGTH), nullable=True)
    )
    op.add_column(
        "decision_runs",
        sa.Column("config_state", sa.String(20), nullable=False, server_default="not_applicable"),
    )
    op.add_column(
        "decision_runs", sa.Column("config_decided_by", sa.String(ID_LENGTH), nullable=True)
    )
    op.add_column(
        "decision_runs", sa.Column("config_decided_at", sa.String(TIMESTAMP_LENGTH), nullable=True)
    )

    # A run that already has a card is awaiting a decision, not exempt
    # from one. Same rule the application uses on insert.
    op.execute("UPDATE decision_runs SET config_state = 'pending' WHERE card IS NOT NULL")

    op.create_index("ix_decision_runs_review_state", "decision_runs", ["review_state"])
    op.create_index("ix_decision_runs_config_state", "decision_runs", ["config_state"])

    op.create_table(
        "decision_run_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.String(ID_LENGTH),
            sa.ForeignKey("decision_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Explicit order: two events can share a timestamp at whatever
        # resolution the clock has. Same reason `approvals.sequence` exists.
        sa.Column("sequence", sa.Integer(), nullable=False),
        # `review` | `approve_config` | `reject_config`.
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_user_id", sa.String(ID_LENGTH), nullable=True),
        # Nickname at the time of the act, readable after a rename.
        sa.Column("username", sa.String(100), nullable=False),
        # Both ends: "approved" alone does not say what it replaced.
        sa.Column("previous_state", sa.String(20), nullable=False),
        sa.Column("new_state", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(TIMESTAMP_LENGTH), nullable=False),
    )
    op.create_index("ix_decision_run_reviews_run", "decision_run_reviews", ["run_id", "sequence"])


def downgrade() -> None:
    op.drop_index("ix_decision_run_reviews_run", table_name="decision_run_reviews")
    op.drop_table("decision_run_reviews")

    op.drop_index("ix_decision_runs_config_state", table_name="decision_runs")
    op.drop_index("ix_decision_runs_review_state", table_name="decision_runs")
    op.drop_column("decision_runs", "config_decided_at")
    op.drop_column("decision_runs", "config_decided_by")
    op.drop_column("decision_runs", "config_state")
    op.drop_column("decision_runs", "reviewed_at")
    op.drop_column("decision_runs", "reviewed_by")
    op.drop_column("decision_runs", "review_state")
