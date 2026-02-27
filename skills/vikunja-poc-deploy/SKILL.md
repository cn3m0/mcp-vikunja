---
name: vikunja-poc-deploy
description: Bootstrap, verify, and connect the Vikunja + MCP PoC repository on a fresh Codex instance. Use when you need fast local setup, admin/token initialization, end-to-end verification, Codex MCP registration, or operational troubleshooting for this project.
---

# Vikunja PoC Deploy

## Overview

Use this skill to bring this repository from fresh checkout to working Vikunja + MCP state with minimal decisions.

## Execute Setup Workflow

1. Validate local prerequisites.

```bash
docker --version
docker compose version
python3 --version
make help
```

2. Start and bootstrap the stack.

```bash
make up
make bootstrap
```

3. Run runtime checks.

```bash
make full-check
```

4. Register MCP server in Codex.

```bash
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
```

## Apply Operational Rules

- Keep secrets in `.env` only.
- Never commit `.env` or runtime tokens.
- Prefer `make` targets over ad-hoc commands for repeatability.
- Run `make publish-check` before publishing repository changes.

## Troubleshoot Fast

- Read service state:

```bash
make ps
```

- Read logs:

```bash
make logs
```

- Rebuild adapter after code changes:

```bash
docker compose up -d --build mcp-adapter
```

- Use command matrix:
  See `references/command-matrix.md`.

