"""Alembic environment.

The database URL comes from ``PLANBENCH_DATABASE_URL`` only — never from
``alembic.ini`` — so a password is never committed. It goes through the
same ``normalise_url`` the application uses, so a URL that works for the
app works for a migration and vice versa.

``target_metadata`` is the application's own metadata, which is what
makes ``alembic revision --autogenerate`` able to diff the models
against a live database.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

REPO_ROOT = Path(__file__).resolve().parents[1]
for package in (
    "packages/schemas",
    "packages/planning",
    "packages/metrics",
    "packages/benchmark",
    "services/simulator",
    "services/tracking",
    "services/agent_service",
    "apps/api",
):
    path = str(REPO_ROOT / package)
    if path not in sys.path:
        sys.path.insert(0, path)

from planbench_api.db.models import Base  # noqa: E402
from planbench_api.db.session import normalise_url  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

ENV_VAR = "PLANBENCH_DATABASE_URL"


def database_url() -> str:
    url = os.environ.get(ENV_VAR, "").strip()
    if not url:
        raise RuntimeError(
            f"{ENV_VAR} is not set. Migrations never carry a connection string in a "
            "tracked file; export it for the command:\n"
            f"  {ENV_VAR}=postgresql://user:pass@host:5432/planbench "
            ".venv/bin/alembic upgrade head"
        )
    return normalise_url(url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (`--sql`).

    Useful when a DBA applies changes by hand, which is the normal
    arrangement for a production database nobody lets an app migrate.
    """
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Catch a column whose type drifted from the model, not just
            # added and removed columns.
            compare_type=True,
            # SQLite cannot ALTER a column in place; batch mode rewrites
            # the table instead. No effect on PostgreSQL.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
