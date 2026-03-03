# Task 38 - Task Command Flow (Read/Write)

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/38`

Goal:
- Define a stable operational flow for task reads/writes/comments through MCP.

## Command Flow

1. Read phase
- `list_projects`
- `list_tasks`
- `get_task` (direct read by task ID, useful from `/tasks/<id>` URLs)
- `list_task_comments` (if task context is needed)

2. Write phase
- `create_task` for new work item.
- `update_task` for direct field changes (title, description, done/date fields, priority).
- `add_task_comment` for status and execution logs.
- `move_task` for lifecycle transitions.

3. Verification phase
- Re-read task/comments after each write to confirm persistence.
- If mismatch occurs, retry once and report `blocked`.

## Write Safety Rules

- Always reference task ID in status comments.
- Use standardized prefixes:
  - `ack: started`
  - `update:`
  - `blocked:`
  - `done:`
- Avoid duplicate comments in same cycle by checking latest comment content.

## Failure Handling

- API/network error: log `blocked` with short reason.
- Permission error: do not retry blindly; escalate in ticket comment.
- MCP stale tools: run reconnect runbook (`task-36`).

## Acceptance Criteria

- Read -> write -> verify loop works repeatedly without inconsistent state.
- Comment updates and bucket transitions remain deterministic.
