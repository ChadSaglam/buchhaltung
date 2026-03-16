#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# project-overview.sh — Comprehensive project health & stats
# ─────────────────────────────────────────────────────────
set -euo pipefail

CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"

echo -e "${BOLD}📒 RDS Buchhaltung — Project Overview${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Git ─────────────────────────────────────────────────
if [ -d .git ]; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
  COMMIT=$(git log -1 --format="%h %s" 2>/dev/null || echo "no commits")
  DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d " ")
  TAGS=$(git tag --sort=-version:refname 2>/dev/null | head -1)
  echo -e "${BOLD}Git${RESET}"
  echo "  Branch:   ${CYAN}${BRANCH}${RESET}"
  echo "  Last:     ${COMMIT}"
  [ -n "$TAGS" ] && echo "  Tag:      ${TAGS}"
  if [ "$DIRTY" -gt 0 ]; then
    echo -e "  Status:   ${YELLOW}${DIRTY} uncommitted changes${RESET}"
  else
    echo -e "  Status:   ${GREEN}Clean${RESET}"
  fi
  echo ""
fi

# ── Code Stats ──────────────────────────────────────────
echo -e "${BOLD}Code Stats${RESET}"
PY_FILES=$(find backend -name "*.py" -not -path "*__pycache__*" -not -path "*/venv/*" -not -path "*alembic/versions*" | wc -l | tr -d " ")
PY_LINES=$(find backend -name "*.py" -not -path "*__pycache__*" -not -path "*/venv/*" -not -path "*alembic/versions*" -exec cat {} + | wc -l | tr -d " ")
TSX_FILES=$(find frontend/src -name "*.tsx" -o -name "*.ts" | wc -l | tr -d " ")
TSX_LINES=$(find frontend/src \( -name "*.tsx" -o -name "*.ts" \) -exec cat {} + | wc -l | tr -d " ")
SH_FILES=$(find scripts -name "*.sh" 2>/dev/null | wc -l | tr -d " ")
SH_LINES=$(find scripts -name "*.sh" -exec cat {} + 2>/dev/null | wc -l | tr -d " ")

echo "  Python:     ${PY_FILES} files, ${PY_LINES} lines"
echo "  TypeScript: ${TSX_FILES} files, ${TSX_LINES} lines"
echo "  Bash:       ${SH_FILES} files, ${SH_LINES} lines"
echo "  Total:      $(( PY_FILES + TSX_FILES + SH_FILES )) files, $(( PY_LINES + TSX_LINES + SH_LINES )) lines"
echo ""

# ── Architecture ────────────────────────────────────────
echo -e "${BOLD}Architecture${RESET}"
echo "  ┌─────────────┐    ┌──────────────┐    ┌────────────┐"
echo "  │  Next.js     │───▶│  FastAPI      │───▶│ PostgreSQL │"
echo "  │  :3000       │    │  :8000        │    │  :5432     │"
echo "  └─────────────┘    └──────┬───────┘    └────────────┘"
echo "                            │"
echo "                     ┌──────┴───────┐"
echo "                     │  Ollama      │"
echo "                     │  :11434      │"
echo "                     └──────────────┘"
echo ""

# ── Backend Detail ──────────────────────────────────────
echo -e "${BOLD}Backend${RESET}"
echo "  Framework:  FastAPI $(python3 -c "import fastapi; print(fastapi.__version__)" 2>/dev/null || echo "?")"
echo "  Python:     $(python3 --version 2>/dev/null || echo "?")"
echo "  Database:   PostgreSQL + asyncpg (async)"
echo ""

echo -e "  ${DIM}Routers (API endpoints):${RESET}"
for f in backend/app/routers/*.py; do
  [ "$(basename $f)" = "__init__.py" ] && continue
  NAME=$(basename "$f" .py)
  ROUTES=$(grep -cE "^\s*@router\.(get|post|put|delete|patch)" "$f" 2>/dev/null || echo "0")
  PREFIX=$(grep -oE "prefix=['\"][^'\"]*['\"]" "$f" 2>/dev/null | head -1 | sed "s/prefix=['\"]//;s/['\"]//g" || echo "")
  printf "    %-20s %2s routes  %s\n" "$NAME" "$ROUTES" "${PREFIX:+($PREFIX)}"
done
TOTAL_ROUTES=0
for f in backend/app/routers/*.py; do
  [ "$(basename $f)" = "__init__.py" ] && continue
  COUNT=$(grep -cE "^\s*@router\.(get|post|put|delete|patch)" "$f" 2>/dev/null || echo "0")
  TOTAL_ROUTES=$((TOTAL_ROUTES + COUNT))
done
echo -e "    ${DIM}Total: ${TOTAL_ROUTES} API routes${RESET}"
echo ""

echo -e "  ${DIM}Models (database tables):${RESET}"
for f in backend/app/models/*.py; do
  NAME=$(basename "$f" .py)
  [ "$NAME" = "__init__" ] || [ "$NAME" = "base" ] && continue
  COLS=$(grep -cE "^\s+\w+\s*=\s*Column\b|^\s+\w+:\s*Mapped" "$f" 2>/dev/null || echo "?")
  printf "    %-20s %s columns\n" "$NAME" "$COLS"
done
echo ""

echo -e "  ${DIM}Services (business logic):${RESET}"
for f in backend/app/services/*.py; do
  NAME=$(basename "$f" .py)
  [ "$NAME" = "__init__" ] && continue
  FUNCS=$(grep -cE "^(async )?def " "$f" 2>/dev/null || echo "0")
  LINES=$(wc -l < "$f" | tr -d " ")
  printf "    %-20s %2s functions  %s lines\n" "$NAME" "$FUNCS" "$LINES"
done
echo ""

# ── Frontend Detail ─────────────────────────────────────
echo -e "${BOLD}Frontend${RESET}"
echo "  Framework:  Next.js $(cd frontend && node -e "console.log(require('next/package.json').version)" 2>/dev/null || echo "?")"
echo "  Node:       $(node --version 2>/dev/null || echo "?")"
echo ""

echo -e "  ${DIM}Pages:${RESET}"
find frontend/src/app -name "page.tsx" | sort | while read f; do
  ROUTE=$(echo "$f" | sed 's|frontend/src/app||;s|/page.tsx||')
  [ -z "$ROUTE" ] && ROUTE="/"
  LINES=$(wc -l < "$f" | tr -d " ")
  printf "    %-30s %s lines\n" "$ROUTE" "$LINES"
done
echo ""

echo -e "  ${DIM}Components:${RESET}"
find frontend/src/components -name "*.tsx" | sort | while read f; do
  NAME=$(basename "$f" .tsx)
  LINES=$(wc -l < "$f" | tr -d " ")
  DIR=$(dirname "$f" | sed 's|frontend/src/components/||')
  printf "    %-25s %-10s %s lines\n" "$NAME" "($DIR)" "$LINES"
done
echo ""

echo -e "  ${DIM}Key Dependencies:${RESET}"
cd frontend
for PKG in next react react-dom tailwindcss axios react-hot-toast lucide-react react-dropzone; do
  VER=$(node -e "try{console.log(require('${PKG}/package.json').version)}catch{console.log('-')}" 2>/dev/null || echo "-")
  [ "$VER" != "-" ] && printf "    %-20s %s\n" "$PKG" "$VER"
done
cd ..
echo ""

# ── Services ────────────────────────────────────────────
echo -e "${BOLD}Service Status${RESET}"

# Backend
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  echo -e "  API:        ${GREEN}● Running${RESET} (port 8000)"
  DOCS="http://localhost:8000/docs"
  echo -e "              ${DIM}Docs: ${DOCS}${RESET}"
else
  echo -e "  API:        ${RED}● Offline${RESET}"
fi

# Frontend
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
  echo -e "  Frontend:   ${GREEN}● Running${RESET} (port 3000)"
else
  echo -e "  Frontend:   ${RED}● Offline${RESET}"
fi

# Ollama
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  OLLAMA_DATA=$(curl -sf http://localhost:11434/api/tags)
  MODEL_COUNT=$(echo "$OLLAMA_DATA" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "0")
  echo -e "  Ollama:     ${GREEN}● Running${RESET} (${MODEL_COUNT} models)"

  # List models with vision capability
  echo "$OLLAMA_DATA" | python3 -c "
import sys,json
models = json.load(sys.stdin).get('models',[])
for m in models:
    name = m.get('name','?')
    size_gb = m.get('size',0) / 1e9
    family = m.get('details',{}).get('family','')
    params = m.get('details',{}).get('parameter_size','')
    print(f'    {name:<30s} {params:>5s}  {size_gb:.1f}GB  {family}')
" 2>/dev/null || true
else
  echo -e "  Ollama:     ${RED}● Offline${RESET}"
fi

# PostgreSQL
if pg_isready -q 2>/dev/null; then
  DB_SIZE=$(psql -U chadev -d chadev_buchhaltung -t -c "SELECT pg_size_pretty(pg_database_size('chadev_buchhaltung'));" 2>/dev/null | tr -d " " || echo "?")
  TABLE_COUNT=$(psql -U chadev -d chadev_buchhaltung -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d " " || echo "?")
  echo -e "  Postgres:   ${GREEN}● Running${RESET} (${DB_SIZE}, ${TABLE_COUNT} tables)"
else
  echo -e "  Postgres:   ${YELLOW}● Not reachable${RESET}"
fi

# Docker
DOCKER_CONTAINERS=$(docker ps --filter "name=buchhaltung" --format "{{.Names}}: {{.Status}}" 2>/dev/null || true)
if [ -n "$DOCKER_CONTAINERS" ]; then
  echo ""
  echo -e "  ${DIM}Docker containers:${RESET}"
  echo "$DOCKER_CONTAINERS" | while read line; do echo "    $line"; done
fi

echo ""

# ── ML Classifier ──────────────────────────────────────
echo -e "${BOLD}ML Classifier${RESET}"
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  TOKEN=$(curl -sf -X POST http://localhost:8000/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${ADMIN_EMAIL:-saglam.chad@chadev.ch}\",\"password\":\"${ADMIN_PASS:-Sahra/2015}\"}" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

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
    print(f'  Model:      ● Trained')
    print(f'  CV Accuracy:    {acc*100:.1f}%')
    print(f'  Train Accuracy: {train_acc*100:.1f}%')
    overfit = abs(train_acc - acc)
    if overfit > 0.05:
        print(f'  ⚠ Overfit gap: {overfit*100:.1f}%')
    else:
        print(f'  ✓ No overfitting detected')
    print(f'  Classes:    {classes} account types')
    print(f'  Samples:    {samples} training rows')
    print(f'  Memory:     {mem} exact-match entries')
    print(f'  Corrections: {corr} pending')
    if trained:
        print(f'  Trained at: {trained}')
else:
    print(f'  Model:      ○ Not trained')
    print(f'  Memory:     {mem} entries')
    print(f'  Samples:    {samples} rows available')

# Classification pipeline
print()
print('  Classification Pipeline:')
print('    1. Exact Match  → Memory lookup (instant)')
print('    2. ML Model     → scikit-learn classifier (fast)')
print('    3. Default      → Kontenplan fallback')
" 2>/dev/null || echo "  Could not parse classifier info"

    # Quick test classification
    echo ""
    echo -e "  ${DIM}Quick test:${RESET}"
    TEST_RESULT=$(curl -s -X POST "http://localhost:8000/api/classify/predict" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"beschreibung":"Migros Lebensmittel","betrag":45.50}' 2>/dev/null || echo "{}")

    echo "$TEST_RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
soll = d.get('kt_soll') or d.get('ktsoll')
haben = d.get('kt_haben') or d.get('kthaben')
if soll:
    src = d.get('source','?')
    conf = d.get('confidence',0)
    mwst = d.get('mwst_code') or d.get('mwstcode') or '-'
    print(f'    \"Migros Lebensmittel\" → {soll}/{haben} (MwSt: {mwst}) [{src}, {conf*100:.0f}%]')
else:
    print('    Could not classify test input')
" 2>/dev/null || true

  else
    echo -e "  ${YELLOW}Could not authenticate${RESET}"
  fi
else
  echo -e "  ${RED}API offline — cannot check${RESET}"
fi

echo ""

# ── Environment ─────────────────────────────────────────
echo -e "${BOLD}Environment Files${RESET}"
for ENV_FILE in backend/.env frontend/.env.local .env; do
  if [ -f "$ENV_FILE" ]; then
    VARS=$(grep -cE "^[A-Z_]+=" "$ENV_FILE" 2>/dev/null || echo "0")
    echo -e "  ${GREEN}✓${RESET} ${ENV_FILE} (${VARS} vars)"
  else
    echo -e "  ${YELLOW}⊘${RESET} ${ENV_FILE} missing"
  fi
done

# Check .gitignore
echo ""
echo -e "${BOLD}Security${RESET}"
if [ -f .gitignore ]; then
  for PATTERN in ".env" "venv" "__pycache__" ".next" "node_modules"; do
    if grep -q "$PATTERN" .gitignore 2>/dev/null; then
      echo -e "  ${GREEN}✓${RESET} .gitignore excludes ${PATTERN}"
    else
      echo -e "  ${RED}✗${RESET} .gitignore missing ${PATTERN}"
    fi
  done
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
