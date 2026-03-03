# Task 44 - Operational Hardening and Recovery

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/44`

Goal:
- Ensure predictable operations and fast recovery across PC, dedicated box, and future VPS/NanoPi phases.

## Scope

This milestone groups:
- Offline/sleep behavior matrix (`task-45`)
- Monitoring and alerting baseline (`task-46`)
- Backup/restore drill protocol (`task-47`)

## Recovery Baseline

1. Detect issue quickly via health and alert signals.
2. Apply deterministic recovery runbook.
3. Verify service and MCP functionality after recovery.
4. Record evidence in ticket comments/docs.

## Artifacts

- `docs/todo/task-45-offline-sleep-behavior-matrix.md`
- `docs/todo/task-46-monitoring-alerting-baseline.md`
- `docs/todo/task-47-backup-restore-drill-protocol.md`

## Acceptance Criteria

- Known outage cases have clear recovery actions.
- Monitoring baseline is defined and actionable.
- Backup/restore drill process is standardized and repeatable.
