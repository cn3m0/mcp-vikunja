# Command Matrix

## Setup

- `make up`: Start all containers and build images.
- `make bootstrap`: Create/verify admin user, generate API token, restart adapter.

## Validation

- `make verify`: Verify Vikunja API and task move flow.
- `make test-mcp`: Verify Streamable HTTP MCP protocol and tool calls.
- `make full-check`: Run `verify` + `test-mcp`.
- `make publish-check`: Run static checks for GitHub publishing.

## Operations

- `make ps`: Show current container status.
- `make logs`: Follow service logs.
- `make down`: Stop containers.
- `make clean`: Stop containers and delete volumes.

## Codex MCP Registration

- `codex mcp add vikunja --url http://localhost:8000/mcp`
- `codex mcp get vikunja`
- `codex mcp list`

