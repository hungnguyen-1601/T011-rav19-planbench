"""Recover, where possible, which bundle each stored run actually ran.

Runs made before ``0014`` recorded no candidate identity. The migration
deliberately does not invent one: the answer is on disk, in each run's
manifest, and matching it back to a bundle means hashing stored archives.
A migration that guessed would write a claim nobody could check, and it
would write it in silence.

**What is matched, and why it is the manifest checksum.** A candidate's
identity hashes the checksum of the plugin's `plugin.json` (HĐ-1.3, and
`planbench_decision.candidate.manifest_checksum`), not the archive. So
the join is: for each stored bundle, hash its manifest; for each run,
read the manifest checksum its candidates recorded; match. A run whose
checksum matches nothing keeps ``bundle_id`` empty and reports a
reliance of ``unknown`` — which is the true answer, not a failure.

Read-only unless ``--write`` is passed. The default prints what it would
do, because a script that edits a decision record on first contact is a
script nobody runs twice.

    python scripts/backfill_run_candidates.py            # report only
    python scripts/backfill_run_candidates.py --write
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for package in ("apps/api", "packages/schemas", "packages/decision"):
    sys.path.insert(0, str(REPO_ROOT / package))


def manifest_checksum_of(archive: Path) -> str | None:
    """Hash the ``plugin.json`` inside a stored bundle archive.

    Returns ``None`` rather than raising for anything unreadable: a
    bundle whose archive is gone is a bundle this script cannot speak
    for, and the run that used it keeps saying ``unknown``.
    """
    try:
        with zipfile.ZipFile(archive) as bundle:
            manifest = next(
                (name for name in bundle.namelist() if name.endswith("plugin.json")), None
            )
            if manifest is None:
                return None
            return hashlib.sha256(bundle.read(manifest)).hexdigest()
    except (OSError, zipfile.BadZipFile):
        return None


def candidates_in(report: dict) -> list[dict]:
    """The candidate identities a stored report carries, if any."""
    rows = report.get("candidates") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [row for row in rows if isinstance(row, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="apply, rather than report")
    parser.add_argument("--database-url", default="", help="defaults to PLANBENCH_DATABASE_URL")
    args = parser.parse_args()

    import os

    from planbench_api.config import get_settings

    url = args.database_url or os.environ.get("PLANBENCH_DATABASE_URL", "")
    if not url:
        url = get_settings().database_url
    if not url:
        print("no database configured; nothing to backfill (in-memory storage keeps no runs)")
        return 0

    from sqlalchemy import select

    from planbench_api.db import SessionFactory, create_db_engine
    from planbench_api.db.models import (
        DecisionRunCandidateRow,
        DecisionRunRow,
        PluginBundleRow,
    )
    from planbench_api.model_storage import LocalModelStorage

    settings = get_settings()
    storage = LocalModelStorage(settings.model_dir)
    sessions = SessionFactory(create_db_engine(url))

    tally: Counter[str] = Counter()
    with sessions.begin() as session:
        by_manifest: dict[str, PluginBundleRow] = {}
        for bundle in session.scalars(select(PluginBundleRow)).all():
            digest = manifest_checksum_of(Path(storage.internal_location(bundle.storage_key)))
            if digest is None:
                tally["bundle archive unreadable"] += 1
                continue
            # Oldest wins, so repeating the script is stable.
            by_manifest.setdefault(digest, bundle)

        for run in session.scalars(select(DecisionRunRow)).all():
            existing = session.scalars(
                select(DecisionRunCandidateRow).where(DecisionRunCandidateRow.run_id == run.id)
            ).all()
            if existing:
                tally["already recorded"] += 1
                continue
            rows = candidates_in(run.report or {})
            if not rows:
                tally["report names no candidates"] += 1
                continue
            for slot, entry in enumerate(rows):
                digest = entry.get("manifest_checksum") or ""
                bundle = by_manifest.get(digest) if digest else None
                stack = entry.get("stack") or entry.get("candidate_id") or "?"
                if digest and bundle is None:
                    tally["no bundle matches the manifest checksum"] += 1
                elif not digest:
                    tally["built-in candidate"] += 1
                else:
                    tally["matched"] += 1
                if not args.write:
                    continue
                session.add(
                    DecisionRunCandidateRow(
                        run_id=run.id,
                        slot=slot,
                        stack=str(stack),
                        local_config=str(entry.get("local_config") or ""),
                        bundle_id=bundle.id if bundle is not None else None,
                        plugin_id=bundle.plugin_id if bundle is not None else None,
                        revision=bundle.revision if bundle is not None else None,
                        archive_checksum=bundle.checksum if bundle is not None else None,
                    )
                )
        if not args.write:
            session.rollback()

    width = max((len(name) for name in tally), default=0)
    for name, count in sorted(tally.items()):
        print(f"{name.ljust(width)}  {count}")
    if not args.write:
        print("\nreport only; pass --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
