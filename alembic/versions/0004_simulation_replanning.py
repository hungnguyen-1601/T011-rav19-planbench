"""Replanning rule on a single simulation.

Additive and nullable. Every simulation stored before this revision ran
without replanning — the code path did not exist — so NULL is not a
missing value to be filled in later, it is the recorded truth. The
repository reads NULL back as ``NO_REPLANNING`` for exactly that reason,
and a backfill would only replace a correct answer with a written-down
copy of the same answer.

The rule goes in its own column rather than into ``simulations.config``.
``config`` holds the algorithm's own parameters; replanning is a rule
imposed on the run, and the whole point of keeping it out of an
algorithm's config (see ``BenchmarkSpec.replanning``) is that no stack
can be granted it while another is denied it.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.add_column("simulations", sa.Column("replanning", JSON_TYPE, nullable=True))


def downgrade() -> None:
    op.drop_column("simulations", "replanning")
