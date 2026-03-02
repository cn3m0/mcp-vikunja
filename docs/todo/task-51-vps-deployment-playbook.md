# Task 51 - VPS Deployment Playbook

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/51`

Goal:
- Provide an executable baseline for production-style deployment on VPS.

## Prerequisites

- VPS with public IP and SSH access.
- Domain/subdomain for service endpoint.
- Docker + Docker Compose available on host.
- Repository access configured.

## Deployment Steps

1. Prepare host
- Update packages.
- Configure firewall: allow `22`, `80`, `443`.
- Install Docker + Compose plugin.

2. Deploy application
- Clone repository.
- Create `.env` from `.env.example`.
- Set strong secrets (`VIKUNJA_JWT_SECRET`, token values).
- Start services:
  - `docker compose up -d --build`

3. Reverse proxy + TLS
- Place Nginx/Caddy/Traefik in front of `vikunja` and `mcp-adapter`.
- Enable HTTPS (Let's Encrypt).
- Route:
  - `/` -> Vikunja
  - `/mcp` -> MCP adapter

4. Verify deployment
- `make verify`
- `make test-mcp`
- Verify MCP registration from fresh Codex session.

## Security Baseline

- Disable public Vikunja registration.
- Keep database port internal only.
- Restrict SSH access (keys only).
- Rotate API token if exposure is suspected.
- Keep `.env` out of version control.

## Backup and Recovery

Minimum:
- Daily PostgreSQL backup.
- Daily config snapshot.
- Retention: at least 7 days.
- Weekly restore test in isolated DB.

## Rollback Strategy

If new release fails:
1. `git checkout` previous known-good commit.
2. `docker compose up -d --build`
3. Re-run `make verify` and `make test-mcp`.

## Acceptance Criteria

- Public HTTPS endpoint functional.
- MCP toolset available and healthy.
- Backup job and restore test procedure documented.
