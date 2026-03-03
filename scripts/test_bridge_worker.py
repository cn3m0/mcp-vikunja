#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER_PATH = ROOT / "mcp_adapter"
sys.path.insert(0, str(MCP_ADAPTER_PATH))

from vikunja_mcp.bridge_worker import (  # noqa: E402
    parse_bind_block,
    parse_command,
    task_mode,
)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r} actual={actual!r}")


def main() -> int:
    # parse_command
    assert_equal(parse_command("ack: started"), ("ack", "started"), "ack command parse failed")
    assert_equal(parse_command("update: value"), ("update", "value"), "update command parse failed")
    assert_equal(parse_command("not-a-command"), None, "invalid command should be ignored")

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

    # task_mode
    mode_ai = task_mode({"labels": [{"title": "mode/ai"}]})
    mode_human = task_mode({"labels": [{"title": "other"}]})
    assert_equal(mode_ai, "ai", "mode/ai resolution failed")
    assert_equal(mode_human, "human", "default mode should be human")

    print("[OK] bridge worker unit checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
