"""Imported algorithm bundles get their own table.

**Its own table rather than a row in `models`.** The two are siblings,
not variants: a model is weights for a controller the platform already
has, a bundle is a controller it has never seen. `models` carries
`framework`, `training_steps`, `observation_schema` — every one of which
would be empty or a lie for a bundle — and a bundle carries a manifest,
a role and an entry point that mean nothing to a checkpoint. One table
holding both would be a table where half the columns are always null and
no constraint can say which half.

**Identity is the manifest's, not the display name's.** The unique
constraint is on `(plugin_id, plugin_version)`, not on
`(owner, name, version)` the way `models` is. A candidate id is derived
from what the plugin declares itself to be, so two uploads claiming one
plugin version are two answers to "what produced this result?" however
differently their uploaders labelled them. Names stay free.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")

ID = sa.String(32)
TIMESTAMP = sa.String(40)


def upgrade() -> None:
    op.create_table(
        "plugin_bundles",
        sa.Column("id", ID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # The manifest's own identity. Longer than a display name because
        # a reverse-DNS plugin id is a real length, not a formality.
        sa.Column("plugin_id", sa.String(200), nullable=False),
        sa.Column("plugin_version", sa.String(40), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("entry_point", sa.String(200), nullable=False),
        # Stored verbatim: the checksum identifies what the author
        # uploaded, and a re-serialisation would identify what this
        # version of the SDK thinks they uploaded.
        sa.Column("manifest", JSON_TYPE, nullable=False),
        sa.Column("manifest_checksum", sa.String(64), nullable=False),
        sa.Column("package_dir", sa.String(120), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("uploaded_by_user_id", ID, nullable=False),
        sa.Column("robot_profile_id", ID, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        sa.UniqueConstraint("plugin_id", "plugin_version", name="uq_plugin_bundles_identity"),
    )
    op.create_index("ix_plugin_bundles_owner", "plugin_bundles", ["uploaded_by_user_id"])
    op.create_index(
        "ix_plugin_bundles_status", "plugin_bundles", ["status", "validation_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_plugin_bundles_status", table_name="plugin_bundles")
    op.drop_index("ix_plugin_bundles_owner", table_name="plugin_bundles")
    op.drop_table("plugin_bundles")
