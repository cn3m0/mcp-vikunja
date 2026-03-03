# Task 42 - Naming and Dedup Convention

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/42`

Goal:
- Prevent duplicate work orders, duplicate comments, and ambiguous task naming.

## Naming Convention

Task title format:
- `M<phase>.<step>: <short action>`
- Example: `M4.1: Define naming and dedup convention`

Comment status format:
- `ack: started`
- `update: <short progress>`
- `blocked: <reason>`
- `done: <result>`

Bridge-authored comments:
- Prefix mandatory: `[bridge]`
- Example: `[bridge] ack: started (session=codex-nanopi-r1)`

## Dedup Keys

Primary idempotency key:
- `task_id + comment_id`

Secondary safety key (optional):
- `task_id + sha256(normalized_comment_body)`

Processing rule:
- If primary key already processed, skip.
- If primary missing but secondary matches very recent event window, skip and log duplicate.

## Watermark Store

Per task state:
- `last_processed_comment_id`
- `last_processed_at`
- `last_command_hash`
- `binding_hash`

Storage requirements:
- Persistent across restarts.
- Atomic update on successful processing.

## Duplicate Handling

When duplicate detected:
1. Do not execute work again.
2. Do not post duplicate status comments.
3. Optionally post one informational dedup comment only if needed for audit.

## Acceptance Criteria

- Same comment cannot trigger action twice.
- Restart/retry cycles do not create duplicate outputs.
- Naming pattern remains consistent across all new tasks/comments.
