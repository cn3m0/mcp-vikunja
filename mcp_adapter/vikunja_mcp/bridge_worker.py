from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


@dataclass
class ActionCommand:
    action: str
    bucket_id: int
    action_id: str


def parse_action_command(text: str) -> ActionCommand | None:
    # level-2 command requiring explicit confirmation
    # format: action: move bucket=40 id=move-to-doing-123
    match = re.match(
        r"^action\s*:\s*(move|reopen)\s+bucket\s*=\s*(\d+)\s+id\s*=\s*([a-zA-Z0-9._-]+)\s*$",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return ActionCommand(
        action=match.group(1).lower(),
        bucket_id=int(match.group(2)),
        action_id=match.group(3),
    )


def parse_confirmation_token(text: str) -> str | None:
    match = re.match(r"^confirm\s*:\s*([a-zA-Z0-9._-]+)\s*$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


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


def parse_allowed_users(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    values = {part.strip().lower() for part in raw.split(",") if part.strip()}
    if not values:
        return None
    return values


def comment_author_username(comment: dict[str, Any]) -> str | None:
    author = comment.get("author") if isinstance(comment, dict) else None
    if not isinstance(author, dict):
        return None
    username = str(author.get("username", "")).strip()
    return username.lower() if username else None


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
    binding_hash: str = ""
    used_confirmations: set[str] | None = None


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
            binding_hash=str(payload.get("binding_hash", "")),
            used_confirmations=set(payload.get("used_confirmations", [])),
        )

    def update_task_state(self, task_id: int, state: TaskState) -> None:
        tasks = self._data.setdefault("tasks", {})
        used_confirmations = sorted(list(state.used_confirmations or set()))[-200:]
        tasks[str(task_id)] = {
            "last_processed_comment_id": int(state.last_processed_comment_id),
            "last_command_hash": state.last_command_hash,
            "binding_hash": state.binding_hash,
            "used_confirmations": used_confirmations,
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
        confirm_ttl_hours: int = 24,
        confirm_allowed_users: set[str] | None = None,
    ) -> None:
        self.client = client
        self.project_id = project_id
        self.state = BridgeState(state_path)
        self.dry_run = dry_run
        self.confirm_ttl = timedelta(hours=max(confirm_ttl_hours, 1))
        self.confirm_allowed_users = confirm_allowed_users

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
        confirmations: dict[str, tuple[int, datetime, str | None]] = {}
        used_confirmations = task_state.used_confirmations or set()

        for comment in comments:
            comment_id = int(comment.get("id", 0))
            text = normalize_text(str(comment.get("comment", "")))
            created_at = self._parse_comment_created(comment.get("created"))
            author_username = comment_author_username(comment)

            token = parse_confirmation_token(text)
            if token and created_at:
                confirmations[token] = (comment_id, created_at, author_username)

            if comment_id <= task_state.last_processed_comment_id:
                bind = parse_bind_block(text)
                if bind:
                    binding = bind
                continue

            bind = parse_bind_block(text)
            if bind:
                binding = bind
                task_state.binding_hash = self._binding_hash(bind)

            # Never process worker-authored comments.
            if text.startswith(BRIDGE_PREFIX):
                task_state.last_processed_comment_id = comment_id
                continue

            command_hash = hashlib.sha256(f"{task_id}:{comment_id}:{text}".encode("utf-8")).hexdigest()
            if command_hash == task_state.last_command_hash:
                task_state.last_processed_comment_id = comment_id
                continue

            action_cmd = parse_action_command(text)
            if action_cmd:
                self._handle_action_command(
                    task=task,
                    comment_id=comment_id,
                    action_cmd=action_cmd,
                    binding=binding,
                    confirmations=confirmations,
                    used_confirmations=used_confirmations,
                )
                task_state.last_processed_comment_id = comment_id
                task_state.last_command_hash = command_hash
                continue

            command = parse_command(text)
            if command:
                cmd_name, cmd_body = command
                self._handle_queue_command(
                    task=task,
                    comment_id=comment_id,
                    command_name=cmd_name,
                    command_body=cmd_body,
                    binding=binding,
                )
                task_state.last_processed_comment_id = comment_id
                task_state.last_command_hash = command_hash
                continue

            task_state.last_processed_comment_id = comment_id
            # keep last_command_hash unchanged for non-command comments

        task_state.used_confirmations = used_confirmations
        self.state.update_task_state(task_id, task_state)

    @staticmethod
    def _parse_comment_created(raw: Any) -> datetime | None:
        if not raw or not isinstance(raw, str):
            return None
        value = raw.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _binding_hash(binding: dict[str, str]) -> str:
        payload = json.dumps(binding, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _handle_queue_command(
        self,
        *,
        task: dict[str, Any],
        comment_id: int,
        command_name: str,
        command_body: str,
        binding: dict[str, str] | None,
    ) -> None:
        task_id = int(task["id"])
        if not binding:
            self._post_bridge_comment(task_id, f"blocked: missing or invalid binding (comment_id={comment_id})")
            return

        try:
            output_path = self._write_work_order(
                task=task,
                comment_id=comment_id,
                command_name=command_name,
                command_body=command_body,
                binding=binding,
            )
            self._post_bridge_comment(
                task_id,
                f"ack: queued command={command_name} comment_id={comment_id} file={output_path}",
            )
        except Exception as exc:  # pragma: no cover - top-level safety
            self._post_bridge_comment(task_id, f"blocked: could not queue command_id={comment_id} reason={exc}")

    def _handle_action_command(
        self,
        *,
        task: dict[str, Any],
        comment_id: int,
        action_cmd: ActionCommand,
        binding: dict[str, str] | None,
        confirmations: dict[str, tuple[int, datetime, str | None]],
        used_confirmations: set[str],
    ) -> None:
        task_id = int(task["id"])
        if not binding:
            self._post_bridge_comment(task_id, f"blocked: missing or invalid binding for action (comment_id={comment_id})")
            return

        if action_cmd.action_id in used_confirmations:
            self._post_bridge_comment(task_id, f"blocked: confirmation already used (action_id={action_cmd.action_id})")
            return

        token = confirmations.get(action_cmd.action_id)
        if not token:
            self._post_bridge_comment(
                task_id,
                f"blocked: missing confirmation for action_id={action_cmd.action_id} expected `confirm: {action_cmd.action_id}`",
            )
            return

        confirm_comment_id, confirm_created, confirm_author = token
        if confirm_comment_id >= comment_id:
            self._post_bridge_comment(
                task_id,
                f"blocked: confirmation must be before action command (action_id={action_cmd.action_id})",
            )
            return

        if datetime.now(timezone.utc) - confirm_created > self.confirm_ttl:
            self._post_bridge_comment(
                task_id,
                f"blocked: confirmation expired (action_id={action_cmd.action_id})",
            )
            return

        if self.confirm_allowed_users and (not confirm_author or confirm_author not in self.confirm_allowed_users):
            allowed = ", ".join(sorted(self.confirm_allowed_users))
            self._post_bridge_comment(
                task_id,
                "blocked: confirmation author not allowed "
                f"(action_id={action_cmd.action_id} author={confirm_author or 'unknown'} allowed={allowed})",
            )
            return

        project_id = int(task.get("project_id", self.project_id))
        try:
            if self.dry_run:
                self._post_bridge_comment(
                    task_id,
                    "ack: dry-run action="
                    f"{action_cmd.action} bucket={action_cmd.bucket_id} action_id={action_cmd.action_id}",
                )
                return

            if action_cmd.action == "reopen":
                self.client.update_task(task_id=task_id, updates={"done": False})

            self.client.move_task(task_id=task_id, target_bucket_id=action_cmd.bucket_id, project_id=project_id)
            used_confirmations.add(action_cmd.action_id)
            self._post_bridge_comment(
                task_id,
                "ack: executed action="
                f"{action_cmd.action} bucket={action_cmd.bucket_id} action_id={action_cmd.action_id}",
            )
        except Exception as exc:
            self._post_bridge_comment(
                task_id,
                f"blocked: action failed action_id={action_cmd.action_id} reason={exc}",
            )

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
    parser.add_argument(
        "--confirm-ttl-hours",
        type=int,
        default=int(os.getenv("BRIDGE_CONFIRM_TTL_HOURS", "24")),
        help="How long confirmation tokens remain valid",
    )
    parser.add_argument(
        "--confirm-allowed-users",
        default=os.getenv("BRIDGE_CONFIRM_ALLOWED_USERS", ""),
        help="Comma-separated usernames allowed to authorize `confirm:` tokens (empty = no restriction)",
    )
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
            confirm_ttl_hours=args.confirm_ttl_hours,
            confirm_allowed_users=parse_allowed_users(args.confirm_allowed_users),
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
