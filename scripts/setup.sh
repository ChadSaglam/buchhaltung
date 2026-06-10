#!/usr/bin/env bash
set -euo pipefail

CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; DIM="\033[2m"; RESET="\033[0m"; BOLD="\033[1m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${BACKEND_DIR:-${ROOT_DIR}/backend}"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
ROOT_ENV_FILE="${ROOT_ENV_FILE:-${ROOT_DIR}/.env}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-${BACKEND_DIR}/.env}"
FRONTEND_ENV_FILE="${FRONTEND_ENV_FILE:-${FRONTEND_DIR}/.env.local}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_BIN="${NPM_BIN:-npm}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
DEFAULT_DATABASE_URL="postgresql://chadev:Chadev%2F2202@localhost:5432/buchhaltung"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"

SETUP_BACKEND=1
SETUP_FRONTEND=1
CHECK_OLLAMA=1
FORCE_ENV=0

log() { echo -e "$1"; }
ok() { log " ${GREEN}✓${RESET} $1"; }
warn() { log " ${YELLOW}⊘${RESET} $1"; }
fail() { log " ${RED}✗${RESET} $1"; exit 1; }
info() { log " ${DIM}$1${RESET}"; }

usage() {
  cat <<EOF
Usage: ./scripts/setup.sh [options]

Options:
  --backend-only
  --frontend-only
  --no-ollama
  --force-env
  --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only) SETUP_BACKEND=1; SETUP_FRONTEND=0; shift ;;
    --frontend-only) SETUP_BACKEND=0; SETUP_FRONTEND=1; shift ;;
    --no-ollama) CHECK_OLLAMA=0; shift ;;
    --force-env) FORCE_ENV=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

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

venv_pip() {
  if [[ -x "${BACKEND_DIR}/venv/bin/pip" ]]; then
    echo "${BACKEND_DIR}/venv/bin/pip"
  elif [[ -x "${BACKEND_DIR}/venv/bin/pip3" ]]; then
    echo "${BACKEND_DIR}/venv/bin/pip3"
  elif [[ -x "${BACKEND_DIR}/venv/bin/pip3.13" ]]; then
    echo "${BACKEND_DIR}/venv/bin/pip3.13"
  else
    fail "No pip executable found in backend virtual environment"
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
  if [[ -n "${DATABASE_URL:-}" ]]; then
    normalize_database_url "${DATABASE_URL}"
    return
  fi

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

  echo "${DEFAULT_DATABASE_URL}"
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    "${PYTHON_BIN}" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  fi
}

write_backend_env() {
  local jwt_secret="$1"
  local database_url="$2"

  cat > "${BACKEND_ENV_FILE}" <<EOF
DATABASE_URL=${database_url}
JWT_SECRET=${jwt_secret}
OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
EOF
}

write_frontend_env() {
  cat > "${FRONTEND_ENV_FILE}" <<EOF
NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
EOF
}

warn_existing_backend_env() {
  [[ -f "${BACKEND_ENV_FILE}" ]] || return 0

  local current_database_url
  current_database_url="$(extract_env_value "${BACKEND_ENV_FILE}" "DATABASE_URL")"

  warn "Backend environment file already exists"
  [[ -n "${current_database_url}" ]] && info "Current DATABASE_URL=${current_database_url}"
  info "Use --force-env to rewrite it"
}

warn_existing_frontend_env() {
  [[ -f "${FRONTEND_ENV_FILE}" ]] || return 0

  local current_api_url
  current_api_url="$(extract_env_value "${FRONTEND_ENV_FILE}" "NEXT_PUBLIC_API_URL")"

  warn "Frontend environment file already exists"
  [[ -n "${current_api_url}" ]] && info "Current NEXT_PUBLIC_API_URL=${current_api_url}"
  info "Use --force-env to rewrite it"
}

setup_backend() {
  local backend_python
  local backend_pip
  local database_url
  local jwt_secret

  require_dir "${BACKEND_DIR}" "Backend"
  require_cmd "${PYTHON_BIN}" "Python"

  log "${BOLD}Setting up backend...${RESET}"

  cd "${BACKEND_DIR}"

  if [[ ! -d "venv" ]]; then
    "${PYTHON_BIN}" -m venv venv
    ok "Created backend virtual environment"
  else
    warn "Backend virtual environment already exists"
  fi

  backend_python="$(venv_python)"
  backend_pip="$(venv_pip)"

  "${backend_python}" -m pip install --upgrade pip setuptools wheel >/dev/null
  ok "Updated backend packaging tools"

  [[ -f "requirements.txt" ]] || fail "backend/requirements.txt not found"
  "${backend_pip}" install -r requirements.txt
  ok "Installed backend dependencies"

  database_url="$(resolve_database_url)"
  jwt_secret="$(extract_env_value "${BACKEND_ENV_FILE}" "JWT_SECRET")"
  [[ -n "${jwt_secret}" ]] || jwt_secret="$(generate_secret)"

  if [[ "${FORCE_ENV}" -eq 1 || ! -f "${BACKEND_ENV_FILE}" ]]; then
    write_backend_env "${jwt_secret}" "${database_url}"
    ok "Wrote backend environment file"
    info "Resolved DATABASE_URL=${database_url}"
  else
    warn_existing_backend_env
  fi

  cd "${ROOT_DIR}"
}

setup_frontend() {
  require_dir "${FRONTEND_DIR}" "Frontend"
  require_cmd node "Node.js"
  require_cmd "${NPM_BIN}" "npm"

  log "${BOLD}Setting up frontend...${RESET}"

  cd "${FRONTEND_DIR}"

  [[ -f "package.json" ]] || fail "frontend/package.json not found"

  if [[ -f "package-lock.json" ]]; then
    "${NPM_BIN}" ci
    ok "Installed frontend dependencies with npm ci"
  else
    "${NPM_BIN}" install
    ok "Installed frontend dependencies with npm install"
  fi

  if [[ "${FORCE_ENV}" -eq 1 || ! -f "${FRONTEND_ENV_FILE}" ]]; then
    write_frontend_env
    ok "Wrote frontend environment file"
  else
    warn_existing_frontend_env
  fi

  cd "${ROOT_DIR}"
}

check_ollama() {
  [[ "${CHECK_OLLAMA}" -eq 1 ]] || return 0

  log "${BOLD}Checking Ollama...${RESET}"

  if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama CLI not installed"
    info "Download: https://ollama.com/download"
    return 0
  fi

  ok "Ollama CLI found"

  if curl -fsS "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    ok "Ollama server reachable"
  else
    warn "Ollama server not running"
    info "Start with: ollama serve"
  fi
}

log "${BOLD}Multi-tenant SaaS Local Setup${RESET}"
echo

[[ "${SETUP_BACKEND}" -eq 1 ]] && { setup_backend; echo; }
[[ "${SETUP_FRONTEND}" -eq 1 ]] && { setup_frontend; echo; }

check_ollama
echo

log "${GREEN}${BOLD}✓ Local setup completed${RESET}"
echo " Backend:  ${BACKEND_DIR}"
echo " Frontend: ${FRONTEND_DIR}"
echo
echo " Start development with:"
echo " ./scripts/dev.sh"
echo
echo " To rewrite env files:"
echo " ./scripts/setup.sh --force-env"