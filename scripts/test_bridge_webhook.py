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
    is_authorized,
    parse_bearer_token,
    write_trigger_file,
)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r} actual={actual!r}")


def main() -> int:
    assert_equal(parse_bearer_token("Bearer abc"), "abc", "bearer parse failed")
    assert_equal(parse_bearer_token("bearer   xyz "), "xyz", "bearer parse trim failed")
    assert_equal(parse_bearer_token("token abc"), "", "invalid auth scheme should return empty")

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
