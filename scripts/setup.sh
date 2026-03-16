#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# setup.sh — First-time project setup
# ─────────────────────────────────────────────────────────
set -euo pipefail

CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"; BOLD="\033[1m"

echo -e "${BOLD}📒 RDS Buchhaltung — Setup${RESET}"
echo ""

# ── Check prerequisites ────────────────────────────────
echo -e "${BOLD}Checking prerequisites...${RESET}"

check() {
  if command -v "$1" &> /dev/null; then
    echo -e "  ${GREEN}✓${RESET} $1 $(command $1 --version 2>/dev/null | head -1)"
  else
    echo -e "  ${RED}✗${RESET} $1 not found"
    return 1
  fi
}

check python3 || { echo "Install Python 3.12+: https://python.org"; exit 1; }
check node || { echo "Install Node.js 20+: https://nodejs.org"; exit 1; }
check npm || exit 1
echo ""

# ── Backend setup ──────────────────────────────────────
echo -e "${BOLD}Setting up backend...${RESET}"
cd backend

if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo -e "  ${GREEN}✓${RESET} Virtual environment created"
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo -e "  ${GREEN}✓${RESET} Python dependencies installed"

if [ ! -f ".env" ]; then
  JWT_SECRET=$(openssl rand -hex 16)
  cat > .env << ENVEOF
DATABASE_URL=postgresql+asyncpg://chadev:chadev@localhost:5432/chadev_buchhaltung
JWT_SECRET=${JWT_SECRET}
OLLAMA_BASE_URL=http://localhost:11434
ENVEOF
  echo -e "  ${GREEN}✓${RESET} .env created (PostgreSQL)"
else
  echo -e "  ${YELLOW}⊘${RESET} .env already exists, skipping"
fi

cd ..

# ── Frontend setup ─────────────────────────────────────
echo -e "${BOLD}Setting up frontend...${RESET}"
cd frontend
npm install --silent
echo -e "  ${GREEN}✓${RESET} Node dependencies installed"

if [ ! -f ".env.local" ]; then
  echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
  echo -e "  ${GREEN}✓${RESET} .env.local created"
fi

cd ..

# ── Ollama check ───────────────────────────────────────
echo ""
echo -e "${BOLD}Checking Ollama...${RESET}"
if command -v ollama &> /dev/null; then
  echo -e "  ${GREEN}✓${RESET} Ollama installed"
  if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} Ollama running"
    if ollama list 2>/dev/null | grep -q "kimi-k2.5:cloud"; then
      echo -e "  ${GREEN}✓${RESET} kimi-k2.5:cloud available"
    else
      echo -e "  ${YELLOW}⊘${RESET} Installing kimi-k2.5:cloud..."
      ollama pull kimi-k2.5:cloud
    fi
  else
    echo -e "  ${YELLOW}⊘${RESET} Ollama not running. Start with: ollama serve"
  fi
else
  echo -e "  ${YELLOW}⊘${RESET} Ollama not installed. Get it: https://ollama.com/download"
fi

echo ""
echo -e "${GREEN}${BOLD}✓ Setup complete!${RESET}"
echo ""
echo "Start development:"
echo "  ./scripts/dev.sh"
echo ""
echo "Or manually:"
echo "  cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  cd frontend && npm run dev"
