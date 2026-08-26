#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

# The repo venv first, when it exists. Not a preference — the hooks read
# `.env` through python-dotenv, which is installed there and nowhere
# else. A system python3 imports nothing, `submit_log.py` falls through
# its `except ImportError: pass`, and every log is skipped with a message
# that names the missing *variable* rather than the missing package. That
# is how 263 entries sat unsent while the hook printed a tidy reason.
if [ -x "$(git rev-parse --show-toplevel 2>/dev/null)/.venv/bin/python" ]; then
  PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
elif [ -x "$(git rev-parse --show-toplevel 2>/dev/null)/.venv/Scripts/python.exe" ]; then
  PY="$(git rev-parse --show-toplevel)/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
elif command -v py >/dev/null 2>&1; then
  PY="py -3"
else
  # PATH lookup failed — probe standard Windows install locations.
  PY=""
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ]; then PY="$cand"; break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

# shellcheck disable=SC2086
exec $PY "$@"
