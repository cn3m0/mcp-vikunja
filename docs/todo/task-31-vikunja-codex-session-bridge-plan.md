# Task 31 - Vikunja <-> Codex Session Bridge (Plan)

## Context

Source task: `http://127.0.0.1:3456/tasks/31`

Goal: Enable reliable collaboration between Vikunja tasks and an active Codex session so work can continue seamlessly in:

- Mode A: Remote PM (via Vikunja)
- Mode B: Deep Work (via PC/tmux/Codex session)

This document is planning/spec only.

## Scope

In scope:

- Pull-based bridge worker (primary transport)
- Optional webhook hooks (deferred)
- Task/session binding via standardized task comment block
- Standardized command/status comments
- Ownership mode switching (`human` / `ai`)
- Idempotent processing and loop prevention
- Security baseline and operational guardrails

Out of scope (MVP):

- Full real-time bi-directional streaming
- Complex scheduler/orchestrator logic
- Multi-agent conflict resolution beyond ownership flag

## High-Level Architecture

```text
Vikunja Task/Comments
        |
        v
Bridge Worker (poller + parser + router)
        |
        +--> Inbox file writer (/srv/work/<project>/inbox/task-<id>.md)
        |
        +--> Codex/tmux notifier (optional)
        |
        +--> Vikunja status comments (ack/update/blocked/done)
```

## Core Design Decisions

1. Pull first:
   - Poll Vikunja at a fixed interval (for stability and easier operations).
2. Webhooks optional:
   - Add later as acceleration path, not as single source of truth.
3. Task-bound session mapping:
   - Use explicit `[bind]...[/bind]` block in task comments.
4. Ownership gate:
   - Process execution commands only when task is in `mode/ai`.

## Data Contracts

### 1. Binding block (comment content)

```text
[bind]
node=np1
session=codex-nanopi-r1
workdir=/srv/work/nanopi-r1
[/bind]
```

Rules:

- Last valid binding block wins.
- Binding is task-local.
- Missing keys fail validation and return `blocked` comment.

### 2. Command/Status comment protocol

Incoming commands (human -> bridge/agent):

- `ack: started`
- `update: <text>`
- `blocked: <reason>`
- `done: <summary>`

Bridge-authored comments (machine prefix to avoid loops):

- Prefix: `[bridge]`
- Example: `[bridge] ack: started (session=codex-nanopi-r1)`

### 3. Ownership mode

Preferred MVP source:

- Vikunja labels:
  - `mode/ai`
  - `mode/human`

Optional secondary source:

- Project file flag:
  - `mode=human|ai`

Resolution rule:

- If label exists, label is authoritative.
- Fallback to file only if label missing.

### 4. Task size classes

- `size/S`
- `size/M`
- `size/L`

Usage:

- `S`: can be fully handled in remote flow.
- `M`: remote + targeted deep-work steps.
- `L`: prefer deep-work mode.

## Worker Behavior (MVP)

Polling cycle:

1. Fetch candidate tasks (project filter + active buckets).
2. For each task:
   - read ownership mode
   - skip if `mode/human`
   - fetch latest comments
   - detect new events since last processed comment ID
3. Parse new comments:
   - binding updates
   - command comments
4. Write normalized work order to inbox file.
5. Post bridge status comment in Vikunja.
6. Persist watermark (`last_processed_comment_id`) per task.

## Idempotency and Loop Prevention

Must-have:

- Persisted state store:
  - key: `task_id`
  - value: `last_processed_comment_id`, `binding_hash`, `last_command_hash`
- Ignore bridge-authored comments by prefix `[bridge]`.
- Ignore duplicate commands by `(task_id + comment_id)` and optional content hash.

## Inbox Transport

Path:

`/srv/work/<project>/inbox/task-<id>.md`

Suggested payload:

- task metadata
- binding data
- normalized command
- source comment ID/timestamp

Write policy:

- atomic write (`.tmp` -> rename)
- include monotonic sequence or comment ID in filename/content for traceability

## Security Requirements

- Dedicated Vikunja token with least privileges.
- No secrets in task comments.
- No secret material in generated inbox files.
- Authenticated endpoints only (if webhook endpoint is enabled later).
- Structured logs without credential leaks.

## Offline / Failure Behavior

If Vikunja unavailable:

- keep local queue of pending bridge outputs
- retry with backoff
- do not duplicate previously acknowledged commands

If session binding invalid/missing:

- post `[bridge] blocked: missing/invalid binding`
- do not execute task command

## Rollout Plan

### Phase 1 (MVP)

- Pull worker
- Binding parser
- Ownership label gate
- Inbox writer
- `ack/update/blocked/done` comments
- Idempotency via last comment ID

### Phase 2

- Optional tmux notifications
- Better task filtering by size labels
- Enhanced error taxonomy

### Phase 3

- Optional webhooks
- Observability metrics and dashboards
- Multi-node routing improvements

## Acceptance Criteria

- Bridge detects new command comments and creates exactly one inbox work order.
- Bridge writes status back to Vikunja via standardized `[bridge]` comments.
- Duplicate polling cycles do not create duplicate work orders.
- `mode/human` tasks are never executed by bridge logic.
- Invalid binding leads to deterministic `blocked` feedback.

## Open Questions

- Exact project selection strategy (single project vs multi-project list)?
- Should ownership mode allow task-level override comments?
- Required SLA for poll interval (e.g. 5s, 15s, 30s)?
- Should `size/L` auto-force `mode/human` unless explicitly overridden?

