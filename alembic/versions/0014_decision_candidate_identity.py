"""What a run actually ran, recorded rather than looked up afterwards.

**The gap this closes.** A selection is requested with stack strings —
``astar+org.vinai.vfh-plus`` — and those strings are resolved to code at
the moment the job starts, which on a queue is not the moment the
request was made. In between, a reviewer can publish a new revision or
withdraw the one that was current. The job then measures something
nobody asked for, under an id that says it measured the other thing, and
nothing in the stored run can tell the difference.

So identity is resolved when the request arrives and written down: the
bundle, its revision, the checksum of the archive, and the provider
fingerprint of the deployment it was resolved against. Re-resolving at
start is what this table exists to prevent.

**No parent row exists at enqueue**, and this table does not try to
invent one. ``decision_runs`` is written when a run *finishes* — a job
that fails leaves no run, which is correct, because there is nothing to
say about a measurement that did not happen. The pinned identity
therefore lives on the queued job until the run is stored, and both are
written in one transaction at the end.

**Nothing is backfilled here.** Runs made before this table have no
recorded identity, and a migration cannot honestly supply one: the
answer is on disk, in each run's manifest, and matching it back to a
bundle means hashing stored archives. That belongs in a script somebody
runs and reads the output of (`scripts/backfill_run_candidates.py`), not
in a migration that would have to guess in silence. Until it runs, those
runs report a reliance of ``unknown``, which is the true answer.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(36)


def upgrade() -> None:
    op.create_table(
        "decision_run_candidates",
        sa.Column(
            "run_id",
            ID,
            sa.ForeignKey("decision_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Position in the request, so the row order a person saw is the
        # row order that comes back.
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("stack", sa.String(200), nullable=False),
        sa.Column("local_config", sa.String(200), nullable=False, server_default=""),
        # Null for a built-in stack: there is no bundle to pin, and the
        # code came with the deployment.
        sa.Column("bundle_id", ID, nullable=True),
        sa.Column("plugin_id", sa.String(200), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.Column("archive_checksum", sa.String(64), nullable=True),
        # What the deployment could offer at the time. A run that reused
        # traces under a different provider graph is a different
        # experiment, and this is what says so.
        sa.Column("provider_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("runtime_profile", sa.String(40), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("run_id", "slot", name="pk_decision_run_candidates"),
    )
    op.create_index(
        "ix_decision_run_candidates_bundle", "decision_run_candidates", ["bundle_id"]
    )

    # production | validation. A validation run is a reviewer watching an
    # unpublished bundle behave; it is never submitted and never approved,
    # and it is the same code path with a different label rather than a
    # second one — a second path would be a second place for replanning
    # to be handled differently.
    op.add_column(
        "decision_runs",
        sa.Column("purpose", sa.String(20), nullable=False, server_default="production"),
    )


def downgrade() -> None:
    op.drop_column("decision_runs", "purpose")
    op.drop_index("ix_decision_run_candidates_bundle", table_name="decision_run_candidates")
    op.drop_table("decision_run_candidates")
