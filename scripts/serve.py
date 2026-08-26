"""Start the API on any platform, without installing anything.

    python scripts/serve.py                       # 127.0.0.1:8000
    python scripts/serve.py --host 0.0.0.0        # reachable from the LAN
    python scripts/serve.py --reload              # restart on edit
    python scripts/serve.py --migrate             # alembic upgrade head first

**Why this exists rather than "just run uvicorn".** The project is not
installed (``pyproject.toml`` says so, and per-package packaging is a
Phase 2+ item), so every package under ``packages/`` and ``services/``
reaches ``sys.path`` only because something puts it there. Running::

    python -m uvicorn planbench_api.main:app

from the repository root therefore fails on the *first* import —
``planbench_api`` itself — and fixing that by hand leads to
``planbench_decision``, then the next one, one traceback at a time. That
is a real session that happened on 2026-08-12, not a hypothetical.

``scripts/dev_stack.sh`` already solved this for Linux, WSL and macOS. It
is a bash script, and README's Windows answer was to double-click
``start.bat`` — a file that does not exist. So on native Windows there
was no supported way to start the server at all. This is that way, and it
works everywhere else too.

**The path list is read, not repeated.** ``pyproject.toml`` already
declares it for pytest, and it was copied into ``dev_stack.sh`` where it
promptly drifted: ``packages/decision`` was added for the suite and not
for the server, so 2277 tests passed against an API that could not boot.
A third hand-maintained copy would be a third chance at the same bug, so
this reads the declaration instead. ``tests/test_dev_stack_pythonpath.py``
holds the remaining pair in step.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: On pytest's path and deliberately not on the server's. ``.`` resolves
#: the ``src.*`` scaffold and ``tests`` makes shared test helpers
#: importable as top-level modules; the API has no business reaching
#: either, and putting them here would let a test helper shadow a real
#: module in production.
TEST_ONLY = frozenset({".", "tests"})


def source_paths() -> list[Path]:
    """The package roots, from the one place that declares them."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = config["tool"]["pytest"]["ini_options"]["pythonpath"]
    return [REPO_ROOT / entry for entry in declared if entry not in TEST_ONLY]


def install_paths() -> list[Path]:
    """Put the package roots on ``sys.path`` and in the environment.

    Both, and the second is not redundant: ``--reload`` starts a child
    process, and a child that inherits only this process's ``sys.path``
    would come up unable to import anything. Prepended rather than
    appended so a stale copy installed in site-packages cannot win over
    the working tree — silently serving yesterday's code is worse than
    not starting.
    """
    paths = source_paths()
    for path in reversed(paths):
        entry = str(path)
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)

    existing = os.environ.get("PYTHONPATH", "")
    ours = os.pathsep.join(str(path) for path in paths)
    os.environ["PYTHONPATH"] = f"{ours}{os.pathsep}{existing}" if existing else ours
    return paths


def default_database() -> str:
    """Persist to SQLite unless told otherwise — same rule as dev_stack.sh.

    **Unset and empty are different things, and the difference is the
    whole point.** Absent means "nobody chose", and the useful default is
    the file, so accounts, profiles and stored runs survive a restart.
    An explicit empty string means somebody chose the in-memory backend
    on purpose, and overriding that would take away the only way to ask
    for a throwaway server.

    Without this, the two launchers disagreed: ``dev_stack.sh`` persisted
    and a bare ``serve.py`` did not, so the same repository served
    different data depending on how it was started — and `/decisions`
    came up empty for reasons that had nothing to do with the decision
    layer.
    """
    chosen = os.environ.get("PLANBENCH_DATABASE_URL")
    if chosen is None:
        chosen = f"sqlite:///{REPO_ROOT / 'planbench.db'}"
        os.environ["PLANBENCH_DATABASE_URL"] = chosen
    return chosen


def migrate() -> None:
    """``alembic upgrade head``, the same step ``dev_stack.sh`` runs.

    Through a subprocess rather than the Python API because alembic reads
    ``alembic.ini`` relative to the working directory, and because a
    migration failure should print alembic's own message rather than a
    stack trace from inside this script.
    """
    print("alembic upgrade head", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"alembic upgrade failed ({result.returncode}). The API is not started: "
            "a server running against a schema older than its models fails later, "
            "further away, and with a worse error."
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # 127.0.0.1 by default. `dev_stack.sh` binds the loopback too, and a
    # development server carrying real evaluation data should be asked
    # for explicitly before it listens on every interface.
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="run `alembic upgrade head` first, as dev_stack.sh does",
    )
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args(argv)

    paths = install_paths()
    print(f"source roots: {len(paths)} on PYTHONPATH (from pyproject.toml)", flush=True)

    database = default_database()
    print(f"database:     {database or 'in-memory (nothing is kept)'}", flush=True)

    if args.migrate:
        migrate()

    import uvicorn

    if args.host == "0.0.0.0":  # noqa: S104 - the warning is the point
        print(
            "⚠ binding 0.0.0.0: the API is reachable from the network. Development "
            "auth and the mock agent provider are not built for that.",
            flush=True,
        )

    uvicorn.run(
        "planbench_api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        # Reload has to be told what to watch: without this it watches the
        # working directory, which here includes artifacts/ and traces/ —
        # a running benchmark would restart the server under itself.
        reload_dirs=[str(path) for path in paths] if args.reload else None,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
