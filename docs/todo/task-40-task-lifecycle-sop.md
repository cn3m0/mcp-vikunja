# Task 40 - Task Lifecycle SOP (To-Do -> Doing -> Done)

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/40`

Goal:
- Define a repeatable lifecycle for operational work in Vikunja.

## Bucket Model

- `To-Do`: planned, not yet active
- `Doing`: actively executed
- `Done`: completed and documented

## Transition Rules

To-Do -> Doing:
- Move when execution starts.
- Add `ack: started` comment with scope.

Doing -> Done:
- Only after deliverable exists and is verifiable.
- Add `done:` comment with evidence links (docs, checks, command results).
- Set `start_date` and `end_date` on the task for timeline/Gantt tracking.

Doing -> To-Do:
- Allowed if blocked by dependency or decision pending.
- Add `blocked:` comment with next trigger condition.

## Status Comment Standard

Use one of:
- `ack: started`
- `update: <progress>`
- `blocked: <reason>`
- `done: <summary>`

## Definition of Done

A task is done when:
1. Required artifact exists (doc/code/config).
2. Relevant checks were executed.
3. Result is documented in the task comment.
4. Task moved to `Done`.
5. `start_date` and `end_date` are set.

## Operational Guardrails

- Do not close task without evidence.
- Keep milestone tasks aligned with subtask states.
- Update parent task with milestone-level summary.
