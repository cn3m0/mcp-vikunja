#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def parse_sse_body(raw_body: str) -> dict[str, Any]:
    data_lines: list[str] = []
    for line in raw_body.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif data_lines and line.strip() == "":
            break
    if not data_lines:
        raise RuntimeError(f"No SSE data field found in response body: {raw_body!r}")
    payload = "\n".join(data_lines)
    return json.loads(payload)


class MCPHttpClient:
    def __init__(self, base_url: str, protocol_version: str = "2025-03-26") -> None:
        self.base_url = base_url.rstrip("/")
        self.protocol_version = protocol_version
        self.session_id: str | None = None
        self._request_id = 0

    def _next_id(self) -> str:
        self._request_id += 1
        return f"req-{self._request_id}"

    def _post(self, payload: dict[str, Any], expect_notification: bool = False) -> dict[str, Any] | None:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id
            headers["MCP-Protocol-Version"] = self.protocol_version

        request = urllib.request.Request(self.base_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                content_type = response.headers.get("Content-Type", "")
                session_id = response.headers.get("mcp-session-id")
                if session_id:
                    self.session_id = session_id

                if expect_notification:
                    if response.status != 202:
                        raise RuntimeError(f"Expected HTTP 202 for notification, got {response.status}")
                    return None

                if content_type.startswith("text/event-stream"):
                    return parse_sse_body(response_body)
                if content_type.startswith("application/json"):
                    return json.loads(response_body) if response_body else {}
                raise RuntimeError(f"Unsupported response content-type: {content_type}")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from MCP endpoint: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach MCP endpoint: {exc}") from exc

    def initialize(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "local-smoke-test", "version": "0.1.0"},
                },
            }
        )
        if not response or "result" not in response:
            raise RuntimeError(f"Initialize failed: {response}")
        if not self.session_id:
            raise RuntimeError("Initialize succeeded but no mcp-session-id was returned")

        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            expect_notification=True,
        )

    def tools_list(self) -> list[str]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            }
        )
        if not response or "result" not in response:
            raise RuntimeError(f"tools/list failed: {response}")
        tools = response["result"].get("tools", [])
        return [tool.get("name", "") for tool in tools if isinstance(tool, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if not response or "result" not in response:
            raise RuntimeError(f"tools/call failed for '{name}': {response}")
        result = response["result"]
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured

        # Fallback for servers/SDK variants where structured content is absent.
        content = result.get("content", [])
        if content and isinstance(content, list) and isinstance(content[0], dict):
            text = content[0].get("text")
            if isinstance(text, str):
                return json.loads(text)
        raise RuntimeError(f"Could not parse tool result for '{name}': {result}")


def main() -> int:
    load_dotenv(ROOT / ".env")
    mcp_url = os.getenv("MCP_ADAPTER_URL", "http://localhost:8000/mcp")
    client = MCPHttpClient(base_url=mcp_url)
    try:
        client.initialize()
        print(f"[OK] MCP initialize successful (session={client.session_id})")

        tools = client.tools_list()
        expected = {
            "health",
            "list_projects",
            "create_project",
            "list_tasks",
            "create_task",
            "list_task_comments",
            "add_task_comment",
            "update_task",
            "move_task",
        }
        missing = sorted(expected.difference(tools))
        if missing:
            raise RuntimeError(f"tools/list missing expected tools: {missing}")
        print(f"[OK] tools/list returned expected toolset ({len(tools)} tools)")

        health = client.call_tool("health", {})
        if not health.get("success"):
            raise RuntimeError(f"health tool returned error: {health}")
        version = health.get("data", {}).get("version")
        print(f"[OK] tools/call health successful (vikunja={version})")

        projects = client.call_tool("list_projects", {"page": 1, "per_page": 50})
        if not projects.get("success"):
            raise RuntimeError(f"list_projects tool returned error: {projects}")
        project_count = len(projects.get("data", []))
        print(f"[OK] tools/call list_projects successful ({project_count} projects visible)")
        return 0
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
