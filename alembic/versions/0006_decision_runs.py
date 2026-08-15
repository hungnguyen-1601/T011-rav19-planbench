"""A run is the record; a card is something a run sometimes produces.

``0005`` gave the decision layer one table, ``decision_cards``, with
``card`` and ``recommended_candidate_id`` NOT NULL. That encodes an
assumption the decision layer exists to refuse: **that every evaluation
ends in a ranking.**

The first MVP run proved it wrong within a day. On the fairness reference
hall, three comparisons out of three produced no Decision Card, because a
card needs *two* candidates through all six gates and only one of four
got there. Those runs are not failures — each carries a full gate table
answering "who was eliminated where, after how many runs", which is the
question HĐ-12 puts on the card in the first place. Under ``0005`` not
one of them could be stored.

Two more artifacts appeared alongside the card and had no home either:
``comparison_report.json`` (every comparison, ranked or not) and
``measurement_report.json`` (one candidate, no comparison possible).

So the table turns around. ``decision_runs`` holds one row per run:

* ``report`` is NOT NULL — a run always produces evidence;
* ``card``, ``manifest``, ``recommended_candidate_id`` and ``status`` are
  NULL — a run *sometimes* produces a recommendation.

Reading it the other way round is what put the pressure on every run to
be rankable, and that pressure is what produced a card bounding a
collision probability off a single episode.

**Dropped rather than migrated.** ``decision_cards`` never had a
repository, a router or a row: nothing outside ``models.py`` referenced
it. Carrying an empty table forward under a name that describes the wrong
shape costs more than it saves.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")

ID_LENGTH = 32
TIMESTAMP_LENGTH = 40


def upgrade() -> None:
    op.drop_index("ix_decision_cards_status", table_name="decision_cards")
    op.drop_index("ix_decision_cards_recommended", table_name="decision_cards")
    op.drop_index("ix_decision_cards_task_profile", table_name="decision_cards")
    op.drop_table("decision_cards")

    op.create_table(
        "decision_runs",
        sa.Column("id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column(
            "task_profile_id",
            sa.String(ID_LENGTH),
            sa.ForeignKey("task_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Which of the three artifacts this run produced. Promoted to a
        # column because "show me the runs that could not be ranked" is a
        # question somebody asks on day one, and digging it out of a JSON
        # body would make it a scan.
        sa.Column("artifact_kind", sa.String(20), nullable=False),
        # HĐ-1.4. NULL for a measurement: one candidate licenses no
        # layer-scoped claim, so there is no scope to declare.
        sa.Column("experiment_scope", sa.String(40), nullable=True),
        sa.Column("contracts_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(TIMESTAMP_LENGTH), nullable=False),
        sa.Column("created_by", sa.String(ID_LENGTH), nullable=True),
        # The evidence. Always present, whatever the verdict.
        sa.Column("report", JSON_TYPE, nullable=False),
        # The recommendation, when the run supported one.
        sa.Column("card", JSON_TYPE, nullable=True),
        sa.Column("manifest", JSON_TYPE, nullable=True),
        sa.Column("recommended_candidate_id", sa.String(ID_LENGTH), nullable=True),
        sa.Column("status", sa.String(30), nullable=True),
        # Traces stay in the artifact store (D15); the checksum is what
        # makes the reference trustworthy rather than decorative.
        sa.Column("run_uri", sa.Text(), nullable=True),
        sa.Column("run_checksum", sa.String(64), nullable=True),
    )
    op.create_index("ix_decision_runs_task_profile", "decision_runs", ["task_profile_id"])
    op.create_index("ix_decision_runs_kind", "decision_runs", ["artifact_kind"])
    op.create_index("ix_decision_runs_recommended", "decision_runs", ["recommended_candidate_id"])
    op.create_index("ix_decision_runs_status", "decision_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_decision_runs_status", table_name="decision_runs")
    op.drop_index("ix_decision_runs_recommended", table_name="decision_runs")
    op.drop_index("ix_decision_runs_kind", table_name="decision_runs")
    op.drop_index("ix_decision_runs_task_profile", table_name="decision_runs")
    op.drop_table("decision_runs")

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
