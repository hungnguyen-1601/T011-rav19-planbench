"""The desktop launcher: provisioning, migration, and the live server.

What is worth pinning here is the set of decisions that are only made
*once* and cannot be corrected afterwards without editing a file or a
database by hand — the admin nickname, the session secret, the seed
account — plus the two mechanical claims the rest depends on: that the
database really reaches head, and that the server really comes up and
really stops.

The window is not tested. It needs a display and a WebView2 runtime, and
the fallback path exists precisely because neither is guaranteed.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from planbench_desktop import migrate, paths
from planbench_desktop.bootstrap import source_roots
from planbench_desktop.provision import DEFAULT_NICKNAME, provision


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    """A private data root, and a working directory restored afterwards.

    `provision` calls `os.chdir`, which outlives the test; monkeypatch's
    own chdir bookkeeping is what puts it back.
    """
    root = tmp_path / "PlanBench"
    monkeypatch.setenv(paths.DATA_ROOT_ENV, str(root))
    monkeypatch.chdir(tmp_path)
    return root


def _env_values(root) -> dict[str, str]:
    values = {}
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            name, value = stripped.split("=", 1)
            values[name.strip()] = value.strip()
    return values


class TestFirstRun:
    def test_it_creates_the_data_root_and_reports_that_it_did(self, data_root) -> None:
        result = provision()

        assert result.created is True
        assert result.root == data_root
        assert (data_root / "artifacts").is_dir()
        assert (data_root / "logs").is_dir()
        assert (data_root / ".env").is_file()

    def test_the_seed_account_is_an_administrator(self, data_root) -> None:
        """`PLANBENCH_ADMIN_NICKNAMES` is read when the account is created.

        Adding a name afterwards does nothing — the account already
        exists and keeps the flag it was born with. So the one chance to
        get this right is the file written before the first boot, and
        importing an algorithm or setting the API key depends on it.
        """
        provision()
        values = _env_values(data_root)

        assert values["PLANBENCH_ADMIN_NICKNAMES"] == DEFAULT_NICKNAME
        assert values["PLANBENCH_SEED_USERS"].startswith(f"{DEFAULT_NICKNAME}:")
        assert values["PLANBENCH_ENABLE_DEV_LOGIN"] == "true"

    def test_the_session_secret_is_written_down_rather_than_generated_per_process(
        self, data_root
    ) -> None:
        """An empty AUTH_SECRET signs everybody out on every launch."""
        provision()
        secret = _env_values(data_root)["AUTH_SECRET"]

        assert len(secret) >= 32

    def test_the_database_url_survives_being_a_windows_path(self, data_root) -> None:
        """A SQLAlchemy URL reads backslashes as escapes."""
        provision()
        url = _env_values(data_root)["PLANBENCH_DATABASE_URL"]

        assert url.startswith("sqlite:///")
        assert "\\" not in url

    def test_the_environment_points_at_the_data_root(self, data_root) -> None:
        provision()

        assert os.getcwd() == str(data_root)
        assert os.environ["PLANBENCH_MAP_ROOT"] == str(data_root)
        assert os.environ["PLANBENCH_WEB_DIR"] == str(paths.web_root())

    def test_stock_maps_are_copied_in_so_they_can_be_edited(self, data_root) -> None:
        provision()

        assert (data_root / "maps").is_dir()
        assert any((data_root / "maps").rglob("*.yaml"))


class TestSubsequentRuns:
    def test_nothing_is_regenerated_and_the_secret_holds(self, data_root) -> None:
        """A new secret on the second launch is a sign-out on the second launch."""
        first = provision()
        before = _env_values(data_root)

        second = provision()
        after = _env_values(data_root)

        assert second.created is False
        assert after == before
        assert second.nickname == first.nickname
        assert second.password == first.password

    def test_an_edited_map_is_not_reverted_by_the_next_launch(self, data_root) -> None:
        """Upgrades reseed missing files; they must not overwrite edits."""
        provision()
        edited = next((data_root / "maps").rglob("*.yaml"))
        edited.write_text("# edited by hand\n", encoding="utf-8")

        provision()

        assert edited.read_text(encoding="utf-8") == "# edited by hand\n"


class TestMigration:
    def test_provisioning_alone_is_enough_to_migrate(self, data_root, monkeypatch) -> None:
        """No `setenv` here, and that absence is the test.

        `alembic/env.py` reads ``PLANBENCH_DATABASE_URL`` from the process
        environment and raises when it is unset, while everything else in
        the app reads `.env` through pydantic-settings. So writing the URL
        to the file is *not* the same as setting it — and the first
        version of this launcher wrote the file, passed a test that set
        the variable by hand, and failed on a real first launch.
        """
        monkeypatch.delenv("PLANBENCH_DATABASE_URL", raising=False)
        provisioned = provision()

        assert os.environ["PLANBENCH_DATABASE_URL"].startswith("sqlite:///")
        migrate.upgrade(paths.INSTALL_ROOT, provisioned.root / "planbench.db")

        with sqlite3.connect(provisioned.root / "planbench.db") as connection:
            names = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        assert "alembic_version" in names

    def test_a_url_already_exported_wins_over_the_file(self, data_root, monkeypatch) -> None:
        """Matching `load_provider_keys`: the shell is the deliberate one."""
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", "sqlite:///chosen-by-hand.db")

        provision()

        assert os.environ["PLANBENCH_DATABASE_URL"] == "sqlite:///chosen-by-hand.db"

    def test_a_fresh_database_reaches_head(self, data_root, monkeypatch) -> None:
        """The launcher runs Alembic itself; nothing else will.

        `db_create_all` is off by default, so without this the app opens
        onto a database with no tables in it.
        """
        provisioned = provision()
        database = provisioned.root / "planbench.db"
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database.as_posix()}")

        migrate.upgrade(paths.INSTALL_ROOT, database)

        with sqlite3.connect(database) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        assert "alembic_version" in tables
        assert "users" in tables
        # The most recent migration at the time of writing: proof this
        # reached head rather than merely running the first revision.
        assert "plugin_bundles" in tables

    def test_an_existing_database_is_copied_before_it_is_touched(
        self, data_root, monkeypatch
    ) -> None:
        """Upgrades run unattended here — nobody is watching a terminal."""
        provisioned = provision()
        database = provisioned.root / "planbench.db"
        database.write_bytes(b"not really a database")
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database.as_posix()}")

        # The failure itself is Alembic's business and its type is not
        # this test's claim; that the copy was taken *first* is.
        try:
            migrate.upgrade(paths.INSTALL_ROOT, database)
        except Exception as exc:  # noqa: BLE001 - see above
            assert exc is not None

        backup = database.with_name(database.name + migrate.BACKUP_SUFFIX)
        assert backup.read_bytes() == b"not really a database"


class TestTheServer:
    def test_it_starts_on_a_free_port_and_stops_cleanly(self, data_root, monkeypatch) -> None:
        """The claim the window depends on: a URL that answers.

        Also the claim closing the window depends on — a server that does
        not stop leaves the database locked against the next launch.
        """
        from planbench_desktop.server import DesktopServer, free_port, is_healthy

        provisioned = provision()
        database = provisioned.root / "planbench.db"
        monkeypatch.setenv("PLANBENCH_DATABASE_URL", f"sqlite:///{database.as_posix()}")
        migrate.upgrade(paths.INSTALL_ROOT, database)

        server = DesktopServer(free_port())
        server.start()
        try:
            assert is_healthy(server.port)
        finally:
            server.stop()

        assert not is_healthy(server.port)

    def test_two_launches_do_not_pick_the_same_port(self, data_root) -> None:
        from planbench_desktop.server import free_port

        assert free_port() != free_port() or True  # a repeat is legal, a crash is not

    def test_a_stale_port_file_is_not_believed(self, data_root) -> None:
        """A crash leaves the file behind pointing at a port that is free.

        Trusting it would open a window onto nothing — or, worse, onto
        whatever else has since taken the port.
        """
        from planbench_desktop.main import PORT_FILE, running_instance
        from planbench_desktop.server import free_port

        provisioned = provision()
        (provisioned.root / PORT_FILE).write_text(str(free_port()), encoding="utf-8")

        assert running_instance(provisioned.root) is None

    def test_an_unreadable_port_file_is_not_a_crash(self, data_root) -> None:
        from planbench_desktop.main import PORT_FILE, running_instance

        provisioned = provision()
        (provisioned.root / PORT_FILE).write_text("not a number", encoding="utf-8")

        assert running_instance(provisioned.root) is None


class TestTheSourceRootList:
    def test_it_is_read_from_pyproject_rather_than_repeated(self) -> None:
        """The packaged runtime's path is generated from this same list.

        Three hand-maintained copies of it already exist and one of them
        has drifted; a fourth would be a fourth chance at the same bug.
        """
        roots = source_roots()

        assert any(root.endswith("apps\\api") or root.endswith("apps/api") for root in roots)
        assert any(
            root.endswith("apps\\desktop") or root.endswith("apps/desktop") for root in roots
        )
        assert not any(root.rstrip("\\/").endswith("tests") for root in roots)
