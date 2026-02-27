#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER_PATH = ROOT / "mcp_adapter"
sys.path.insert(0, str(MCP_ADAPTER_PATH))

from vikunja_mcp.vikunja_api import VikunjaApiError, VikunjaClient  # noqa: E402


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_client() -> VikunjaClient:
    load_dotenv(ROOT / ".env")
    base_url = os.getenv("VIKUNJA_PUBLIC_URL", "http://localhost:3456/").rstrip("/")
    api_token = os.getenv("VIKUNJA_API_TOKEN")
    if not api_token:
        raise RuntimeError("Missing VIKUNJA_API_TOKEN in environment or .env")
    return VikunjaClient(base_url=f"{base_url}/api/v1", token=api_token, timeout=20.0)


def find_or_create_project(client: VikunjaClient, title: str) -> dict:
    projects = client.list_projects(page=1, per_page=200)
    existing = next((p for p in projects if p.get("title") == title), None)
    if existing:
        return existing
    return client.create_project(title=title, description="Proof-of-Concept project created by verify_poc.py")


def main() -> int:
    try:
        client = get_client()
        info = client.health()
        print(f"[OK] API reachable: {info.get('frontend_url', 'info endpoint responded')}")

        project = find_or_create_project(client, "CN3M0 PoC")
        project_id = int(project["id"])
        print(f"[OK] Project available: CN3M0 PoC (id={project_id})")

        task = client.create_task(project_id=project_id, title=f"PoC Task {int(time.time())}")
        task_id = int(task["id"])
        print(f"[OK] Task created: id={task_id}")

        view_id = client.resolve_view_id(project_id=project_id)
        buckets = client.list_buckets(project_id=project_id, view_id=view_id)
        if len(buckets) < 2:
            raise RuntimeError(
                f"Need at least 2 buckets to verify move_task. Found {len(buckets)} in view {view_id}."
            )
        target_bucket_id = int(buckets[1]["id"])

        moved = client.move_task(
            task_id=task_id,
            target_bucket_id=target_bucket_id,
            project_id=project_id,
            view_id=view_id,
        )
        print(
            "[OK] Task moved: "
            f"task_id={moved.get('task_id', task_id)} "
            f"bucket_id={moved.get('bucket_id', target_bucket_id)}"
        )

        summary = (
            f"Projekt CN3M0 PoC ist erreichbar. "
            f"Neuer Task {task_id} wurde erstellt und in Bucket {target_bucket_id} verschoben."
        )
        print(f"[OK] Summary: {summary}")
        return 0
    except (VikunjaApiError, RuntimeError, KeyError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

