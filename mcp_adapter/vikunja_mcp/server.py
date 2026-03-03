from __future__ import annotations

import logging
import os
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .vikunja_api import VikunjaApiError, VikunjaClient


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("vikunja-mcp")

APP_NAME = "vikunja-mcp"

mcp = FastMCP(
    APP_NAME,
    host=os.getenv("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.getenv("FASTMCP_PORT", "8000")),
)


def _client() -> VikunjaClient:
    base_url = os.getenv("VIKUNJA_URL", "http://localhost:3456/api/v1")
    token = os.getenv("VIKUNJA_API_TOKEN", "")
    timeout = float(os.getenv("VIKUNJA_TIMEOUT", "15"))
    return VikunjaClient(base_url=base_url, token=token, timeout=timeout)


def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def _err(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def _run(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        data = fn()
        return _ok(data)
    except VikunjaApiError as exc:
        logger.warning("%s failed: %s", name, exc)
        code = f"VIKUNJA_{exc.status_code}" if exc.status_code else "VIKUNJA_ERROR"
        return _err(code, exc.message, exc.details)
    except Exception as exc:  # pragma: no cover - defensive top-level handler
        logger.exception("%s failed unexpectedly", name)
        return _err("INTERNAL_ERROR", str(exc), None)


@mcp.tool()
def health() -> dict[str, Any]:
    """Check reachability of the Vikunja API."""

    return _run("health", lambda: _client().health())


@mcp.tool()
def list_projects(page: int = 1, per_page: int = 50) -> dict[str, Any]:
    """List projects visible to the configured Vikunja user."""

    return _run("list_projects", lambda: _client().list_projects(page=page, per_page=per_page))


@mcp.tool()
def create_project(title: str, description: str | None = None) -> dict[str, Any]:
    """Create a new project in Vikunja."""

    return _run("create_project", lambda: _client().create_project(title=title, description=description))


@mcp.tool()
def list_tasks(
    project_id: int,
    view_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    """List tasks in a project. If view_id is omitted, a kanban view is auto-selected."""

    return _run(
        "list_tasks",
        lambda: _client().list_tasks(project_id=project_id, view_id=view_id, page=page, per_page=per_page),
    )


@mcp.tool()
def create_task(
    project_id: int,
    title: str,
    description: str | None = None,
    bucket_id: int | None = None,
) -> dict[str, Any]:
    """Create a task in a project."""

    return _run(
        "create_task",
        lambda: _client().create_task(
            project_id=project_id,
            title=title,
            description=description,
            bucket_id=bucket_id,
        ),
    )


@mcp.tool()
def list_task_comments(task_id: int, order_by: str = "asc") -> dict[str, Any]:
    """List comments for a specific task."""

    return _run("list_task_comments", lambda: _client().list_task_comments(task_id=task_id, order_by=order_by))


@mcp.tool()
def add_task_comment(task_id: int, comment: str) -> dict[str, Any]:
    """Add a comment to a specific task."""

    return _run("add_task_comment", lambda: _client().add_task_comment(task_id=task_id, comment=comment))


@mcp.tool()
def update_task(task_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """Update fields on an existing task."""

    return _run("update_task", lambda: _client().update_task(task_id=task_id, updates=updates))


@mcp.tool()
def move_task(
    task_id: int,
    target_bucket_id: int,
    project_id: int | None = None,
    view_id: int | None = None,
) -> dict[str, Any]:
    """Move a task to a bucket. project_id/view_id are optional and auto-resolved when omitted."""

    return _run(
        "move_task",
        lambda: _client().move_task(
            task_id=task_id,
            target_bucket_id=target_bucket_id,
            project_id=project_id,
            view_id=view_id,
        ),
    )


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mount_path = os.getenv("MCP_MOUNT_PATH", "/")
    logger.info("Starting %s (transport=%s)", APP_NAME, transport)
    if transport == "sse":
        mcp.run(transport="sse", mount_path=mount_path)
        return
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
