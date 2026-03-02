# Task 49 - Phase A Local PC Baseline Runbook

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/49`

Goal:
- Keep development velocity on the current PC while enforcing a predictable and testable runtime baseline.

## Scope

In scope:
- Local startup/shutdown routine
- Health and MCP verification routine
- Backup and restore minimum routine
- Known limitations while running on a personal workstation

Out of scope:
- Public internet exposure
- Full VPS-grade hardening

## Standard Start Procedure

1. Ensure local `.env` is present and valid.
2. Start stack:
   - `docker compose up -d`
3. Bootstrap token/admin if needed:
   - `make bootstrap`
4. Verify baseline:
   - `make verify`
   - `make test-mcp`

## Daily Development Routine

Before coding:
1. `git pull origin main`
2. `docker compose ps`
3. `make verify`

After runtime-related changes:
1. `docker compose up -d --build mcp-adapter`
2. `make test-mcp`
3. If MCP tools look stale in Codex session:
   - `codex mcp remove vikunja`
   - `codex mcp add vikunja --url http://localhost:8000/mcp`
   - `codex mcp get vikunja`

## Backup and Restore Minimum

Backup minimum (daily or before risky changes):
1. Export PostgreSQL dump.
2. Snapshot important config (`.env`, compose files, docs).

Restore test minimum (weekly):
1. Restore dump into isolated local DB/container.
2. Start Vikunja against restored DB.
3. Confirm task and comment integrity.

## Known Constraints in Phase A

- If PC sleeps/shuts down, service stops.
- Local network changes can break endpoint reachability.
- No uptime guarantee for remote collaboration.

Mitigation:
- Keep tasks/status in Vikunja updated before shutdown.
- Use this phase only as development baseline, not as final availability target.

## Exit Criteria for Task 49

1. Team can execute start/verify flow without missing steps.
2. One backup + one restore test documented.
3. All related commands validated in current environment.
