#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# project-overview.sh — Comprehensive project health & stats
# ─────────────────────────────────────────────────────────
set -uo pipefail

CYAN=$'\033[36m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'
RESET=$'\033[0m'; BOLD=$'\033[1m'; DIM=$'\033[2m'

# Load env files safely (values may contain ^, =, / etc. that break `source`)
load_env() {
  local file="$1"
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    local key="${line%%=*}"
    local val="${line#*=}"
    # strip surrounding quotes and trailing whitespace
    key="$(echo "$key" | tr -d ' ')"
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"; val="${val#\'}"
    [ -n "$key" ] && export "$key=$val"
  done < "$file"
}

load_env backend/.env
load_env .env

ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASS="${ADMIN_PASS:-}"

# Derive DB connection parts from DATABASE_URL when not set explicitly
parse_db() {
  local url="${DATABASE_URL:-}"
  url="${url#*://}"
  local creds="${url%%@*}"
  local hostpart="${url#*@}"
  DB_USER="${DB_USER:-${creds%%:*}}"
  local rawpass="${creds#*:}"
  DB_PASS="${DB_PASS:-$(python3 -c "import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1]))" "$rawpass" 2>/dev/null || echo "$rawpass")}"
  DB_HOST="${DB_HOST:-$(echo "$hostpart" | sed 's|[:/].*||')}"
  DB_NAME="${DB_NAME:-$(echo "$hostpart" | sed 's|.*/||')}"
}
parse_db

echo "${BOLD}📒 Buchhaltung — Project Overview${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Git ─────────────────────────────────────────────────
if [ -d .git ]; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
  COMMIT=$(git log -1 --format="%h %s" 2>/dev/null || echo "no commits")
  DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d " ")
  TAGS=$(git tag --sort=-version:refname 2>/dev/null | head -1)
  echo "${BOLD}Git${RESET}"
  echo "  Branch: ${CYAN}${BRANCH}${RESET}"
  echo "  Last:   ${COMMIT}"
  [ -n "$TAGS" ] && echo "  Tag:    ${TAGS}"
  if [ "$DIRTY" -gt 0 ]; then
    echo "  Status: ${YELLOW}${DIRTY} uncommitted changes${RESET}"
  else
    echo "  Status: ${GREEN}Clean${RESET}"
  fi
  echo ""
fi

# ── Code Stats ──────────────────────────────────────────
echo "${BOLD}Code Stats${RESET}"
PY_FILES=$(find backend -name "*.py" \
  -not -path "*__pycache__*" \
  -not -path "*/venv/*" \
  -not -path "*alembic/versions*" | wc -l | tr -d " ")
PY_LINES=$(find backend -name "*.py" \
  -not -path "*__pycache__*" \
  -not -path "*/venv/*" \
  -not -path "*alembic/versions*" -exec cat {} + | wc -l | tr -d " ")
TSX_FILES=$(find frontend/src \( -name "*.tsx" -o -name "*.ts" \) | wc -l | tr -d " ")
TSX_LINES=$(find frontend/src \( -name "*.tsx" -o -name "*.ts" \) -exec cat {} + | wc -l | tr -d " ")
SH_FILES=$(find . -maxdepth 2 -name "*.sh" -not -path "*/venv/*" 2>/dev/null | wc -l | tr -d " ")
SH_LINES=$(find . -maxdepth 2 -name "*.sh" -not -path "*/venv/*" -exec cat {} + 2>/dev/null | wc -l | tr -d " ")

echo "  Python:     ${PY_FILES} files, ${PY_LINES} lines"
echo "  TypeScript: ${TSX_FILES} files, ${TSX_LINES} lines"
echo "  Bash:       ${SH_FILES} files, ${SH_LINES} lines"
echo "  Total:      $(( PY_FILES + TSX_FILES + SH_FILES )) files, $(( PY_LINES + TSX_LINES + SH_LINES )) lines"
echo ""

# ── Architecture ────────────────────────────────────────
echo "${BOLD}Architecture${RESET}"
echo "  ┌─────────────┐   ┌──────────────┐   ┌────────────┐"
echo "  │  Next.js    │──▶│   FastAPI    │──▶│ PostgreSQL │"
echo "  │  :3000      │   │   :8000      │   │  :5432     │"
echo "  └─────────────┘   └──────┬───────┘   └────────────┘"
echo "                           │"
echo "                    ┌──────┴───────┐"
echo "                    │   Ollama     │"
echo "                    │   :11434     │"
echo "                    └──────────────┘"
echo ""

# ── Backend Detail ──────────────────────────────────────
echo "${BOLD}Backend${RESET}"
echo "  Framework: FastAPI $( (cd backend && python3 -c "import fastapi; print(fastapi.__version__)") 2>/dev/null || echo "?")"
echo "  Python:    $(python3 --version 2>/dev/null || echo "?")"
echo "  Database:  PostgreSQL + asyncpg (async)"
echo ""

echo "  ${DIM}Routers (API endpoints):${RESET}"
TOTAL_ROUTES=0
for f in backend/app/routers/*.py; do
  NAME=$(basename "$f" .py)
  [ "$NAME" = "__init__" ] && continue
  ROUTES=$(grep -E "^\s*@router\.(get|post|put|delete|patch)" "$f" 2>/dev/null | wc -l | tr -d " ")
  PREFIX=$(grep -oE "prefix=['\"][^'\"]*['\"]" "$f" 2>/dev/null | head -1 | sed "s/prefix=['\"]//;s/['\"]//g")
  printf "    %-22s %2s routes %s\n" "$NAME" "$ROUTES" "${PREFIX:+($PREFIX)}"
  TOTAL_ROUTES=$(( TOTAL_ROUTES + ROUTES ))
done
echo "    ${DIM}Total: ${TOTAL_ROUTES} API routes${RESET}"
echo ""

echo "  ${DIM}Models (database tables):${RESET}"
for f in backend/app/models/*.py; do
  NAME=$(basename "$f" .py)
  if [ "$NAME" = "__init__" ] || [ "$NAME" = "base" ]; then continue; fi
  COLS=$(grep -E "^\s+\w+\s*=\s*Column\b|^\s+\w+:\s*Mapped" "$f" 2>/dev/null | wc -l | tr -d " ")
  printf "    %-22s %s columns\n" "$NAME" "$COLS"
done
echo ""

echo "  ${DIM}Schemas (Pydantic):${RESET}"
for f in backend/app/schemas/*.py; do
  NAME=$(basename "$f" .py)
  [ "$NAME" = "__init__" ] && continue
  CLASSES=$(grep -E "^class \w+.*BaseModel" "$f" 2>/dev/null | wc -l | tr -d " ")
  LINES=$(wc -l < "$f" | tr -d " \n")
  printf "    %-22s %2s schemas %s lines\n" "$NAME" "$CLASSES" "$LINES"
done
echo ""

echo "  ${DIM}Services (business logic):${RESET}"
for f in backend/app/services/*.py; do
  NAME=$(basename "$f" .py)
  [ "$NAME" = "__init__" ] && continue
  FUNCS=$(grep -E "^\s*(async )?def " "$f" 2>/dev/null | wc -l | tr -d " ")
  LINES=$(wc -l < "$f" | tr -d " \n")
  printf "    %-22s %2s functions %s lines\n" "$NAME" "$FUNCS" "$LINES"
done
echo ""

# ── Frontend Detail ─────────────────────────────────────
echo "${BOLD}Frontend${RESET}"
NEXT_VER=$( (cd frontend && node -e "console.log(require('next/package.json').version)") 2>/dev/null || echo "?")
echo "  Framework: Next.js ${NEXT_VER}"
echo "  Node:      $(node --version 2>/dev/null || echo "?")"
echo ""

echo "  ${DIM}Pages:${RESET}"
find frontend/src/app -name "page.tsx" 2>/dev/null | sort | while read -r f; do
  ROUTE=$(echo "$f" | sed 's|frontend/src/app||;s|/page.tsx||')
  [ -z "$ROUTE" ] && ROUTE="/"
  LINES=$(wc -l < "$f" | tr -d " \n")
  printf "    %-32s %s lines\n" "$ROUTE" "$LINES"
done
echo ""

echo "  ${DIM}Components:${RESET}"
find frontend/src/components -name "*.tsx" 2>/dev/null | sort | while read -r f; do
  NAME=$(basename "$f" .tsx)
  LINES=$(wc -l < "$f" | tr -d " \n")
  DIR=$(dirname "$f" | sed 's|frontend/src/components/||;s|frontend/src/components||')
  [ -z "$DIR" ] && DIR="."
  printf "    %-27s %-12s %s lines\n" "$NAME" "($DIR)" "$LINES"
done
echo ""

echo "  ${DIM}Hooks & Lib:${RESET}"
find frontend/src/hooks frontend/src/lib \( -name "*.ts" -o -name "*.tsx" \) 2>/dev/null | sort | while read -r f; do
  NAME=$(basename "$f")
  DIR=$(dirname "$f" | sed 's|frontend/src/||')
  LINES=$(wc -l < "$f" | tr -d " \n")
  printf "    %-27s %-12s %s lines\n" "$NAME" "($DIR)" "$LINES"
done
echo ""

echo "  ${DIM}Key Dependencies:${RESET}"
(
  cd frontend || exit 0
  for PKG in next react react-dom tailwindcss axios react-hot-toast lucide-react react-dropzone; do
    VER=$(node -e "try{console.log(require('${PKG}/package.json').version)}catch{console.log('-')}" 2>/dev/null || echo "-")
    [ "$VER" != "-" ] && printf "    %-22s %s\n" "$PKG" "$VER"
  done
)
echo ""

# ── Service Status ───────────────────────────────────────
echo "${BOLD}Service Status${RESET}"

if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "  API:      ${GREEN}● Running${RESET} (port 8000) — http://localhost:8000/docs"
else
  echo "  API:      ${RED}● Offline${RESET}"
fi

if curl -sf http://localhost:3000 > /dev/null 2>&1; then
  echo "  Frontend: ${GREEN}● Running${RESET} (port 3000)"
else
  echo "  Frontend: ${RED}● Offline${RESET}"
fi

if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  OLLAMA_DATA=$(curl -sf http://localhost:11434/api/tags)
  MODEL_COUNT=$(echo "$OLLAMA_DATA" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "0")
  echo "  Ollama:   ${GREEN}● Running${RESET} (${MODEL_COUNT} models)"
  echo "$OLLAMA_DATA" | python3 -c "
import sys,json
models = json.load(sys.stdin).get('models',[])
for m in models:
    name = m.get('name','?')
    size_gb = m.get('size',0) / 1e9
    params = m.get('details',{}).get('parameter_size','')
    print(f'    {name:<32} {params:>6} {size_gb:.1f}GB')
" 2>/dev/null || true
else
  echo "  Ollama:   ${RED}● Offline${RESET}"
fi

if pg_isready -q 2>/dev/null; then
  export PGPASSWORD="$DB_PASS"
  DB_SIZE=$(psql -U "${DB_USER}" -h "${DB_HOST:-127.0.0.1}" -d "${DB_NAME:-buchhaltung}" \
    -t -c "SELECT pg_size_pretty(pg_database_size(current_database()));" 2>/dev/null | tr -d " \n" || echo "?")
  TABLE_COUNT=$(psql -U "${DB_USER}" -h "${DB_HOST:-127.0.0.1}" -d "${DB_NAME:-buchhaltung}" \
    -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d " \n" || echo "?")
  unset PGPASSWORD
  echo "  Postgres: ${GREEN}● Running${RESET} (${DB_SIZE:-?}, ${TABLE_COUNT:-?} tables)"
else
  echo "  Postgres: ${YELLOW}● Not reachable${RESET}"
fi

DOCKER_CONTAINERS=$(docker ps --filter "name=buchhaltung" --format "{{.Names}}: {{.Status}}" 2>/dev/null || true)
if [ -n "$DOCKER_CONTAINERS" ]; then
  echo ""
  echo "  ${DIM}Docker containers:${RESET}"
  echo "$DOCKER_CONTAINERS" | while read -r line; do echo "    $line"; done
fi
echo ""

# ── ML Classifier ───────────────────────────────────────
echo "${BOLD}ML Classifier${RESET}"
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  TOKEN=$(python3 - "$ADMIN_EMAIL" "$ADMIN_PASS" <<'PY' 2>/dev/null
import sys, json, urllib.request
email, password = sys.argv[1], sys.argv[2]
data = json.dumps({"email": email, "password": password}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/auth/login",
    data=data, headers={"Content-Type": "application/json"}, method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        print(json.load(r).get("access_token", ""))
except Exception:
    print("")
PY
)

  if [ -n "$TOKEN" ]; then
    INFO=$(curl -sf http://localhost:8000/api/classify/info -H "Authorization: Bearer $TOKEN" 2>/dev/null || echo "{}")
    echo "$INFO" | python3 -c "
import sys, json
d = json.load(sys.stdin)
has = d.get('has_model', False)
acc = max(d.get('model_accuracy',0), d.get('cv_accuracy',0))
train_acc = d.get('train_accuracy', 0)
mem = d.get('memory_count', 0)
corr = d.get('correction_count', 0)
samples = d.get('total_samples', 0)
classes = d.get('classes', 0)
trained = d.get('trained_at', '')
if has:
    print('  Model:          ● Trained')
    print(f'  CV Accuracy:    {acc*100:.1f}%')
    print(f'  Train Accuracy: {train_acc*100:.1f}%')
    overfit = abs(train_acc - acc)
    print(f'  ⚠ Overfit gap:  {overfit*100:.1f}%' if overfit > 0.05 else '  ✓ No overfitting')
    print(f'  Classes:        {classes}')
    print(f'  Samples:        {samples}')
    print(f'  Memory entries: {mem}')
    print(f'  Corrections:    {corr} pending')
    if trained: print(f'  Trained at:     {trained}')
else:
    print('  Model:   ○ Not trained')
    print(f'  Memory:  {mem} entries | Samples: {samples}')
print()
print('  Pipeline: 1. Exact Match → 2. ML Model → 3. Kontenplan fallback')
" 2>/dev/null || echo "  Could not parse classifier info"

    echo ""
    echo "  ${DIM}Quick test (Migros Lebensmittel / 45.50):${RESET}"
    TEST=$(curl -s -X POST "http://localhost:8000/api/classify/predict" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"beschreibung":"Migros Lebensmittel","betrag":45.50}' 2>/dev/null || echo "{}")
    echo "$TEST" | python3 -c "
import sys, json
d = json.load(sys.stdin)
soll = d.get('kt_soll') or d.get('ktsoll')
haben = d.get('kt_haben') or d.get('kthaben')
src = d.get('source','?')
conf = d.get('confidence',0)
mwst = d.get('mwst_code') or d.get('mwstcode') or '-'
if soll:
    print(f'  → {soll}/{haben}  MwSt: {mwst}  [{src}, {conf*100:.0f}%]')
else:
    print('  Could not classify test input')
" 2>/dev/null || true
  else
    echo "  ${YELLOW}Could not authenticate (check ADMIN_EMAIL / ADMIN_PASS in .env)${RESET}"
  fi
else
  echo "  ${RED}API offline — skipping${RESET}"
fi
echo ""

# ── Environment ─────────────────────────────────────────
echo "${BOLD}Environment Files${RESET}"
for ENV_FILE in backend/.env frontend/.env.local .env; do
  if [ -f "$ENV_FILE" ]; then
    VARS=$(grep -E "^[A-Z_]+=" "$ENV_FILE" 2>/dev/null | wc -l | tr -d " ")
    echo "  ${GREEN}✓${RESET} ${ENV_FILE} (${VARS} vars)"
  else
    echo "  ${YELLOW}⊘${RESET} ${ENV_FILE} missing"
  fi
done
echo ""

# ── Security ────────────────────────────────────────────
echo "${BOLD}Security${RESET}"
if [ -f .gitignore ]; then
  for PATTERN in ".env" "venv" "__pycache__" ".next" "node_modules"; do
    if grep -q "$PATTERN" .gitignore 2>/dev/null; then
      echo "  ${GREEN}✓${RESET} .gitignore excludes ${PATTERN}"
    else
      echo "  ${RED}✗${RESET} .gitignore missing ${PATTERN}"
    fi
  done
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"