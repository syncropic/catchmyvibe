.PHONY: help install dev build test lint clean docker-up docker-down migrate

# Default target
help:
	@echo "CatchMyVibe - DJ Enhancement Platform"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development:"
	@echo "  install     Install all dependencies"
	@echo "  dev         Start development servers"
	@echo "  dev-backend Start backend only"
	@echo "  dev-frontend Start frontend only"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up   Start all services with Docker"
	@echo "  docker-down Stop all Docker services"
	@echo "  docker-logs View Docker logs"
	@echo ""
	@echo "Database:"
	@echo "  migrate     Run database migrations"
	@echo "  seed        Seed database with sample data"
	@echo ""
	@echo "Testing:"
	@echo "  test        Run all tests"
	@echo "  test-backend Run backend tests"
	@echo "  test-frontend Run frontend tests"
	@echo ""
	@echo "Utilities:"
	@echo "  lint        Run linters"
	@echo "  format      Format code"
	@echo "  clean       Clean build artifacts"

# Installation
install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

# Development
dev:
	@echo "Starting development servers..."
	@make docker-up &
	@sleep 5
	cd frontend && npm run dev

dev-backend:
	cd backend && uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Docker
docker-up:
	docker-compose up -d postgres redis
	@echo "Waiting for services to be ready..."
	@sleep 3
	@echo "Services ready!"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

docker-all:
	docker-compose up -d

# Database
migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m scripts.seed_data

# Testing
test: test-backend test-frontend

test-backend:
	cd backend && pytest -v

test-frontend:
	cd frontend && npm test

# Linting
lint: lint-backend lint-frontend

lint-backend:
	cd backend && ruff check .
	cd backend && mypy .

lint-frontend:
	cd frontend && npm run lint

# Formatting
format: format-backend format-frontend

format-backend:
	cd backend && ruff format .

format-frontend:
	cd frontend && npx prettier --write .

# Cleaning
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.coverage
	rm -rf frontend/.next
	rm -rf frontend/node_modules/.cache

# Import helpers
import-rekordbox:
	@echo "Upload your Rekordbox XML export to /api/import/rekordbox"

import-serato:
	@echo "Run: curl -X POST http://localhost:8000/api/import/serato"

# Analysis helpers
analyze-all:
	curl -X POST http://localhost:8000/api/analysis/enrich

# Quick status check
status:
	@echo "=== Backend ==="
	@curl -s http://localhost:8000/health || echo "Backend not running"
	@echo ""
	@echo "=== Frontend ==="
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend running" || echo "Frontend not running"
	@echo ""
	@echo "=== Docker ==="
	@docker-compose ps
