#!/usr/bin/env bash
set -euo pipefail

CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'
MAGENTA='\033[35m'; RESET='\033[0m'; BOLD='\033[1m'; DIM='\033[2m'

BACKEND="backend/app"
SERVICES="$BACKEND/services"
MODELS="$BACKEND/models"
ROUTERS="$BACKEND/routers"
FRONT="frontend/src"

echo -e "${BOLD}🗺  Buchhaltung — V3 → V10 Roadmap${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

VERSIONS=""
CUR=""
CUR_DONE=0
CUR_TOTAL=0
SUMMARY=""
GD=0
GT=0

flush_phase() {
  [ -z "$CUR" ] && return
  SUMMARY="${SUMMARY}${CUR} ${CUR_DONE} ${CUR_TOTAL}"$'\n'
  GD=$(( GD + CUR_DONE ))
  GT=$(( GT + CUR_TOTAL ))
}

phase() {
  flush_phase
  CUR="$1"; CUR_DONE=0; CUR_TOTAL=0
  echo; echo -e "${BOLD}$2${RESET}"
}

check() {
  local desc="$1"; shift
  CUR_TOTAL=$(( CUR_TOTAL + 1 ))
  if eval "$@" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} $desc"
    CUR_DONE=$(( CUR_DONE + 1 ))
  else
    echo -e "  ${RED}✗${RESET} $desc"
  fi
}

# ── V3: Tenant-safe & dynamic core ───────────────────────────
phase V3 "${CYAN}V3 — Tenant-safe & dynamic core${RESET}"
check "ollama_vision reads base_url from config (no hardcoded URL)" \
  "! grep -q 'localhost:11434' $SERVICES/ollama_vision.py"
check "no module-level _status_cache (tenant leak)" \
  "! grep -q '^_status_cache' $SERVICES/ollama_vision.py"
check "async HTTP client (httpx) not blocking requests" \
  "grep -q 'httpx' $SERVICES/ollama_vision.py"
check "Tesseract subprocess wrapped async (to_thread/executor)" \
  "grep -rq 'to_thread\|run_in_executor' $SERVICES/scanner/"
check "scanner queries filter by tenant_id" \
  "grep -q 'tenant_id' $SERVICES/scanner/scanner_service.py"
check "OCR text cleaner in parse_invoice_text" \
  "grep -q 'parse_invoice_text' $SERVICES/ollama_vision.py"

# ── V4: Per-tenant ML lifecycle ──────────────────────────────
phase V4 "${CYAN}V4 — Per-tenant ML lifecycle${RESET}"
check "model artifact keyed by tenant_id column" \
  "grep -q 'tenant_id' $MODELS/classifier_model.py"
check "explicit model version/revision column" \
  "grep -Eq 'version|revision' $MODELS/classifier_model.py"
check "background training worker module" \
  "test -f $SERVICES/training_worker.py || test -f $SERVICES/jobs.py || test -f $SERVICES/tasks.py || test -f $BACKEND/worker.py"
check "accuracy history table/model" \
  "test -f $MODELS/accuracy_history.py || test -f $MODELS/model_history.py"
check "corrections retraining hook" \
  "grep -qi 'correction' $SERVICES/classifier.py"
check "confidence-threshold review queue model" \
  "grep -rqi 'needs_review\|review_queue' $MODELS/"

# ── V5: Trust, audit & observability ─────────────────────────
phase V5 "${MAGENTA}V5 — Trust, audit & observability${RESET}"
check "audit log model" \
  "ls $MODELS/audit_log.py 2>/dev/null || grep -rqi 'class.*Audit' $MODELS/"
check "structured /api/health/detail endpoint" \
  "grep -rq 'health/detail\|health_detail' $ROUTERS/"
check "per-tenant usage metering model" \
  "test -f $MODELS/usage.py || test -f $MODELS/usage_event.py"
check "request rate limiting (slowapi/limiter)" \
  "grep -rqi 'slowapi\|RateLimit\|limiter' $BACKEND/ --include='*.py'"
check "structured JSON logging configured" \
  "grep -rqi 'structlog\|json.*logging\|logging.config' $BACKEND/ --include='*.py'"
check "Sentry / error tracking wired" \
  "grep -rqi 'sentry' $BACKEND/ --include='*.py'"

# ── V6: Billing & plans ──────────────────────────────────────
phase V6 "${MAGENTA}V6 — Billing & subscription plans${RESET}"
check "subscription/plan model" \
  "ls $MODELS/subscription.py $MODELS/plan.py 2>/dev/null"
check "Stripe (or provider) integration" \
  "grep -rqi 'stripe' $BACKEND/ --include='*.py'"
check "plan-based feature gating dependency" \
  "grep -rqi 'require_plan\|feature_flag\|has_feature' $BACKEND/ --include='*.py'"
check "billing router" \
  "ls $ROUTERS/billing.py 2>/dev/null"

# ── V7: Quality & testing ────────────────────────────────────
phase V7 "${YELLOW}V7 — Quality & testing${RESET}"
check "tenant-isolation tests" \
  "grep -rliq 'tenant' backend/tests/ 2>/dev/null"
check "scanner pipeline tests" \
  "ls backend/tests/test_scanner*.py 2>/dev/null"
check "CI workflow present" \
  "ls .github/workflows/*.yml 2>/dev/null || ls .gitlab-ci.yml 2>/dev/null"
check "pre-commit / lint config (ruff)" \
  "ls .pre-commit-config.yaml 2>/dev/null || grep -rqi 'ruff' pyproject.toml 2>/dev/null"
check "frontend e2e tests (Playwright)" \
  "grep -rqi 'playwright' frontend/package.json 2>/dev/null"

# ── V8: User experience ──────────────────────────────────────
phase V8 "${YELLOW}V8 — User-friendly UX${RESET}"
check "global error boundary component" \
  "ls $FRONT/components/shared/ErrorBoundary.tsx 2>/dev/null"
check "data fetching cache (SWR / react-query)" \
  "grep -rqi 'swr\|@tanstack/react-query' frontend/package.json 2>/dev/null"
check "i18n multi-language (already present)" \
  "ls $FRONT/lib/i18n.ts 2>/dev/null"
check "onboarding / empty-state guidance" \
  "grep -rliq 'onboarding\|EmptyState' $FRONT/components/ 2>/dev/null"
check "accessibility (aria) usage in UI" \
  "grep -rliq 'aria-' $FRONT/components/ 2>/dev/null"
check "skeleton loaders (already present)" \
  "ls $FRONT/components/shared/LoadingSkeleton.tsx 2>/dev/null"

# ── V9: Scale & deployment ───────────────────────────────────
phase V9 "${CYAN}V9 — Scale & deployment${RESET}"
check "backend Dockerfile installs tesseract" \
  "grep -qi 'tesseract' backend/Dockerfile 2>/dev/null"
check "docker-compose for full stack" \
  "ls docker-compose.yml compose.yaml 2>/dev/null"
check "Redis / cache layer configured" \
  "grep -rqi 'redis' $BACKEND/ --include='*.py' 2>/dev/null"
check "object storage for model artifacts (S3/minio)" \
  "grep -rqi 'boto3\|minio\|\\bs3\\b' $BACKEND/ --include='*.py' 2>/dev/null"
check "DB connection pool tuned (pool_size)" \
  "grep -rqi 'pool_size\|max_overflow' $BACKEND/ --include='*.py' 2>/dev/null"

# ── V10: Intelligence & automation ───────────────────────────
phase V10 "${MAGENTA}V10 — Advanced intelligence${RESET}"
check "duplicate-invoice detection" \
  "grep -rqi 'duplicate' $SERVICES/ 2>/dev/null"
check "vendor auto-learning (fuzzy/embedding)" \
  "grep -rqi 'fuzzy\|similarity\|embedding' $SERVICES/ 2>/dev/null"
check "auto-retrain scheduler (cron/celery beat)" \
  "grep -rqi 'beat\|scheduler\|cron' $BACKEND/ --include='*.py' 2>/dev/null"
check "model A/B or shadow eval" \
  "grep -rqi 'shadow\|ab_test\|champion' $BACKEND/ --include='*.py' 2>/dev/null"
check "webhook export to external tools" \
  "grep -rqi 'webhook' $BACKEND/ --include='*.py' 2>/dev/null"

flush_phase

# ── Summary ──────────────────────────────────────────────────
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BOLD}Roadmap Progress by Version${RESET}"

printf '%s' "$SUMMARY" | while read -r V D T; do
  [ -z "$V" ] && continue
  pct=$(( T > 0 ? D * 100 / T : 0 ))
  if   [ "$pct" -ge 80 ]; then c=$GREEN
  elif [ "$pct" -ge 40 ]; then c=$YELLOW
  else c=$RED; fi
  bars=$(( pct / 10 )); bar=""
  i=0
  while [ $i -lt 10 ]; do
    if [ $i -lt $bars ]; then bar="${bar}█"; else bar="${bar}░"; fi
    i=$(( i + 1 ))
  done
  printf "  %-4s ${c}%s${RESET} %2d/%-2d (%d%%)\n" "$V" "$bar" "$D" "$T" "$pct"
done

echo
GPCT=$(( GT > 0 ? GD * 100 / GT : 0 ))
echo -e "${BOLD}Total: ${GD}/${GT} (${GPCT}%)${RESET}"
echo -e "${DIM}Re-run after each milestone. Green = shipped, Red = backlog.${RESET}"
echo
