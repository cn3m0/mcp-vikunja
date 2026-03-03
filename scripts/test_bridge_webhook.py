#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER_PATH = ROOT / "mcp_adapter"
sys.path.insert(0, str(MCP_ADAPTER_PATH))

from vikunja_mcp.bridge_webhook import (  # noqa: E402
    extract_project_ids,
    is_authorized,
    parse_bearer_token,
    parse_int_csv_set,
    parse_lower_csv_set,
    resolve_event_name,
    should_accept_webhook,
    write_trigger_file,
)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r} actual={actual!r}")


def main() -> int:
    assert_equal(parse_bearer_token("Bearer abc"), "abc", "bearer parse failed")
    assert_equal(parse_bearer_token("bearer   xyz "), "xyz", "bearer parse trim failed")
    assert_equal(parse_bearer_token("token abc"), "", "invalid auth scheme should return empty")
    assert_equal(parse_lower_csv_set("task.created, task.updated"), {"task.created", "task.updated"}, "lower csv parse failed")
    assert_equal(parse_int_csv_set("13,14,x"), {13, 14}, "int csv parse failed")

    event_name = resolve_event_name("Task.Created", {})
    assert_equal(event_name, "task.created", "header event should win")
    event_name = resolve_event_name("", {"event": "task.updated"})
    assert_equal(event_name, "task.updated", "payload event fallback failed")

    payload = {
        "task": {"id": 5, "project_id": 13},
        "project": {"id": 14},
        "items": [{"project_id": "15"}],
    }
    project_ids = extract_project_ids(payload)
    assert_equal(project_ids, {13, 14, 15}, "project id extraction failed")

    allowed, reason = should_accept_webhook(
        event_name="task.updated",
        project_ids={13},
        allowed_events={"task.updated"},
        allowed_project_ids={13, 14},
        require_project_match=False,
    )
    assert_equal((allowed, reason), (True, "accepted"), "acceptance positive case failed")
    allowed, reason = should_accept_webhook(
        event_name="task.deleted",
        project_ids={13},
        allowed_events={"task.updated"},
        allowed_project_ids=None,
        require_project_match=False,
    )
    assert_equal((allowed, reason), (False, "event"), "event filter should block")
    allowed, reason = should_accept_webhook(
        event_name="task.updated",
        project_ids={99},
        allowed_events=None,
        allowed_project_ids={13},
        require_project_match=False,
    )
    assert_equal((allowed, reason), (False, "project"), "project filter should block")
    allowed, reason = should_accept_webhook(
        event_name="task.updated",
        project_ids=set(),
        allowed_events=None,
        allowed_project_ids={13},
        require_project_match=True,
    )
    assert_equal((allowed, reason), (False, "project_missing"), "strict project filter should block missing project id")

    assert_equal(
        is_authorized(expected_token="", header_token=None, authorization_header=None),
        True,
        "empty expected token should allow",
    )
    assert_equal(
        is_authorized(expected_token="abc", header_token="abc", authorization_header=None),
        True,
        "header token auth failed",
    )
    assert_equal(
        is_authorized(expected_token="abc", header_token=None, authorization_header="Bearer abc"),
        True,
        "bearer auth failed",
    )
    assert_equal(
        is_authorized(expected_token="abc", header_token="wrong", authorization_header="Bearer wrong"),
        False,
        "invalid auth should fail",
    )

    with tempfile.TemporaryDirectory(prefix="bridge-webhook-test-") as tmpdir:
        trigger = Path(tmpdir) / "trigger.signal"
        payload = {"received_at": "2026-03-03T00:00:00Z", "event": "task.updated"}
        write_trigger_file(trigger, payload)
        assert_equal(trigger.exists(), True, "trigger file should be written")
        data = json.loads(trigger.read_text(encoding="utf-8"))
        assert_equal(data.get("event"), "task.updated", "trigger payload event mismatch")

    print("[OK] bridge webhook unit checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
