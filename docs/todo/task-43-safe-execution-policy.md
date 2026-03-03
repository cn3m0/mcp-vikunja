# Task 43 - Safe Execution Policy

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/43`

Goal:
- Reduce destructive or irreversible actions from automated flows.

## Policy Levels

Level 1 (safe by default, no extra confirmation):
- Read operations
- Creating tasks/comments
- Moving task within normal lifecycle (`To-Do -> Doing -> Done`)

Level 2 (requires explicit confirmation token in task comment):
- Bulk task moves
- Re-opening completed milestones
- Cross-project task operations

Level 3 (manual only, no autonomous execution):
- Delete operations
- Token/secret rotation actions
- Destructive infra changes

## Confirmation Protocol

For Level 2 operations, require comment pattern:
- `confirm: <action-id>`

Rules:
- Confirmation must come from human user.
- Confirmation expires after 24 hours.
- One confirmation can be used once.

## Execution Preconditions

Before any write operation:
1. Ownership mode must be `mode/ai`.
2. Valid binding must exist.
3. Dedup check must pass.
4. Required confirmation (if Level 2) must be present.

If any precondition fails:
- Post `blocked: <reason>`
- Do not execute action.

## Audit Requirements

Each executed write action should log:
- action type
- task id
- actor/source (`human` or `bridge`)
- timestamp
- outcome (`ok`, `blocked`, `error`)

## Acceptance Criteria

- No Level 3 action runs automatically.
- Level 2 actions always require explicit valid confirmation.
- All blocked cases produce deterministic ticket feedback.
