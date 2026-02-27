SHELL := /bin/bash

.PHONY: help up bootstrap verify test-mcp logs ps down clean

help:
	@echo "Available targets:"
	@echo "  make up         - Start all services (build if needed)"
	@echo "  make bootstrap  - Create/verify admin user and generate API token"
	@echo "  make verify     - Run Vikunja PoC verification"
	@echo "  make test-mcp   - Run MCP streamable-http smoke test"
	@echo "  make logs       - Follow service logs"
	@echo "  make ps         - Show container status"
	@echo "  make down       - Stop services"
	@echo "  make clean      - Stop services and remove volumes"

up:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	docker compose up -d --build

bootstrap:
	python3 scripts/bootstrap_admin_and_token.py
	docker compose up -d --build mcp-adapter

verify:
	python3 scripts/verify_poc.py

test-mcp:
	python3 scripts/test_mcp_adapter.py

logs:
	docker compose logs -f db vikunja mcp-adapter

ps:
	docker compose ps

down:
	docker compose down

clean:
	docker compose down -v

