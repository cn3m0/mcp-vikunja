# PROJECT.md

## mcp-vikunja

### Goal: Self-hosted Kanban with AI integration (Codex)

---

## 1. Project Objective

This project provides a locally hosted Kanban infrastructure consisting of:

- Vikunja (self-hosted Kanban system)
- PostgreSQL database
- MCP server (Model Context Protocol adapter)
- Codex API integration

Target capabilities for Codex:

- read board state
- create tasks
- move tasks
- evaluate status
- generate summaries

The entire environment runs locally via Docker Compose.

---

## 2. Architecture Overview

System components:

1. PostgreSQL (persistence)
2. Vikunja backend
3. Vikunja web UI
4. MCP adapter service (Node or Python)
5. Local Codex integration

Network model:

- all containers run in the same Docker network
- Vikunja is reachable at `http://localhost:3456`
- MCP accesses Vikunja through the internal Docker network

---

## 3. Requirements

### Functional

- Vikunja starts without errors
- admin user exists
- API token can be generated
- MCP can:
  - list projects
  - list tasks
  - create tasks
  - add task comments
  - move tasks

### Non-functional

- no cloud dependency required
- no unnecessary external dependencies
- reproducible startup via `docker compose up`
- configuration via `.env`

---

## 4. Implementation Tasks (for Codex)

### Phase 1 - Infrastructure

1. Create Docker Compose setup:
   - `postgres:16-alpine`
   - `vikunja/vikunja:latest`
2. Configure environment values:
   - DB credentials
   - JWT secret
   - public URL
3. Ensure:
   - DB healthcheck enabled
   - restart policies configured
   - persistent volumes configured

### Phase 2 - Initialization

1. Start containers
2. Verify:
   - port `3456` is reachable
3. Create admin user
4. Generate API token
5. Document token handling via environment variable

### Phase 3 - MCP Adapter

1. Create local MCP service
2. Implement tools:
   - `health`
   - `list_projects`
   - `create_project`
   - `list_tasks`
   - `create_task`
   - `list_task_comments`
   - `add_task_comment`
   - `move_task`
3. API auth via Bearer token
4. Implement robust error handling
5. Keep logging minimal but traceable

### Phase 4 - Verification

Codex should validate automatically:

- Is the Vikunja API reachable?
- Can a project be created?
- Can a task be created?
- Can a task be moved?

If all checks pass, the implementation is successful.

---

## 5. Security Requirements

- never hardcode API tokens
- use environment variables for secrets
- disable open registration in production-like operation
- do not expose services publicly without reverse proxy

---

## 6. Optional Extensions

- Nginx reverse proxy
- HTTPS via Let's Encrypt
- OAuth integration
- webhook-based AI automation
- task digest generator

---

## 7. Success Criteria

The project is considered successful when:

- `docker compose up` starts the full system
- a project named `CN3M0 PoC` can be created
- a task can be created via MCP
- a task comment can be added via MCP
- the task can be moved between Kanban columns
- Codex can summarize board state

---

## 8. Motivation

This setup is intended as:

- AI-augmented project management system
- experimental infrastructure for CN3M0
- foundation for autonomous task orchestration

---

## 9. Working Style

Codex may:

- create files
- update Compose configuration
- generate MCP code
- write test scripts
- analyze logs

Codex should:

- work deterministically
- avoid unnecessary dependencies
- keep the system minimal
