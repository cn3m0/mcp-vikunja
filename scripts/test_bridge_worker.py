#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER_PATH = ROOT / "mcp_adapter"
sys.path.insert(0, str(MCP_ADAPTER_PATH))

from vikunja_mcp.bridge_worker import (  # noqa: E402
    ActionCommand,
    BridgeWorker,
    comment_author_username,
    parse_action_command,
    parse_allowed_users,
    parse_bind_block,
    parse_command,
    parse_confirmation_token,
    render_notify_command,
    task_mode,
)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r} actual={actual!r}")


class FakeClient:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int]] = []
        self.updates: list[tuple[int, dict]] = []
        self.comments: list[tuple[int, str]] = []

    def move_task(self, task_id: int, target_bucket_id: int, *, project_id: int | None = None, view_id: int | None = None) -> dict:  # noqa: ARG002
        self.moves.append((task_id, target_bucket_id, int(project_id or 0)))
        return {"task_id": task_id, "bucket_id": target_bucket_id}

    def update_task(self, task_id: int, updates: dict) -> dict:
        self.updates.append((task_id, updates))
        return {"id": task_id, **updates}

    def add_task_comment(self, task_id: int, comment: str) -> dict:
        self.comments.append((task_id, comment))
        return {"id": len(self.comments), "task_id": task_id, "comment": comment}


def main() -> int:
    # parse_command
    assert_equal(parse_command("ack: started"), ("ack", "started"), "ack command parse failed")
    assert_equal(parse_command("update: value"), ("update", "value"), "update command parse failed")
    assert_equal(parse_command("not-a-command"), None, "invalid command should be ignored")

    # parse_action_command + confirmation
    action = parse_action_command("action: move bucket=40 id=mv-001")
    assert_equal(action.action if action else None, "move", "action parse failed (name)")
    assert_equal(action.bucket_id if action else None, 40, "action parse failed (bucket)")
    assert_equal(action.action_id if action else None, "mv-001", "action parse failed (id)")
    reopen = parse_action_command("action: reopen bucket=41 id=rp-001")
    assert_equal(reopen.action if reopen else None, "reopen", "reopen action parse failed")
    assert_equal(parse_action_command("action: invalid"), None, "invalid action should be ignored")

    token = parse_confirmation_token("confirm: mv-001")
    assert_equal(token, "mv-001", "confirm token parse failed")
    assert_equal(parse_confirmation_token("confirm "), None, "invalid confirm token should be ignored")

    # parse_bind_block
    bind = parse_bind_block(
        """
        [bind]
        node=np1
        session=codex-nanopi-r1
        workdir=/srv/work/nanopi-r1
        [/bind]
        """.strip()
    )
    assert_equal(
        bind,
        {"node": "np1", "session": "codex-nanopi-r1", "workdir": "/srv/work/nanopi-r1"},
        "bind block parse failed",
    )

    bad_bind = parse_bind_block("[bind]\nnode=np1\nsession=x\n[/bind]")
    assert_equal(bad_bind, None, "invalid bind should be ignored")

    # parse_allowed_users + comment_author_username
    assert_equal(parse_allowed_users("admin, OpsBot"), {"admin", "opsbot"}, "allowed users parse failed")
    assert_equal(parse_allowed_users(""), None, "empty allowlist should disable restriction")
    rendered_notify = render_notify_command(
        "echo {task_id}:{command}:{session}",
        {"task_id": "5", "command": "ack", "session": "codex-a"},
    )
    assert_equal(rendered_notify, "echo 5:ack:codex-a", "notify command rendering failed")
    assert_equal(
        comment_author_username({"author": {"username": "Admin"}}),
        "admin",
        "author username extraction failed",
    )
    assert_equal(comment_author_username({"author": {}}), None, "missing author username should be None")

    # task_mode
    mode_ai = task_mode({"labels": [{"title": "mode/ai"}]})
    mode_human = task_mode({"labels": [{"title": "other"}]})
    assert_equal(mode_ai, "ai", "mode/ai resolution failed")
    assert_equal(mode_human, "human", "default mode should be human")

    # action execution: reopen should set done=false then move
    fake = FakeClient()
    worker = BridgeWorker(
        client=fake,  # type: ignore[arg-type]
        project_id=13,
        state_path=Path("/tmp/test-bridge-worker-state.json"),
        dry_run=False,
        confirm_ttl_hours=24,
        confirm_allowed_users={"admin"},
    )
    used: set[str] = set()
    worker._handle_action_command(
        task={"id": 123, "project_id": 13},
        comment_id=10,
        action_cmd=ActionCommand(action="reopen", bucket_id=40, action_id="ac-1"),
        binding={"node": "np1", "session": "s", "workdir": "/tmp"},
        confirmations={"ac-1": (9, datetime.now(timezone.utc), "admin")},
        used_confirmations=used,
    )
    assert_equal(fake.updates, [(123, {"done": False})], "reopen should update task done=false")
    assert_equal(fake.moves, [(123, 40, 13)], "reopen should move task to target bucket")
    assert_equal("ac-1" in used, True, "used confirmations should include consumed action id")

    # action execution should be blocked if confirmer is not in allowlist
    fake_blocked = FakeClient()
    worker_blocked = BridgeWorker(
        client=fake_blocked,  # type: ignore[arg-type]
        project_id=13,
        state_path=Path("/tmp/test-bridge-worker-state-blocked.json"),
        dry_run=False,
        confirm_ttl_hours=24,
        confirm_allowed_users={"admin"},
    )
    worker_blocked._handle_action_command(
        task={"id": 124, "project_id": 13},
        comment_id=10,
        action_cmd=ActionCommand(action="move", bucket_id=40, action_id="ac-2"),
        binding={"node": "np1", "session": "s", "workdir": "/tmp"},
        confirmations={"ac-2": (9, datetime.now(timezone.utc), "guest")},
        used_confirmations=set(),
    )
    assert_equal(fake_blocked.updates, [], "blocked action should not update task")
    assert_equal(fake_blocked.moves, [], "blocked action should not move task")
    assert_equal(any("author not allowed" in c[1] for c in fake_blocked.comments), True, "block reason missing")

    # queue command should write work-order and run notification command
    notify_file = Path(tempfile.gettempdir()) / "bridge-notify-test.txt"
    notify_file.unlink(missing_ok=True)

    fake_queue = FakeClient()
    worker_queue = BridgeWorker(
        client=fake_queue,  # type: ignore[arg-type]
        project_id=13,
        state_path=Path("/tmp/test-bridge-worker-state-queue.json"),
        dry_run=False,
        notify_command=f"printf '{{task_id}}:{{command}}:{{comment_id}}' > {notify_file}",
        notify_timeout_seconds=5,
    )
    with tempfile.TemporaryDirectory(prefix="bridge-queue-test-") as tmpdir:
        worker_queue._handle_queue_command(
            task={"id": 125, "project_id": 13, "title": "Queue Demo"},
            comment_id=77,
            command_name="update",
            command_body="check notify path",
            binding={"node": "np1", "session": "s", "workdir": tmpdir},
        )
        inbox_file = Path(tmpdir) / "inbox" / "task-125-comment-77.md"
        assert_equal(inbox_file.exists(), True, "queue command should create work-order file")
        payload = inbox_file.read_text(encoding="utf-8")
        assert_equal("check notify path" in payload, True, "work-order body missing")

    assert_equal(notify_file.exists(), True, "notify file should be created")
    assert_equal(notify_file.read_text(encoding="utf-8"), "125:update:77", "notify command output mismatch")
    notify_file.unlink(missing_ok=True)

    print("[OK] bridge worker unit checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
