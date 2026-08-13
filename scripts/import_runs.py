"""Load runs already on disk into the API's store.

    python scripts/import_runs.py            # import everything under artifacts/runs
    python scripts/import_runs.py --dry-run  # say what would happen, change nothing

**Why this is needed at all.** The decision layer was built as pure
functions over files: ``compare.py`` writes ``comparison_report.json``
and friends under ``artifacts/runs/``, and that is where every real
measurement this project has made still lives. The API stores runs in a
database, and stores only what it computed itself. So on 2026-08-12 there
were fourteen run directories on disk, six of them full comparisons, and
``GET /decisions`` returned ``[]`` — the page rendered "no runs yet" over
a repository full of evidence.

**Nothing here invents a value.** Older reports predate fields that were
added later: ``run_uri`` and ``run_checksum`` arrived with A2,
``constraints`` on the manifest with contract 6.4.0, and
``gate_only_deployment`` with 6.5.0. They import as null, because a null
means "this run did not record it" and a filled-in guess would be a claim
about a measurement nobody made. The one field with no honest source at
all is ``contracts_version`` for a run that produced no card: the report
does not carry it, so it imports as ``unknown`` rather than as today's
version, which would date the run wrongly.

**Nothing here is approved.** Every imported run lands ``unreviewed``,
and ``config_state`` follows the same rule the service uses on insert:
``pending`` where a card exists, ``not_applicable`` where none does. An
import is a filing action, not a human one (HĐ-14).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TEST_ONLY = frozenset({".", "tests"})


def _install_paths() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for entry in reversed(config["tool"]["pytest"]["ini_options"]["pythonpath"]):
        if entry in TEST_ONLY:
            continue
        sys.path.insert(0, str(REPO_ROOT / entry))


_install_paths()

import yaml  # noqa: E402
from sqlalchemy import create_engine, inspect  # noqa: E402

from planbench_api.db.decision_repositories import (  # noqa: E402
    SqlDecisionRunRepository,
    SqlTaskProfileRepository,
)
from planbench_api.db.session import SessionFactory  # noqa: E402
from planbench_api.decisions import StoredDecisionRun  # noqa: E402
from planbench_api.errors import NotFoundError  # noqa: E402
from planbench_schemas.task_profile import TaskProfile  # noqa: E402

DEFAULT_RUN_ROOT = REPO_ROOT / "artifacts" / "runs"
DEFAULT_PROFILE_DIR = REPO_ROOT / "profiles"
DEFAULT_DATABASE = f"sqlite:///{REPO_ROOT / 'planbench.db'}"


def run_id_for(directory: Path) -> str:
    """A stable id derived from where the run lives.

    Deterministic on purpose: re-running the import must not file the
    same measurement twice under two ids, because the second copy would
    then be reviewed and approved separately from the first.
    """
    relative = directory.resolve().relative_to(REPO_ROOT).as_posix()
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:32]


def load_profile(profile_id: str, profile_dir: Path) -> dict | None:
    """The deployment this run was measured on, as the API stores it.

    ``decision_runs`` has a real foreign key into ``task_profiles``, and
    that is deliberate (a run is a statement *about* a deployment). So a
    run whose profile is not on disk cannot be filed, and saying so is
    better than filing it against a stub nobody declared.

    **Validated and dumped, not passed through.** This used to return the
    parsed YAML unchanged, which made the sentence above false: HĐ-2's
    document form writes a pose as ``[x, y, theta]`` while
    ``POST /task-profiles`` stores what ``model_dump`` produces,
    ``{x, y, theta}``. Two importers of one contract therefore filed two
    shapes, and a reader written against either one broke on rows from
    the other — which is exactly how `/simulate` came to crash on first
    paint against the shipped deployments.

    Validating here also means an unparseable profile is refused at
    import rather than filed as a row nothing downstream can read.
    """
    path = profile_dir / f"{profile_id}.yaml"
    if not path.is_file():
        return None
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TaskProfile.model_validate(loaded).model_dump(mode="json")


def stored_run(directory: Path, report: dict) -> StoredDecisionRun:
    card = report.get("decision_card")
    identity = report.get("identity", {})
    return StoredDecisionRun(
        id=run_id_for(directory),
        task_profile_id=identity["task_profile_id"],
        artifact_kind="decision_card" if card else "comparison",
        experiment_scope=identity.get("experiment_scope"),
        # The report does not carry it, and the card does only when there
        # is a card. Stamping today's version on a run from two days ago
        # would misdate it.
        contracts_version=(card or {}).get("contracts_version", "unknown"),
        created_at=identity.get("created_at", ""),
        # Runs made from the CLI have no account behind them, and
        # inventing one would put a name in the audit trail that never
        # acted.
        created_by=None,
        report=report,
        card=card,
        manifest=report.get("manifest"),
        recommended_candidate_id=(card or {}).get("recommended", {}).get("candidate_id"),
        status=(card or {}).get("status"),
        run_uri=report.get("run_uri"),
        run_checksum=report.get("run_checksum"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    reports = sorted(args.run_root.glob("*/*/comparison_report.json"))
    if not reports:
        print(f"no comparison_report.json under {args.run_root}")
        return 0

    engine = create_engine(args.database)
    if not args.dry_run and "decision_runs" not in set(inspect(engine).get_table_names()):
        raise SystemExit(
            f"{args.database} has no decision_runs table. Run migrations first:\n"
            "  .venv/Scripts/python.exe -m alembic upgrade head"
        )
    sessions = SessionFactory(engine)
    profiles = SqlTaskProfileRepository(sessions)
    runs = SqlDecisionRunRepository(sessions)

    filed = skipped = missing = 0
    for path in reports:
        directory = path.parent
        report = json.loads(path.read_text(encoding="utf-8"))
        label = directory.name
        profile_id = report.get("identity", {}).get("task_profile_id")
        if not profile_id:
            print(f"  ?  {label}: report has no task_profile_id — skipped")
            missing += 1
            continue

        profile = load_profile(profile_id, args.profiles)
        if profile is None:
            print(f"  ?  {label}: deployment {profile_id!r} not in {args.profiles} — skipped")
            missing += 1
            continue

        run = stored_run(directory, report)
        if args.dry_run:
            print(f"  +  {label}  ({run.artifact_kind}, {run.id})")
            filed += 1
            continue

        # Idempotent by the id, not by content: a second import of the
        # same directory must not produce a second row to review.
        try:
            runs.get(run.id)
        except NotFoundError:
            pass
        else:
            print(f"  =  {label}: already filed as {run.id}")
            skipped += 1
            continue

        profiles.create(profile)
        runs.create(run)
        card = "card" if run.card else "gate table only"
        print(f"  +  {label}  ({card})")
        filed += 1

    verb = "would file" if args.dry_run else "filed"
    print(f"\n{verb} {filed}, already present {skipped}, skipped {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
