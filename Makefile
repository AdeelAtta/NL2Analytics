.PHONY: help install dev test test-backend test-frontend lint typecheck format clean build-backend build-frontend up down db-migrate db-seed pre-commit setup

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	cd backend && uv sync
	cd frontend && npm install

dev: ## Start development environment
	docker compose -f infra/docker/docker-compose.yml up -d postgres
	cd backend && uv run uvicorn app.main:create_app --reload --port 8100 &
	cd frontend && npm run dev

test: ## Run all tests
	cd backend && uv run pytest
	cd frontend && npm run test

test-backend: ## Run backend tests only
	cd backend && uv run pytest

test-frontend: ## Run frontend tests only
	cd frontend && npm run test

lint: ## Run all linters
	cd backend && uv run ruff check .
	cd frontend && npm run lint

typecheck: ## Run type checkers
	cd backend && uv run mypy .
	cd frontend && npm run typecheck

format: ## Format all code
	cd backend && uv run ruff format .
	cd frontend && npx prettier --write .

clean: ## Clean build artifacts
	rm -rf backend/.venv frontend/node_modules frontend/.next
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build-backend: ## Build backend Docker image
	docker build -f infra/docker/Dockerfile.backend -t schemaintern-backend:latest .

build-frontend: ## Build frontend Docker image
	docker build -f infra/docker/Dockerfile.frontend -t schemaintern-frontend:latest .

up: ## Start all services with Docker Compose
	docker compose -f infra/docker/docker-compose.yml up -d

down: ## Stop all services
	docker compose -f infra/docker/docker-compose.yml down

db-migrate: ## Run database migrations
	cd backend && uv run alembic upgrade head

db-seed: ## Seed placeholder data (legacy)
	cd backend && uv run scripts/seed.py

seed: ## Seed a test database (usage: make seed DB=lego [PASSWORD=postgres])
	POSTGRES_PASSWORD=$(PASSWORD) ./bin/seed.sh $(DB)

seed-all: ## Seed all test databases (usage: make seed-all [PASSWORD=postgres])
	POSTGRES_PASSWORD=$(PASSWORD) ./bin/seed.sh --all

seed-docker: ## Seed using docker-compose postgres (usage: make seed-docker DB=lego)
	./bin/seed.sh --docker $(DB)

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

setup: install pre-commit db-migrate db-seed ## Full setup (install + migrate + seed)

prod: ## Start production stack
	docker compose up -d --build

prod-logs: ## Tail production logs
	docker compose logs -f

prod-down: ## Stop production stack
	docker compose down

dev-up: ## Start dev stack
	docker compose -f docker-compose.dev.yml up -d --build

dev-down: ## Stop dev stack
	docker compose -f docker-compose.dev.yml down
