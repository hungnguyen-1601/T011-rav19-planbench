"""What is waiting to be reviewed, and the one command that approves it — W1.6.

An approved trait row may back a promoted claim, so approving one is a
person's decision and not a step in a pipeline. This script is the
person's side of it: it lists what the table holds, says which anchors a
reader could actually go and check, and records one approval at a time
under the name of whoever made it.

    python scripts/review_algorithm_traits.py list
    python scripts/review_algorithm_traits.py approve dwa --by "An Tong"
    python scripts/review_algorithm_traits.py seed

Nothing here approves anything on its own, and there is deliberately no
``--all``: a review that can be done for six rows with one flag is a
review that will be.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("schemas", "planning", "metrics", "benchmark", "decision", "explanation"):
    sys.path.insert(0, str(ROOT / "packages" / package))
sys.path.insert(0, str(ROOT / "services" / "simulator"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from planbench_api.db import (  # noqa: E402
    SessionFactory,
    SqlTraitRepository,
    create_all,
    create_db_engine,
)
from planbench_benchmark.outcome import TRAITS  # noqa: E402
from planbench_benchmark.traits_review import (  # noqa: E402
    ReviewRefusal,
    approve,
    awaiting_review,
    summarise,
)
from planbench_benchmark.traits_store import entries_from_mapping  # noqa: E402

DEFAULT_URL = f"sqlite:///{(ROOT / 'planbench.db').as_posix()}"


def repository(url: str) -> SqlTraitRepository:
    engine = create_db_engine(url)
    create_all(engine)
    return SqlTraitRepository(SessionFactory(engine))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=DEFAULT_URL)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="every row, its status and whether its anchor is checkable")
    commands.add_parser("seed", help="write the shipped natures as draft rows, once")
    approving = commands.add_parser("approve", help="record one review")
    approving.add_argument("algorithm_id")
    approving.add_argument("--by", required=True, help="who is accountable for this approval")

    args = parser.parse_args()
    traits = repository(args.database_url)

    if args.command == "seed":
        written = traits.seed(entries_from_mapping(TRAITS))
        print(f"{written} row(s) written as draft; existing rows were left alone")
        return 0

    if args.command == "list":
        source = traits.load()
        if not source.entries:
            print("the table is empty; run `seed` to write the shipped natures as drafts")
            return 0
        print(summarise(source.entries))
        pending = awaiting_review(source)
        print()
        print(
            f"{len(pending)} of {len(source.entries)} row(s) may inform a hypothesis "
            "and may not back a claim"
        )
        return 0

    entry = traits.get(args.algorithm_id)
    if entry is None:
        print(f"no trait row for {args.algorithm_id!r}")
        return 1
    try:
        reviewed = approve(
            entry, reviewed_by=args.by, at=datetime.now(UTC).isoformat(timespec="seconds")
        )
    except ReviewRefusal as refused:
        print(f"refused: {refused}")
        return 1
    traits.save(reviewed)
    print(f"{reviewed.algorithm_id} approved by {reviewed.reviewed_by} at {reviewed.updated_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
