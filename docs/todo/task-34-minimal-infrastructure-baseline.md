# Task 34 - Minimal Infrastructure Baseline (Assuming VPS)

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/34`

Assumption:
- Runtime target is VPS (from Task 33 proposal).

Objective:
- Define the smallest production-safe baseline that keeps Vikunja + MCP available 24/7.

## Baseline Topology

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

## Required Components

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

## Minimum Security Baseline

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

## Operational Baseline

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

## Sleep/Offline Behavior (with VPS)

- Laptop sleep/shutdown: no service impact.
- Home network outage: no service impact.
- VPS reboot: automatic service restart via restart policy.
- Single-region outage: service unavailable (mitigate later with snapshot + secondary host plan).

## Immediate Implementation Checklist

1. Provision VPS with Docker runtime.
2. Deploy stack via `docker compose up -d`.
3. Add reverse proxy + TLS.
4. Confirm health checks (`make verify`, `make test-mcp`).
5. Configure backup cron/systemd timer.
6. Document restore procedure.

## Decision Status

- Status: `Draft ready`
- Depends on: Task 33 confirmation
