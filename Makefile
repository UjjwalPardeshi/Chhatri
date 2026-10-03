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
# The stage demo flag set (docs/06-delivery/stage-script.md). The backend and the console must read the same list.
STAGE_FLAGS ?= n1_miniapp,n2_ask_chhatri,n3_slip_precheck,x4_lender_request,x6_provider_panel,h24_whatif,console_polish,telegram_channel
# GEMINI_MODEL for the stage: the free tier allows about 20 requests a day per model, and .env may name a model that is
# spent or retired (gemini-2.5-flash-lite was spent and gemini-2.5-flash answered HTTP 404 on 3 Oct 2026), which sends
# the slip to a person on stage. STAGE_GEMINI_BACKUPS are tried in order when the main model is spent or slow.
# STAGE_AI=live (the default) uses the keys in .env: Gemini reads the slip and answers free questions, and the footer
# says LIVE. STAGE_AI=sim blanks both AI keys so every badge reads SIMULATED.
STAGE_GEMINI_MODEL ?= gemini-3.5-flash-lite
STAGE_GEMINI_BACKUPS ?= gemini-flash-lite-latest
STAGE_AI ?= live
ifeq ($(STAGE_AI),sim)
STAGE_AI_ENV := GOOGLE_API_KEY= SARVAM_API_KEY=
else
STAGE_AI_ENV :=
endif
COVERAGE_MIN ?= 80
INFRA_COVERAGE_MIN ?= 90

.PHONY: help setup data test test-backend test-frontend test-slow test-infra evals dev demo-check judge demo-stage stage-e2e e2e \
	env check-keys up down lint n8n-workflows n8n-selftest clean

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

# COVERAGE_CORE=sysmon: Python 3.12's low-overhead tracer (coverage >= 7.4); several times faster here.
test-backend: ## Backend pytest -m "not slow" with coverage >= 80% (COVERAGE_MIN)
	cd $(ROOT)/backend && COVERAGE_CORE=sysmon $(PY) -m pytest -m "not slow" --cov=chhatri --cov-report=term-missing --cov-fail-under=$(COVERAGE_MIN)

test-frontend: ## Frontend typecheck, lint and unit tests (B7 scripts)
	cd $(ROOT)/frontend && $(NPM) run typecheck && $(NPM) run lint && $(NPM) run test

test-slow: ## Golden numbers + full-artefact flows (pytest -m slow; needs committed artefacts, never rebuilds them)
	cd $(ROOT)/backend && $(PY) -m pytest -m slow

test-infra: ## Infra checks: n8n workflows generated from WORKFLOWS, compose, Makefile, env, nginx, scripts
	cd $(ROOT) && $(PY) scripts/n8n_workflows.py --check
	cd $(ROOT) && $(PY) -m pytest -p no:cacheprovider scripts/tests --cov=scripts --cov-report=term-missing --cov-fail-under=$(INFRA_COVERAGE_MIN)

evals: ## H25 offline evaluation suites (no network, no key): writes backend/artifacts/evals/summary.json
	cd $(ROOT)/backend && $(PY) -m chhatri.evals

dev: ## Backend (uvicorn :8000, reload) + console (vite :5173, proxies /api); Ctrl+C stops both
	trap 'kill $$(jobs -p) 2>/dev/null || true' INT TERM EXIT; \
	(cd $(ROOT)/backend && $(PY) -m uvicorn --factory chhatri.api.app:create_app --reload --host 127.0.0.1 --port $(BACKEND_PORT)) & \
	(cd $(ROOT)/frontend && VITE_API_URL=http://127.0.0.1:$(BACKEND_PORT) $(NPM) run dev -- --host 127.0.0.1 --port $(CONSOLE_PORT) --strictPort) & \
	wait

demo-check: ## Every scenario through the HTTP API: python backend/scripts/demo_check.py (needs artefacts)
	cd $(ROOT) && $(PY) backend/scripts/demo_check.py

# Without backend/.venv the script runs on python3 (its top is stdlib only) and reports the missing venv as a FAIL.
judge: ## One command for a judge: environment, keys (SET / NOT SET), artefacts vs MANIFEST.json, demo check, audit chain, typecheck; ends CHHATRI JUDGE READY or lists what failed
	cd $(ROOT) && $(if $(wildcard $(PY)),$(PY),python3) scripts/judge.py

demo-stage: ## The 3-minute stage demo: backend + console, stage flag set, synthetic data, no reload. Live Gemini by default; STAGE_AI=sim: no AI keys
	trap 'kill $$(jobs -p) 2>/dev/null || true' INT TERM EXIT; \
	(cd $(ROOT)/backend && CHHATRI_FEATURES=$(STAGE_FLAGS) CHHATRI_DATA_IS_SYNTHETIC=true GEMINI_MODEL=$(STAGE_GEMINI_MODEL) GEMINI_BACKUP_MODELS=$(STAGE_GEMINI_BACKUPS) $(STAGE_AI_ENV) $(PY) -m uvicorn --factory chhatri.api.app:create_app --host 127.0.0.1 --port $(BACKEND_PORT)) & \
	(cd $(ROOT)/frontend && VITE_FEATURES=$(STAGE_FLAGS) VITE_API_URL=http://127.0.0.1:$(BACKEND_PORT) $(NPM) run dev -- --host 127.0.0.1 --port $(CONSOLE_PORT) --strictPort) & \
	wait

stage-e2e: ## Walk the stage script against the real backend on :8301/:5301, then stop both. Default STAGE_E2E_AI=sim (no keys); STAGE_E2E_AI=live uses the .env Gemini key and asserts LIVE gemini (STAGE_RUNS=3 repeats it)
	cd $(ROOT) && STAGE_FLAGS="$(STAGE_FLAGS)" STAGE_E2E_AI="$${STAGE_E2E_AI:-sim}" STAGE_GEMINI_MODEL="$(STAGE_GEMINI_MODEL)" STAGE_RUNS="$${STAGE_RUNS:-1}" bash scripts/stage_e2e.sh

e2e: ## Playwright (chromium) against running backend + console at CONSOLE_URL (default :5173)
	cd $(ROOT)/frontend && CONSOLE_URL=$(CONSOLE_URL) $(NPM) run test:e2e

env: ## Create .env from .env.example with generated secrets; an existing .env is only checked, never overwritten
	python3 $(ROOT)/scripts/init_env.py

check-keys: ## SARVAM_API_KEY, GOOGLE_API_KEY, TELEGRAM_BOT_TOKEN as SET / NOT SET (never printed); lists the Gemini models and the Telegram bot's username
	python3 $(ROOT)/scripts/check_keys.py

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
