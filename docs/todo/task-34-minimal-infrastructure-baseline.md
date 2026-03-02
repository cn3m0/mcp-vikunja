# Task 34 - Minimal Infrastructure Baseline (Phased Profiles)

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/34`

Confirmed strategy from Task 33:
- Phase A: current PC (development baseline)
- Phase B: optional dedicated always-on Codex PC
- Phase C: long-term VPS and/or private NanoPi hosting

Objective:
- Define the smallest reliable baseline that works now on PC and migrates cleanly to always-on targets.

## Common Topology (All Phases)

```text
Internet
   |
   v
Reverse Proxy (TLS)
   |
   +--> vikunja (web + API)
   |
   +--> mcp-adapter (/mcp endpoint)
   |
   v
PostgreSQL (internal network only)
```

## Required Components (Common)

1. Reverse proxy
- Nginx, Caddy, or Traefik
- TLS termination (Let's Encrypt)
- Rate-limit and request size limits for public endpoints

2. Container runtime
- Docker + Docker Compose
- Restart policies (`unless-stopped`) for all services
- Explicit health checks

3. Core services
- `db` (PostgreSQL)
- `vikunja`
- `mcp-adapter`

4. Persistence
- Named volumes for database + Vikunja files
- Regular backup job (daily minimum)

5. Observability
- Container logs (`json-file` rotation or external collector)
- Health endpoint probes
- Simple alerting channel (mail/ntfy/Slack webhook)

## Minimum Security Baseline (Common)

Network:
- Only reverse-proxy ports exposed publicly.
- Database not exposed publicly.
- MCP endpoint reachable only through controlled ingress.

Secrets:
- Keep all secrets in `.env` or secret manager.
- Rotate `VIKUNJA_API_TOKEN` if leaked.
- Use long random JWT secret.

Access:
- Disable public registration.
- Separate admin user from automation token where possible.

## Operational Baseline (Common)

Backups:
- PostgreSQL dump daily.
- Volume/file backup daily.
- Retention minimum 7 days.

Recovery targets:
- RTO: 15 minutes
- RPO: 24 hours

Verification routine:
- Weekly restore test in isolated environment.
- Monthly token/secret review.

## Phase Profiles

### Phase A - Current PC (active now)

Target:
- Fast iteration and local development.

Required controls:
- Keep `docker compose` reproducible with `.env`.
- Validate `make verify` + `make test-mcp` after each relevant change.
- Add backup/restore script and test at least once.

Risk:
- Service unavailable when PC sleeps/shuts down.

### Phase B - Dedicated Codex PC (short-term optional)

Target:
- Always-on internal runtime without full VPS migration.

Required controls:
- Static local IP/DNS.
- Auto-start stack on boot.
- SSH-key-only access + firewall hardening.
- Remote health monitoring.

Risk:
- Depends on home power and internet.

### Phase C - VPS / NanoPi (long-term)

Target:
- Stable external availability and reduced dependence on personal workstation.

Required controls:
- Reverse proxy + TLS.
- Encrypted backups with retention.
- Recovery drill and migration runbook.

Risk:
- VPS: recurring cost and cloud dependency.
- NanoPi private host: home infrastructure dependency.

## Immediate Implementation Checklist

1. Finalize Phase A hardening tasks (local baseline).
2. Prepare Phase B checklist (dedicated box readiness).
3. Prepare Phase C deployment playbook (VPS/NanoPi migration).
4. Confirm health checks (`make verify`, `make test-mcp`) per phase.
5. Document restore procedure and test evidence.

## Decision Status

- Status: `In progress`
- Depends on: phase task execution and validation
