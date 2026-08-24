"""First run: build the data root, then point the app at it.

Everything here happens **before any PlanBench module is imported**, and
that ordering is the reason this is a separate module rather than a few
lines in `main`. `Settings` is `lru_cache`d and `planbench_api.main`
builds the application at import time — by the time `create_app` has
run, the environment it read is the environment it will keep.

Four things are decided here, and three of them are decided *once*,
because the code that consumes them only looks at first boot:

**AUTH_SECRET.** Empty means "generate a random one per process", which
on a server behind a restart policy is a mild annoyance and on a desktop
app means being signed out every single time it opens.

**The admin nickname.** `PLANBENCH_ADMIN_NICKNAMES` is read when an
account is *created* and never again, so adding a name after the first
launch has no effect at all — the account exists and keeps the flag it
was born with. On a machine with one user who needs to import algorithms
and set the API key, getting this wrong on first boot means a database
edit to recover.

**The seed account.** Dev login is the sign-in path for the desktop
build: OAuth would need a registered redirect URI and a browser round
trip to reach a server that only exists while the app is open.

**Where everything is written.** `.env`, `artifacts/` and the map root
are all resolved relative to the working directory, so `chdir` into the
data root settles all three at once — and it settles them the same way
`load_provider_keys` resolves `.env`, rather than by a second path that
could disagree with it.
"""

from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path

from planbench_desktop import paths

#: Copied from the installation into the data root on first run, so a
#: person can edit a map without writing inside Program Files and so an
#: upgrade cannot overwrite what they edited.
SEEDED_ASSETS = ("maps", "profiles")

#: The account created on first launch. The password is generated per
#: installation and written to `.env`, where the person who installed
#: the app can read it; a fixed default would be the same password on
#: every machine this is ever installed on.
DEFAULT_NICKNAME = "admin"

ENV_TEMPLATE = """\
# PlanBench desktop settings. Edit while the app is closed.
#
# The API key is easier to set from the Settings page inside the app;
# this file is where that page writes it.

AUTH_SECRET={secret}
PLANBENCH_ENABLE_DEV_LOGIN=true
PLANBENCH_SEED_USERS={nickname}:{password}
PLANBENCH_ADMIN_NICKNAMES={nickname}
# Sign-ins last twelve hours: this is one machine with one person on it,
# and the server-side default of one hour is written for a shared API.
PLANBENCH_JWT_TTL_MINUTES=720
PLANBENCH_DATABASE_URL=sqlite:///{database}

# Filled in by the Settings page. A key here is read at startup.
# OPENAI_API_KEY=

# Updates are checked anonymously; releases are public and no
# credential is needed. Setting a read-only GitHub token here only
# raises the rate limit for a machine that opens the app very often.
# PLANBENCH_UPDATE_TOKEN=
PLANBENCH_AGENT_PROVIDER=auto
PLANBENCH_AGENT_MODEL=o4-mini
"""


class Provisioned:
    """What first run created, for the welcome message and the logs."""

    def __init__(self, root: Path, created: bool, nickname: str, password: str) -> None:
        self.root = root
        self.created = created
        self.nickname = nickname
        self.password = password


def _env_entries(env_path: Path) -> dict[str, str]:
    """The plain NAME=value lines of `.env`, comments and blanks skipped."""
    entries: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        entries[name.strip()] = value.strip()
    return entries


#: Read out of `.env` into the process environment by the launcher.
#: Neither is a pydantic setting: the database URL is consumed by
#: `alembic/env.py`, which reads the raw environment, and the update
#: token is consumed by the updater before any setting object exists.
LAUNCHER_VARS = ("PLANBENCH_DATABASE_URL", "PLANBENCH_UPDATE_TOKEN")


def _export_launcher_vars(env_path: Path) -> None:
    """Put the variables read outside pydantic-settings into the environment.

    `alembic/env.py` reads ``PLANBENCH_DATABASE_URL`` from the *process
    environment* and raises when it is unset. Everything else reads
    `.env` through pydantic-settings, so this one variable is the only
    place where writing the file is not the same as setting the value —
    and the failure is at first launch, on the migration, before the
    window ever opens.

    An existing value wins, matching :func:`load_provider_keys`: a value
    exported deliberately for one run should not be replaced by a file.
    """
    entries = _env_entries(env_path)
    for name in LAUNCHER_VARS:
        if os.environ.get(name):
            continue
        value = entries.get(name, "")
        if value:
            os.environ[name] = value


def _read_seed_account(env_path: Path) -> tuple[str, str]:
    """The nickname and password already in `.env`, if it has them."""
    entry = _env_entries(env_path).get("PLANBENCH_SEED_USERS", "").split(",")[0]
    if ":" in entry:
        nickname, password = entry.split(":", 1)
        return nickname.strip(), password.strip()
    return DEFAULT_NICKNAME, ""


def _seed_assets(root: Path) -> None:
    """Copy maps and profiles in, without overwriting edited copies.

    File by file rather than `copytree`: an upgrade adding a new stock
    map should deliver it, and the same upgrade must not silently revert
    a map somebody drew on.
    """
    for name in SEEDED_ASSETS:
        source = paths.INSTALL_ROOT / name
        if not source.is_dir():
            continue
        target = root / name
        for item in source.rglob("*"):
            if item.is_dir():
                continue
            destination = target / item.relative_to(source)
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def provision() -> Provisioned:
    """Create or adopt the data root and set the environment from it.

    Safe to call on every launch: the `.env` is written once and read
    afterwards, so a person's edits to it survive.
    """
    root = paths.data_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "artifacts").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)

    env_path = root / ".env"
    first_run = not env_path.exists()
    if first_run:
        password = secrets.token_urlsafe(9)
        env_path.write_text(
            ENV_TEMPLATE.format(
                secret=secrets.token_urlsafe(48),
                nickname=DEFAULT_NICKNAME,
                password=password,
                # POSIX separators: this is a SQLAlchemy URL, and a
                # Windows path dropped into one has backslashes that the
                # URL parser reads as escapes.
                database=(root / "planbench.db").as_posix(),
            ),
            encoding="utf-8",
        )
        nickname, credential = DEFAULT_NICKNAME, password
    else:
        nickname, credential = _read_seed_account(env_path)

    _seed_assets(root)

    # `chdir` before anything reads configuration. `.env`, the artifact
    # root and the map root are all relative to the working directory,
    # and this is the one call that makes all three agree.
    os.chdir(root)
    # Assigned rather than defaulted. The map root's "." default would
    # resolve correctly through the chdir above, but only for a reader
    # who knows the chdir happened; and `setdefault` would let a value
    # left over from an earlier run point a fresh data root's maps at
    # the previous one.
    os.environ["PLANBENCH_MAP_ROOT"] = str(root)
    os.environ["PLANBENCH_WEB_DIR"] = str(paths.web_root())
    _export_launcher_vars(env_path)

    return Provisioned(root, first_run, nickname, credential)


__all__ = ["DEFAULT_NICKNAME", "LAUNCHER_VARS", "SEEDED_ASSETS", "Provisioned", "provision"]
