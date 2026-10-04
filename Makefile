# Equilibrium - AI Atlas for the World's Rare Diseases
# Works with GNU make on Linux/macOS and Git Bash on Windows.
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

BACKEND  := backend
FRONTEND := frontend

.PHONY: help setup dev dev-backend dev-frontend lint fmt typecheck test check build \
        docker-up docker-down data data-offline data-report openai-smoke clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend + frontend deps and git hooks
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && pnpm install
	@if command -v pre-commit >/dev/null 2>&1; then pre-commit install; \
	else echo "pre-commit not found - optional: 'uv tool install pre-commit' then 'pre-commit install'"; fi

dev: ## How to run the stack locally
	@echo "Run in two terminals:"
	@echo "  make dev-backend    # http://localhost:8000 (GET /health)"
	@echo "  make dev-frontend   # http://localhost:3000"
	@echo "Or everything in containers: make docker-up"

dev-backend: ## Run the API with reload on :8000
	cd $(BACKEND) && uv run uvicorn atlas.api.main:app --reload --port 8000

dev-frontend: ## Run the Next.js dev server on :3000
	cd $(FRONTEND) && pnpm dev

lint: ## Lint backend (ruff) and frontend (eslint + prettier check)
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && pnpm lint && pnpm format:check

fmt: ## Auto-format backend and frontend
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .
	cd $(FRONTEND) && pnpm format

typecheck: ## Type-check backend (mypy) and frontend (tsc)
	cd $(BACKEND) && uv run mypy src
	cd $(FRONTEND) && pnpm typecheck

test: ## Run unit tests (backend coverage gate + frontend)
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && pnpm test

check: lint typecheck test ## lint + typecheck + test (what CI runs)

build: ## Production build of the frontend
	cd $(FRONTEND) && pnpm build

docker-up: ## Build and start backend + frontend containers (backend image bakes in data/snapshot/)
	docker compose up --build -d
	@echo "backend:  http://localhost:8000/health"
	@echo "frontend: http://localhost:3000"

docker-down: ## Stop containers
	docker compose down

data: ## Refresh every source online (rewrites data/cache/) and rebuild data/snapshot/
	cd $(BACKEND) && uv run python -m atlas.pipeline build

data-offline: ## Rebuild data/snapshot/ from the committed cache only (no network, deterministic)
	cd $(BACKEND) && uv run python -m atlas.pipeline build --offline

data-report: ## Print snapshot counts and the hero-path / honest-gap checks
	cd $(BACKEND) && uv run python -m atlas.pipeline report

openai-smoke: ## Check OpenAI models/embeddings with a real key (BATCH=1 also submits a Batch)
	cd $(BACKEND) && uv run python scripts/openai_smoke.py $(if $(BATCH),--batch,)

clean: ## Remove caches and build output
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache \
		$(BACKEND)/htmlcov $(BACKEND)/coverage.xml $(BACKEND)/.coverage
	rm -rf $(FRONTEND)/.next $(FRONTEND)/coverage $(FRONTEND)/playwright-report $(FRONTEND)/test-results
	find . -type d -name __pycache__ -not -path './node_modules/*' -prune -exec rm -rf {} +
