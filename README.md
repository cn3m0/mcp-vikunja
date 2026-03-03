# mcp-vikunja

Production-ready, self-hosted Vikunja + MCP stack for AI-driven project management.

- [AI-Driven Project Management: Introducing MCP-Vikunja](https://www.cn3m0.com/proof/ai-driven-project-management-introducing-mcp-vikunja/ "AI-Driven Project Management: Introducing MCP-Vikunja")
- [What is the Model Context Protocol (MCP)?](https://modelcontextprotocol.io/docs/getting-started/intro "What is the Model Context Protocol (MCP)?")
- [What are skills?](https://agentskills.io/what-are-skills "What are skills?")
- [Vikunja: The open-source, self-hostable to-do app](https://vikunja.io/ "Vikunja: The open-source, self-hostable to-do app")

## Overview

`mcp-vikunja` connects [Vikunja](https://github.com/go-vikunja/vikunja "GitHub / Vikunja") to MCP-compatible AI agents (for example Codex), so agents can manage project and task workflows directly via tool calls.

This repository provides:

- Vikunja web app and REST API
- [PostgreSQL](https://www.postgresql.org/) persistence
- [Python FastMCP](https://pypi.org/project/fastmcp/) adapter
- Bootstrap and verification scripts
- Make-based one-command onboarding
- GitHub publish readiness (CI + license + contribution guide)

## Why

[AI coding agents](https://openai.com/codex/ "AI coding agents") can generate code, but real engineering also needs:

- project structure
- task lifecycle management
- status transitions
- execution loops with feedback

With MCP integration, the agent can operate on actual project state instead of only text context.

## Architecture

```text
Codex / AI Agent
        |
        v
MCP Adapter (this project)
        |
        v
Vikunja API (REST)
        |
        v
PostgreSQL
```

Runtime services:

- `db`: `postgres:16-alpine`
- `vikunja`: `vikunja/vikunja:latest` on `http://localhost:3456`
- `mcp-adapter`: FastMCP service on `http://localhost:8000/mcp`
- `bridge-worker` (optional profile): pull-based task bridge worker

## Status

- Ready for day-to-day use.
- Reproducible via Docker Compose.
- End-to-end validated for Vikunja API and MCP flows.

## Project Documents

- [Project Definition](./PROJECT.md)
- [Execution Plan](./PLAN.md)
- [Contribution Guide](./CONTRIBUTING.md)
- [Code of Conduct](./CODE_OF_CONDUCT.md)
- [Open Source Respect Guidelines (EN)](./OPEN_SOURCE_OF_CONDUCT.md)
- [Open Source Respect Guidelines (DE)](./OPEN_SOURCE_OF_CONDUCT.de.md)
- [Open Source Respect - Public Short Version](./OPEN_SOURCE_OF_CONDUCT_PUBLIC.md)
- [Skills Overview](./skills/README.md)
- [Main Deploy Skill](./skills/mcp-vikunja-deploy/SKILL.md)
- [Task 31 Bridge Plan](./docs/todo/task-31-vikunja-codex-session-bridge-plan.md)
- [Task 33 Runtime Decision Matrix](./docs/todo/task-33-runtime-target-decision-matrix.md)
- [Task 34 Minimal Infrastructure Baseline](./docs/todo/task-34-minimal-infrastructure-baseline.md)
- [Task 49 Phase A Local Baseline Runbook](./docs/todo/task-49-phase-a-local-baseline-runbook.md)
- [Task 50 Dedicated Codex Box Readiness Checklist](./docs/todo/task-50-dedicated-codex-box-readiness-checklist.md)
- [Task 51 VPS Deployment Playbook](./docs/todo/task-51-vps-deployment-playbook.md)
- [Task 52 NanoPi Private-Host Profile](./docs/todo/task-52-nanopi-private-host-profile.md)
- [Task 35 Binding and Ownership Model](./docs/todo/task-35-binding-ownership-model.md)
- [Task 36 MCP Reconnect Runbook](./docs/todo/task-36-mcp-reconnect-runbook.md)
- [Task 37 Session Bootstrap Checklist](./docs/todo/task-37-session-bootstrap-checklist.md)
- [Task 38 Task Command Flow](./docs/todo/task-38-task-command-flow.md)
- [Task 39 Comment Write Verification](./docs/todo/task-39-comment-write-verification.md)
- [Task 40 Task Lifecycle SOP](./docs/todo/task-40-task-lifecycle-sop.md)
- [Task 41 Idempotency and Safety Guardrails](./docs/todo/task-41-idempotency-safety-guardrails.md)
- [Task 42 Naming and Dedup Convention](./docs/todo/task-42-naming-and-dedup-convention.md)
- [Task 43 Safe Execution Policy](./docs/todo/task-43-safe-execution-policy.md)
- [Task 44 Operational Hardening and Recovery](./docs/todo/task-44-operational-hardening-recovery.md)
- [Task 45 Offline/Sleep Behavior Matrix](./docs/todo/task-45-offline-sleep-behavior-matrix.md)
- [Task 46 Monitoring and Alerting Baseline](./docs/todo/task-46-monitoring-alerting-baseline.md)
- [Task 47 Backup/Restore Drill Protocol](./docs/todo/task-47-backup-restore-drill-protocol.md)
- [Task 64 Markdown Comment Rendering](./docs/todo/task-64-markdown-comment-rendering.md)

## Features

### Implemented MCP tools

- `health`
- `list_projects`
- `create_project`
- `list_tasks`
- `create_task`
- `list_task_comments`
- `add_task_comment`
- `move_task`

### Design principles

- minimal dependencies
- deterministic behavior
- environment-based configuration
- no hardcoded credentials
- fully self-hostable

### Bridge worker MVP

Implemented as `python -m vikunja_mcp.bridge_worker`:

- pull-based polling loop
- ownership gate via labels (`mode/ai`, `mode/human`)
- optional ownership fallback via `BRIDGE_MODE_FILE` (`mode=ai|human`) when labels are missing
- optional task-selection filters:
  - `BRIDGE_SKIP_DONE=true|false`
  - `BRIDGE_ALLOWED_BUCKET_IDS=40,41`
  - `BRIDGE_REQUIRED_LABELS=size/s,size/m`
- optional multi-project polling via `BRIDGE_PROJECT_IDS=13,14`
- `[bind]...[/bind]` parsing (`node`, `session`, `workdir`)
- idempotent state watermark (`last_processed_comment_id`)
- bridge comment prefix protection (`[bridge]`)
- inbox work order file output: `<workdir>/inbox/task-<id>-comment-<id>.md`
- level-2 action policy with explicit confirmations:
  - `confirm: <action-id>`
  - `action: move bucket=<id> id=<action-id>`
  - `action: reopen bucket=<id> id=<action-id>`
  - optional confirmer allowlist via `BRIDGE_CONFIRM_ALLOWED_USERS`
- optional queue notification hook via `BRIDGE_NOTIFY_COMMAND`
- failed bridge comments are queued locally and retried (`BRIDGE_PENDING_COMMENTS_FILE`)
- failed poll cycles use exponential backoff (`BRIDGE_BACKOFF_MIN_SECONDS` / `BRIDGE_BACKOFF_MAX_SECONDS`)

## Prerequisites

- [Docker](https://www.docker.com)
- [Docker Compose](https://docs.docker.com/compose/)
- [Python](https://www.python.org/) 3.12+

## Quick Start

One command:

```bash
make onboard
```

`make onboard` runs:

- `make up`
- `make bootstrap`
- `make full-check`

## Manual Setup

1. Create `.env`:

```bash
cp .env.example .env
```

2. Start services:

```bash
make up
```

3. Create/verify admin user and API token:

```bash
make bootstrap
```

4. Run runtime checks:

```bash
make full-check
```

## Codex Integration

Register the MCP server in Codex:

```bash
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
codex mcp list
```

Note: `/mcp` is a Streamable HTTP MCP endpoint. Browser GET requests are not a valid MCP protocol test.

### MCP Reconnect (Hard Refresh)

If another Codex session still sees old tools, run this refresh sequence:

1. Update project state:

```bash
git pull origin main
```

2. Rebuild/restart the MCP adapter with the latest code:

```bash
docker compose up -d --build mcp-adapter
```

3. Re-register MCP in Codex:

```bash
codex mcp remove vikunja
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp get vikunja
```

## Operations

Common commands:

- `make help`
- `make ps`
- `make logs`
- `make down`
- `make clean`

Validation:

- `make verify` (Vikunja workflow validation)
- `make test-mcp` (MCP protocol + tool-call validation)
- `make test-bridge` (bridge parser/unit checks)
- `make test-api` (Vikunja API helper unit checks)
- `make bridge-once` (one bridge poll cycle, optional `BRIDGE_DRY_RUN=1`)
- `make monitor` (quick health checks: compose + API + MCP port)
- `make monitor-full` (monitor + verify + test-mcp smoke)
- `make watchdog-once` (single watchdog cycle + status snapshot)
- `make watchdog-loop` (continuous monitoring loop)
- `make backup-drill` (SQL backup + restore drill in temporary DB)
- `make full-check` (verify + test-mcp)
- `make publish-check` (static publish checks)

Monitoring + backup drill examples:

```bash
# Quick status (non-destructive)
make monitor

# Full smoke check
make monitor-full

# One watchdog cycle (writes /tmp/mcp-vikunja-watchdog/status.json)
make watchdog-once

# Continuous watchdog loop (Ctrl+C to stop)
make watchdog-loop

# Alert integration (example: ntfy) when any check fails
python3 scripts/monitor_stack.py --alert-command 'ntfy publish ops-alerts "mcp-vikunja FAIL: {summary}"'

# Watchdog with failure notification callback
python3 scripts/watchdog_loop.py --notify-command 'ntfy publish ops-alerts "watchdog FAIL: {summary}"'

# Weekly backup/restore drill with JSON evidence
python3 scripts/backup_restore_drill.py --report-file /tmp/mcp-vikunja-backups/latest-drill.json
```

Bridge worker run options:

```bash
# One-shot local cycle
BRIDGE_PROJECT_ID=13 BRIDGE_DRY_RUN=1 make bridge-once

# One-shot cycle for multiple projects
BRIDGE_PROJECT_IDS=13,14 BRIDGE_DRY_RUN=1 make bridge-once

# Continuous bridge worker via compose profile
docker compose --profile bridge up -d --build bridge-worker

# Restrict processing to active execution buckets + size labels
BRIDGE_PROJECT_ID=13 BRIDGE_ALLOWED_BUCKET_IDS=40,41 BRIDGE_REQUIRED_LABELS=size/s,size/m make bridge-once

# Continuous worker retry tuning + pending-comment spool path
BRIDGE_BACKOFF_MIN_SECONDS=5 BRIDGE_BACKOFF_MAX_SECONDS=120 BRIDGE_PENDING_COMMENTS_FILE=/var/lib/vikunja-bridge/pending-comments.jsonl docker compose --profile bridge up -d --build bridge-worker

# Direct python invocation (export .env first)
set -a; source .env; set +a
PYTHONPATH=./mcp_adapter python3 -m vikunja_mcp.bridge_worker --project-id 13 --once

# Direct python invocation for multiple projects
PYTHONPATH=./mcp_adapter python3 -m vikunja_mcp.bridge_worker --project-ids 13,14 --once
```

Queue notification example (host-side worker):

```bash
export BRIDGE_NOTIFY_COMMAND='tmux display-message -t {session} "bridge task={task_id} cmd={command} file={file}"'
export BRIDGE_NOTIFY_TIMEOUT_SECONDS=8
BRIDGE_PROJECT_ID=13 make bridge-once
```

Mode fallback file example:

```bash
cat > /tmp/bridge-mode.env <<'EOF'
mode=ai
EOF
export BRIDGE_MODE_FILE=/tmp/bridge-mode.env
BRIDGE_PROJECT_ID=13 make bridge-once
```

Note:
- `BRIDGE_NOTIFY_COMMAND` runs as a shell command in the worker runtime context.
- If worker runs in Docker, host `tmux` is usually not reachable from container runtime.
- `BRIDGE_MODE_FILE` is project-wide fallback; keep it on `mode=human` unless you explicitly want AI mode without labels.

Action command example:

```text
confirm: move-to-doing-001
action: move bucket=40 id=move-to-doing-001

confirm: reopen-task-001
action: reopen bucket=39 id=reopen-task-001
```

The action is executed only if:
- task resolves to `ai` mode (`mode/ai` label or optional `BRIDGE_MODE_FILE` fallback)
- valid `[bind]` block exists
- confirmation token exists, is unexpired, and unused
- optional confirmer allowlist check passes (`BRIDGE_CONFIRM_ALLOWED_USERS`)

## Environment Variables

Main variables in `.env.example`:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `VIKUNJA_JWT_SECRET`
- `VIKUNJA_PUBLIC_URL`
- `VIKUNJA_ENABLE_REGISTRATION`
- `VIKUNJA_INTERNAL_URL`
- `VIKUNJA_ADMIN_USERNAME`
- `VIKUNJA_ADMIN_EMAIL`
- `VIKUNJA_ADMIN_PASSWORD`
- `VIKUNJA_API_TOKEN_TITLE`
- `VIKUNJA_API_TOKEN`
- `MCP_URL` (optional, default `http://localhost:8000/mcp`)
- `BRIDGE_PROJECT_ID`
- `BRIDGE_PROJECT_IDS` (optional comma-separated project IDs; polled together with `BRIDGE_PROJECT_ID` if both are set)
- `BRIDGE_POLL_INTERVAL`
- `BRIDGE_STATE_FILE`
- `BRIDGE_CONFIRM_TTL_HOURS`
- `BRIDGE_CONFIRM_ALLOWED_USERS` (comma-separated usernames, optional)
- `BRIDGE_NOTIFY_COMMAND` (optional shell command for queue notifications)
- `BRIDGE_NOTIFY_TIMEOUT_SECONDS`
- `BRIDGE_MODE_FILE` (optional fallback mode file path)
- `BRIDGE_SKIP_DONE` (default `true`, skip tasks where `done=true`)
- `BRIDGE_ALLOWED_BUCKET_IDS` (optional comma-separated bucket IDs to include)
- `BRIDGE_REQUIRED_LABELS` (optional comma-separated labels, at least one must match)
- `BRIDGE_PENDING_COMMENTS_FILE` (optional JSONL spool for bridge comments that could not be posted)
- `BRIDGE_PENDING_COMMENTS_MAX` (max retained queued bridge comments, default `500`)
- `BRIDGE_BACKOFF_MIN_SECONDS` (retry backoff min delay for failed poll cycles)
- `BRIDGE_BACKOFF_MAX_SECONDS` (retry backoff max delay for failed poll cycles)

## Security

- Keep token/secrets in `.env` only.
- Never commit `.env` or runtime tokens.
- Registration is disabled by default (`VIKUNJA_ENABLE_REGISTRATION=false`).
- Use a reverse proxy and HTTPS for public exposure.

## GitHub Publishing

Before publishing:

```bash
make publish-check
```

Included in this repo:

- CI workflow: `.github/workflows/ci.yml`
- License: `LICENSE` (MIT)
- Contribution guide: `CONTRIBUTING.md`
- Secret protection: `.env` is ignored via `.gitignore`

## Reusable Codex Skill

This repo includes a reusable skill for fast setup on other Codex instances:

- `skills/mcp-vikunja-deploy`

Skills info is available in `skills/README.md`.

Install locally:

```bash
mkdir -p "$HOME/.codex/skills"
cp -r skills/mcp-vikunja-deploy "$HOME/.codex/skills/"
```

Invoke by skill name: `mcp-vikunja-deploy`.

## Long-Term Vision

`mcp-vikunja` is a foundation for AI-native project orchestration:

- autonomous task planning
- iterative execution loops
- agent self-reflection on board state
- structured AI-assisted engineering workflows
