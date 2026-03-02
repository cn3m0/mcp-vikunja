# Task 35 - MCP Binding and Ownership Model

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/35`

Goal:
- Ensure every Codex session can deterministically attach to the right execution context and avoid command collisions.

## Binding Model

Binding source:
- Task comment block (latest valid block wins):

```text
[bind]
node=np1
session=codex-nanopi-r1
workdir=/srv/work/nanopi-r1
[/bind]
```

Validation rules:
- Required keys: `node`, `session`, `workdir`
- Ignore malformed blocks.
- If no valid block exists, system returns `blocked` status for execution commands.

Resolution rules:
- One active binding per task.
- Last valid binding by comment timestamp is authoritative.

## Ownership Model

Primary control:
- Task label based mode:
  - `mode/ai`
  - `mode/human`

Behavior:
- `mode/ai`: bridge/agent may execute command flow.
- `mode/human`: bridge/agent must not execute; only observe/comment.

Fallback:
- If mode label is absent, default to safe behavior (`mode/human`).

## Safety Rules

- Ignore machine-authored comments with prefix `[bridge]`.
- Process each comment ID exactly once.
- Store per-task watermark: `last_processed_comment_id`.
- Reject execution if binding exists but `workdir` path fails validation.

## Operational Contract

1. Human updates binding/mode in task.
2. Bridge validates ownership + binding.
3. If valid and in `mode/ai`, command is accepted and processed.
4. Bridge posts deterministic status comment (`ack/update/blocked/done`).

## Acceptance Criteria

- Binding resolution is deterministic.
- `mode/human` reliably prevents execution.
- Duplicate poll cycles do not trigger duplicate work.
