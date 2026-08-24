#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

_test_py() {
  [ -n "${1:-}" ] && "$@" -c "import sys" >/dev/null 2>&1
}

PY=""
TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [ -n "$TOPLEVEL" ] && [ -x "$TOPLEVEL/.venv/bin/python" ] && _test_py "$TOPLEVEL/.venv/bin/python"; then
  PY="$TOPLEVEL/.venv/bin/python"
elif [ -n "$TOPLEVEL" ] && [ -x "$TOPLEVEL/.venv/Scripts/python.exe" ] && _test_py "$TOPLEVEL/.venv/Scripts/python.exe"; then
  PY="$TOPLEVEL/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1 && _test_py python3; then
  PY=python3
elif command -v python >/dev/null 2>&1 && _test_py python; then
  PY=python
elif command -v py >/dev/null 2>&1 && _test_py py -3; then
  PY="py -3"
else
  # PATH lookup failed — probe standard Windows install locations.
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ] && _test_py "$cand"; then
      PY="$cand"
      break
    fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

# shellcheck disable=SC2086
exec $PY "$@"
