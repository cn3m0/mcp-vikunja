# Task 45 - Offline/Sleep Behavior Matrix

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/45`

Goal:
- Define expected system behavior under offline/sleep/restart events.

## Behavior Matrix

| Scenario | Expected Impact | Detection | Recovery Action | Severity |
|---|---|---|---|---|
| Dev PC sleep | Local stack unavailable | `docker compose ps` / failed health checks | Wake host, restart compose if needed | Medium |
| Dev PC shutdown | Local stack unavailable | Same as above | Start host, run startup checklist | Medium |
| Docker daemon restart | Temporary service interruption | Container restart events | Wait for auto-restart, run `make verify` | Low |
| Vikunja container crash | Task API unavailable | `docker compose ps` / logs | Auto-restart, inspect logs | High |
| MCP adapter crash | Tool calls fail | `codex mcp get` / adapter logs | Rebuild adapter + reconnect runbook | High |
| Home network outage | Remote access lost | Endpoint unavailable | Restore network, re-verify services | Medium |
| VPS outage (future phase) | Public service unavailable | External monitoring alert | Failover/restore procedure | High |

## Operational Rules

1. After any outage event, run:
- `make verify`
- `make test-mcp`

2. If MCP tools are stale after recovery:
- Apply reconnect runbook (`task-36`).

3. For repeated instability:
- open `blocked` comment and keep task in `Doing` until root cause is tracked.

## Acceptance Criteria

- Team can identify impact class for each outage type.
- Recovery steps are deterministic and documented.
