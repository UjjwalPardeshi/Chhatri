.PHONY: help setup data test test-backend test-frontend e2e dev demo-check up down lint clean

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)Chhatri — make targets (SPEC §23)$(NC)"
	@echo ""
	@echo "$(GREEN)Setup & Data$(NC)"
	@echo "  make setup          Create venv, install deps, npm ci"
	@echo "  make data           Build zones, hexes, calibration, model, backtest artifacts"
	@echo ""
	@echo "$(GREEN)Testing$(NC)"
	@echo "  make test           Run all tests (backend + frontend)"
	@echo "  make test-backend   Backend tests only (pytest with coverage)"
	@echo "  make test-frontend  Frontend tests only (vitest)"
	@echo "  make e2e            Playwright E2E tests (monsoon replay + officer approve)"
	@echo ""
	@echo "$(GREEN)Development$(NC)"
	@echo "  make dev            Run backend + frontend concurrently (uvicorn + vite)"
	@echo "  make demo-check     Smoke test: run all scenarios, check golden numbers"
	@echo ""
	@echo "$(GREEN)Docker Compose$(NC)"
	@echo "  make up             Start all services (backend, frontend, n8n if set)"
	@echo "  make down           Stop and remove containers"
	@echo ""
	@echo "$(GREEN)Code Quality$(NC)"
	@echo "  make lint           Run ruff check on backend"
	@echo "  make clean          Remove venv, node_modules, .pytest_cache, build artifacts"
	@echo ""

# === Setup ===

setup: backend-venv backend-deps frontend-deps
	@echo "$(GREEN)✓ Setup complete$(NC)"
	@echo "  Backend venv: backend/.venv"
	@echo "  Frontend npm: frontend/node_modules"
	@echo ""
	@echo "  Start development with: $(BLUE)make dev$(NC)"

backend-venv:
	@test -d backend/.venv || python3 -m venv backend/.venv
	@echo "$(GREEN)✓ Backend venv ready$(NC)"

backend-deps: backend-venv
	@. backend/.venv/bin/activate && pip install --upgrade pip setuptools wheel
	@. backend/.venv/bin/activate && pip install -e "backend[dev]"
	@echo "$(GREEN)✓ Backend dependencies installed$(NC)"

frontend-deps:
	@test -d frontend/node_modules || (cd frontend && npm ci)
	@echo "$(GREEN)✓ Frontend dependencies installed$(NC)"

# === Data ===

data: backend-deps
	@. backend/.venv/bin/activate && python backend/scripts/build_geo.py
	@. backend/.venv/bin/activate && python backend/scripts/calibrate.py
	@. backend/.venv/bin/activate && python backend/scripts/build_data.py
	@echo "$(GREEN)✓ Artifacts built: zones, hexes, calibration, model, backtest$(NC)"

# === Testing ===

test: test-backend test-frontend
	@echo "$(GREEN)✓ All tests passed$(NC)"

test-backend: backend-deps data
	@. backend/.venv/bin/activate && pytest backend/tests -v --cov=backend/chhatri --cov-report=term-missing --cov-fail-under=80 -m "not slow"
	@echo "$(GREEN)✓ Backend tests passed (≥80% coverage)$(NC)"

test-frontend: frontend-deps
	@cd frontend && npm run test:unit
	@echo "$(GREEN)✓ Frontend tests passed$(NC)"

e2e: backend-deps frontend-deps data
	@. backend/.venv/bin/activate && python -m pytest backend/tests -v -k "test_" --co > /dev/null 2>&1
	@cd frontend && npm run test:e2e
	@echo "$(GREEN)✓ E2E tests passed$(NC)"

# === Development ===

dev: backend-deps frontend-deps data
	@echo "$(BLUE)Starting development servers...$(NC)"
	@echo "  Backend (FastAPI):  http://localhost:8000"
	@echo "  Frontend (Vite):    http://localhost:5173"
	@echo "  Swagger docs:       http://localhost:8000/docs"
	@echo ""
	@echo "Press Ctrl+C to stop both servers"
	@echo ""
	@(. backend/.venv/bin/activate && cd backend && uvicorn --factory chhatri.api.app:create_app --reload --host 0.0.0.0 --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

# === Demo & Acceptance ===

demo-check: backend-deps data
	@echo "$(BLUE)Running demo scenarios...$(NC)"
	@. backend/.venv/bin/activate && python backend/scripts/demo_check.py
	@echo "$(GREEN)✓ Demo check passed$(NC)"

# === Docker Compose ===

up:
	docker compose config > /dev/null || (echo "$(RED)✗ docker-compose.yml is invalid$(NC)" && exit 1)
	@echo "$(BLUE)Starting Docker services...$(NC)"
	docker compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:80"
	@echo "  n8n:      http://localhost:5678 (if enabled via profile)"

down:
	docker compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

# === Code Quality ===

lint: backend-deps
	@. backend/.venv/bin/activate && ruff check backend/chhatri backend/tests
	@echo "$(GREEN)✓ Lint passed$(NC)"

# === Cleanup ===

clean:
	rm -rf backend/.venv
	rm -rf backend/.pytest_cache backend/.ruff_cache
	rm -rf backend/chhatri.egg-info
	rm -rf backend/.coverage backend/htmlcov
	rm -rf frontend/node_modules frontend/dist
	rm -rf frontend/.vite-cache
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# === Utilities ===

version:
	@echo "Chhatri — Build for India AI Hackathon · Track 2"
	@echo "Demo: 3 Oct 2026"
	@echo "Repo: https://github.com/palkia/Chhatri"
