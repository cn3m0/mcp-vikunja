from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .vikunja_api import VikunjaApiError, VikunjaClient


LOGGER = logging.getLogger("vikunja-bridge-worker")
BRIDGE_PREFIX = "[bridge]"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(raw: str) -> str:
    # Vikunja comment payload may contain basic html wrappers.
    text = re.sub(r"<[^>]+>", "", raw or "")
    text = text.replace("\r\n", "\n")
    return text.strip()


def parse_command(text: str) -> tuple[str, str] | None:
    match = re.match(r"^(ack|update|blocked|done)\s*:\s*(.*)$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).lower(), match.group(2).strip()


def parse_bind_block(text: str) -> dict[str, str] | None:
    matches = re.findall(r"\[bind\](.*?)\[/bind\]", text, flags=re.IGNORECASE | re.DOTALL)
    if not matches:
        return None

    block = matches[-1]
    data: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip().lower()] = value.strip()

    required = {"node", "session", "workdir"}
    if not required.issubset(set(data)):
        return None
    if not data["workdir"].startswith("/"):
        return None
    return {k: data[k] for k in ("node", "session", "workdir")}


def task_mode(task: dict[str, Any]) -> str:
    labels = task.get("labels") or []
    titles = {str(label.get("title", "")).lower() for label in labels if isinstance(label, dict)}
    if "mode/ai" in titles:
        return "ai"
    return "human"


@dataclass
class TaskState:
    last_processed_comment_id: int = 0
    last_command_hash: str = ""


class BridgeState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = {"tasks": {}}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            LOGGER.warning("State file is invalid json, starting clean: %s", self.path)
            self._data = {"tasks": {}}

    def get_task_state(self, task_id: int) -> TaskState:
        payload = (self._data.get("tasks") or {}).get(str(task_id), {})
        return TaskState(
            last_processed_comment_id=int(payload.get("last_processed_comment_id", 0)),
            last_command_hash=str(payload.get("last_command_hash", "")),
        )

    def update_task_state(self, task_id: int, state: TaskState) -> None:
        tasks = self._data.setdefault("tasks", {})
        tasks[str(task_id)] = {
            "last_processed_comment_id": int(state.last_processed_comment_id),
            "last_command_hash": state.last_command_hash,
            "updated_at": _now_iso(),
        }
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)
        self._dirty = False


class BridgeWorker:
    def __init__(
        self,
        client: VikunjaClient,
        project_id: int,
        state_path: Path,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.project_id = project_id
        self.state = BridgeState(state_path)
        self.dry_run = dry_run

    def run_once(self) -> None:
        tasks = self.client.list_tasks(project_id=self.project_id, page=1, per_page=300)
        LOGGER.info("Found %d tasks in project %s", len(tasks), self.project_id)

        for task in sorted(tasks, key=lambda t: int(t.get("id", 0))):
            mode = task_mode(task)
            if mode != "ai":
                continue
            self._process_task(task)

        self.state.save()

    def _process_task(self, task: dict[str, Any]) -> None:
        task_id = int(task["id"])
        title = str(task.get("title", ""))
        comments = self.client.list_task_comments(task_id=task_id, order_by="asc")
        LOGGER.info("Processing task #%s (%s), comments=%d", task_id, title, len(comments))

        task_state = self.state.get_task_state(task_id)
        binding: dict[str, str] | None = None

        for comment in comments:
            comment_id = int(comment.get("id", 0))
            if comment_id <= task_state.last_processed_comment_id:
                bind = parse_bind_block(normalize_text(str(comment.get("comment", ""))))
                if bind:
                    binding = bind
                continue

            text = normalize_text(str(comment.get("comment", "")))

            bind = parse_bind_block(text)
            if bind:
                binding = bind

            # Never process worker-authored comments.
            if text.startswith(BRIDGE_PREFIX):
                task_state.last_processed_comment_id = comment_id
                continue

            command = parse_command(text)
            if command is None:
                task_state.last_processed_comment_id = comment_id
                continue

            cmd_name, cmd_body = command
            command_hash = hashlib.sha256(f"{task_id}:{comment_id}:{cmd_name}:{cmd_body}".encode("utf-8")).hexdigest()
            if command_hash == task_state.last_command_hash:
                task_state.last_processed_comment_id = comment_id
                continue

            if not binding:
                self._post_bridge_comment(task_id, f"blocked: missing or invalid binding (comment_id={comment_id})")
                task_state.last_processed_comment_id = comment_id
                task_state.last_command_hash = command_hash
                continue

            try:
                output_path = self._write_work_order(
                    task=task,
                    comment_id=comment_id,
                    command_name=cmd_name,
                    command_body=cmd_body,
                    binding=binding,
                )
                self._post_bridge_comment(
                    task_id,
                    f"ack: queued command={cmd_name} comment_id={comment_id} file={output_path}",
                )
            except Exception as exc:  # pragma: no cover - top-level safety
                self._post_bridge_comment(task_id, f"blocked: could not queue command_id={comment_id} reason={exc}")

            task_state.last_processed_comment_id = comment_id
            task_state.last_command_hash = command_hash

        self.state.update_task_state(task_id, task_state)

    def _write_work_order(
        self,
        *,
        task: dict[str, Any],
        comment_id: int,
        command_name: str,
        command_body: str,
        binding: dict[str, str],
    ) -> str:
        task_id = int(task["id"])
        workdir = Path(binding["workdir"])
        inbox = workdir / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        file_name = f"task-{task_id}-comment-{comment_id}.md"
        target = inbox / file_name
        payload = (
            f"# Work Order\n\n"
            f"- generated_at: {_now_iso()}\n"
            f"- task_id: {task_id}\n"
            f"- task_title: {task.get('title', '')}\n"
            f"- project_id: {task.get('project_id', '')}\n"
            f"- comment_id: {comment_id}\n"
            f"- command: {command_name}\n"
            f"- node: {binding.get('node', '')}\n"
            f"- session: {binding.get('session', '')}\n"
            f"- workdir: {binding.get('workdir', '')}\n\n"
            f"## Body\n\n"
            f"{command_body}\n"
        )

        if self.dry_run:
            LOGGER.info("Dry-run: skipping write for %s", target)
            return str(target)

        tmp = target.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(target)
        return str(target)

    def _post_bridge_comment(self, task_id: int, message: str) -> None:
        content = f"{BRIDGE_PREFIX} {message}"
        if self.dry_run:
            LOGGER.info("Dry-run: comment task#%s: %s", task_id, content)
            return
        self.client.add_task_comment(task_id=task_id, comment=content)


def build_client() -> VikunjaClient:
    base_url = os.getenv("VIKUNJA_URL", "http://localhost:3456/api/v1")
    token = os.getenv("VIKUNJA_API_TOKEN", "")
    timeout = float(os.getenv("VIKUNJA_TIMEOUT", "15"))
    return VikunjaClient(base_url=base_url, token=token, timeout=timeout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vikunja <-> Codex bridge pull worker")
    parser.add_argument("--project-id", type=int, required=True, help="Vikunja project id to poll")
    parser.add_argument(
        "--state-file",
        default=os.getenv("BRIDGE_STATE_FILE", "/tmp/mcp-vikunja-bridge/state.json"),
        help="Persistent state file path",
    )
    parser.add_argument("--interval", type=int, default=int(os.getenv("BRIDGE_POLL_INTERVAL", "15")))
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files or comments")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        client = build_client()
        worker = BridgeWorker(
            client=client,
            project_id=args.project_id,
            state_path=Path(args.state_file),
            dry_run=args.dry_run,
        )
        if args.once:
            worker.run_once()
            return 0

        LOGGER.info("Starting bridge worker (project_id=%s interval=%ss)", args.project_id, args.interval)
        while True:
            try:
                worker.run_once()
            except VikunjaApiError as exc:
                LOGGER.warning("Bridge cycle failed: %s", exc)
            time.sleep(max(args.interval, 1))
    except Exception as exc:  # pragma: no cover - defensive entrypoint
        LOGGER.exception("Fatal bridge worker error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
