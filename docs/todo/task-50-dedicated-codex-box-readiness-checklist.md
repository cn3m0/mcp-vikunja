# Task 50 - Dedicated Codex Box Readiness Checklist

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/50`

Goal:
- Prepare a short-term always-on machine for Codex + Vikunja stack operation.

## Readiness Checklist

1. Host baseline
- Linux host updated.
- Fixed hostname and static LAN IP.
- Correct timezone and NTP sync enabled.

2. Access hardening
- SSH key-only login.
- Password login disabled.
- Root SSH login disabled.
- Host firewall enabled (allow only SSH + required app ports).

3. Runtime installation
- Docker installed.
- Docker Compose plugin installed.
- Repository cloned and `.env` configured.

4. Service startup behavior
- `docker compose up -d --build` works.
- Services auto-restart after reboot (`restart: unless-stopped` validated).
- Optional: systemd unit to ensure compose startup on boot.

5. Health validation
- `make verify` passes.
- `make test-mcp` passes.
- MCP endpoint reachable from Codex session.

6. Backup baseline
- Daily DB backup configured.
- Config snapshot (`.env`, compose files) configured.
- Restore drill task scheduled.

7. Monitoring baseline
- Container logs accessible.
- Health probe script/cron available.
- Alert path defined (mail/ntfy/webhook).

## Acceptance Criteria

- Box survives reboot and services come back healthy.
- MCP tools are available in a new Codex session.
- Backup and restore process documented and runnable.
