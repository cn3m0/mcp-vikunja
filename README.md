# mcp-vikunja

Production-ready, self-hosted Vikunja + MCP stack for AI-driven project management.

- [AI-Driven Project Management: Introducing MCP-Vikunja](https://www.cn3m0.com/proof/ai-driven-project-management-introducing-mcp-vikunja/ "AI-Driven Project Management: Introducing MCP-Vikunja")
- [What is the Model Context Protocol (MCP)?](https://modelcontextprotocol.io/docs/getting-started/intro "What is the Model Context Protocol (MCP)?")
- [What are skills?](https://agentskills.io/what-are-skills "What are skills?")
- [Vikunja: The open-source, self-hostable to-do app](https://vikunja.io/ "Vikunja: The open-source, self-hostable to-do app")

## Overview

`mcp-vikunja` connects [Vikunja](https://github.com/go-vikunja/vikunja "GitHub / Vikunja") to MCP-compatible AI agents (for example Codex), so agents can manage project and task workflows directly via tool calls.

This repository provides:

- Vikunja web app and REST API
- [PostgreSQL](https://www.postgresql.org/) persistence
- [Python FastMCP](https://pypi.org/project/fastmcp/) adapter
- Bootstrap and verification scripts
- Make-based one-command onboarding
- GitHub publish readiness (CI + license + contribution guide)

## Why

[AI coding agents](https://openai.com/codex/ "AI coding agents") can generate code, but real engineering also needs:

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

## Project Documents

- [Project Definition](./PROJECT.md)
- [Execution Plan](./PLAN.md)
- [Contribution Guide](./CONTRIBUTING.md)
- [Code of Conduct](./CODE_OF_CONDUCT.md)
- [Open Source Respect Guidelines (EN)](./OPEN_SOURCE_OF_CONDUCT.md)
- [Open Source Respect Guidelines (DE)](./OPEN_SOURCE_OF_CONDUCT.de.md)
- [Open Source Respect - Public Short Version](./OPEN_SOURCE_OF_CONDUCT_PUBLIC.md)
- [Skills Overview](./skills/README.md)
- [Main Deploy Skill](./skills/mcp-vikunja-deploy/SKILL.md)
- [Task 31 Bridge Plan](./docs/todo/task-31-vikunja-codex-session-bridge-plan.md)
- [Task 33 Runtime Decision Matrix](./docs/todo/task-33-runtime-target-decision-matrix.md)
- [Task 34 Minimal Infrastructure Baseline](./docs/todo/task-34-minimal-infrastructure-baseline.md)
- [Task 49 Phase A Local Baseline Runbook](./docs/todo/task-49-phase-a-local-baseline-runbook.md)

## Features

### Implemented MCP tools

- `health`
- `list_projects`
- `create_project`
- `list_tasks`
- `create_task`
- `list_task_comments`
- `add_task_comment`
- `move_task`

### Design principles

- minimal dependencies
- deterministic behavior
- environment-based configuration
- no hardcoded credentials
- fully self-hostable

## Prerequisites

- [Docker](https://www.docker.com)
- [Docker Compose](https://docs.docker.com/compose/)
- [Python](https://www.python.org/) 3.12+

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

### MCP Reconnect (Hard Refresh)

If another Codex session still sees old tools, run this refresh sequence:

1. Update project state:

```bash
git pull origin main
```

2. Rebuild/restart the MCP adapter with the latest code:

```bash
docker compose up -d --build mcp-adapter
```

3. Re-register MCP in Codex:

```bash
codex mcp remove vikunja
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
```

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

- `skills/mcp-vikunja-deploy`

Skills info is available in `skills/README.md`.

Install locally:

```bash
mkdir -p "$HOME/.codex/skills"
cp -r skills/mcp-vikunja-deploy "$HOME/.codex/skills/"
```

Invoke by skill name: `mcp-vikunja-deploy`.

## Long-Term Vision

`mcp-vikunja` is a foundation for AI-native project orchestration:

- autonomous task planning
- iterative execution loops
- agent self-reflection on board state
- structured AI-assisted engineering workflows
