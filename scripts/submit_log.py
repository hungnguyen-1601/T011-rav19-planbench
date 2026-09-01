#!/usr/bin/env python3
"""
Submit .ai-log/session.jsonl to grading server, and rotate it either way.
Called by git pre-push hook or manually.

The live log is rotated on every push:
  - Each entry is appended to .ai-log/archive/<its own date>.jsonl
  - Appended, never overwritten; the hook recreates session.jsonl
  - Rotation happens whether or not a server is configured

If the POST fails, the pending file is restored so nothing is lost.

**Rotation used to be conditional on submitting, and that lost the point
of it.** `AI_LOG_SERVER` is unset on this machine, so `main` returned at
its first line — before the rename — and the live file simply grew: five
hundred and forty-two entries across two days had to be filed by hand on
2026-08-31, and three pushes before that committed a session file that
should have been empty. The archive is the record of the work; submitting
it somewhere is a separate errand, and failing at the errand is no reason
to skip the record.

**Entries are filed under the day they happened, not the day the push
ran.** The two differ whenever a session crosses midnight or a rotation
is late, and a reader asking what was done on the 30th should not have to
know when somebody happened to push.
"""

import contextlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _load_dotenv_by_hand() -> None:
    """Read `.env` without python-dotenv.

    The import used to fall through to `pass`, which meant a Python
    lacking the package produced "AI_LOG_SERVER not set" — a message that
    names the wrong missing thing and reads like a configuration choice.
    Logs were dropped for days behind it. This file is a handful of
    `KEY=value` lines; parsing it is cheaper than the failure mode.
    """
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            # A real environment variable outranks the file, which is
            # what `load_dotenv` does and what CI relies on.
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    _load_dotenv_by_hand()

SERVER_URL = os.environ.get("AI_LOG_SERVER", "")
API_KEY = os.environ.get("AI_LOG_API_KEY", "")
LOG_DIR = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
LOG_FILE = LOG_DIR / "session.jsonl"
ARCHIVE_DIR = LOG_DIR / "archive"

# Match server-side MAX_BATCH_ENTRIES so we never get a 422.
# If the local file has more than this, we submit the oldest BATCH_LIMIT
# and leave the rest for the next push.
BATCH_LIMIT = 500


def _normalize_for_ingest(entry: dict) -> dict:
    """Adapt locally lossless hook data to the server's current schema."""
    response = entry.get("tool_response")
    if response is not None and not isinstance(response, str):
        entry["tool_response"] = json.dumps(response, ensure_ascii=False, default=str)
    return entry


def _day_of(line: bytes, fallback: str) -> str:
    """The date an entry belongs under.

    ``fallback`` carries the day of the line before it, so a line this
    cannot parse is filed beside its neighbours rather than dropped or
    swept into today. Nothing here is allowed to lose a line: an entry
    that cannot be read is still evidence that something happened.
    """
    with contextlib.suppress(Exception):
        stamp = json.loads(line.decode("utf-8"))["ts"]
        if isinstance(stamp, str) and len(stamp) >= 10:
            return stamp[:10]
    return fallback


def _archive_lines(lines: list[bytes]) -> dict[str, int]:
    """Append each line to the archive for the day it happened.

    Appended, never overwritten, and grouped so one open per day does
    the work rather than one per line. Returns what went where, which is
    what the caller prints — a rotation that says nothing is a rotation
    nobody notices has stopped.
    """
    if not lines:
        return {}
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    by_day: dict[str, list[bytes]] = {}
    day = today
    for line in lines:
        day = _day_of(line, day)
        by_day.setdefault(day, []).append(line)
    for name, rows in by_day.items():
        with open(ARCHIVE_DIR / f"{name}.jsonl", "ab") as fh:
            fh.write(b"\n".join(rows) + b"\n")
    return {name: len(rows) for name, rows in by_day.items()}


def _read_lines(path: Path) -> list[bytes]:
    """The file as lines, with blanks dropped and no trailing empty."""
    if not path.exists():
        return []
    return [line for line in path.read_bytes().split(b"\n") if line.strip()]


def _restore_pending(pending: Path) -> None:
    """Failure path: put pending back at LOG_FILE so the next push retries.
    If hook wrote new entries to LOG_FILE in the meantime, prepend pending."""
    if not pending.exists():
        return
    if LOG_FILE.exists():
        # Concat: pending (older) + LOG_FILE (newer) → LOG_FILE
        tmp = LOG_FILE.with_suffix(".merge.jsonl")
        with open(tmp, "wb") as out:
            with open(pending, "rb") as a:
                shutil.copyfileobj(a, out)
            with open(LOG_FILE, "rb") as b:
                shutil.copyfileobj(b, out)
        os.replace(tmp, LOG_FILE)
        pending.unlink()
    else:
        pending.rename(LOG_FILE)


def _rotate_only(pending: Path) -> None:
    """File the batch and stop, for when there is nowhere to submit it.

    The whole file goes, not the first `BATCH_LIMIT`: that ceiling exists
    to keep a POST under the server's own limit, and with no POST there is
    nothing to defer.
    """
    filed = _archive_lines(_read_lines(pending))
    pending.unlink()
    where = ", ".join(f"{name} (+{count})" for name, count in sorted(filed.items()))
    print(f"[ai-log] Archived {sum(filed.values())} entries → {where}", file=sys.stderr)


def main():
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        print("[ai-log] No logs to rotate.", file=sys.stderr)
        sys.exit(0)

    if not SERVER_URL:
        # **Rotate anyway.** Returning here was the bug: no server meant no
        # archiving either, so the live file grew without limit and every
        # push committed a session log that should have been empty. The
        # archive is the record of the work; the POST is an errand.
        pending = LOG_FILE.with_name(f"session.pending.{int(time.time())}.jsonl")
        try:
            LOG_FILE.rename(pending)
        except FileNotFoundError:
            sys.exit(0)
        print("[ai-log] AI_LOG_SERVER not set — archiving locally.", file=sys.stderr)
        _rotate_only(pending)
        sys.exit(0)

    # Atomic rename closes the race window: hook writes that arrive after this
    # land in a fresh LOG_FILE, not in the batch we're about to POST.
    pending = LOG_FILE.with_name(f"session.pending.{int(time.time())}.jsonl")
    try:
        LOG_FILE.rename(pending)
    except FileNotFoundError:
        print("[ai-log] No logs to submit.", file=sys.stderr)
        sys.exit(0)

    # **Which raw lines back the batch, not only the parsed entries.**
    # The batch is what gets POSTed; the raw lines beside it are what gets
    # archived, and the two have to name the same set. Archiving the whole
    # pending file while also handing the leftover back to the live log
    # filed those entries twice — 107 of them are duplicated in
    # archive/2026-08-30.jsonl, in one run beginning at index 500, which is
    # BATCH_LIMIT exactly.
    entries = []
    submitted_lines: list[bytes] = []
    leftover_lines: list[bytes] = []
    for line in _read_lines(pending):
        if len(entries) >= BATCH_LIMIT:
            leftover_lines.append(line)
            continue
        submitted_lines.append(line)
        # An unparseable line is dropped from the batch rather than
        # aborting it, and still archived: it is evidence either way.
        with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
            entries.append(_normalize_for_ingest(json.loads(line.decode("utf-8"))))

    if not entries:
        # Nothing to send; archive whatever was there (probably junk) and bail.
        _archive_lines(submitted_lines + leftover_lines)
        pending.unlink()
        print("[ai-log] No valid entries to submit.", file=sys.stderr)
        sys.exit(0)

    payload = json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(
        SERVER_URL,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[ai-log] Submitted {len(entries)} entries → {resp.status}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        # HTTPError is also a URLError, but it carries the validation response
        # body. Preserve it so schema failures such as 422 can be diagnosed
        # instead of being reduced to an opaque status line.
        with contextlib.suppress(Exception):
            detail = e.read().decode("utf-8", errors="replace").strip()
        if not detail:
            detail = str(e)
        _restore_pending(pending)
        print(
            f"[ai-log] Submit failed: HTTP {e.code}: {detail[:4000]} — logs kept locally.",
            file=sys.stderr,
        )
        sys.exit(0)  # Don't block push on server validation errors
    except urllib.error.URLError as e:
        # Failure: restore the whole pending (including leftover) for next push.
        _restore_pending(pending)
        print(f"[ai-log] Submit failed: {e} — logs kept locally.", file=sys.stderr)
        sys.exit(0)  # Don't block push on server error

    # Success: archive exactly what was submitted, then hand the leftover
    # back. The leftover is deliberately *not* archived here — it has not
    # been submitted, and the next push will archive it when it is.
    filed = _archive_lines(submitted_lines)
    pending.unlink()
    where = ", ".join(f"{name} (+{count})" for name, count in sorted(filed.items()))
    print(f"[ai-log] Archived {sum(filed.values())} entries → {where}", file=sys.stderr)

    if leftover_lines:
        # More than BATCH_LIMIT entries existed; put the rest back so the
        # next push picks them up.
        with open(LOG_FILE, "ab") as f:
            f.write(b"\n".join(leftover_lines) + b"\n")
        print(
            f"[ai-log] {len(leftover_lines)} entries deferred to next push.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
