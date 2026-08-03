"""Robot profiles, the model registry, and assistant conversations.

Additive only. Nothing existing is rewritten or dropped, so benchmarks,
maps, scenarios, users, reviews and reports all survive untouched, and a
downgrade loses only what this revision created.

Benchmarks that already carry a `model_path` in their algorithm config
keep working: the config is a JSON column, the PPO adapter still accepts
`model_path`, and `services.py` only reaches for the registry when a
`model_id` is present. Migrating those into registry records is a
deliberate act, not something a schema change should do behind
somebody's back — the file it points at may no longer exist, and
inventing a record for a missing file would be worse than leaving the
benchmark honestly legacy.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")

ID = sa.String(32)
TIMESTAMP = sa.String(40)


def upgrade() -> None:
    op.create_table(
        "robot_profiles",
        sa.Column("id", ID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("radius", sa.Float(), nullable=False),
        sa.Column("footprint", sa.String(40), nullable=False),
        sa.Column("max_linear_velocity", sa.Float(), nullable=False),
        sa.Column("max_angular_velocity", sa.Float(), nullable=False),
        sa.Column("lidar_beams", sa.Integer(), nullable=False),
        sa.Column("lidar_range", sa.Float(), nullable=False),
        sa.Column("observation_type", sa.String(60), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("created_by_user_id", ID, nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_robot_profiles_owner", "robot_profiles", ["created_by_user_id"])

    op.create_table(
        "models",
        sa.Column("id", ID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("algorithm_type", sa.String(40), nullable=False),
        sa.Column("framework", sa.String(60), nullable=False),
        sa.Column("framework_version", sa.String(40), nullable=False),
        # The bytes live in model storage; this is the key, never the file.
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("uploaded_by_user_id", ID, nullable=False),
        sa.Column("robot_profile_id", ID, nullable=False),
        sa.Column("observation_schema", JSON_TYPE, nullable=False),
        sa.Column("action_schema", JSON_TYPE, nullable=False),
        sa.Column("training_environment", sa.String(120), nullable=False),
        sa.Column("training_steps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        # One person may not have two models with the same name *and*
        # version; different people may, and versions are how you
        # supersede your own.
        sa.UniqueConstraint(
            "uploaded_by_user_id", "name", "version", name="uq_models_name_version"
        ),
    )
    op.create_index("ix_models_owner", "models", ["uploaded_by_user_id"])
    op.create_index("ix_models_status", "models", ["status", "validation_status"])

    op.create_table(
        "model_documents",
        sa.Column("id", ID, primary_key=True),
        sa.Column("model_id", ID, sa.ForeignKey("models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_model_documents_model", "model_documents", ["model_id"])

    op.create_table(
        "model_usages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_id", ID, nullable=False),
        sa.Column("benchmark_id", ID, nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        # Recorded at use time: a later re-upload cannot rewrite what ran.
        sa.Column("model_checksum", sa.String(64), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_model_usages_model", "model_usages", ["model_id"])
    op.create_index("ix_model_usages_benchmark", "model_usages", ["benchmark_id"])

    op.create_table(
        "conversations",
        sa.Column("id", ID, primary_key=True),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
    )
    op.create_index("ix_conversations_user", "conversations", ["user_id", "updated_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            ID,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
    )
    op.create_index(
        "ix_conversation_messages_conversation", "conversation_messages", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_conversation", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_user", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_model_usages_benchmark", table_name="model_usages")
    op.drop_index("ix_model_usages_model", table_name="model_usages")
    op.drop_table("model_usages")

    op.drop_index("ix_model_documents_model", table_name="model_documents")
    op.drop_table("model_documents")

    op.drop_index("ix_models_status", table_name="models")
    op.drop_index("ix_models_owner", table_name="models")
    op.drop_table("models")

    op.drop_index("ix_robot_profiles_owner", table_name="robot_profiles")
    op.drop_table("robot_profiles")
