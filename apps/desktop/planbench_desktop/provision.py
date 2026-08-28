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

import logging
import os
import secrets
import shutil
from pathlib import Path

from planbench_desktop import paths

#: Copied from the installation into the data root on first run, so a
#: person can edit a map without writing inside Program Files and so an
#: upgrade cannot overwrite what they edited.
SEEDED_ASSETS = ("maps", "profiles")

#: The account created on first launch.
DEFAULT_NICKNAME = "admin"

#: What a desktop install is, stated in the process rather than read from
#: `.env`.
#:
#: **This is the line that keeps an upgrade from taking away somebody's
#: access.** An installed copy has an `.env` written by whichever version
#: created it, and a copy created before roles existed says nothing about
#: a deployment profile. The server reads a missing profile as
#: ``production`` — correct for a server, and wrong here: it would leave
#: the one account the person signs in with holding engineer and admin
#: and nothing else, unable to approve a configuration or import an
#: algorithm. The launcher knows what it is; it does not need the file to
#: tell it.
DEPLOYMENT_PROFILE = "desktop-single-user"

#: The three packages the seeded account holds, and the two extra
#: accounts a desktop install offers.
#:
#: ``admin`` carries all three because one person on one machine is the
#: whole deployment: they create the work, they review it, and they
#: operate the app. ``engineer`` and ``reviewer`` exist so the same
#: machine can also *show* the workflow as it behaves with two people —
#: signing in as one of them is the only way to see what an engineer's
#: screen actually withholds.
SEED_ACCOUNTS = (
    (DEFAULT_NICKNAME, "engineer+reviewer+admin"),
    ("engineer", "engineer"),
    ("reviewer", "reviewer"),
)

#: Defaults the profile implies, applied only where `.env` is silent.
#:
#: Separate from the template on purpose: the template is written once,
#: at first run, and an installation created two versions ago will never
#: see a line added to it. These are applied on **every** launch, so a
#: copy whose file predates them still behaves like the desktop build it
#: is. An explicit value in `.env` always wins — somebody who edited the
#: file meant it.
PROFILE_DEFAULTS = {
    "PLANBENCH_DEPLOYMENT_PROFILE": DEPLOYMENT_PROFILE,
    # One person cannot be two, so the separation-of-duties rule that a
    # shared deployment needs would make this build's approve button
    # permanently unusable. Relaxed here, and every such act is written
    # to the trail as `self_*` so the record never claims a second human
    # looked.
    "PLANBENCH_SEPARATION_OF_DUTIES": "relaxed",
}

#: **A known password, on purpose, for now.**
#:
#: The generated one it replaced was per-installation and unguessable,
#: and it made the first thing a new user did be "open File Explorer,
#: find `.env`, copy a random string" — which is a poor way to meet an
#: application. This is a deliberate, temporary trade against that, and
#: it is bounded by where the server listens: the API binds
#: `127.0.0.1` only (`server.HOST`), so reaching this account means
#: already being on the machine and logged in as its owner. On a shared
#: or remote-desktop machine that is no longer true, which is the case
#: this owes an answer to.
#:
#: Replaced in the next version by something that does not trade one for
#: the other — a first-run screen that shows the credential, or no login
#: at all for a single-user desktop build.
DEFAULT_PASSWORD = "admin"

ENV_TEMPLATE = """\
# PlanBench desktop settings. Edit while the app is closed.
#
# The API key is easier to set from the Settings page inside the app;
# this file is where that page writes it.

AUTH_SECRET={secret}
PLANBENCH_ENABLE_DEV_LOGIN=true
# Sign in with these. Change the password here and restart the app to
# use a different one; the account is created from this line the first
# time the app runs, and re-reads it on every launch after that.
# `name:roles:password`. Roles are joined with `+`; the three accounts
# exist so this machine can show the workflow both ways — as one person
# who does everything, and as the two separate jobs the platform is
# built around.
PLANBENCH_SEED_USERS={seed_users}
PLANBENCH_ADMIN_NICKNAMES={nickname}
PLANBENCH_DEPLOYMENT_PROFILE={profile}
# One person cannot be two. Every self-approval is recorded as `self_*`.
PLANBENCH_SEPARATION_OF_DUTIES=relaxed
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


def seed_users_line(password: str) -> str:
    """The `PLANBENCH_SEED_USERS` value for a fresh install.

    The extra two accounts take their nickname as their password, the
    same trade the main one makes and for the same reason: the API binds
    ``127.0.0.1``, so reaching them means already being on the machine.
    """
    return ",".join(
        f"{nickname}:{roles}:{password if nickname == DEFAULT_NICKNAME else nickname}"
        for nickname, roles in SEED_ACCOUNTS
    )


def apply_profile_defaults(env_path: Path) -> dict[str, str]:
    """Fill in what this build is, where the file does not say.

    Returns what was applied, for the log.

    **Every launch, not only the first**, and that is the whole point: a
    copy installed before roles existed has an `.env` that will never
    grow these lines by itself, and without them an upgrade silently
    demotes the account its owner signs in with. Anything the file
    states explicitly wins — including a person who set the profile to
    ``demo``.

    The seed line is filled in too, and not only the profile. A file from
    an older build carries ``admin:<password>`` in the two-part form,
    which names no roles at all; a reconciliation with nothing to
    reconcile leaves the account exactly as under-privileged as before,
    so setting the profile alone fixes nothing.
    """
    stated = _env_entries(env_path)
    applied: dict[str, str] = {}
    for name, value in PROFILE_DEFAULTS.items():
        if stated.get(name) or os.environ.get(name):
            continue
        os.environ[name] = value
        applied[name] = value

    if not _states_roles(stated.get("PLANBENCH_SEED_USERS", "")):
        nickname, password = _read_seed_account(env_path)
        # Keep whatever password the file carries — changing somebody's
        # credential during an upgrade is not a thing an upgrade may do.
        line = seed_users_line(password or DEFAULT_PASSWORD)
        if nickname != DEFAULT_NICKNAME:
            # They renamed the account. Grant the same three packages to
            # the name they actually use, and leave the stock two out:
            # inventing accounts on somebody's machine is not repair.
            line = f"{nickname}:{SEED_ACCOUNTS[0][1]}:{password or DEFAULT_PASSWORD}"
        os.environ["PLANBENCH_SEED_USERS"] = line
        applied["PLANBENCH_SEED_USERS"] = line
    return applied


def _states_roles(seed_users: str) -> bool:
    """Whether a seed line names roles, rather than only a password."""
    return any(entry.count(":") >= 2 for entry in seed_users.split(",") if entry.strip())


def _read_seed_account(env_path: Path) -> tuple[str, str]:
    """The nickname and password already in `.env`, if it has them."""
    entry = _env_entries(env_path).get("PLANBENCH_SEED_USERS", "").split(",")[0]
    parts = [part.strip() for part in entry.split(":")]
    if len(parts) >= 3:
        # `name:roles:password` — the password is everything after the
        # second colon, because a password may contain one.
        return parts[0], ":".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1]
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
        password = DEFAULT_PASSWORD
        env_path.write_text(
            ENV_TEMPLATE.format(
                secret=secrets.token_urlsafe(48),
                nickname=DEFAULT_NICKNAME,
                password=password,
                profile=DEPLOYMENT_PROFILE,
                seed_users=seed_users_line(password),
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
    # What the System page shows. `Settings.version` is a constant in
    # config.py — right for the API as a service, wrong for an installed
    # application, where "which build am I running?" is answered by the
    # stamp the installer wrote. Since the installer no longer puts the
    # version in the file name, this is the only place a person can read
    # it.
    os.environ["PLANBENCH_VERSION"] = paths.version()
    # What a decision card's manifest records as the code that produced
    # it. `resolve_git_sha` already prefers this variable over shelling
    # out, and shelling out is what fails here: an installation has no
    # `.git`, so without this every selection run dies at the point of
    # writing its card.
    stamped = paths.commit()
    if stamped:
        os.environ.setdefault("PLANBENCH_GIT_SHA", stamped)
    _export_launcher_vars(env_path)
    applied = apply_profile_defaults(env_path)
    if applied:
        logging.getLogger("planbench.desktop").info(
            "deployment defaults applied for this build: %s", ", ".join(sorted(applied))
        )

    return Provisioned(root, first_run, nickname, credential)


__all__ = [
    "DEPLOYMENT_PROFILE",
    "PROFILE_DEFAULTS",
    "SEED_ACCOUNTS",
    "DEFAULT_NICKNAME",
    "DEFAULT_PASSWORD",
    "LAUNCHER_VARS",
    "SEEDED_ASSETS",
    "Provisioned",
    "provision",
]
