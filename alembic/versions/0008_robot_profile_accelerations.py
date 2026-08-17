"""Acceleration limits on a robot profile.

**Why the vehicle needed two more columns.** A deployment's robot is a
`TaskRobotSpec`, and `RobotConfig` requires both accelerations — the
simulator clamps every command against them. A robot profile could not
express either, so the one place the platform records *vehicles* could
not describe a vehicle completely enough to deploy it. Anybody filling a
deployment form had to type those two numbers from memory, which is how
one hall ends up measured on a robot that accelerates twice as hard as
the warehouse's copy of the same robot.

**Additive and nullable, and NULL is the answer rather than a hole.** A
profile stored before this revision never declared an acceleration —
there was no field to declare it in. Writing a default into those rows
would put a physical claim about somebody's vehicle into the database
with nobody's name against it, and a deployment built from it would then
be measured as if that claim were checked. So the column stays empty and
the deployment form asks its author, which is the same shape of answer
HĐ-1.6 gives for an undeclared tuning: silence is a state, not a zero.

**What is *not* here: ``control_period``.** It is the deployment's
T_cycle and gate G4's threshold — a requirement about the target board,
not a property of the vehicle. The same robot in a hall and in a
warehouse aisle can be held to two different cycles, and a copy of it on
this table would let one profile edit widen a gate for every deployment
using that vehicle, with no new ``task_profile_id`` to mark that the
world changed.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("robot_profiles", sa.Column("max_linear_acceleration", sa.Float(), nullable=True))
    op.add_column(
        "robot_profiles", sa.Column("max_angular_acceleration", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("robot_profiles", "max_angular_acceleration")
    op.drop_column("robot_profiles", "max_linear_acceleration")
