# Task 41 - Idempotency and Safety Guardrails

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/41`

Goal:
- Define a coherent guardrail set to prevent duplicate execution and unsafe automation.

## Scope

This milestone combines:
- Naming and dedup convention (`task-42`)
- Safe execution policy (`task-43`)

## Guardrail Set

1. Deterministic naming and status vocabulary.
2. Mandatory dedup keys (`task_id + comment_id`).
3. Persistent watermark per task.
4. Ownership gate (`mode/ai` required for execution).
5. Confirmation gate for medium-risk actions.
6. Strict block on destructive autonomous actions.

## Implementation Sequence

1. Apply naming convention to new tasks/comments.
2. Enforce dedup check before each execution step.
3. Enforce policy levels for write actions.
4. Emit structured `blocked` feedback when conditions fail.

## Artifacts

- `docs/todo/task-42-naming-and-dedup-convention.md`
- `docs/todo/task-43-safe-execution-policy.md`

## Acceptance Criteria

- Duplicate execution is prevented across restarts/retries.
- Unsafe actions are gated or blocked deterministically.
- Operators can audit why an action was executed or blocked.
