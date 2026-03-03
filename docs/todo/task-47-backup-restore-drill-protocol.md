# Task 47 - Backup/Restore Drill Protocol

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/47`

Goal:
- Standardize recurring backup and restore drills.

## Backup Procedure (Baseline)

1. Create SQL dump from `db` container.
2. Store backup with UTC timestamp filename.
3. Record file size and checksum.

Example filename:
- `/tmp/mcp-vikunja-backups/vikunja_<timestamp>.sql`

## Restore Drill Procedure

1. Create temporary test database.
2. Restore latest backup into test DB.
3. Validate core counts:
- tables
- projects
- tasks
- task comments
4. Drop test DB after verification.

## Drill Schedule

- Minimum: weekly in active development phase.
- Mandatory: before major environment migration (PC -> Codex box -> VPS/NanoPi).

## Evidence Requirements

For each drill record:
- backup filename
- restore target DB name
- verification query results
- success/failure outcome
- timestamp

## Acceptance Criteria

- Drill can be executed without touching production DB.
- Verification output is captured and traceable.

## Implementation Note (2026-03-03)

- Added `scripts/backup_restore_drill.py`:
  - creates SQL dump from `db` container
  - computes SHA256 and file size
  - restores into temporary drill DB
  - validates counts for `projects`, `tasks`, `task_comments`
  - drops temporary DB by default (optional keep flag)
  - supports JSON evidence output via `--report-file`
- Added Make target:
  - `make backup-drill`
