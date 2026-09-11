# Buchhaltung — one command per job. `make help` lists everything.
.DEFAULT_GOAL := help
SHELL := /bin/bash
PY  := backend/venv/bin/python
PIP := backend/venv/bin/pip
BIN := backend/venv/bin
FRONTEND_PORT ?= 3000
BACKEND_PORT  ?= 8000

.PHONY: help setup doctor dev-deps e2e-deps hooks dev stop ports test test-backend test-unit test-e2e lint fix typecheck check api-types migrate migration ai-context status clean docker

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend + frontend dependencies
	@if [ ! -x "$(PY)" ]; then \
		echo "→ creating backend/venv with $$(python3 --version)"; \
		python3 -m venv backend/venv; \
	else \
		echo "→ reusing existing backend/venv ($$($(PY) --version))"; \
	fi
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt -r backend/requirements-dev.txt
	cd frontend && npm install
	@$(MAKE) --no-print-directory e2e-deps
	@$(MAKE) --no-print-directory hooks

doctor: ## Show which interpreters and tools this repo is actually using
	@echo "  repo python   : $$($(PY) --version 2>&1)  ($(PY))"
	@echo "  venv layout   : $$(ls -d backend/venv/lib/python* 2>/dev/null | tr '\n' ' ')"
	@echo "  system python : $$(python3 --version 2>&1)"
	@echo "  node          : $$(node --version 2>/dev/null || echo missing)"
	@if ls "$$HOME/Library/Caches/ms-playwright"/chromium* >/dev/null 2>&1 || ls "$$HOME/.cache/ms-playwright"/chromium* >/dev/null 2>&1; then \
		echo "  ✔ playwright chromium"; \
	else \
		echo "  ✘ playwright chromium  MISSING — run: make e2e-deps"; \
	fi
	@for m in ruff pytest pytest_asyncio pytest_cov pytest_env pre_commit; do \
		if $(PY) -c "import $$m" >/dev/null 2>&1; then echo "  ✔ $$m"; else echo "  ✘ $$m  MISSING — run: make setup"; fi; \
	done
	@if [ "$$(ls -d backend/venv/lib/python* 2>/dev/null | wc -l | tr -d ' ')" -gt 1 ]; then \
		echo ""; \
		echo "  ⚠ backend/venv holds more than one Python version — that is how tools go missing."; \
		echo "    Fix with: rm -rf backend/venv && make setup"; \
	fi

e2e-deps: ## Ensure Playwright's browser binaries are downloaded
	@cd frontend && npx playwright install chromium

dev-deps: ## Ensure the dev/test toolchain is installed in backend/venv
	@if [ ! -x "$(PY)" ]; then \
		echo "✘ backend/venv is missing or broken. Run: make setup"; exit 1; \
	fi
	@$(PY) -c "import ruff" >/dev/null 2>&1 || $(PY) -m ruff --version >/dev/null 2>&1 || true
	@$(PY) -c "import pytest, pytest_asyncio, pytest_cov, pytest_env" >/dev/null 2>&1 || { \
		echo "→ dev toolchain missing from backend/venv, installing…"; \
		$(PIP) install -q -r backend/requirements-dev.txt; \
	}

hooks: ## Install the git pre-commit / pre-push hooks
	@if [ -x "$(BIN)/pre-commit" ]; then \
		"$(BIN)/pre-commit" install; \
	elif command -v pre-commit >/dev/null 2>&1; then \
		pre-commit install; \
	else \
		echo "  pre-commit not found — run: $(PIP) install pre-commit && make hooks"; \
	fi

dev: ## Run backend + frontend together
	./scripts/dev.sh

ports: ## Show what is holding the dev ports
	@for p in $(BACKEND_PORT) $(FRONTEND_PORT); do \
		pid=$$(lsof -ti tcp:$$p 2>/dev/null); \
		if [ -n "$$pid" ]; then \
			echo "  port $$p → PID $$pid  ($$(ps -p $$pid -o comm= 2>/dev/null))"; \
		else \
			echo "  port $$p → free"; \
		fi; \
	done

stop: ## Free the dev ports (kills whatever is on 8000 and 3000)
	@for p in $(BACKEND_PORT) $(FRONTEND_PORT); do \
		pid=$$(lsof -ti tcp:$$p 2>/dev/null); \
		if [ -n "$$pid" ]; then \
			echo "  killing PID $$pid on port $$p"; kill $$pid 2>/dev/null || true; \
		fi; \
	done; \
	sleep 1; $(MAKE) --no-print-directory ports

test: test-backend test-unit test-e2e ## Backend tests + frontend unit + e2e

test-unit: ## Frontend unit tests only (vitest, pure helpers)
	cd frontend && npm run test

test-e2e: e2e-deps ## Frontend end-to-end tests only
	cd frontend && npx playwright test

test-backend: dev-deps ## Backend tests only, with coverage
	$(PY) -m pytest --cov=backend/app --cov-report=term-missing

lint: dev-deps ## Lint everything (no writes)
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	cd frontend && npm run lint

fix: dev-deps ## Auto-fix what can be auto-fixed
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .
	cd frontend && npm run lint -- --fix

typecheck: ## TypeScript strict typecheck
	cd frontend && npm run typecheck

check: lint typecheck test ## Everything CI runs, locally

api-types: ## Regenerate frontend types from the FastAPI OpenAPI schema
	./scripts/gen-api-types.sh

migrate: ## Apply database migrations
	cd backend && ../$(PY) -m alembic upgrade head

migration: ## Create a migration: make migration m="add x"
	cd backend && ../$(PY) -m alembic revision --autogenerate -m "$(m)"

ai-context: ## Regenerate the machine-readable repo map for AI agents
	./scripts/ai-context.sh

status: ## Regenerate STATUS.md (tests, routes, migrations, open roadmap items)
	./scripts/status.sh

docker: ## Build and run the whole stack
	docker compose up --build

clean: ## Remove caches and build artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache frontend/.next frontend/tsconfig.tsbuildinfo
