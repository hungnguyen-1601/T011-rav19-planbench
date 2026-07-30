"""Alembic migrations, run against a real (SQLite) database.

Two things these tests protect:

1. **The migration actually runs, and reverses.** A downgrade nobody has
   executed is a downgrade that does not work, and it is only ever
   needed under pressure.
2. **The migration and the models agree.** They are written separately,
   so they can drift; a schema built by ``upgrade head`` is compared
   table-by-table and column-by-column against ``Base.metadata``.

SQLite is not PostgreSQL: this proves the migration's structure, not its
behaviour under a production dialect. See docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from planbench_api.db.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

# Columns whose SQL type differs harmlessly between the two definitions
# (JSON renders as TEXT on SQLite either way). Compared by name only.
TYPE_INSENSITIVE = {"payload", "config", "run", "spec", "report", "record"}


def alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


@pytest.fixture
def database(tmp_path, monkeypatch) -> str:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    # env.py reads the URL from the environment only, so a password
    # never has to live in a tracked file.
    monkeypatch.setenv("PLANBENCH_DATABASE_URL", url)
    return url


def test_upgrade_creates_every_table(database):
    command.upgrade(alembic_config(database), "head")
    tables = set(inspect(create_engine(database)).get_table_names())
    assert {
        "maps",
        "scenarios",
        "simulations",
        "benchmarks",
        "approvals",
        "episodes",
    } <= tables


def test_downgrade_removes_everything_it_created(database):
    config = alembic_config(database)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    remaining = set(inspect(create_engine(database)).get_table_names())
    # alembic_version is Alembic's own bookkeeping table.
    assert remaining <= {"alembic_version"}


def test_upgrade_is_repeatable_after_a_downgrade(database):
    config = alembic_config(database)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert "benchmarks" in inspect(create_engine(database)).get_table_names()


def test_migration_matches_the_models(database):
    """The migration and the ORM are written by hand; keep them equal."""
    command.upgrade(alembic_config(database), "head")
    inspector = inspect(create_engine(database))

    migrated = {name for name in inspector.get_table_names() if name != "alembic_version"}
    declared = set(Base.metadata.tables)
    assert migrated == declared, "tables differ between the migration and the models"

    for table_name in sorted(declared):
        table = Base.metadata.tables[table_name]
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert set(columns) == set(table.columns.keys()), f"{table_name}: columns differ"

        for column_name, column in table.columns.items():
            migrated_column = columns[column_name]
            assert migrated_column["nullable"] == column.nullable, (
                f"{table_name}.{column_name}: nullability differs"
            )
            if column_name not in TYPE_INSENSITIVE:
                assert (
                    str(migrated_column["type"])
                    .upper()
                    .startswith(str(column.type).split("(")[0].upper()[:4])
                ), f"{table_name}.{column_name}: type differs"


def test_primary_keys_match_the_models(database):
    command.upgrade(alembic_config(database), "head")
    inspector = inspect(create_engine(database))
    for table_name, table in Base.metadata.tables.items():
        migrated = set(inspector.get_pk_constraint(table_name)["constrained_columns"])
        assert migrated == {column.name for column in table.primary_key}, table_name


def test_cascade_deletes_are_declared(database):
    """Deleting a benchmark must take its episodes and approvals with it.

    Without the cascade they would be unreachable rows nobody ever
    cleans up.
    """
    command.upgrade(alembic_config(database), "head")
    inspector = inspect(create_engine(database))
    for table_name in ("episodes", "approvals"):
        keys = inspector.get_foreign_keys(table_name)
        assert keys, f"{table_name} has no foreign key to benchmarks"
        assert keys[0]["referred_table"] == "benchmarks"
        assert keys[0]["options"].get("ondelete") == "CASCADE"


def test_indexes_cover_the_hot_lookups(database):
    """The queries the API actually issues, in index form."""
    command.upgrade(alembic_config(database), "head")
    inspector = inspect(create_engine(database))
    indexed = {
        table: {tuple(index["column_names"]) for index in inspector.get_indexes(table)}
        for table in ("maps", "benchmarks", "episodes", "approvals", "scenarios")
    }
    # Episodes are always listed per benchmark, in episode order.
    assert ("benchmark_id", "episode_index") in indexed["episodes"]
    # The leaderboard groups by conditions_checksum.
    assert ("conditions_checksum",) in indexed["benchmarks"]
