#!/usr/bin/env python3
"""
Shared AI hook logger — works with Claude Code, Gemini CLI, Codex, Cursor, Copilot.
Reads JSON from stdin, normalizes to common format, appends to .ai-log/session.jsonl
"""

import contextlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))


def git(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""
    return out.strip()


def cli_arg(prefix: str) -> str:
    """Return the value of the first ``--name=value`` argument."""
    for arg in sys.argv[1:]:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return ""


def canonical_path(path: str) -> str:
    """Normalize Windows extended paths and casing for safe root matching."""
    if path.startswith("\\\\?\\"):
        path = path[4:]
    return os.path.normcase(os.path.abspath(path))


def select_repo_root() -> bool:
    """Restrict a user-level hook to the explicitly configured repository.

    Without ``--repo-root`` the historical project-local behavior is kept.
    When it is provided, events from every other Codex workspace are ignored.
    The process also changes to the git root so relative ``.ai-log`` paths are
    stable when a session starts from a repository subdirectory.
    """
    expected = cli_arg("--repo-root=")
    if not expected:
        return True

    actual = git("git rev-parse --show-toplevel")
    if not actual or canonical_path(actual) != canonical_path(expected):
        return False

    os.chdir(actual)
    return True


def detect_tool(data: dict) -> str:
    """Detect which AI tool sent this hook event.

    Priority:
      1. --tool=NAME CLI argument (cross-platform: works in cmd.exe, PowerShell, bash)
      2. AI_TOOL_NAME env var (legacy, bash-only when set inline)
      3. Heuristics from payload shape
    """
    for arg in sys.argv[1:]:
        if arg.startswith("--tool="):
            return arg.split("=", 1)[1].lower()
    tool_env = os.environ.get("AI_TOOL_NAME", "").lower()
    if tool_env:
        return tool_env
    # Heuristics
    if "transcript_path" in data:
        return "codex"
    gemini_prefixes = ("Before", "After", "Session", "Pre", "Notification")
    if data.get("hook_event_name", "").startswith(gemini_prefixes):
        return "gemini"
    if data.get("hook_event_name", "")[0:1].islower():
        # camelCase event names → Cursor or Copilot
        if "workspace_roots" in data:
            return "cursor"
        if "toolName" in data:
            return "copilot"
    if "hook_event_name" in data:
        return "claude"
    return "unknown"


def resolve_claude_model(data: dict) -> str:
    """Claude Code hook payloads carry no top-level `model` field. Fall back
    to the session transcript (`transcript_path`), which logs one JSON object
    per turn with `message.model` set — read from the tail and take the most
    recent one."""
    transcript = data.get("transcript_path")
    if not transcript:
        return ""
    path = Path(transcript)
    if not path.is_file():
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 20000))
            chunk = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    for line in reversed(chunk.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message")
        model = message.get("model") if isinstance(message, dict) else None
        if model:
            return model
    return ""


def normalize(data: dict, tool: str) -> dict | None:
    """Normalize tool-specific payload to common log entry."""
    event = data.get("hook_event_name") or data.get("event", "")
    ts = datetime.now(VN_TZ).isoformat()

    # Resolve repo from git origin. When cwd is not a git working tree (or
    # origin isn't set), skip the event entirely — these entries can't be
    # tied back to a team on the server and would just clutter the pending
    # queue forever.
    origin = git("git remote get-url origin")
    if not origin:
        return None
    repo = origin.rstrip("/").split("/")[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    model = data.get("model", "")
    if not model and tool == "claude":
        model = resolve_claude_model(data)

    base = {
        "ts": ts,
        "tool": tool,
        "event": event,
        "session_id": (
            data.get("session_id") or data.get("conversation_id") or data.get("generation_id") or ""
        ),
        "model": model,
        "repo": repo,
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        "student": (
            git("git config user.email")
            or os.environ.get("USERNAME", os.environ.get("USER", "unknown"))
        ),
    }

    if tool == "claude":
        prompt = ""
        # UserPromptSubmit: prompt is at top level
        if event == "UserPromptSubmit":
            prompt = data.get("prompt", "")[:1000]
        # PostToolUse: extract from tool_input
        elif isinstance(data.get("tool_input"), dict):
            prompt = data["tool_input"].get("prompt") or data["tool_input"].get("content") or ""
        base.update(
            {
                "prompt": prompt,
                "tool_name": data.get("tool_name", ""),
                "tool_input": data.get("tool_input") if event != "UserPromptSubmit" else None,
                "tool_response": str(data.get("tool_response", ""))[:500],
            }
        )

    elif tool == "gemini":
        if event == "BeforeAgent":
            prompt = data.get("prompt", "")[:1000]
            base.update({"prompt": prompt})
        else:
            req = data.get("request", {})
            contents = req.get("contents", [])
            prompt = ""
            for c in reversed(contents):
                for part in c.get("parts", []):
                    if part.get("text"):
                        prompt = part["text"][:1000]
                        break
                if prompt:
                    break
            resp = data.get("response", {})
            answer = ""
            with contextlib.suppress(Exception):
                answer = resp["candidates"][0]["content"]["parts"][0]["text"][:500]
            base.update({"prompt": prompt, "response_summary": answer})

    elif tool == "codex":
        base.update(
            {
                "prompt": data.get("prompt", "")[:1000],
                "turn_id": data.get("turn_id", ""),
                "transcript_path": data.get("transcript_path", ""),
                "tool_name": data.get("tool_name", ""),
                "tool_input": data.get("tool_input"),
                "tool_response": data.get("tool_response"),
            }
        )

    elif tool == "cursor":
        base.update(
            {
                "prompt": data.get("prompt", "")[:1000],
                "files_context": data.get("attachments", []),
            }
        )

    elif tool == "copilot":
        base.update(
            {
                "prompt": data.get("prompt", "")[:1000],
                "tool_name": data.get("toolName", ""),
                "tool_args": data.get("toolArgs"),
            }
        )

    # Skip only true noise: no prompt AND no tool-specific payload (tool_input,
    # response_summary, tool_response, tool_args, files_context). Previously
    # this only checked `prompt`, which dropped Claude Bash/Edit events (their
    # tool_input has `command` / `file_path`, not `prompt` or `content`) and
    # any Gemini/Cursor/Copilot turn that carried context but no plain prompt.
    payload_keys = (
        "prompt",
        "tool_input",
        "response_summary",
        "tool_response",
        "tool_args",
        "files_context",
    )
    lifecycle_events = (
        "SessionStart",
        "sessionStart",
        "Stop",
        "stop",
        "SessionEnd",
        "sessionEnd",
        "AfterModel",
    )
    has_payload = any(base.get(k) for k in payload_keys)
    if not has_payload and event not in lifecycle_events:
        return None

    return base


def main():
    if not select_repo_root():
        # A user-level hook is active for all local Codex sessions. Return a
        # valid no-op response outside the one repository it is allowed to log.
        print("{}")
        return

    # Read stdin as UTF-8 explicitly. On Windows, sys.stdin defaults to the
    # system code page (e.g. cp1252), which corrupts non-Latin1 prompts
    # (Vietnamese, CJK, emoji) into mojibake. The hook payload is always UTF-8.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    if not raw:
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = detect_tool(data)
    entry = normalize(data, tool)
    if not entry:
        sys.exit(0)

    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "session.jsonl"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Codex validates hook output against event-specific schemas. An empty
    # object is a successful no-op for UserPromptSubmit, PostToolUse and Stop.
    # Other integrations keep the historical acknowledgement payload.
    print(json.dumps({} if tool == "codex" else {"status": "logged"}))


if __name__ == "__main__":
    main()
