#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER_PATH = ROOT / "mcp_adapter"
sys.path.insert(0, str(MCP_ADAPTER_PATH))

import vikunja_mcp.vikunja_api as vikunja_api  # noqa: E402
from vikunja_mcp.vikunja_api import VikunjaClient  # noqa: E402


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r} actual={actual!r}")


class FakeVikunjaClient(VikunjaClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://localhost:3456/api/v1", token="dummy")
        self.last_json: dict | None = None

    def _request(self, method: str, path: str, *, auth: bool = True, params=None, json_data=None):  # type: ignore[override]
        self.last_json = json_data
        return {"id": 1, "comment": (json_data or {}).get("comment", "")}


def main() -> int:
    # static normalization checks
    assert_equal(
        VikunjaClient.normalize_comment_text("Line1\\n- item"),
        "Line1\n- item",
        "escaped newline should be decoded",
    )
    assert_equal(
        VikunjaClient.normalize_comment_text("Header\\n\\n- item 1\\n- item 2"),
        "Header\n\n- item 1\n- item 2",
        "escaped markdown block should be decoded",
    )
    assert_equal(
        VikunjaClient.normalize_comment_text("Line1\r\nLine2"),
        "Line1\nLine2",
        "CRLF should normalize to LF",
    )
    assert_equal(
        VikunjaClient.normalize_comment_text("Path C:\\new\\node"),
        "Path C:\\new\\node",
        "plain backslashes should not be changed without escaped newline tokens",
    )
    assert_equal(
        VikunjaClient.normalize_comment_text("Plain\\nText"),
        "Plain\\nText",
        "non-markdown escaped newline should remain unchanged",
    )

    # markdown/html preparation
    assert_equal(
        VikunjaClient.prepare_comment_for_vikunja("<p>already html</p>"),
        "<p>already html</p>",
        "html input should stay unchanged",
    )

    # add_task_comment should send normalized body
    fake = FakeVikunjaClient()
    original_renderer = vikunja_api._markdown_to_html
    vikunja_api._markdown_to_html = lambda text, extensions=None, output_format=None: f"<p>{text}</p>"  # type: ignore[assignment]
    fake.add_task_comment(task_id=64, comment="Update:\\n- bullet 1\\n- bullet 2")
    vikunja_api._markdown_to_html = original_renderer

    assert_equal(
        (fake.last_json or {}).get("comment"),
        "<p>Update:\n- bullet 1\n- bullet 2</p>",
        "request payload comment rendering failed",
    )

    print("[OK] vikunja api checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
