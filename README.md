# mcp-vikunja

Production-ready, self-hosted Vikunja + MCP stack for AI-driven project management.

## Overview

`mcp-vikunja` connects [Vikunja](https://vikunja.io/) to MCP-compatible AI agents (for example Codex), so agents can manage project and task workflows directly via tool calls.

This repository provides:

- Vikunja web app and REST API
- PostgreSQL persistence
- Python FastMCP adapter
- Bootstrap and verification scripts
- Make-based one-command onboarding
- GitHub publish readiness (CI + license + contribution guide)

## Why

AI coding agents can generate code, but real engineering also needs:

- project structure
- task lifecycle management
- status transitions
- execution loops with feedback

With MCP integration, the agent can operate on actual project state instead of only text context.

## Architecture

```text
Codex / AI Agent
        |
        v
MCP Adapter (this project)
        |
        v
Vikunja API (REST)
        |
        v
PostgreSQL
```

Runtime services:

- `db`: `postgres:16-alpine`
- `vikunja`: `vikunja/vikunja:latest` on `http://localhost:3456`
- `mcp-adapter`: FastMCP service on `http://localhost:8000/mcp`

## Status

- Ready for day-to-day use.
- Reproducible via Docker Compose.
- End-to-end validated for Vikunja API and MCP flows.

## Features

### Implemented MCP tools

- `health`
- `list_projects`
- `create_project`
- `list_tasks`
- `create_task`
- `move_task`

### Design principles

- minimal dependencies
- deterministic behavior
- environment-based configuration
- no hardcoded credentials
- fully self-hostable

## Prerequisites

- Docker
- Docker Compose
- Python 3.12+

## Quick Start

One command:

```bash
make onboard
```

`make onboard` runs:

- `make up`
- `make bootstrap`
- `make full-check`

## Manual Setup

1. Create `.env`:

```bash
cp .env.example .env
```

2. Start services:

```bash
make up
```

3. Create/verify admin user and API token:

```bash
make bootstrap
```

4. Run runtime checks:

```bash
make full-check
```

## Codex Integration

Register the MCP server in Codex:

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

Validation:

- `make verify` (Vikunja workflow validation)
- `make test-mcp` (MCP protocol + tool-call validation)
- `make full-check` (verify + test-mcp)
- `make publish-check` (static publish checks)

## Environment Variables

Main variables in `.env.example`:

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

## Security

- Keep token/secrets in `.env` only.
- Never commit `.env` or runtime tokens.
- Registration is disabled by default (`VIKUNJA_ENABLE_REGISTRATION=false`).
- Use a reverse proxy and HTTPS for public exposure.

## GitHub Publishing

Before publishing:

```bash
make publish-check
```

Included in this repo:

- CI workflow: `.github/workflows/ci.yml`
- License: `LICENSE` (MIT)
- Contribution guide: `CONTRIBUTING.md`
- Secret protection: `.env` is ignored via `.gitignore`

## Reusable Codex Skill

This repo includes a reusable skill for fast setup on other Codex instances:

- `skills/vikunja-poc-deploy`

Install locally:

```bash
mkdir -p "$HOME/.codex/skills"
cp -r skills/vikunja-poc-deploy "$HOME/.codex/skills/"
```

Invoke by skill name: `vikunja-poc-deploy`.

## Long-Term Vision

`mcp-vikunja` is a foundation for AI-native project orchestration:

- autonomous task planning
- iterative execution loops
- agent self-reflection on board state
- structured AI-assisted engineering workflows

