#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

from session_bridge_loop import (  # type: ignore[import-not-found]
    SessionBridgeState,
    normalize_tmux_target,
    parse_reply_line,
    parse_work_order,
)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r} actual={actual!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="session-bridge-test-") as tmpdir:
        root = Path(tmpdir)
        file_path = root / "task-123-comment-99.md"
        file_path.write_text(
            (
                "# Work Order\n\n"
                "- generated_at: 2026-03-03T14:00:00+00:00\n"
                "- task_id: 123\n"
                "- task_title: Demo\n"
                "- project_id: 13\n"
                "- comment_id: 99\n"
                "- command: update\n"
                "- node: np1\n"
                "- session: codex-main\n"
                "- workdir: /srv/work/demo\n\n"
                "## Body\n\n"
                "please implement x\n"
            ),
            encoding="utf-8",
        )
        work_order = parse_work_order(file_path)
        assert_equal(work_order is not None, True, "work order should parse")
        assert_equal(work_order.task_id if work_order else None, 123, "task_id parse failed")
        assert_equal(work_order.comment_id if work_order else None, 99, "comment_id parse failed")
        assert_equal(work_order.command if work_order else None, "update", "command parse failed")
        assert_equal(work_order.session if work_order else None, "codex-main", "session parse failed")
        assert_equal(work_order.body if work_order else None, "please implement x", "body parse failed")

        assert_equal(normalize_tmux_target("codex-main", ""), "codex-main:0.0", "session target normalize failed")
        assert_equal(
            normalize_tmux_target("codex-main:1.0", ""),
            "codex-main:1.0",
            "explicit pane target normalize failed",
        )
        assert_equal(normalize_tmux_target("", "fallback:0.0"), "fallback:0.0", "fallback target failed")
        assert_equal(normalize_tmux_target("", ""), None, "empty target should be none")

        assert_equal(
            parse_reply_line("BRIDGE_REPLY task=123 hello world", "BRIDGE_REPLY"),
            (123, "hello world"),
            "reply line parse failed",
        )
        assert_equal(
            parse_reply_line("  BRIDGE_REPLY task=123 hi", "BRIDGE_REPLY"),
            (123, "hi"),
            "reply line parse with leading spaces failed",
        )
        assert_equal(
            parse_reply_line("user@box$ BRIDGE_REPLY task=123 hi", "BRIDGE_REPLY"),
            None,
            "reply line should not match prompt-prefixed text",
        )
        assert_equal(parse_reply_line("BRIDGE_REPLY task=x hi", "BRIDGE_REPLY"), None, "invalid task id should fail")
        assert_equal(parse_reply_line("BRIDGE_REPLY task=42", "BRIDGE_REPLY"), None, "missing body should fail")

        state_path = root / "state.json"
        state = SessionBridgeState(state_path)
        state.mark_processed_work_order("123:99")
        state.mark_posted_reply_hash("h1")
        state.set_tmux_log_offset(42)
        state.save()

        loaded = SessionBridgeState(state_path)
        assert_equal("123:99" in loaded.processed_work_orders, True, "processed key state save/load failed")
        assert_equal("h1" in loaded.posted_reply_hashes, True, "reply hash state save/load failed")
        assert_equal(loaded.tmux_log_offset, 42, "log offset state save/load failed")

    print("[OK] session bridge checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
