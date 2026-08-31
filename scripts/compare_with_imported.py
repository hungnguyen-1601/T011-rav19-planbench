"""``compare.py``, with the imported algorithms this deployment holds.

``compare.py`` knows the built-in registry and nothing else, which is
correct for what it was written for and wrong for one question: the only
pairing on record that produced a *supported* contrast — a detector
firing on one side of an episode and not the other — put DWA against an
imported VFH+ controller, and the built-in registry has no second local
controller to put against DWA at all. Every built-in pairing varies a
config or a planner, the two stacks then behave alike, and no detector
separates them.

So this reads the bundles a deployment has installed, registers them the
way the API does at startup, and hands the rest to ``compare.py``. The
database is opened **read-only**: this is somebody's running deployment,
and a script that generates experiment data has no business writing to
it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _package in (
    "packages/schemas",
    "packages/benchmark",
    "packages/decision",
    "packages/explanation",
    "packages/plugin_sdk",
    "packages/metrics",
    "packages/planning",
    "services/simulator",
    "ml",
    "services/tracking",
    "services/agent_service",
    "services/analyst_service",
    "apps/api",
    "apps/desktop",
    "scripts",
):
    sys.path.insert(0, str(REPO_ROOT / _package))

import compare  # noqa: E402


def register_imported(database: Path, install_root: Path) -> list[str]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from planbench_api.artifacts import FileSystemArtifactStore
    from planbench_api.db.repositories import SqlRepositoryHub
    from planbench_api.plugin_service import sync_catalogue

    engine = create_engine(f"sqlite:///{database}?mode=ro", connect_args={"uri": True})
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    hub = SqlRepositoryHub(sessions, FileSystemArtifactStore(install_root.parent))
    return sync_catalogue(hub.plugin_bundles, install_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--list-only", action="store_true")
    known, rest = parser.parse_known_args(argv)

    registered = register_imported(known.database, known.install_root)
    print(f"imported algorithms registered: {', '.join(registered) or 'none'}", file=sys.stderr)
    if known.list_only:
        return 0
    return compare.main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
