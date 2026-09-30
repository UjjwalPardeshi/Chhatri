# Chhatri developer commands (SPEC §23; binding decisions B7, B8).
#
# Only `data` builds artefacts; no other target depends on it. `test` never needs artefacts;
# `test-slow` and `demo-check` read the committed artefacts and never rebuild them.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PYTHON ?= python3.12
VENV := $(ROOT)/backend/.venv
PY := $(VENV)/bin/python
NPM ?= npm
BACKEND_PORT ?= 8000
CONSOLE_PORT ?= 5173
CONSOLE_URL ?= http://localhost:$(CONSOLE_PORT)
COVERAGE_MIN ?= 80
INFRA_COVERAGE_MIN ?= 90

.PHONY: help setup data test test-backend test-frontend test-slow test-infra dev demo-check e2e \
	env up down lint n8n-workflows n8n-selftest clean

help: ## List the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

setup: ## Create backend/.venv, install backend[dev], npm ci in frontend/
	test -x $(PY) || $(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e "$(ROOT)/backend[dev]"
	cd $(ROOT)/frontend && $(NPM) ci

data: ## Build every artefact: python backend/scripts/build_data.py (slow; the only artefact writer)
	cd $(ROOT) && $(PY) backend/scripts/build_data.py

test: test-backend test-frontend ## Fast suite: backend (not slow, coverage >= 80%) + frontend typecheck, lint, test

test-backend: ## Backend pytest -m "not slow" with coverage >= 80% (COVERAGE_MIN)
	cd $(ROOT)/backend && $(PY) -m pytest -m "not slow" --cov=chhatri --cov-report=term-missing --cov-fail-under=$(COVERAGE_MIN)

test-frontend: ## Frontend typecheck, lint and unit tests (B7 scripts)
	cd $(ROOT)/frontend && $(NPM) run typecheck && $(NPM) run lint && $(NPM) run test

test-slow: ## Golden numbers + full-artefact flows (pytest -m slow; needs committed artefacts, never rebuilds them)
	cd $(ROOT)/backend && $(PY) -m pytest -m slow

test-infra: ## Infra checks: n8n workflows generated from WORKFLOWS, compose, Makefile, env, nginx, scripts
	cd $(ROOT) && $(PY) scripts/n8n_workflows.py --check
	cd $(ROOT) && $(PY) -m pytest -p no:cacheprovider scripts/tests --cov=scripts --cov-report=term-missing --cov-fail-under=$(INFRA_COVERAGE_MIN)

dev: ## Backend (uvicorn :8000, reload) + console (vite :5173, proxies /api); Ctrl+C stops both
	trap 'kill $$(jobs -p) 2>/dev/null || true' INT TERM EXIT; \
	(cd $(ROOT)/backend && $(PY) -m uvicorn --factory chhatri.api.app:create_app --reload --host 127.0.0.1 --port $(BACKEND_PORT)) & \
	(cd $(ROOT)/frontend && VITE_API_URL=http://127.0.0.1:$(BACKEND_PORT) $(NPM) run dev -- --host 127.0.0.1 --port $(CONSOLE_PORT) --strictPort) & \
	wait

demo-check: ## Every scenario through the HTTP API: python backend/scripts/demo_check.py (needs artefacts)
	cd $(ROOT) && $(PY) backend/scripts/demo_check.py

e2e: ## Playwright (chromium) against running backend + console at CONSOLE_URL (default :5173)
	cd $(ROOT)/frontend && CONSOLE_URL=$(CONSOLE_URL) $(NPM) run test:e2e

env: ## Create .env from .env.example with generated secrets; an existing .env is only checked, never overwritten
	python3 $(ROOT)/scripts/init_env.py

up: env ## docker compose up -d --build (backend, frontend, n8n), waits until healthy
	cd $(ROOT) && docker compose up -d --build --wait

down: ## Stop the docker stack (keeps volumes)
	cd $(ROOT) && docker compose down

lint: ## ruff check + format check (backend; scripts via scripts/ruff.toml, which extends the backend config)
	cd $(ROOT)/backend && $(PY) -m ruff check . && $(PY) -m ruff format --check .
	cd $(ROOT) && $(PY) -m ruff check scripts && $(PY) -m ruff format --check scripts

n8n-workflows: ## Regenerate n8n/workflows/*.json from chhatri.workflows.definitions.WORKFLOWS
	cd $(ROOT) && $(PY) scripts/n8n_workflows.py

n8n-selftest: ## Run the pinned n8n image with the workflows against a stub backend (needs docker)
	cd $(ROOT) && $(PY) scripts/n8n_selftest.py --start-container

clean: ## Remove caches and build output (keeps .venv, node_modules, artefacts and .env)
	rm -rf $(ROOT)/backend/.pytest_cache $(ROOT)/backend/.ruff_cache $(ROOT)/backend/htmlcov $(ROOT)/backend/.coverage
	rm -rf $(ROOT)/frontend/dist $(ROOT)/frontend/test-results $(ROOT)/frontend/playwright-report
	find $(ROOT)/backend $(ROOT)/scripts -name __pycache__ -type d -prune -exec rm -rf {} +
