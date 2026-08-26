"""Bring the desktop database up to head before the app opens.

Alembic through its Python API rather than `alembic upgrade head` in a
subprocess, for two reasons that both only show up once packaged.

`alembic.ini` names `script_location = alembic` — a path relative to the
working directory, which by this point is the *data* root and holds no
migrations at all. Setting it explicitly is the fix; the alternative is
a `chdir` back and forth around the call, which is the same fix written
so that a later edit can break it.

And a subprocess would spawn `sys.executable -m alembic`, which in the
shipped runtime is a Python that has to find its own way back to twelve
source roots. It does — that is what `python312._pth` is for — but it is
a second path through the packaging that nothing else exercises, in
service of something the library does perfectly well in-process.

The backup is taken because upgrades run unattended here. On a server a
failed migration is a person watching a terminal; on a desktop it is an
app that will not open and a database nobody thought to copy.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("planbench.desktop")

#: Kept alongside the database rather than in a backups directory: one
#: file, obviously named, next to the thing it is a copy of.
BACKUP_SUFFIX = ".bak"


def _backup(database: Path) -> None:
    if not database.exists():
        return
    backup = database.with_name(database.name + BACKUP_SUFFIX)
    shutil.copy2(database, backup)
    logger.info("database backed up to %s", backup.name)


def upgrade(install_root: Path, database: Path) -> None:
    """Run every pending migration against ``database``.

    ``PLANBENCH_DATABASE_URL`` is already set by provisioning, and
    ``alembic/env.py`` reads it from the environment — passing it again
    here would create a second place the URL is decided.
    """
    from alembic.config import Config

    from alembic import command

    _backup(database)
    config = Config(str(install_root / "alembic.ini"))
    config.set_main_option("script_location", str(install_root / "alembic"))
    command.upgrade(config, "head")
    logger.info("database schema is at head")


__all__ = ["BACKUP_SUFFIX", "upgrade"]
