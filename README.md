# Vikunja MCP Kanban Stack

Production-ready self-hosted Kanban stack with MCP integration for Codex.

This project provides:

- Vikunja web app and API
- PostgreSQL persistence
- MCP adapter exposing Vikunja operations as MCP tools
- Automated bootstrap and verification scripts
- Make-based one-command onboarding

## Status

- Ready for day-to-day project management use.
- Fully reproducible with Docker Compose.
- Validated end-to-end (Vikunja API + MCP tool flow).

## Architecture

- `db`: PostgreSQL 16 (`postgres:16-alpine`)
- `vikunja`: `vikunja/vikunja:latest` on `http://localhost:3456`
- `mcp-adapter`: Python FastMCP service on `http://localhost:8000/mcp`

## Prerequisites

- Docker
- Docker Compose
- Python 3.12+

## Quick Start

Run everything in one command:

```bash
make onboard
```

`make onboard` runs:

- `make up`
- `make bootstrap`
- `make full-check`

## Manual Setup

1. Create environment file:

```bash
cp .env.example .env
```

2. Start services:

```bash
make up
```

3. Create admin user and API token:

```bash
make bootstrap
```

4. Run runtime checks:

```bash
make full-check
```

## MCP Tools

The adapter currently exposes:

- `health`
- `list_projects`
- `create_project`
- `list_tasks`
- `create_task`
- `move_task`

## Codex Integration

Register the running MCP server in Codex:

```bash
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
codex mcp list
```

Note: `/mcp` is a Streamable HTTP MCP endpoint. Browser GET requests are not a valid MCP protocol test.

## Operations

Common commands:

- `make help`
- `make ps`
- `make logs`
- `make down`
- `make clean`

Validation commands:

- `make verify` (Vikunja workflow validation)
- `make test-mcp` (MCP protocol + tool-call validation)
- `make full-check` (both checks)
- `make publish-check` (static publish checks)

## Environment Variables

Main values in `.env.example`:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `VIKUNJA_JWT_SECRET`
- `VIKUNJA_PUBLIC_URL`
- `VIKUNJA_ENABLE_REGISTRATION`
- `VIKUNJA_INTERNAL_URL`
- `VIKUNJA_ADMIN_USERNAME`
- `VIKUNJA_ADMIN_EMAIL`
- `VIKUNJA_ADMIN_PASSWORD`
- `VIKUNJA_API_TOKEN_TITLE`
- `VIKUNJA_API_TOKEN`

## GitHub Publishing

Before publishing:

```bash
make publish-check
```

This repository includes:

- CI workflow: `.github/workflows/ci.yml`
- License: `LICENSE` (MIT)
- Contribution guide: `CONTRIBUTING.md`
- Secret protection via `.gitignore` (`.env` is excluded)

## Codex Skill for Fast Reuse

A reusable skill is included for other Codex instances:

- `skills/vikunja-poc-deploy`

Install it into another Codex environment:

```bash
mkdir -p "$HOME/.codex/skills"
cp -r skills/vikunja-poc-deploy "$HOME/.codex/skills/"
```

Then invoke it by name: `vikunja-poc-deploy`.

