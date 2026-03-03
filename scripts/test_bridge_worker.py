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
    compute_backoff_seconds,
    parse_action_command,
    parse_allowed_users,
    parse_bool,
    parse_bind_block,
    parse_command,
    parse_confirmation_token,
    parse_int_set,
    parse_int_list,
    parse_mode_override,
    parse_lower_set,
    merge_project_ids,
    parse_mode_value,
    read_mode_file,
    render_notify_command,
    should_process_task,
    task_mode_with_override,
    task_mode,
    latest_mode_override_from_comments,
)
from vikunja_mcp.vikunja_api import VikunjaClient  # noqa: E402


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


class FlakyCommentClient(FakeClient):
    def __init__(self, failures_before_success: int) -> None:
        super().__init__()
        self.failures_remaining = failures_before_success

    def add_task_comment(self, task_id: int, comment: str) -> dict:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise RuntimeError("simulated comment failure")
        return super().add_task_comment(task_id=task_id, comment=comment)


class FakeListTasksClient(VikunjaClient):
    def __init__(self, payload: list[dict]) -> None:
        super().__init__(base_url="http://localhost:3456/api/v1", token="dummy")
        self._payload = payload

    def _request(self, method: str, path: str, *, auth: bool = True, params=None, json_data=None):  # type: ignore[override]
        return self._payload

    def resolve_view_id(self, project_id: int, preferred_kind: str = "kanban") -> int:  # noqa: ARG002
        return 52


class FakeMultiProjectClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.projects_listed: list[int] = []

    def list_tasks(self, project_id: int, *, view_id: int | None = None, page: int = 1, per_page: int = 50) -> list[dict]:  # noqa: ARG002
        self.projects_listed.append(project_id)
        # mark tasks as done so selection may skip without requiring list_task_comments
        return [
            {
                "id": (project_id * 1000) + 1,
                "title": f"task-{project_id}",
                "project_id": project_id,
                "done": True,
                "bucket_id": 40,
                "labels": [{"title": "mode/ai"}],
            }
        ]

    def list_task_comments(self, task_id: int, order_by: str = "asc") -> list[dict]:  # noqa: ARG002
        return []


def main() -> int:
    # parse_command
    assert_equal(parse_command("ack: started"), ("ack", "started"), "ack command parse failed")
    assert_equal(parse_command("update: value"), ("update", "value"), "update command parse failed")
    assert_equal(parse_command("not-a-command"), None, "invalid command should be ignored")
    assert_equal(parse_mode_override("mode: ai"), "ai", "mode override parse failed")
    assert_equal(parse_mode_override("mode: HUMAN"), "human", "mode override parse uppercase failed")
    assert_equal(parse_mode_override("mode: invalid"), None, "invalid mode override should be ignored")

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
    assert_equal(parse_lower_set("X, y"), {"x", "y"}, "lower set parse failed")
    assert_equal(parse_int_set("40, 41, x"), {40, 41}, "int set parse failed")
    assert_equal(parse_int_list("13, 14, x,13"), [13, 14], "int list parse failed")
    assert_equal(merge_project_ids(12, [13, 12, 14]), [12, 13, 14], "merge project ids failed")
    assert_equal(merge_project_ids(None, [13, 13]), [13], "merge project ids with none failed")
    assert_equal(parse_int_set(""), None, "empty int set should be None")
    assert_equal(parse_bool("yes"), True, "bool yes parse failed")
    assert_equal(parse_bool("0", default=True), False, "bool false parse failed")
    assert_equal(parse_bool("unknown", default=True), True, "bool default fallback failed")
    assert_equal(compute_backoff_seconds(0, 5, 300), 5, "backoff at 0 failures should be min")
    assert_equal(compute_backoff_seconds(1, 5, 300), 5, "backoff first failure should be min")
    assert_equal(compute_backoff_seconds(2, 5, 300), 10, "backoff second failure should double")
    assert_equal(compute_backoff_seconds(10, 5, 60), 60, "backoff should clamp to max")
    assert_equal(parse_allowed_users(""), None, "empty allowlist should disable restriction")
    assert_equal(parse_mode_value("mode=ai"), "ai", "mode parser should support key=value")
    assert_equal(parse_mode_value("human"), "human", "mode parser should support plain value")
    assert_equal(parse_mode_value("mode=invalid"), None, "mode parser should reject invalid values")
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
    mode_human_label = task_mode({"labels": [{"title": "mode/human"}]}, fallback_mode="ai")
    mode_ai_fallback = task_mode({"labels": []}, fallback_mode="ai")
    mode_human = task_mode({"labels": [{"title": "other"}]})
    mode_override = task_mode_with_override({"labels": [{"title": "mode/human"}]}, comment_override="ai")
    assert_equal(mode_ai, "ai", "mode/ai resolution failed")
    assert_equal(mode_human_label, "human", "mode/human label must override fallback")
    assert_equal(mode_ai_fallback, "ai", "fallback mode file should allow ai mode without label")
    assert_equal(mode_human, "human", "default mode should be human")
    assert_equal(mode_override, "ai", "comment override should take precedence when enabled")

    override_from_comments = latest_mode_override_from_comments(
        [
            {"id": 1, "comment": "mode: human"},
            {"id": 2, "comment": "[bridge] mode: ai"},
            {"id": 3, "comment": "mode: ai"},
        ]
    )
    assert_equal(override_from_comments, "ai", "latest non-bridge mode override should win")

    allowed, reason = should_process_task(
        {"id": 1, "done": False, "bucket_id": 40, "labels": [{"title": "mode/ai"}, {"title": "size/M"}]},
        mode="ai",
        skip_done=True,
        allowed_bucket_ids={40},
        required_labels={"size/m"},
    )
    assert_equal((allowed, reason), (True, "selected"), "task selection positive case failed")

    allowed, reason = should_process_task(
        {"id": 2, "done": True, "bucket_id": 40, "labels": [{"title": "mode/ai"}]},
        mode="ai",
        skip_done=True,
        allowed_bucket_ids=None,
        required_labels=None,
    )
    assert_equal((allowed, reason), (False, "done"), "task selection done filter failed")

    allowed, reason = should_process_task(
        {"id": 3, "done": False, "bucket_id": 41, "labels": [{"title": "mode/ai"}]},
        mode="ai",
        skip_done=False,
        allowed_bucket_ids={40},
        required_labels=None,
    )
    assert_equal((allowed, reason), (False, "bucket"), "task selection bucket filter failed")

    allowed, reason = should_process_task(
        {"id": 4, "done": False, "bucket_id": 40, "labels": [{"title": "mode/ai"}]},
        mode="ai",
        skip_done=False,
        allowed_bucket_ids=None,
        required_labels={"size/l"},
    )
    assert_equal((allowed, reason), (False, "labels"), "task selection label filter failed")

    with tempfile.TemporaryDirectory(prefix="bridge-mode-file-") as tmpdir:
        mode_file = Path(tmpdir) / ".bridge-mode"
        mode_file.write_text("# comment\nmode=ai\n", encoding="utf-8")
        assert_equal(read_mode_file(mode_file), "ai", "mode file read failed")
        mode_file.write_text("mode=invalid\n", encoding="utf-8")
        assert_equal(read_mode_file(mode_file), None, "invalid mode file should be ignored")

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

    # failed comment posting should spool and later flush pending comments
    with tempfile.TemporaryDirectory(prefix="bridge-pending-comments-") as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        pending_file = Path(tmpdir) / "pending-comments.jsonl"
        flaky = FlakyCommentClient(failures_before_success=1)
        worker_spool = BridgeWorker(
            client=flaky,  # type: ignore[arg-type]
            project_id=13,
            state_path=state_file,
            dry_run=False,
            pending_comments_path=pending_file,
            pending_comments_max=20,
        )
        worker_spool._post_bridge_comment(200, "ack: queued test")
        assert_equal(len(flaky.comments), 0, "failed post should not be recorded as sent")
        assert_equal(pending_file.exists(), True, "failed post should create pending comments spool")
        worker_spool._flush_pending_bridge_comments(limit=10)
        assert_equal(len(flaky.comments), 1, "flush should send previously queued comment")
        assert_equal(pending_file.exists(), False, "pending spool should be removed after successful flush")

    # worker should poll all configured projects in one cycle
    with tempfile.TemporaryDirectory(prefix="bridge-multi-project-") as tmpdir:
        multi_client = FakeMultiProjectClient()
        multi_worker = BridgeWorker(
            client=multi_client,  # type: ignore[arg-type]
            project_id=None,
            project_ids=[13, 14],
            state_path=Path(tmpdir) / "state.json",
            dry_run=True,
            skip_done=True,
        )
        multi_worker.run_once()
        assert_equal(multi_client.projects_listed, [13, 14], "multi-project polling order mismatch")

    # list_tasks should flatten bucket payload even if first bucket has no `tasks` key
    bucket_payload = [
        {"id": 39, "title": "To-Do"},
        {"id": 40, "title": "Doing", "tasks": [{"id": 101, "title": "Task A"}]},
    ]
    list_client = FakeListTasksClient(bucket_payload)
    flattened = list_client.list_tasks(project_id=13, view_id=52)
    assert_equal(len(flattened), 1, "list_tasks flattening failed for bucket payload")
    assert_equal(flattened[0].get("id"), 101, "flattened task id mismatch")
    assert_equal(flattened[0].get("bucket_id"), 40, "flattened task bucket mismatch")

    print("[OK] bridge worker unit checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
