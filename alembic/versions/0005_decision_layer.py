"""Task profiles, candidates and decision cards (CONTRACTS HĐ-2, HĐ-1, HĐ-12/13).

Three new tables, no change to any existing one. The decision layer was
built as pure functions over files under ``artifacts/runs/``; this is the
first revision that lets a run be stored and looked up, which is what the
API needs before it can serve a card it did not just compute.

**Bodies as JSON, not as columns.** ``TaskProfile``, ``Candidate`` and
the card are frozen Pydantic models that the decision layer validates on
the way in. Shredding them into columns would create a second definition
of each contract, in DDL, that drifts from the first — exactly what §16
puts one owner on each schema to prevent. Only the fields a query needs
are promoted: ids, environment, stack label, status.

**``candidate_id`` is the primary key of ``candidates``** rather than a
surrogate. HĐ-1.3 makes it a hash of everything that defines the
configuration, so two rows with the same id *are* the same candidate; an
autoincrement key would let one stack be registered twice under two
names and split its own history.

**Traces stay out of the database (D15).** A card and its manifest are a
few kilobytes and are the deliverable. The Parquet traces behind them are
megabytes per episode and stay in the artifact store, referenced by
``run_uri`` with a ``run_checksum`` beside it — a URI on its own cannot
say that the files it points at are the ones the card was computed from.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")

ID_LENGTH = 32
TIMESTAMP_LENGTH = 40


def upgrade() -> None:
    op.create_table(
        "task_profiles",
        sa.Column("id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column("environment", sa.String(200), nullable=False),
        sa.Column("owner_user_id", sa.String(ID_LENGTH), nullable=True),
        sa.Column("created_at", sa.String(TIMESTAMP_LENGTH), nullable=False),
        sa.Column("profile", JSON_TYPE, nullable=False),
    )
    op.create_index("ix_task_profiles_owner", "task_profiles", ["owner_user_id"])

    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("stack_label", sa.String(200), nullable=False),
        sa.Column("registered_by", sa.String(ID_LENGTH), nullable=True),
        sa.Column("created_at", sa.String(TIMESTAMP_LENGTH), nullable=False),
        sa.Column("spec", JSON_TYPE, nullable=False),
        sa.Column("tuning", JSON_TYPE, nullable=True),
    )
    op.create_index("ix_candidates_stack_label", "candidates", ["stack_label"])

    op.create_table(
        "decision_cards",
        sa.Column("id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column(
            "task_profile_id",
            sa.String(ID_LENGTH),
            sa.ForeignKey("task_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recommended_candidate_id", sa.String(ID_LENGTH), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("contracts_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(TIMESTAMP_LENGTH), nullable=False),
        sa.Column("created_by", sa.String(ID_LENGTH), nullable=True),
        sa.Column("card", JSON_TYPE, nullable=False),
        sa.Column("manifest", JSON_TYPE, nullable=False),
        sa.Column("run_uri", sa.Text(), nullable=True),
        sa.Column("run_checksum", sa.String(64), nullable=True),
    )
    op.create_index("ix_decision_cards_task_profile", "decision_cards", ["task_profile_id"])
    op.create_index("ix_decision_cards_recommended", "decision_cards", ["recommended_candidate_id"])
    op.create_index("ix_decision_cards_status", "decision_cards", ["status"])


def downgrade() -> None:
    # Cards first: they hold the foreign key into task_profiles.
    op.drop_index("ix_decision_cards_status", table_name="decision_cards")
    op.drop_index("ix_decision_cards_recommended", table_name="decision_cards")
    op.drop_index("ix_decision_cards_task_profile", table_name="decision_cards")
    op.drop_table("decision_cards")

    op.drop_index("ix_candidates_stack_label", table_name="candidates")
    op.drop_table("candidates")

    op.drop_index("ix_task_profiles_owner", table_name="task_profiles")
    op.drop_table("task_profiles")
