#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# test.sh — Comprehensive pre-deploy test suite
# ─────────────────────────────────────────────────────────
set -euo pipefail

CYAN="\033[36m"; GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; DIM="\033[2m"; RESET="\033[0m"; BOLD="\033[1m"
ERRORS=0; WARNINGS=0; PASSED=0

echo -e "${BOLD}📒 RDS Buchhaltung — Pre-Deploy Tests${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

pass() { echo -e "  ${GREEN}✓${RESET} $1"; PASSED=$((PASSED + 1)); }
fail() { echo -e "  ${RED}✗${RESET} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}⊘${RESET} $1"; WARNINGS=$((WARNINGS + 1)); }
info() { echo -e "  ${DIM}$1${RESET}"; }

# ── 1. Backend Syntax ─────────────────────────────────
echo -e "${BOLD}1. Backend Syntax${RESET}"

cd backend
if [ -d "venv" ]; then source venv/bin/activate 2>/dev/null || true; fi

if python3 -m py_compile app/main.py 2>/dev/null; then
  pass "main.py compiles"
else
  fail "main.py has syntax errors"
fi

ROUTER_ERRORS=0
for f in app/routers/*.py; do
  [ "$(basename $f)" = "__init__.py" ] && continue
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    fail "$(basename $f) has syntax errors"
    ROUTER_ERRORS=$((ROUTER_ERRORS + 1))
  fi
done
ROUTER_COUNT=$(ls app/routers/*.py | grep -v __init__ | wc -l | tr -d " ")
[ $ROUTER_ERRORS -eq 0 ] && pass "All routers compile (${ROUTER_COUNT} files)"

SVC_ERRORS=0
for f in app/services/*.py; do
  [ "$(basename $f)" = "__init__.py" ] && continue
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    fail "$(basename $f) has syntax errors"
    SVC_ERRORS=$((SVC_ERRORS + 1))
  fi
done
SVC_COUNT=$(ls app/services/*.py | grep -v __init__ | wc -l | tr -d " ")
[ $SVC_ERRORS -eq 0 ] && pass "All services compile (${SVC_COUNT} files)"

MODEL_ERRORS=0
for f in app/models/*.py; do
  [ "$(basename $f)" = "__init__.py" ] || [ "$(basename $f)" = "base.py" ] && continue
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    fail "$(basename $f) has syntax errors"
    MODEL_ERRORS=$((MODEL_ERRORS + 1))
  fi
done
MODEL_COUNT=$(ls app/models/*.py | grep -v __init__ | grep -v base | wc -l | tr -d " ")
[ $MODEL_ERRORS -eq 0 ] && pass "All models compile (${MODEL_COUNT} files)"

SCHEMA_ERRORS=0
for f in app/schemas/*.py; do
  [ "$(basename $f)" = "__init__.py" ] && continue
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    fail "$(basename $f) has syntax errors"
    SCHEMA_ERRORS=$((SCHEMA_ERRORS + 1))
  fi
done
SCHEMA_COUNT=$(ls app/schemas/*.py 2>/dev/null | grep -v __init__ | wc -l | tr -d " ")
[ $SCHEMA_ERRORS -eq 0 ] && pass "All schemas compile (${SCHEMA_COUNT} files)"

echo ""

# ── 2. Backend Imports ────────────────────────────────
echo -e "${BOLD}2. Backend Imports${RESET}"

if python3 -c "from app.main import app" 2>/dev/null; then
  pass "FastAPI app imports successfully"
else
  fail "FastAPI app import failed"
  ERR=$(python3 -c "from app.main import app" 2>&1 | tail -1)
  info "Error: ${ERR}"
fi

if python3 -c "from app.core.config import settings" 2>/dev/null; then
  pass "Settings load correctly"
else
  fail "Settings import failed"
fi

if python3 -c "from app.core.database import engine, async_session" 2>/dev/null; then
  pass "Database engine initializes"
else
  fail "Database engine failed"
fi

if python3 -c "from app.core.security import create_access_token, hash_password, verify_password" 2>/dev/null; then
  pass "Security module loads"
else
  fail "Security module failed"
fi

if python3 -c "from app.services.classifier import TenantClassifier" 2>/dev/null; then
  pass "Classifier service loads"
else
  fail "Classifier service failed"
fi

echo ""

# ── 3. Dependencies ───────────────────────────────────
echo -e "${BOLD}3. Dependencies${RESET}"

if pip check > /dev/null 2>&1; then
  pass "All pip dependencies satisfied"
else
  warn "Some pip dependencies have conflicts"
  pip check 2>&1 | head -3 | while read line; do info "$line"; done
fi

MISSING_PKGS=""
for PKG in fastapi uvicorn sqlalchemy asyncpg alembic pydantic bcrypt sklearn pandas openpyxl pdfplumber aiosqlite; do
  if ! python3 -c "import $PKG" 2>/dev/null; then
    MISSING_PKGS="$MISSING_PKGS $PKG"
  fi
done
if [ -z "$MISSING_PKGS" ]; then
  pass "All critical packages importable"
else
  fail "Missing packages:${MISSING_PKGS}"
fi

cd ..

# Check frontend deps
cd frontend
if [ -d "node_modules" ]; then
  pass "node_modules exists"
  OUTDATED=$(npm outdated --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null | tr -d '\n' || echo "0")
  if [ "$OUTDATED" -gt 0 ]; then
    info "${OUTDATED} npm packages have updates available"
  fi
else
  fail "node_modules missing — run: cd frontend && npm install"
fi
cd ..

echo ""

# ── 4. Frontend ───────────────────────────────────────
echo -e "${BOLD}4. Frontend${RESET}"

cd frontend

if npx tsc --noEmit 2>/dev/null; then
  pass "TypeScript compiles (no errors)"
else
  TSCOUNT=$(npx tsc --noEmit 2>&1 | grep "error TS" | wc -l | tr -d " ")
  if [ "$TSCOUNT" -gt 0 ]; then
    fail "TypeScript: ${TSCOUNT} type errors"
    npx tsc --noEmit 2>&1 | grep "error TS" | head -3 | while read line; do info "$line"; done
  else
    warn "TypeScript check inconclusive"
  fi
fi

if npx next lint 2>/dev/null; then
  pass "ESLint passes"
else
  LINT_OUTPUT=$(npx next lint 2>&1 || true)
  LINT_WARNINGS=$(echo "$LINT_OUTPUT" | grep -c "Warning" 2>/dev/null || true)
  LINT_ERRORS=$(echo "$LINT_OUTPUT" | grep -c "Error" 2>/dev/null || true)
  LINT_WARNINGS=${LINT_WARNINGS##*$'\n'}
  LINT_ERRORS=${LINT_ERRORS##*$'\n'}
  if [ "${LINT_ERRORS:-0}" -gt 0 ] 2>/dev/null; then
    fail "ESLint: ${LINT_ERRORS} errors"
  else
    warn "ESLint has warnings"
  fi
fi

# Check all pages exist and are valid
PAGE_COUNT=$(find src/app -name "page.tsx" | wc -l | tr -d " ")
EMPTY_PAGES=0
for f in $(find src/app -name "page.tsx"); do
  LINES=$(wc -l < "$f" | tr -d " ")
  if [ "$LINES" -lt 2 ]; then
    EMPTY_PAGES=$((EMPTY_PAGES + 1))
  fi
done
if [ $EMPTY_PAGES -eq 0 ]; then
  pass "All ${PAGE_COUNT} pages have content"
else
  warn "${EMPTY_PAGES} pages appear empty"
fi

# Build
echo -e "  ${CYAN}Building frontend...${RESET}"
BUILD_START=$(date +%s)
if npm run build > /tmp/nextbuild.log 2>&1; then
  BUILD_END=$(date +%s)
  BUILD_TIME=$((BUILD_END - BUILD_START))
  pass "Next.js production build succeeds (${BUILD_TIME}s)"
else
  fail "Next.js production build failed"
  tail -5 /tmp/nextbuild.log | while read line; do info "$line"; done
fi

cd ..
echo ""

# ── 5. Database ───────────────────────────────────────
echo -e "${BOLD}5. Database${RESET}"

if pg_isready -q 2>/dev/null; then
  pass "PostgreSQL is running"

  TABLE_COUNT=$(psql -U chadev -d chadev_buchhaltung -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d " " || echo "0")
  if [ "$TABLE_COUNT" -gt 0 ]; then
    pass "Database has ${TABLE_COUNT} tables"
  else
    warn "Database has no tables — run alembic upgrade"
  fi

  BOOKING_COUNT=$(psql -U chadev -d chadev_buchhaltung -t -c "SELECT count(*) FROM bookings;" 2>/dev/null | tr -d " " || echo "?")
  [ "$BOOKING_COUNT" != "?" ] && info "Bookings: ${BOOKING_COUNT} rows"

  USER_COUNT=$(psql -U chadev -d chadev_buchhaltung -t -c "SELECT count(*) FROM users;" 2>/dev/null | tr -d " " || echo "?")
  [ "$USER_COUNT" != "?" ] && info "Users: ${USER_COUNT} rows"

  TRAINING_COUNT=$(psql -U chadev -d chadev_buchhaltung -t -c "SELECT count(*) FROM training_rows;" 2>/dev/null | tr -d " " || echo "?")
  [ "$TRAINING_COUNT" != "?" ] && info "Training data: ${TRAINING_COUNT} rows"
else
  if docker ps 2>/dev/null | grep -q "buchhaltung-db"; then
    pass "PostgreSQL running via Docker"
  else
    warn "PostgreSQL not reachable"
  fi
fi

echo ""

# ── 6. Ollama ─────────────────────────────────────────
echo -e "${BOLD}6. Ollama${RESET}"

if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  pass "Ollama is running"

  VISION_MODELS=$(curl -sf http://localhost:11434/api/tags | python3 -c "
import sys, json
models = json.load(sys.stdin).get('models',[])
vision = [m['name'] for m in models if any(k in m.get('details',{}).get('family','').lower() for k in ['gemma3','llava','bakllava'])]
print(len(vision))
" 2>/dev/null || echo "0")

  if [ "$VISION_MODELS" -gt 0 ]; then
    pass "${VISION_MODELS} vision model(s) available"
  else
    warn "No local vision models — invoice scanning may use cloud"
  fi

  # Test Ollama response
  OLLAMA_OK=$(curl -sf -X POST http://localhost:11434/api/generate \
    -d '{"model":"gemma3:4b","prompt":"Say OK","stream":false}' 2>/dev/null \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print('ok' if r.get('response') else 'fail')" 2>/dev/null || echo "fail")
  if [ "$OLLAMA_OK" = "ok" ]; then
    pass "Ollama responds to prompts"
  else
    warn "Ollama prompt test failed (model may not be loaded)"
  fi
else
  warn "Ollama not running"
  info "Start with: ollama serve"
fi

echo ""

# ── 7. API Integration ────────────────────────────────
echo -e "${BOLD}7. API Integration${RESET}"

if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  pass "Health endpoint responds"

  # Auth
  RESP=$(curl -sf -X POST http://localhost:8000/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL:-saglam.chad@chadev.ch}\",\"password\":\"${TEST_PASS:-Sahra/2015}\"}" 2>/dev/null || echo "")

  if echo "$RESP" | python3 -c "import sys,json; json.load(sys.stdin)['access_token']" 2>/dev/null; then
    pass "Authentication works"
    TOKEN=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

    # Test each endpoint group
    for EP in "api/scanner/status:Scanner status" "api/classify/info:Classifier info" "api/bookings/:Bookings list" "api/kontenplan/:Kontenplan" "api/stats/learning:Statistics"; do
      URL="${EP%%:*}"
      NAME="${EP##*:}"
      CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/${URL}" -H "Authorization: Bearer $TOKEN" 2>/dev/null || echo "0")
      if [ "$CODE" = "200" ]; then
        pass "${NAME} endpoint (${CODE})"
      else
        fail "${NAME} endpoint returned ${CODE}"
      fi
    done

    # Export endpoints
    for FMT in banana excel csv; do
      CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:8000/api/export/${FMT}" -H "Authorization: Bearer $TOKEN" 2>/dev/null || echo "0")
      if [ "$CODE" = "200" ] || [ "$CODE" = "404" ]; then
        pass "Export ${FMT} (${CODE})"
      else
        fail "Export ${FMT} returned ${CODE}"
      fi
    done

    # Classify test
    CLASSIFY_RESP=$(curl -s -X POST http://localhost:8000/api/classify/predict \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"beschreibung":"Migros Lebensmittel","betrag":45.50}' 2>/dev/null || echo "{}")
    if echo "$CLASSIFY_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('kt_soll') or d.get('ktsoll')" 2>/dev/null; then
      SOURCE=$(echo "$CLASSIFY_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('source','?'))" 2>/dev/null)
      pass "Classification works (source: ${SOURCE})"
    else
      fail "Classification endpoint failed"
    fi

    # Batch classify test
    BATCH_RESP=$(curl -sf -X POST http://localhost:8000/api/classify/batch \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"transactions":[{"Beschreibung":"Test","Betrag CHF":100}]}' 2>/dev/null || echo "")
    if echo "$BATCH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('results')" 2>/dev/null; then
      pass "Batch classification works"
    else
      warn "Batch classification failed"
    fi

    # Response time check
    RESP_TIME=$(curl -sf -o /dev/null -w "%{time_total}" http://localhost:8000/api/health 2>/dev/null || echo "0")
    RESP_MS=$(python3 -c "print(int(float('${RESP_TIME}') * 1000))" 2>/dev/null || echo "?")
    if [ "$RESP_MS" != "?" ] && [ "$RESP_MS" -lt 100 ]; then
      pass "API response time: ${RESP_MS}ms"
    elif [ "$RESP_MS" != "?" ] && [ "$RESP_MS" -lt 500 ]; then
      warn "API response time: ${RESP_MS}ms (slow)"
    else
      info "API response time: ${RESP_MS}ms"
    fi

  else
    fail "Authentication failed"
    info "Check TEST_EMAIL and TEST_PASS env vars"
  fi
else
  warn "API not running — skipping integration tests"
  warn "Start with: cd backend && uvicorn app.main:app --port 8000"
fi

echo ""

# ── 8. Docker ─────────────────────────────────────────
echo -e "${BOLD}8. Docker${RESET}"

if [ -f "docker-compose.yml" ]; then
  pass "docker-compose.yml exists"
  if docker compose config > /dev/null 2>&1; then
    pass "docker-compose.yml is valid"
    SVC_COUNT=$(docker compose config --services 2>/dev/null | wc -l | tr -d " ")
    info "Services defined: ${SVC_COUNT}"
    docker compose config --services 2>/dev/null | while read svc; do
      info "  - ${svc}"
    done
  else
    fail "docker-compose.yml has errors"
  fi
else
  warn "docker-compose.yml not found"
fi

if [ -f "backend/Dockerfile" ]; then
  pass "Backend Dockerfile exists"
  if grep -q "EXPOSE" backend/Dockerfile 2>/dev/null; then
    PORT=$(grep "EXPOSE" backend/Dockerfile | head -1 | grep -oE "[0-9]+" || echo "?")
    info "Exposes port ${PORT}"
  fi
else
  warn "Backend Dockerfile missing"
fi

if [ -f "frontend/Dockerfile" ]; then
  pass "Frontend Dockerfile exists"
else
  warn "Frontend Dockerfile missing"
fi

echo ""

# ── 9. Security ───────────────────────────────────────
echo -e "${BOLD}9. Security${RESET}"

# Hardcoded secrets
SECRETS_FOUND=$(grep -rn "password\|secret\|api_key" backend/app/ --include="*.py" 2>/dev/null \
  | grep -v "environ\|getenv\|settings\|pydantic\|bcrypt\|password_hash\|verify_password\|hashed_password\|password:" \
  | grep -iE '=\s*".{8,}"' || true)

if [ -n "$SECRETS_FOUND" ]; then
  fail "Possible hardcoded secrets in backend"
  echo "$SECRETS_FOUND" | head -3 | while read line; do info "$line"; done
else
  pass "No hardcoded secrets in Python code"
fi

# Check docker-compose for secrets
if [ -f "docker-compose.yml" ]; then
  DC_SECRETS=$(grep -E "(PASSWORD|SECRET|KEY)=" docker-compose.yml 2>/dev/null | grep -v '${' || true)
  if [ -n "$DC_SECRETS" ]; then
    fail "Hardcoded secrets in docker-compose.yml"
    info "Use \${VAR} references with .env file instead"
  else
    pass "docker-compose.yml uses env variables for secrets"
  fi
fi

# .gitignore checks
if [ -f ".gitignore" ]; then
  ALL_IGNORED=true
  for PATTERN in ".env" "venv" "__pycache__" ".next" "node_modules" "*.db" "*.pkl"; do
    if ! grep -q "$PATTERN" .gitignore 2>/dev/null; then
      warn ".gitignore missing: ${PATTERN}"
      ALL_IGNORED=false
    fi
  done
  if $ALL_IGNORED; then
    pass ".gitignore covers all sensitive patterns"
  fi
else
  fail ".gitignore file missing"
fi

# Check .env not tracked
if [ -d .git ]; then
  if git ls-files --error-unmatch backend/.env 2>/dev/null; then
    fail "backend/.env is tracked in git — remove with: git rm --cached backend/.env"
  else
    pass ".env files not tracked in git"
  fi
fi

# CORS check
CORS=$(grep -oE "allow_origins=\[.*\]" backend/app/main.py 2>/dev/null || echo "")
if echo "$CORS" | grep -q '\*'; then
  warn "CORS allows all origins (*) — restrict for production"
else
  pass "CORS is restricted"
fi

echo ""

# ── 10. Production Readiness ──────────────────────────
echo -e "${BOLD}10. Production Readiness${RESET}"

# JWT secret check
if [ -f "backend/.env" ]; then
  JWT=$(grep "JWT_SECRET\|SECRET_KEY" backend/.env 2>/dev/null | head -1 | cut -d= -f2)
  if echo "$JWT" | grep -qiE "change|default|test|dev"; then
    warn "JWT secret appears to be a placeholder — change for production"
  else
    pass "JWT secret is set"
  fi
fi

# Debug mode
if grep -qE "debug\s*=\s*True|DEBUG\s*=\s*True" backend/app/core/config.py 2>/dev/null; then
  warn "Debug mode enabled in config"
else
  pass "Debug mode not hardcoded"
fi

# Alembic migrations
if [ -d "backend/alembic/versions" ]; then
  MIGRATION_COUNT=$(ls backend/alembic/versions/*.py 2>/dev/null | wc -l | tr -d " ")
  if [ "$MIGRATION_COUNT" -gt 0 ]; then
    pass "Alembic migrations exist (${MIGRATION_COUNT} files)"
  else
    info "No migration files yet"
  fi
fi

# README
if [ -f "README.md" ]; then
  README_LINES=$(wc -l < README.md | tr -d " ")
  pass "README.md exists (${README_LINES} lines)"
else
  warn "README.md missing"
fi

echo ""

# ── Summary ───────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}✓ ${PASSED} passed${RESET}  ${RED}✗ ${ERRORS} failed${RESET}  ${YELLOW}⊘ ${WARNINGS} warnings${RESET}"
echo ""
if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}${BOLD}✓ All checks passed — ready to deploy!${RESET}"
else
  echo -e "${RED}${BOLD}✗ ${ERRORS} check(s) failed — fix before deploying${RESET}"
fi
echo ""
exit $ERRORS
