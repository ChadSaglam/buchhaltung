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

RUN_BACKEND=1
RUN_FRONTEND=1
RUN_INTEGRATION=1
RUN_DOCKER=1
RUN_OLLAMA=1

PASSED=0
WARNINGS=0
ERRORS=0

log() { echo -e "$1"; }
pass() { log " ${GREEN}✓${RESET} $1"; PASSED=$((PASSED + 1)); }
warn() { log " ${YELLOW}⊘${RESET} $1"; WARNINGS=$((WARNINGS + 1)); }
fail_check() { log " ${RED}✗${RESET} $1"; ERRORS=$((ERRORS + 1)); }
info() { log " ${DIM}$1${RESET}"; }

usage() {
  cat <<EOF
Usage: ./scripts/test.sh [options]

Options:
  --backend-only
  --frontend-only
  --no-integration
  --no-docker
  --no-ollama
  --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only) RUN_BACKEND=1; RUN_FRONTEND=0; RUN_INTEGRATION=0; RUN_DOCKER=0; shift ;;
    --frontend-only) RUN_BACKEND=0; RUN_FRONTEND=1; RUN_INTEGRATION=0; RUN_DOCKER=0; RUN_OLLAMA=0; shift ;;
    --no-integration) RUN_INTEGRATION=0; shift ;;
    --no-docker) RUN_DOCKER=0; shift ;;
    --no-ollama) RUN_OLLAMA=0; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail_check "Unknown option: $1"; usage; exit 1 ;;
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
    fail_check "No Python executable found in backend virtual environment"
    return 1
  fi
}

venv_pip() {
  if [[ -x "${BACKEND_DIR}/venv/bin/pip" ]]; then
    echo "${BACKEND_DIR}/venv/bin/pip"
  elif [[ -x "${BACKEND_DIR}/venv/bin/pip3" ]]; then
    echo "${BACKEND_DIR}/venv/bin/pip3"
  elif [[ -x "${BACKEND_DIR}/venv/bin/pip3.13" ]]; then
    echo "${BACKEND_DIR}/venv/bin/pip3.13"
  else
    fail_check "No pip executable found in backend virtual environment"
    return 1
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

require_dir() {
  local path="$1"
  local label="$2"
  [[ -d "$path" ]] || fail_check "${label} directory not found: ${path}"
}

compile_python_tree() {
  local label="$1"
  local path="$2"
  local py_exec="$3"

  if [[ ! -d "$path" ]]; then
    warn "${label} directory missing: ${path}"
    return 0
  fi

  local count=0
  local failed=0

  while IFS= read -r -d '' file; do
    count=$((count + 1))
    if ! "${py_exec}" -m py_compile "$file" 2>/dev/null; then
      fail_check "${file#${ROOT_DIR}/} has syntax errors"
      failed=$((failed + 1))
    fi
  done < <(find "$path" -type f -name "*.py" ! -name "__init__.py" -print0)

  [[ "$failed" -eq 0 ]] && pass "${label} compiles (${count} files)"
}

test_backend() {
  local backend_python
  local backend_pip
  local current_database_url

  log "${BOLD}1. Backend${RESET}"
  require_dir "${BACKEND_DIR}" "Backend"

  cd "${BACKEND_DIR}"

  if [[ -d "venv" ]]; then
    pass "Backend virtual environment found"
  else
    fail_check "Backend virtual environment missing"
    cd "${ROOT_DIR}"
    echo
    return
  fi

  backend_python="$(venv_python)" || { cd "${ROOT_DIR}"; echo; return; }
  backend_pip="$(venv_pip)" || { cd "${ROOT_DIR}"; echo; return; }

  [[ -f "requirements.txt" ]] && pass "requirements.txt exists" || fail_check "requirements.txt missing"

  current_database_url="$(resolve_database_url)"
  if [[ -n "${current_database_url}" ]]; then
    info "Resolved DATABASE_URL=${current_database_url}"
  else
    warn "DATABASE_URL is not set in backend/.env or .env"
  fi

  compile_python_tree "Backend routers" "${BACKEND_DIR}/app/routers" "${backend_python}"
  compile_python_tree "Backend services" "${BACKEND_DIR}/app/services" "${backend_python}"
  compile_python_tree "Backend models" "${BACKEND_DIR}/app/models" "${backend_python}"
  compile_python_tree "Backend schemas" "${BACKEND_DIR}/app/schemas" "${backend_python}"

  if "${backend_python}" -c "from app.main import app" >/dev/null 2>&1; then
    pass "FastAPI app imports successfully"
  else
    fail_check "FastAPI app import failed"
  fi

  if "${backend_python}" -c "from app.core.config import settings" >/dev/null 2>&1; then
    pass "Backend settings import successfully"
  else
    fail_check "Backend settings import failed"
  fi

  if "${backend_pip}" check >/dev/null 2>&1; then
    pass "Backend pip dependencies are consistent"
  else
    warn "pip check reported dependency issues"
  fi

  cd "${ROOT_DIR}"
  echo
}

test_frontend() {
  log "${BOLD}2. Frontend${RESET}"
  require_dir "${FRONTEND_DIR}" "Frontend"

  cd "${FRONTEND_DIR}"

  [[ -f "package.json" ]] && pass "package.json exists" || fail_check "package.json missing"

  if [[ -d "node_modules" ]]; then
    pass "node_modules exists"
  else
    fail_check "node_modules missing"
    cd "${ROOT_DIR}"
    echo
    return
  fi

  if npx tsc --noEmit >/dev/null 2>&1; then
    pass "TypeScript compiles"
  else
    fail_check "TypeScript compilation failed"
  fi

  if npx next lint >/dev/null 2>&1; then
    pass "Next.js lint passes"
  else
    warn "Next.js lint reported issues"
  fi

  if npm run build >/tmp/buchhaltung-frontend-build.log 2>&1; then
    pass "Frontend production build succeeds"
  else
    fail_check "Frontend production build failed"
    tail -5 /tmp/buchhaltung-frontend-build.log | while read -r line; do info "$line"; done
  fi

  cd "${ROOT_DIR}"
  echo
}

test_integration() {
  [[ "${RUN_INTEGRATION}" -eq 1 ]] || return 0

  log "${BOLD}3. Integration${RESET}"

  if curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    pass "API health endpoint responds"
  else
    warn "API not running at http://${BACKEND_HOST}:${BACKEND_PORT}"
    info "Ensure PostgreSQL is running and the database from DATABASE_URL exists"
    echo
    return 0
  fi

  if curl -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}" >/dev/null 2>&1; then
    pass "Frontend responds"
  else
    warn "Frontend not running at http://${FRONTEND_HOST}:${FRONTEND_PORT}"
  fi

  echo
}

test_ollama() {
  [[ "${RUN_OLLAMA}" -eq 1 ]] || return 0

  log "${BOLD}4. Ollama${RESET}"

  if curl -fsS "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    pass "Ollama responds at ${OLLAMA_BASE_URL}"
  else
    warn "Ollama not reachable at ${OLLAMA_BASE_URL}"
  fi

  echo
}

test_docker() {
  [[ "${RUN_DOCKER}" -eq 1 ]] || return 0

  log "${BOLD}5. Docker${RESET}"

  if [[ -f "${ROOT_DIR}/docker-compose.yml" ]]; then
    pass "docker-compose.yml exists"
    if docker compose config >/dev/null 2>&1; then
      pass "docker-compose.yml is valid"
    else
      fail_check "docker-compose.yml is invalid"
    fi
  else
    warn "docker-compose.yml not found"
  fi

  [[ -f "${BACKEND_DIR}/Dockerfile" ]] && pass "Backend Dockerfile exists" || warn "Backend Dockerfile missing"
  [[ -f "${FRONTEND_DIR}/Dockerfile" ]] && pass "Frontend Dockerfile exists" || warn "Frontend Dockerfile missing"

  echo
}

log "${BOLD}Multi-tenant SaaS Local Test Suite${RESET}"
echo

[[ "${RUN_BACKEND}" -eq 1 ]] && test_backend
[[ "${RUN_FRONTEND}" -eq 1 ]] && test_frontend
test_integration
test_ollama
test_docker

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e " ${GREEN}✓ ${PASSED} passed${RESET} ${RED}✗ ${ERRORS} failed${RESET} ${YELLOW}⊘ ${WARNINGS} warnings${RESET}"

if [[ "${ERRORS}" -gt 0 ]]; then
  exit 1
fi