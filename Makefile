SHELL := /bin/bash

.PHONY: help onboard up bootstrap verify test-mcp full-check publish-check logs ps down clean

help:
	@echo "Available targets:"
	@echo "  make up         - Start all services (build if needed)"
	@echo "  make onboard    - One-command bootstrap + full runtime checks"
	@echo "  make bootstrap  - Create/verify admin user and generate API token"
	@echo "  make verify     - Run Vikunja PoC verification"
	@echo "  make test-mcp   - Run MCP streamable-http smoke test"
	@echo "  make full-check - Run verify and MCP smoke test"
	@echo "  make publish-check - Run static checks for GitHub publishing"
	@echo "  make logs       - Follow service logs"
	@echo "  make ps         - Show container status"
	@echo "  make down       - Stop services"
	@echo "  make clean      - Stop services and remove volumes"

up:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	docker compose up -d --build

onboard: up bootstrap full-check

bootstrap:
	python3 scripts/bootstrap_admin_and_token.py
	docker compose up -d --build mcp-adapter

verify:
	python3 scripts/verify_poc.py

test-mcp:
	python3 scripts/test_mcp_adapter.py

full-check: verify test-mcp

publish-check:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	docker compose config >/dev/null
	python3 -m compileall scripts mcp_adapter >/dev/null
	@echo "publish-check: OK"

logs:
	docker compose logs -f db vikunja mcp-adapter

ps:
	docker compose ps

down:
	docker compose down

clean:
	docker compose down -v
