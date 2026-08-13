.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help setup dev prod check clean

help: ## Show the supported repository commands
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install the current backend and root frontend dependencies
	cd server && uv sync --dev
	cd web && bun install --ignore-scripts --registry https://registry.npmmirror.com

dev: ## Start the only local development deployment with bind mounts
	docker compose -f docker-compose.dev.yml up --build

prod: ## Start the only production deployment with a static web export
	docker compose -f docker-compose.yml up --build -d

check: ## Run frontend type and style checks
	cd web && bun run type-check
	cd web && bun run lint:check

clean: ## Remove generated frontend and Python cache directories
	pwsh -NoProfile -Command "foreach ($$path in @('web/.next','web/out','web/node_modules','web/.cache','server/.pytest_cache','server/.ruff_cache')) { if (Test-Path -LiteralPath $$path) { [System.IO.Directory]::Delete((Resolve-Path -LiteralPath $$path).Path, $$true) } }"
