.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help setup dev prod prod-pull test check clean

help: ## Show the supported repository commands
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install the current backend and root frontend dependencies
	cd server && uv sync --dev
	cd web && bun install --ignore-scripts --registry https://registry.npmmirror.com

dev: ## Start the only local development deployment with bind mounts
	docker compose -f docker-compose.dev.yml up --build

prod: ## Start the production Next standalone Web, API, scheduler, and database
	$(MAKE) prod-pull
	docker compose -f docker-compose.yml up -d

prod-pull: ## Pull accelerated API and Web images using the configured tag
	docker compose -f docker-compose.yml pull postgres api web scheduler migrate api-var-init

test: ## Run the backend test suite against the current checkout
	cd server && uv run pytest tests

check: ## Run all backend architecture/style and frontend quality gates
	cd server && uv run python scripts/check_architecture.py
	cd server && uv run python scripts/export_openapi.py --check
	cd server && uv run ruff check lingxilearn tests scripts
	cd server && uv run ruff format --check lingxilearn tests scripts
	cd web && bun run check
	cd web && bun run build

check-contracts: ## Verify OpenAPI export and generated TypeScript contracts are in sync
	cd server && uv run python scripts/export_openapi.py --check
	cd web && bun run generate:api
	git diff --exit-code -- server/openapi.json web/shared/api/generated/schema.ts

clean: ## Remove generated frontend and Python cache directories
	pwsh -NoProfile -Command "foreach ($$path in @('web/.next','web/out','web/node_modules','web/.cache','server/.pytest_cache','server/.ruff_cache')) { if (Test-Path -LiteralPath $$path) { [System.IO.Directory]::Delete((Resolve-Path -LiteralPath $$path).Path, $$true) } }"
