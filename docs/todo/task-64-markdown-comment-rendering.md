# Task 64 - Markdown Comment Rendering via Vikunja MCP

## Context

Date: 2026-03-03  
Related task: `http://127.0.0.1:3456/tasks/64`

Goal:
- Ensure comments posted through MCP preserve markdown line structure in Vikunja UI.

## Observed Issue

- Some MCP comment payloads arrived with literal escaped newlines (`\\n`) instead of real line breaks.
- Result in UI: markdown list/paragraph formatting looked compressed.

## Root Cause

- `add_task_comment` forwarded comment payload as-is.
- When upstream caller double-escaped newline sequences, Vikunja received one-line text containing `\\n`.

## Implemented Fix

- Added conservative normalization in `VikunjaClient.normalize_comment_text()`.
- Behavior:
  - Normalize real line endings (`\r\n`, `\r` -> `\n`).
  - Decode escaped newline sequences only for markdown-like patterns:
    - `\\n\\n`, `\\n- `, `\\n* `, `\\n# `, `\\n> `, `\\n````, `\\n1. ` ...
  - Avoid broad decoding to reduce false positives (for example paths like `C:\\new\\node`).

## Verification

- Unit tests:
  - `scripts/test_vikunja_api.py`
  - `scripts/test_bridge_worker.py`
- Runtime checks:
  - `make publish-check`
  - `python3 scripts/test_mcp_adapter.py`
- End-to-end MCP tool roundtrip:
  - `add_task_comment` with escaped markdown newlines
  - `list_task_comments` confirms real newlines stored

## Acceptance Status

- Implemented and verified on API/tool layer.
- Final UI rendering confirmation pending manual visual check in Vikunja web app.
