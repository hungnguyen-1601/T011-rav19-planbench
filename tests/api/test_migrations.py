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


class TestDecisionLayerTables:
    """Revisions 0005 and 0006 — HĐ-2, HĐ-1 and HĐ-12/13 given somewhere
    to live, and then given the *right shape*.

    ``test_migration_matches_the_models`` above already compares every
    table column by column, so these check the decisions that comparison
    cannot see: which key was chosen, what a delete is allowed to do,
    what stays out of the database entirely — and which columns are
    allowed to be absent.
    """

    def test_the_three_tables_exist(self, database):
        command.upgrade(alembic_config(database), "head")
        tables = set(inspect(create_engine(database)).get_table_names())
        assert {"task_profiles", "candidates", "decision_runs"} <= tables
        assert "decision_cards" not in tables, (
            "0006 replaced decision_cards with decision_runs; a leftover table under the "
            "old name describes the wrong shape and invites writes nobody reads"
        )

    def test_a_candidate_is_keyed_by_its_own_hash(self, database):
        """HĐ-1.3: ``candidate_id`` identifies the configuration.

        A surrogate key would let the same planner, controller,
        parameters and code version be registered twice under two rows,
        which is exactly the split identity the contract's hash exists to
        make impossible.
        """
        command.upgrade(alembic_config(database), "head")
        inspector = inspect(create_engine(database))
        assert inspector.get_pk_constraint("candidates")["constrained_columns"] == ["candidate_id"]

    def test_a_run_always_has_evidence_and_sometimes_has_a_card(self, database):
        """The point of 0006, asserted on nullability.

        ``0005`` made ``card`` and ``recommended_candidate_id`` NOT NULL,
        which says every evaluation ends in a ranking. The first MVP run
        disproved that in a day: three comparisons out of three produced
        no card, because a card needs *two* candidates through all six
        gates and only one of four got there. Each of those runs still
        carried a full gate table — the very thing HĐ-12 puts on a card.

        So the nullability is the contract here, not decoration: evidence
        is mandatory, a recommendation is not.
        """
        command.upgrade(alembic_config(database), "head")
        nullable = {
            column["name"]: column["nullable"]
            for column in inspect(create_engine(database)).get_columns("decision_runs")
        }
        assert nullable["report"] is False, "a run without evidence is not a run"
        for optional in ("card", "manifest", "recommended_candidate_id", "status"):
            assert nullable[optional] is True, (
                f"{optional} must be nullable — a run that could not be ranked is a result, "
                "and a schema that refuses to store it puts pressure on every run to be "
                "rankable"
            )

    def test_the_kind_of_artifact_is_a_column_not_a_json_field(self, database):
        """"Show me the runs that could not be ranked" is a day-one
        question. Buried in the JSON body it would be a table scan, and
        the answer people cannot query is the answer they stop asking."""
        command.upgrade(alembic_config(database), "head")
        inspector = inspect(create_engine(database))
        columns = {c["name"] for c in inspector.get_columns("decision_runs")}
        assert "artifact_kind" in columns
        indexed = {tuple(index["column_names"]) for index in inspector.get_indexes("decision_runs")}
        assert ("artifact_kind",) in indexed

    def test_a_run_cannot_outlive_its_deployment(self, database):
        """RESTRICT, not CASCADE. A run is a statement about one
        deployment profile; deleting the profile out from under it would
        leave a result nobody can interpret, and silently deleting the
        run instead would destroy the audit trail. Both are worse than
        refusing the delete.
        """
        command.upgrade(alembic_config(database), "head")
        keys = inspect(create_engine(database)).get_foreign_keys("decision_runs")
        assert keys, "decision_runs has no foreign key to task_profiles"
        assert keys[0]["referred_table"] == "task_profiles"
        assert keys[0]["options"].get("ondelete") == "RESTRICT"

    def test_traces_are_referenced_not_stored(self, database):
        """D15. The report, card and manifest are kilobytes and belong in
        the row; the Parquet traces are megabytes per episode and stay in
        the artifact store. The checksum is what makes the reference
        trustworthy — a URI alone cannot say the files it points at are
        the ones this run was computed from.
        """
        command.upgrade(alembic_config(database), "head")
        columns = {
            column["name"]
            for column in inspect(create_engine(database)).get_columns("decision_runs")
        }
        assert {"report", "card", "manifest", "run_uri", "run_checksum"} <= columns
        assert not {name for name in columns if "trace" in name or "parquet" in name}

    def test_the_lookups_the_api_will_issue_are_indexed(self, database):
        command.upgrade(alembic_config(database), "head")
        inspector = inspect(create_engine(database))
        indexed = {tuple(index["column_names"]) for index in inspector.get_indexes("decision_runs")}
        assert ("task_profile_id",) in indexed
        assert ("recommended_candidate_id",) in indexed
        assert ("status",) in indexed

    def test_downgrade_puts_the_old_table_back(self, database):
        """0006 drops a table, so its downgrade has to recreate it — a
        migration that cannot be undone is one nobody dares apply."""
        config = alembic_config(database)
        command.upgrade(config, "head")
        command.downgrade(config, "0005")
        tables = set(inspect(create_engine(database)).get_table_names())
        assert "decision_cards" in tables
        assert "decision_runs" not in tables
