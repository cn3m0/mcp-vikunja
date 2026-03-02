# Task 36 - MCP Reconnect Runbook

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/36`

Goal:
- Recover quickly when a Codex session sees stale or incomplete MCP tools.

## Reconnect Procedure

1. Update project state:

```bash
git pull origin main
```

2. Rebuild/restart adapter:

```bash
docker compose up -d --build mcp-adapter
```

3. Re-register MCP in Codex:

```bash
codex mcp remove vikunja
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
codex mcp list
```

4. Validate toolset:
- Confirm expected tools are visible:
  - `health`
  - `list_projects`
  - `create_project`
  - `list_tasks`
  - `create_task`
  - `list_task_comments`
  - `add_task_comment`
  - `move_task`

## Troubleshooting

If `codex mcp get vikunja` fails:
- Check adapter logs:
  - `docker compose logs mcp-adapter --tail=100`
- Check service health:
  - `docker compose ps`
- Confirm `.env` token exists and is valid.

If tools are still stale:
- Restart full stack:
  - `docker compose up -d --build`
- Re-run registration commands.

## Acceptance Criteria

- New Codex session sees the expected toolset.
- `health` and `list_projects` calls return success.
