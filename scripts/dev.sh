#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# dev.sh — Start all services for local development
# ─────────────────────────────────────────────────────────
set -euo pipefail

trap 'echo ""; echo "Shutting down..."; kill 0; exit 0' SIGINT SIGTERM

CYAN="\033[36m"; GREEN="\033[32m"; RESET="\033[0m"; BOLD="\033[1m"

echo -e "${BOLD}📒 RDS Buchhaltung — Development Mode${RESET}"
echo ""

# ── Start Ollama if not running ────────────────────────
if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  if command -v ollama &> /dev/null; then
    echo -e "${CYAN}Starting Ollama...${RESET}"
    ollama serve &
    sleep 2
  fi
fi

# ── Backend ────────────────────────────────────────────
echo -e "${CYAN}Starting backend (port 8000)...${RESET}"
cd backend
if [ -d "venv" ]; then
  source venv/bin/activate
fi
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend
for i in {1..15}; do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} Backend ready"
    break
  fi
  sleep 1
done

# ── Frontend ───────────────────────────────────────────
echo -e "${CYAN}Starting frontend (port 3000)...${RESET}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}${BOLD}All services running:${RESET}"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services."

wait
