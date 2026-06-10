#!/usr/bin/env bash
set -euo pipefail

CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; DIM="\033[2m"; RESET="\033[0m"; BOLD="\033[1m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${BACKEND_DIR:-${ROOT_DIR}/backend}"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
ROOT_ENV_FILE="${ROOT_ENV_FILE:-${ROOT_DIR}/.env}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-${BACKEND_DIR}/.env}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"

START_BACKEND=1
START_FRONTEND=1
START_OLLAMA=0
PIDS=()

log() { echo -e "$1"; }
ok() { log " ${GREEN}✓${RESET} $1"; }
warn() { log " ${YELLOW}⊘${RESET} $1"; }
fail() { log " ${RED}✗${RESET} $1"; exit 1; }
info() { log " ${DIM}$1${RESET}"; }

usage() {
  cat <<EOF
Usage: ./scripts/dev.sh [options]

Options:
  --backend-only
  --frontend-only
  --with-ollama
  --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only) START_BACKEND=1; START_FRONTEND=0; shift ;;
    --frontend-only) START_BACKEND=0; START_FRONTEND=1; shift ;;
    --with-ollama) START_OLLAMA=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

venv_python() {
  if [[ -x "${BACKEND_DIR}/venv/bin/python" ]]; then
    echo "${BACKEND_DIR}/venv/bin/python"
  elif [[ -x "${BACKEND_DIR}/venv/bin/python3" ]]; then
    echo "${BACKEND_DIR}/venv/bin/python3"
  elif [[ -x "${BACKEND_DIR}/venv/bin/python3.13" ]]; then
    echo "${BACKEND_DIR}/venv/bin/python3.13"
  else
    fail "No Python executable found in backend virtual environment"
  fi
}

extract_env_value() {
  local file_path="$1"
  local key="$2"
  [[ -f "$file_path" ]] || return 0
  grep -E "^${key}=" "$file_path" 2>/dev/null | tail -1 | cut -d= -f2-
}

normalize_database_url() {
  local url="$1"
  if [[ "$url" == postgresql://* ]]; then
    echo "postgresql+asyncpg://${url#postgresql://}"
  else
    echo "$url"
  fi
}

resolve_database_url() {
  local value=""

  value="$(extract_env_value "${BACKEND_ENV_FILE}" "DATABASE_URL")"
  if [[ -n "$value" ]]; then
    normalize_database_url "$value"
    return
  fi

  value="$(extract_env_value "${ROOT_ENV_FILE}" "DATABASE_URL")"
  if [[ -n "$value" ]]; then
    normalize_database_url "$value"
    return
  fi

  echo ""
}

database_name_from_url() {
  local url="$1"
  local without_query="${url%%\?*}"
  echo "${without_query##*/}"
}

cleanup() {
  echo
  log "${YELLOW}Stopping local services...${RESET}"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  wait >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

require_dir() {
  local path="$1"
  local label="$2"
  [[ -d "$path" ]] || fail "${label} directory not found: ${path}"
}

require_cmd() {
  local cmd="$1"
  local label="${2:-$1}"
  command -v "$cmd" >/dev/null 2>&1 || fail "${label} is required but not installed"
}

is_port_busy() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${port} )" | tail -n +2 | grep -q .
  else
    return 1
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local retries="${3:-30}"

  for ((i=1; i<=retries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      ok "${label} is ready"
      return 0
    fi
    sleep 1
  done

  return 1
}

show_backend_env_summary() {
  local current_database_url
  current_database_url="$(resolve_database_url)"

  if [[ -n "${current_database_url}" ]]; then
    info "Using DATABASE_URL=${current_database_url}"
  else
    warn "DATABASE_URL is not set in ${BACKEND_ENV_FILE} or ${ROOT_ENV_FILE}"
  fi
}

check_database_reachability() {
  local backend_python
  local database_url
  local database_name

  backend_python="$(venv_python)"
  database_url="$(resolve_database_url)"
  [[ -n "${database_url}" ]] || fail "DATABASE_URL is missing"

  database_name="$(database_name_from_url "${database_url}")"

  if "${backend_python}" - "${database_url}" <<'PY' >/tmp/buchhaltung-db-check.log 2>&1
import asyncio
import sys
import asyncpg

database_url = sys.argv[1]
if database_url.startswith("postgresql+asyncpg://"):
    database_url = "postgresql://" + database_url[len("postgresql+asyncpg://"):]

async def main():
    conn = await asyncpg.connect(database_url)
    try:
        await conn.fetchval("select 1")
    finally:
        await conn.close()

asyncio.run(main())
PY
  then
    ok "Database is reachable"
    return 0
  fi

  warn "Database is not reachable with current DATABASE_URL"
  info "Target database: ${database_name}"
  if [[ -s /tmp/buchhaltung-db-check.log ]]; then
    while IFS= read -r line; do
      info "$line"
    done < /tmp/buchhaltung-db-check.log
  fi
  info "Create it or update DATABASE_URL in backend/.env or .env"
  info "Example:"
  info "createdb ${database_name}"
  info "or"
  info "DATABASE_URL=postgresql+asyncpg://<user>:<password>@127.0.0.1:5432/<database> ./scripts/dev.sh"
  return 1
}

start_ollama() {
  if curl -fsS "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    ok "Ollama already running"
    return 0
  fi

  [[ "${START_OLLAMA}" -eq 1 ]] || { warn "Ollama not running"; info "Use --with-ollama to auto-start it"; return 0; }

  require_cmd ollama "Ollama"

  log "${BOLD}Starting Ollama...${RESET}"
  ollama serve >/dev/null 2>&1 &
  PIDS+=("$!")
  if wait_for_http "${OLLAMA_BASE_URL}/api/tags" "Ollama" 15; then
    ok "Ollama is ready"
  else
    fail "Ollama did not become ready"
  fi
}

start_backend() {
  local backend_python

  require_dir "${BACKEND_DIR}" "Backend"

  is_port_busy "${BACKEND_PORT}" && fail "Backend port ${BACKEND_PORT} is already in use"

  log "${BOLD}Starting backend...${RESET}"

  cd "${BACKEND_DIR}"
  [[ -d "venv" ]] || fail "Backend virtual environment not found. Run ./scripts/setup.sh first"
  [[ -f "app/main.py" ]] || fail "backend/app/main.py not found"

  show_backend_env_summary
  check_database_reachability || exit 1

  backend_python="$(venv_python)"
  "${backend_python}" -m uvicorn app.main:app --reload --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" &
  PIDS+=("$!")

  cd "${ROOT_DIR}"

  if wait_for_http "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" "Backend API" 30; then
    ok "Backend API is ready"
  else
    fail "Backend failed to become ready"
  fi
}

start_frontend() {
  require_dir "${FRONTEND_DIR}" "Frontend"
  require_cmd npm "npm"

  is_port_busy "${FRONTEND_PORT}" && fail "Frontend port ${FRONTEND_PORT} is already in use"

  log "${BOLD}Starting frontend...${RESET}"

  cd "${FRONTEND_DIR}"
  [[ -f "package.json" ]] || fail "frontend/package.json not found"

  npm run dev -- --hostname "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" &
  PIDS+=("$!")

  cd "${ROOT_DIR}"

  if wait_for_http "http://${FRONTEND_HOST}:${FRONTEND_PORT}" "Frontend" 45; then
    ok "Frontend is ready"
  else
    fail "Frontend failed to become ready"
  fi
}

log "${BOLD}Multi-tenant SaaS Local Development${RESET}"
echo

start_ollama
echo
[[ "${START_BACKEND}" -eq 1 ]] && { start_backend; echo; }
[[ "${START_FRONTEND}" -eq 1 ]] && { start_frontend; echo; }

log "${GREEN}${BOLD}✓ Local services are running${RESET}"
[[ "${START_FRONTEND}" -eq 1 ]] && echo " Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
[[ "${START_BACKEND}" -eq 1 ]] && echo " Backend:  http://${BACKEND_HOST}:${BACKEND_PORT}"
[[ "${START_BACKEND}" -eq 1 ]] && echo " Docs:     http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo
echo " Press Ctrl+C to stop."

wait