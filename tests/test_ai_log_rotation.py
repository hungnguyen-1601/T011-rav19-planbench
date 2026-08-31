"""The session log has to reach the archive, and reach it once.

`.ai-log` is the record of what was done and when, so the failure modes
here are not cosmetic: an entry that never rotates is evidence sitting in
a file that grows without limit, and an entry that rotates twice is a
count nobody can trust.

Both had happened before these tests existed.

* `AI_LOG_SERVER` is unset on the machine this runs on, and `main`
  returned at its first line — before the rename — so nothing was ever
  archived. Five hundred and forty-two entries across two days had to be
  filed by hand on 2026-08-31, and three pushes before that committed a
  session file that should have been empty.
* The success path archived the whole pending file *and* handed the
  entries past `BATCH_LIMIT` back to the live log, which archived them
  again on the next push. `archive/2026-08-30.jsonl` carries 107 entries
  twice, in one unbroken run beginning at index 500.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _submitter(tmp_path: Path, *, server: str = ""):  # type: ignore[no-untyped-def]
    """The script, imported fresh against a throwaway log directory.

    Reimported per test because it reads its paths at module scope, which
    is fine for a script run once by a hook and would otherwise leak one
    test's directory into the next.
    """
    import os

    os.environ["AI_LOG_DIR"] = str(tmp_path / ".ai-log")
    os.environ["AI_LOG_SERVER"] = server
    spec = importlib.util.spec_from_file_location(
        "submit_log_under_test", REPO / "scripts" / "submit_log.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _entry(day: str, index: int) -> str:
    return json.dumps(
        {"ts": f"{day}T09:{index // 60:02d}:{index % 60:02d}.000000+07:00", "n": index},
        ensure_ascii=False,
    )


def _write_log(module, lines: list[str]) -> None:  # type: ignore[no-untyped-def]
    module.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    module.LOG_FILE.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def _archived(module) -> dict[str, list[dict]]:  # type: ignore[no-untyped-def]
    out: dict[str, list[dict]] = {}
    if not module.ARCHIVE_DIR.exists():
        return out
    for path in sorted(module.ARCHIVE_DIR.glob("*.jsonl")):
        out[path.stem] = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
        ]
    return out


class TestRotationHappensWithoutAServer:
    """Returning early when nothing can be submitted skipped the archiving
    too, and archiving is the part that matters locally."""

    def test_entries_reach_the_archive(self, tmp_path: Path) -> None:
        module = _submitter(tmp_path)
        _write_log(module, [_entry("2026-08-30", i) for i in range(5)])
        with pytest.raises(SystemExit) as exit_code:
            module.main()
        assert exit_code.value.code == 0
        assert [row["n"] for row in _archived(module)["2026-08-30"]] == [0, 1, 2, 3, 4]

    def test_the_live_log_is_emptied(self, tmp_path: Path) -> None:
        module = _submitter(tmp_path)
        _write_log(module, [_entry("2026-08-30", i) for i in range(3)])
        with pytest.raises(SystemExit):
            module.main()
        assert not module.LOG_FILE.exists() or module.LOG_FILE.stat().st_size == 0

    def test_no_pending_file_is_left_behind(self, tmp_path: Path) -> None:
        """Two orphaned `session.pending.*` files sit in this repository
        from rotations that renamed and then never finished."""
        module = _submitter(tmp_path)
        _write_log(module, [_entry("2026-08-30", i) for i in range(3)])
        with pytest.raises(SystemExit):
            module.main()
        assert list(module.LOG_DIR.glob("session.pending.*")) == []

    def test_the_whole_file_goes_not_the_first_batch(self, tmp_path: Path) -> None:
        """`BATCH_LIMIT` keeps a POST under the server's own ceiling. With
        no POST there is nothing to defer, and deferring would leave the
        overflow in the live file for a rotation that never comes."""
        module = _submitter(tmp_path)
        count = module.BATCH_LIMIT + 40
        _write_log(module, [_entry("2026-08-30", i) for i in range(count)])
        with pytest.raises(SystemExit):
            module.main()
        assert len(_archived(module)["2026-08-30"]) == count


class TestAnEntryIsFiledUnderTheDayItHappened:
    def test_a_session_crossing_midnight_splits(self, tmp_path: Path) -> None:
        module = _submitter(tmp_path)
        _write_log(
            module,
            [_entry("2026-08-30", 1), _entry("2026-08-30", 2), _entry("2026-08-31", 3)],
        )
        with pytest.raises(SystemExit):
            module.main()
        filed = _archived(module)
        assert [row["n"] for row in filed["2026-08-30"]] == [1, 2]
        assert [row["n"] for row in filed["2026-08-31"]] == [3]

    def test_an_existing_archive_is_appended_never_replaced(self, tmp_path: Path) -> None:
        module = _submitter(tmp_path)
        module.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        (module.ARCHIVE_DIR / "2026-08-30.jsonl").write_bytes(
            (_entry("2026-08-30", 0) + "\n").encode("utf-8")
        )
        _write_log(module, [_entry("2026-08-30", 1)])
        with pytest.raises(SystemExit):
            module.main()
        assert [row["n"] for row in _archived(module)["2026-08-30"]] == [0, 1]

    def test_a_line_that_cannot_be_read_is_kept_beside_its_neighbours(self, tmp_path: Path) -> None:
        """Dropping it would lose evidence and sweeping it into today
        would misdate it. It goes where the line before it went."""
        module = _submitter(tmp_path)
        _write_log(module, [_entry("2026-08-30", 1), "{not json at all", _entry("2026-08-30", 2)])
        with pytest.raises(SystemExit):
            module.main()
        rows = (module.ARCHIVE_DIR / "2026-08-30.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(rows) == 3
        assert "{not json at all" in rows

    def test_an_undateable_first_line_falls_back_to_today(self, tmp_path: Path) -> None:
        module = _submitter(tmp_path)
        _write_log(module, ["{not json at all"])
        with pytest.raises(SystemExit):
            module.main()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        assert (module.ARCHIVE_DIR / f"{today}.jsonl").exists()


class TestNothingIsArchivedTwice:
    """The bug this class exists for is visible in the repository: 107
    entries appear twice in `archive/2026-08-30.jsonl`, in one run
    starting at index 500."""

    def test_the_deferred_overflow_is_not_archived_yet(self, tmp_path: Path) -> None:
        """With a server configured and reachable, only the submitted
        batch is filed. The rest goes back to the live log and is filed
        when it too has been sent."""
        module = _submitter(tmp_path, server="http://localhost:9/ingest")
        count = module.BATCH_LIMIT + 7
        _write_log(module, [_entry("2026-08-30", i) for i in range(count)])
        sent: dict[str, int] = {}

        class _Response:
            status = 200

            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, *_: object) -> None:
                return None

        def _urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
            sent["entries"] = len(json.loads(request.data.decode("utf-8"))["entries"])
            return _Response()

        module.urllib.request.urlopen = _urlopen  # type: ignore[assignment]
        module.main()

        assert sent["entries"] == module.BATCH_LIMIT
        assert len(_archived(module)["2026-08-30"]) == module.BATCH_LIMIT
        assert len(module.LOG_FILE.read_text(encoding="utf-8").splitlines()) == 7

    def test_the_overflow_survives_to_be_archived_next_time(self, tmp_path: Path) -> None:
        """The deferred entries are the ones the old code archived early
        and then handed back. Whatever else changes, they must still be
        in the live log afterwards, exactly once."""
        module = _submitter(tmp_path, server="")
        count = module.BATCH_LIMIT + 7
        _write_log(module, [_entry("2026-08-30", i) for i in range(count)])
        with pytest.raises(SystemExit):
            module.main()
        filed = [row["n"] for row in _archived(module)["2026-08-30"]]
        assert filed == list(range(count))
        assert len(filed) == len(set(filed))


class TestAFailedSubmitLosesNothing:
    def test_the_batch_returns_to_the_live_log(self, tmp_path: Path) -> None:
        """A server that refuses must leave the machine where it found
        it, so the next push can try again with the same evidence."""
        module = _submitter(tmp_path, server="http://localhost:9/ingest")
        _write_log(module, [_entry("2026-08-30", i) for i in range(4)])

        def _urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
            raise module.urllib.error.URLError("refused")

        module.urllib.request.urlopen = _urlopen  # type: ignore[assignment]
        with pytest.raises(SystemExit) as exit_code:
            module.main()
        assert exit_code.value.code == 0, "a failed submit must not block the push"
        assert len(module.LOG_FILE.read_text(encoding="utf-8").splitlines()) == 4
        assert _archived(module) == {}, "nothing is filed until it has been sent"
