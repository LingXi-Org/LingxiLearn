.DEFAULT_GOAL := help
SHELL := /bin/bash
PY := server/.venv/bin/python
BASE ?= http://localhost:8000

.PHONY: help setup artifacts dev api web test smoke eval check clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies
	cd server && uv venv --python 3.13 && uv pip install -e ".[dev]"
	cd web && npm install --no-audit --no-fund
	$(MAKE) artifacts

artifacts: ## Regenerate the teaching captures and verify their ground truth
	$(PY) scripts/build_artifacts.py --check

dev: artifacts ## Build the web app and serve everything from one port (:8000)
	cd web && npm run build
	cd server && .venv/bin/python -m uvicorn lingxilearn.main:app --port 8000 --reload

api: ## Run only the API (use with `make web` for hot reload)
	cd server && .venv/bin/python -m uvicorn lingxilearn.main:app --port 8000 --reload

web: ## Run the Next.js dev server against a local API
	cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev

test: ## Unit tests and type checks
	cd server && .venv/bin/python -m pytest -q
	cd server && .venv/bin/ruff check lingxilearn
	cd server && .venv/bin/mypy --config-file pyproject.toml lingxilearn
	cd web && npx tsc --noEmit
	cd web && npm test -- --run

smoke: ## End-to-end checks: kernel, HTTP+SSE, and the real browser
	@for m in web-slow reliable-delivery; do \
	  for l in confused ideal; do \
	    printf '  kernel %-18s %-9s ' $$m $$l; \
	    $(PY) scripts/smoke.py --mission $$m --learner $$l | grep '^RESULT'; \
	  done; \
	done
	@for m in web-slow reliable-delivery; do \
	  printf '  api    %-18s ' $$m; \
	  $(PY) scripts/api_smoke.py --base $(BASE) --mission $$m | grep '^RESULT'; \
	done
	@for m in web-slow reliable-delivery; do \
	  printf '  ui     %-18s ' $$m; \
	  $(PY) scripts/ui_smoke.py --base $(BASE) --mission $$m | grep '^RESULT'; \
	done

eval: ## Run the evaluation harness (leakage, misconceptions, evidence, gain)
	cd server && .venv/bin/python -m lingxilearn.eval

check: test eval ## Everything that does not need a running server

clean: ## Remove build output and local state
	rm -rf var web/out web/.next server/.pytest_cache server/.ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
