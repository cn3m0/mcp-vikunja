# Task 46 - Monitoring and Alerting Baseline

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/46`

Goal:
- Define a minimum monitoring baseline for service health and quick issue detection.

## Minimum Signals

Health checks:
- `db` healthy
- `vikunja` healthy
- `mcp-adapter` reachable (`/mcp` protocol checks via test script)

Runtime checks:
- `make verify` result
- `make test-mcp` result

Operational signals:
- container restart count
- recent error logs from `mcp-adapter` and `vikunja`

## Alert Conditions

Trigger alert when:
1. `vikunja` or `mcp-adapter` unavailable for > 2 minutes.
2. MCP tool calls fail repeatedly.
3. Unexpected repeated container restarts.

## Alert Channels

Supported baseline channels:
- local notification (`ntfy`)
- email
- chat webhook (Slack/Matrix/Discord)

Recommended minimum:
- one human-visible async channel (email or ntfy).

## Check Frequency

- Health poll: every 1-2 minutes.
- Full verify/mcp smoke: daily or after deployment changes.

## Acceptance Criteria

- Failures are detected without manual dashboard checking.
- Recovery actions can be started within minutes.
