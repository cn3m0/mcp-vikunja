# PLAN.md

## Document Status

- Created on: 2026-02-27
- Last updated: 2026-02-27
- Source: `PROJECT.md`
- Purpose: capture baseline and provide an implementation plan with execution status

## 0. Baseline (from PROJECT.md)

- Goal: self-hosted Kanban with AI integration (Codex), delivered as `mcp-vikunja`.
- Target system:
  - Vikunja (Kanban)
  - PostgreSQL (persistence)
  - MCP server (Model Context Protocol adapter)
  - local Codex integration
- Operating model: local Docker Compose.
- Target Codex capabilities:
  - read board state
  - create tasks
  - move tasks
  - evaluate status
  - generate summaries
- Initial status:
  - requirements defined
  - implementation planned

## 1. Goal and Scope

### In scope

- Docker Compose stack with `postgres:16-alpine` and `vikunja/vikunja:latest`
- `.env`-based configuration (DB, JWT secret, public URL, token)
- initialization flow with admin user and API token
- local MCP adapter with defined tool contracts
- end-to-end verification of core use cases

### Out of scope (initially)

- Nginx reverse proxy
- HTTPS via Let's Encrypt
- OAuth integration
- webhook automation
- task digest generator as separate product feature

## 2. Architecture and Components

### Components

- PostgreSQL:
  - persistent storage for Vikunja data
  - healthcheck required
- Vikunja backend/API:
  - API for UI and MCP adapter
  - Bearer token authentication
- Vikunja web UI:
  - operational interface and manual validation
- MCP adapter service:
  - wraps Vikunja API as MCP tools
  - minimal, traceable logging
- Codex:
  - consumes MCP tools for read/write operations and summaries

### Network and Reachability

- all containers share one Docker network
- UI/API reachable at `http://localhost:3456`
- MCP adapter reaches Vikunja via Docker internal network

## 3. Implementation Phases and Deliverables

### Phase 1: Infrastructure

- Tasks:
  - define Docker Compose
  - connect PostgreSQL and Vikunja
  - configure persistent volumes
  - set restart policies
  - enforce DB healthcheck
- Deliverables:
  - `docker-compose.yml`
  - `.env.example` (or equivalent documented env variables)
- Acceptance criteria:
  - `docker compose up` starts without configuration errors
  - PostgreSQL reports healthy
  - Vikunja connects to DB successfully

### Phase 2: Initialization

- Tasks:
  - start services and verify port `3456`
  - create admin user
  - generate API token
  - document token handling via env only
- Deliverables:
  - initialization instructions/scripts in repo
  - defined env variable for token
- Acceptance criteria:
  - admin login works
  - token-authenticated API request works

### Phase 3: MCP Adapter

- Tasks:
  - create local MCP service
  - implement tools: `health`, `list_projects`, `create_project`, `list_tasks`, `create_task`, `list_task_comments`, `add_task_comment`, `move_task`
  - implement robust error handling
  - add minimal structured logging
- Deliverables:
  - MCP service implementation
  - tool definitions and run instructions
- Acceptance criteria:
  - all tools respond with consistent structure
  - error paths provide clear error codes/messages

### Phase 4: Verification

- Tasks:
  - run automated/scripted end-to-end checks
  - document verification results
- Deliverables:
  - verification script(s) or reproducible command set
  - test protocol/log
- Acceptance criteria:
  - API reachable
  - project creation works
  - task creation works
  - task move works

## 4. Public Interfaces (MCP Tools/API)

### Common Response Contract

- Success:
  - `success: true`
  - `data: object`
- Error:
  - `success: false`
  - `error.code: string`
  - `error.message: string`
  - `error.details: object|null`

### Tool Contracts

- `health`
  - Input: none
  - Output: API reachability and service status
- `list_projects`
  - Input: optional `page`, `per_page`
  - Output: list with `id`, `title`, `description`
- `create_project`
  - Input: `title` (required), `description` (optional)
  - Output: created project with `id`
- `list_tasks`
  - Input: `project_id` (required), optional `view_id`, `page`, `per_page`
  - Output: list with `id`, `title`, `bucket/status`, `project_id`
- `create_task`
  - Input: `project_id` (required), `title` (required), `description` (optional), `bucket_id` (optional)
  - Output: created task with `id`
- `list_task_comments`
  - Input: `task_id` (required), optional `order_by` (`asc`/`desc`)
  - Output: list with comment `id`, `comment`, `author`, timestamps
- `add_task_comment`
  - Input: `task_id` (required), `comment` (required)
  - Output: created task comment with `id`
- `move_task`
  - Input: `task_id` (required), `target_bucket_id` (required), optional `project_id`, `view_id`
  - Output: updated task bucket assignment

## 5. Verification and Test Cases

### Core scenarios

- API reachability:
  - Expectation: `health` returns `success: true`
- Project creation:
  - Action: `create_project` with title `CN3M0 PoC`
  - Expectation: project ID returned
- Task creation:
  - Action: `create_task` in project `CN3M0 PoC`
  - Expectation: task ID returned
- Task move:
  - Action: `move_task` to another Kanban bucket
  - Expectation: bucket/status updated
- Task comment:
  - Action: `add_task_comment` on an existing task
  - Expectation: comment ID returned and comment is visible in task comments
- Summary:
  - Action: read board data via MCP and generate board summary
  - Expectation: consistent, traceable summary output

### Negative tests

- Invalid token:
  - Expectation: authentication error with clear message
- Missing required fields:
  - Expectation: validation error with field-level detail
- Non-existing IDs:
  - Expectation: 404-like mapping in tool error object

## 6. Security and Operational Requirements

- never hardcode API token in source code
- keep secrets in environment variables
- disable registration in production-like mode
- no public exposure without reverse proxy
- ensure reproducibility via `docker compose up`

## 7. Risks, Assumptions, Open Points

### Assumptions

- Docker and Docker Compose are available locally
- port `3456` is available
- using `vikunja/vikunja:latest` is acceptable for this deployment

### Defaults

- documentation language: English
- MCP implementation language: Python (implemented)
- local-first operation model

### Risks

- potential breaking changes from `vikunja/vikunja:latest`
- inconsistent error mapping without strict response contracts
- accidental token leakage via careless logging

## 8. Definition of Done

- [x] `docker compose up` starts all core services
- [x] admin user is created and usable
- [x] API token is generated and configured via env only
- [x] project `CN3M0 PoC` can be created
- [x] task can be created via MCP
- [x] task comment can be added via MCP
- [x] task can be moved between Kanban columns via MCP
- [x] Codex can summarize board state
- [x] reproducible verification is documented

## 9. Baseline-to-Current Tracking

| Area | Baseline (2026-02-27) | Current Status | Evidence |
|---|---|---|---|
| Infrastructure (Compose, DB, Vikunja) | Planned | DONE | docker compose + healthchecks active |
| Initialization (admin, token) | Planned | DONE | `scripts/bootstrap_admin_and_token.py` |
| MCP adapter (tools) | Planned | DONE | `mcp_adapter/vikunja_mcp/server.py` |
| Verification (E2E) | Planned | DONE | `scripts/verify_poc.py` successful |
| Security/secrets | Requirements defined | DONE | token only in `.env`, `.gitignore` active |
