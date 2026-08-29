"""Archive map rows that duplicate a row already holding the same grid.

**Archive, never delete.** A map is referenced by scenarios, by
simulations, by benchmarks and — by path — by deployments. Deleting a
duplicate turns every one of those references into a hole, and an audit
trail pointing at nothing is not an audit trail. Archiving takes the row
out of `GET /maps` and out of every picker built on it while leaving
`get(map_id)` answering exactly as before, so nothing that already
points at the row stops resolving. It is also reversible: clearing
`archived_at` puts the row back.

**Which row survives.** The oldest of each group, because that is what
`SqlMapRepository.find_by_checksum` returns and the two must agree — a
cleanup that kept the newest would leave `adopt()` handing out an id
this script had just archived. A row a deployment pins by path is never
archived regardless, on the same principle: something names it.

Dry run by default. Pass `--write` to apply.

    python scripts/dedupe_maps.py                 # report only
    python scripts/dedupe_maps.py --write         # apply
    python scripts/dedupe_maps.py --db other.db   # a copy first, ideally
"""

from __future__ import annotations

import argparse
import collections
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def pinned_map_ids(connection: sqlite3.Connection) -> set[str]:
    """Map ids named by a deployment's `environment.map` path.

    Deployments do not carry a `map_id` column — they name a file, and
    the file's stem carries the id and the version. Missing this is how
    a cleanup archives the ground under a stored comparison.
    """
    pinned: set[str] = set()
    for (environment,) in connection.execute("SELECT environment FROM task_profiles"):
        path = environment or ""
        if not path.startswith("maps/custom/") or "__v" not in path:
            continue
        stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        pinned.add(stem.rpartition("__v")[0])
    return pinned


def plan(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """`(id, name, keeper_id)` for every row this would archive."""
    groups: dict[str, list[sqlite3.Row]] = collections.defaultdict(list)
    rows = connection.execute(
        "SELECT id, name, checksum, created_at, archived_at FROM maps "
        "WHERE archived_at IS NULL ORDER BY created_at, id"
    ).fetchall()
    for row in rows:
        groups[row["checksum"]].append(row)

    pinned = pinned_map_ids(connection)
    doomed: list[tuple[str, str, str]] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        keeper = group[0]
        for row in group[1:]:
            if row["id"] in pinned:
                # Named by a deployment. Archiving it would take the
                # ground out from under a filed comparison for the sake
                # of a tidier list.
                continue
            doomed.append((row["id"], row["name"], keeper["id"]))
    return doomed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(REPO_ROOT / "planbench.db"))
    parser.add_argument("--write", action="store_true", help="apply; otherwise report only")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    total = connection.execute("SELECT COUNT(*) FROM maps WHERE archived_at IS NULL").fetchone()[0]
    doomed = plan(connection)

    by_keeper = collections.Counter(keeper for _, _, keeper in doomed)
    print(f"{total} live maps; {len(doomed)} of them duplicate an older row")
    for keeper, count in by_keeper.most_common():
        name = connection.execute("SELECT name FROM maps WHERE id = ?", (keeper,)).fetchone()
        print(f"  keep {keeper} ({name['name'] if name else '?'}) — archive {count}")

    if not doomed:
        print("nothing to do")
        return 0

    if not args.write:
        print("\ndry run. Re-run with --write to apply.")
        return 0

    stamp = connection.execute("SELECT datetime('now')").fetchone()[0]
    connection.executemany(
        "UPDATE maps SET archived_at = ? WHERE id = ? AND archived_at IS NULL",
        [(stamp, map_id) for map_id, _, _ in doomed],
    )
    connection.commit()
    print(f"\narchived {len(doomed)} rows at {stamp}")
    print("Reversible: UPDATE maps SET archived_at = NULL WHERE archived_at = '" + stamp + "';")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
