# Task 37 - Codex Session Bootstrap Checklist

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/37`

Goal:
- Start any new Codex session with predictable project context and working MCP tools.

## Bootstrap Checklist

1. Pull latest repository state:

```bash
git pull origin main
```

2. Ensure stack is running:

```bash
docker compose ps
docker compose up -d --build mcp-adapter
```

3. Register/refresh MCP endpoint:

```bash
codex mcp remove vikunja
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
```

4. Validate baseline:

```bash
make verify
make test-mcp
```

5. Confirm working context in Vikunja:
- Project board reachable.
- Current milestone/task in `Doing`.
- Last status comment and ownership mode are consistent.

## Quick Session Start Prompt Template

Use in new session:

```text
Read PROJECT.md and PLAN.md, then continue with task #<id> in Vikunja project 13.
Confirm MCP tools available before making changes.
```

## Acceptance Criteria

- Session can immediately read/write tasks.
- MCP toolset is available without manual debugging.
- Runtime checks pass before feature work starts.
