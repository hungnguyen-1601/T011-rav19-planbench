#!/usr/bin/env bash
#
# Start, stop and inspect the local PlanBench stack.
#
#   ./scripts/dev_stack.sh start
#   ./scripts/dev_stack.sh stop
#   ./scripts/dev_stack.sh restart
#   ./scripts/dev_stack.sh status
#   ./scripts/dev_stack.sh logs
#

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

# ================================================================
# Load .env
# ================================================================

# Export every variable loaded from .env so the API and frontend
# processes can read them.
if [[ -f "$ENV_FILE" ]]; then
  set -a
  set +u

  # shellcheck disable=SC1090
  source "$ENV_FILE"

  set -u
  set +a
fi

# ================================================================
# Load Node.js/npm from NVM inside WSL
# ================================================================

# start.bat launches a fresh non-interactive WSL shell.
# NVM is normally loaded only in interactive terminals, so without this
# block the script may accidentally use Windows npm from /mnt/c/.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  set +u

  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"

  # Try the default NVM version first.
  nvm use --silent default >/dev/null 2>&1 || true

  set -u
fi

NODE_BIN="$(command -v node || true)"
NPM_BIN="$(command -v npm || true)"

# Fallback when no NVM default alias exists or Windows npm is still
# selected: put the newest installed NVM Node version first in PATH.
if [[ -z "$NODE_BIN" ||
      -z "$NPM_BIN" ||
      "$NODE_BIN" == /mnt/c/* ||
      "$NPM_BIN" == /mnt/c/* ]]; then

  LATEST_NVM_NODE="$(
    find "$NVM_DIR/versions/node" \
      -mindepth 1 \
      -maxdepth 1 \
      -type d \
      2>/dev/null |
      sort -V |
      tail -n 1 ||
      true
  )"

  if [[ -n "$LATEST_NVM_NODE" ]]; then
    export PATH="$LATEST_NVM_NODE/bin:$PATH"
  fi
fi

NODE_BIN="$(command -v node || true)"
NPM_BIN="$(command -v npm || true)"

# ================================================================
# Paths and configuration
# ================================================================

RUN_DIR="$ROOT/.run"

# Support both API_PORT/WEB_PORT from .env and the longer variable names.
API_PORT="${PLANBENCH_API_PORT:-${API_PORT:-8000}}"
WEB_PORT="${PLANBENCH_WEB_PORT:-${WEB_PORT:-3000}}"
STARTUP_TIMEOUT="${PLANBENCH_STARTUP_TIMEOUT:-120}"

# Local development persists to SQLite by default, so accounts, review
# requests and benchmarks survive a restart. Set PLANBENCH_DATABASE_URL
# in .env to point somewhere else (PostgreSQL in production), or to an
# empty string for the in-memory backend.
if [[ -z "${PLANBENCH_DATABASE_URL+x}" ]]; then
  PLANBENCH_DATABASE_URL="sqlite:///$ROOT/planbench.db"
fi
export PLANBENCH_DATABASE_URL

API_LOG="$RUN_DIR/api.log"
WEB_LOG="$RUN_DIR/web.log"

API_PID="$RUN_DIR/api.pid"
WEB_PID="$RUN_DIR/web.pid"

# Must stay in step with `pythonpath` in pyproject.toml, minus the two
# entries that are test-only ("." and "tests"). Nothing enforces that
# today and the drift is not hypothetical: `packages/decision` was added
# for pytest when the decision layer landed and never added here, so the
# suite imported `planbench_decision` happily while the *server* could
# not start at all — the API reaches it through
# `planbench_benchmark.candidates`, which imports it at module level.
# A green suite said nothing about it, because pytest supplies its own
# path and never runs this script. `tests/test_dev_stack_pythonpath.py`
# now compares the two lists.
PY_PATH="$ROOT/packages/schemas:$ROOT/packages/planning:$ROOT/packages/metrics"
PY_PATH="$PY_PATH:$ROOT/packages/benchmark:$ROOT/packages/decision"
PY_PATH="$PY_PATH:$ROOT/services/simulator"
PY_PATH="$PY_PATH:$ROOT/services/tracking:$ROOT/services/agent_service"
PY_PATH="$PY_PATH:$ROOT/ml:$ROOT/apps/api"

# ================================================================
# Utility functions
# ================================================================

info() {
  printf '  %s\n' "$*"
}

warn() {
  printf '  ! %s\n' "$*" >&2
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

# ================================================================
# Prerequisite checks
# ================================================================

check_prerequisites() {
  command -v curl >/dev/null 2>&1 ||
    die "curl is missing inside WSL."

  command -v setsid >/dev/null 2>&1 ||
    die "setsid is missing inside WSL."

  command -v lsof >/dev/null 2>&1 ||
    die "lsof is missing inside WSL. Install it with:
  sudo apt install lsof"

  [[ -n "$NODE_BIN" ]] ||
    die "Node.js was not found inside WSL."

  [[ -n "$NPM_BIN" ]] ||
    die "npm was not found inside WSL."

  case "$NODE_BIN" in
    /mnt/c/* | *.exe | *.cmd)
      die "Windows Node.js was selected instead of WSL Node.js:
  $NODE_BIN"
      ;;
  esac

  case "$NPM_BIN" in
    /mnt/c/* | *.exe | *.cmd)
      die "Windows npm was selected instead of WSL npm:
  $NPM_BIN"
      ;;
  esac

  [[ "$API_PORT" =~ ^[0-9]+$ ]] ||
    die "API_PORT must be a number, got: $API_PORT"

  [[ "$WEB_PORT" =~ ^[0-9]+$ ]] ||
    die "WEB_PORT must be a number, got: $WEB_PORT"

  [[ "$STARTUP_TIMEOUT" =~ ^[0-9]+$ ]] ||
    die "PLANBENCH_STARTUP_TIMEOUT must be a number."

  [[ -x "$ROOT/.venv/bin/uvicorn" ]] ||
    die "Python environment missing. Create it once:
  cd '$ROOT'
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt

requirements.txt, not docker/requirements-api.txt. The latter builds the
API *image* and deliberately carries no pytest, no ruff and no httpx, so
a .venv built from it runs the server and cannot run the suite. This
message said the wrong file until 2026-08-12; README, CI and this script
now all name the same one."

  [[ -f "$ROOT/apps/web/package.json" ]] ||
    die "Frontend package.json was not found:
  $ROOT/apps/web/package.json"

  [[ -d "$ROOT/apps/web/node_modules" ]] ||
    die "Frontend dependencies missing. Install them once:
  cd '$ROOT/apps/web'
  '$NPM_BIN' install"

  info "Node  $NODE_BIN"
  info "npm   $NPM_BIN"
}

# ================================================================
# Database migrations
# ================================================================

# Always before the API starts. An API serving a schema older than its
# code fails one request at a time, in ways that look like bugs; a
# migration that fails here says so once, plainly, and stops.
run_migrations() {
  if [[ -z "$PLANBENCH_DATABASE_URL" ]]; then
    # Reached when .env contains a bare `PLANBENCH_DATABASE_URL=`. That
    # sets the variable to an empty string, so the default a few lines
    # above never applies — a difference between "unset" and "set to
    # nothing" that is easy to miss and costs a whole session's work.
    warn "database  in-memory: maps, benchmarks and accounts are lost on restart."
    warn "          PLANBENCH_DATABASE_URL is set to an empty string in .env."
    warn "          To keep your data, put this in .env instead:"
    warn "              PLANBENCH_DATABASE_URL=sqlite:///$ROOT/planbench.db"
    warn "          then run:  .venv/bin/alembic upgrade head"
    return 0
  fi

  if [[ ! -x "$ROOT/.venv/bin/alembic" ]]; then
    die "alembic is missing from the virtualenv. Install it once:
  '$ROOT/.venv/bin/pip' install alembic"
  fi

  info "database  $PLANBENCH_DATABASE_URL"

  local output
  if ! output="$(cd "$ROOT" && PYTHONPATH="$PY_PATH" \
      "$ROOT/.venv/bin/alembic" upgrade head 2>&1)"; then
    printf '%s\n' "$output" >&2
    die "database migration failed — the API was not started.
Fix the error above, then run ./scripts/dev_stack.sh start again."
  fi

  info "migrations up to date"
}

# ================================================================
# Sign-in configuration
# ================================================================

# Reports what sign-in will actually offer. Never fails: a checkout with
# no OAuth credentials must still start, with those buttons simply not
# shown. Values are never printed — only whether they are set.
check_sign_in() {
  local methods=()

  [[ -n "${GOOGLE_CLIENT_ID:-}" && -n "${GOOGLE_CLIENT_SECRET:-}" ]] &&
    methods+=("Google")

  [[ -n "${GITHUB_CLIENT_ID:-}" && -n "${GITHUB_CLIENT_SECRET:-}" ]] &&
    methods+=("GitHub")

  case "${PLANBENCH_ENABLE_DEV_LOGIN:-}" in
    1 | true | TRUE | True | yes | on)
      methods+=("password (development)")
      ;;
  esac

  if [[ ${#methods[@]} -eq 0 ]]; then
    warn "no sign-in method is configured — the login page will say so."
    warn "Fill GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET and/or"
    warn "GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET in .env, or set"
    warn "PLANBENCH_ENABLE_DEV_LOGIN=true for local password sign-in."
  else
    info "sign-in   ${methods[*]}"
  fi

  if [[ -z "${AUTH_SECRET:-}" ]]; then
    warn "AUTH_SECRET is unset — a random one is generated per start, so"
    warn "everyone is signed out on every restart. Set it in .env."
  fi

  if [[ -n "${GOOGLE_CLIENT_ID:-}" || -n "${GITHUB_CLIENT_ID:-}" ]]; then
    info "callback  http://localhost:$API_PORT/api/v1/auth/oauth/google/callback"
    info "          http://localhost:$API_PORT/api/v1/auth/oauth/github/callback"
  fi
}

# ================================================================
# Port management
# ================================================================

free_port() {
  local port="$1"
  local pids
  local pid

  pids="$(
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null ||
      true
  )"

  if [[ -z "$pids" ]]; then
    return 0
  fi

  info "port $port was in use — stopping pid(s) $(echo "$pids" | tr '\n' ' ')"

  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true

  # Wait up to five seconds for the processes to stop.
  for _ in {1..20}; do
    pids="$(
      lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null ||
        true
    )"

    if [[ -z "$pids" ]]; then
      return 0
    fi

    sleep 0.25
  done

  warn "port $port is still in use; forcing the remaining process(es) to stop"

  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
}

# ================================================================
# Startup readiness check
# ================================================================

wait_for() {
  local url="$1"
  local label="$2"
  local log="$3"
  local pid_file="$4"

  local deadline=$((SECONDS + STARTUP_TIMEOUT))
  local pid

  while [[ "$SECONDS" -lt "$deadline" ]]; do
    if curl -sf -o /dev/null "$url"; then
      return 0
    fi

    # Stop waiting immediately when the process has already crashed.
    if [[ -f "$pid_file" ]]; then
      pid="$(cat "$pid_file" 2>/dev/null || true)"

      if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
        warn "$label process exited before becoming ready."
        warn "Last lines of $log:"

        tail -n 40 "$log" >&2 || true
        return 1
      fi
    fi

    sleep 1
  done

  warn "$label did not answer within ${STARTUP_TIMEOUT}s."
  warn "Last lines of $log:"

  tail -n 40 "$log" >&2 || true
  return 1
}

# ================================================================
# Credentials
# ================================================================

print_credentials() {
  local found

  # Only printed when the API generated one, which it does only when dev
  # login is on and PLANBENCH_SEED_USERS is empty.
  found="$(
    grep -o \
      '"message": "developer password: [^"]*"' \
      "$API_LOG" \
      2>/dev/null |
      sed 's/.*developer password: //; s/"$//' ||
      true
  )"

  if [[ -n "$found" ]]; then
    printf '\n  Generated development login (new on every restart):\n'
    printf '    developer  /  %s\n' "$found"
    printf '  Set PLANBENCH_SEED_USERS in .env to keep a fixed one.\n'
  fi
}

# ================================================================
# Start stack
# ================================================================

start_stack() {
  check_prerequisites

  mkdir -p "$RUN_DIR"

  # Clear logs from previous runs.
  : >"$API_LOG"
  : >"$WEB_LOG"

  free_port "$API_PORT"
  free_port "$WEB_PORT"

  printf '\nStarting PlanBench\n'

  run_migrations
  check_sign_in

  # --------------------------------------------------------------
  # Start FastAPI
  # --------------------------------------------------------------

  setsid env \
    PYTHONPATH="$PY_PATH" \
    PLANBENCH_ARTIFACT_DIR="${PLANBENCH_ARTIFACT_DIR:-$ROOT/artifacts}" \
    PLANBENCH_API_PUBLIC_URL="${PLANBENCH_API_PUBLIC_URL:-http://localhost:$API_PORT}" \
    PLANBENCH_WEB_APP_URL="${PLANBENCH_WEB_APP_URL:-http://localhost:$WEB_PORT}" \
    "$ROOT/.venv/bin/uvicorn" \
      planbench_api.main:app \
      --host 0.0.0.0 \
      --port "$API_PORT" \
      </dev/null \
      >"$API_LOG" \
      2>&1 &

  echo "$!" >"$API_PID"

  # --------------------------------------------------------------
  # Start Next.js using the absolute Linux npm path
  # --------------------------------------------------------------

  pushd "$ROOT/apps/web" >/dev/null

  setsid env \
    NEXT_PUBLIC_API_URL="http://localhost:$API_PORT" \
    "$NPM_BIN" run dev -- --port "$WEB_PORT" \
      </dev/null \
      >"$WEB_LOG" \
      2>&1 &

  echo "$!" >"$WEB_PID"

  popd >/dev/null

  # --------------------------------------------------------------
  # Wait for API
  # --------------------------------------------------------------

  if ! wait_for \
    "http://localhost:$API_PORT/api/v1/health" \
    "API" \
    "$API_LOG" \
    "$API_PID"; then

    stop_stack
    die "the API failed to start"
  fi

  info "API   http://localhost:$API_PORT/docs"

  # --------------------------------------------------------------
  # Wait for frontend
  # --------------------------------------------------------------

  if ! wait_for \
    "http://localhost:$WEB_PORT/" \
    "Web UI" \
    "$WEB_LOG" \
    "$WEB_PID"; then

    stop_stack
    die "the web UI failed to start"
  fi

  info "Web   http://localhost:$WEB_PORT"

  print_credentials

  printf '\n  Logs   %s\n' "$API_LOG"
  printf '         %s\n' "$WEB_LOG"
  printf '  Stop   ./scripts/dev_stack.sh stop\n\n'
}

# ================================================================
# Stop stack
# ================================================================

stop_one() {
  local pid_file="$1"
  local label="$2"

  local pid
  local pgid

  [[ -f "$pid_file" ]] || return 0

  pid="$(cat "$pid_file" 2>/dev/null || true)"

  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    pgid="$(
      ps -o pgid= -p "$pid" 2>/dev/null |
        tr -d ' ' ||
        true
    )"

    if [[ -n "$pgid" ]]; then
      # Kill the whole process group.
      kill -- "-$pgid" 2>/dev/null || true
    else
      kill "$pid" 2>/dev/null || true
    fi

    info "stopped $label (pid $pid)"
  fi

  rm -f "$pid_file"
}

stop_stack() {
  printf '\nStopping PlanBench\n'

  stop_one "$API_PID" "API"
  stop_one "$WEB_PID" "web UI"

  # Handle processes left behind without a PID file.
  free_port "$API_PORT"
  free_port "$WEB_PORT"

  printf '\n'
}

# ================================================================
# Status
# ================================================================

status_stack() {
  printf '\nPlanBench status\n'

  if curl -sf \
    "http://localhost:$API_PORT/api/v1/health" \
    >/dev/null 2>&1; then

    info "API   running  http://localhost:$API_PORT/docs"
  else
    info "API   not running on port $API_PORT"
  fi

  if curl -sf -o /dev/null \
    "http://localhost:$WEB_PORT/" \
    2>/dev/null; then

    info "Web   running  http://localhost:$WEB_PORT"
  else
    info "Web   not running on port $WEB_PORT"
  fi

  printf '\n'
}

# ================================================================
# Logs
# ================================================================

logs_stack() {
  mkdir -p "$RUN_DIR"
  touch "$API_LOG" "$WEB_LOG"

  tail -n 40 -f "$API_LOG" "$WEB_LOG"
}

# ================================================================
# Main command
# ================================================================

case "${1:-start}" in
  start)
    start_stack
    ;;

  stop)
    stop_stack
    ;;

  restart)
    stop_stack
    start_stack
    ;;

  status)
    status_stack
    ;;

  logs)
    logs_stack
    ;;

  *)
    die "unknown command '${1}'. Use:
  start | stop | restart | status | logs"
    ;;
esac