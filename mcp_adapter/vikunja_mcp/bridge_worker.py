from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
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
    return parse_lower_set(raw)


def parse_lower_set(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    values = {part.strip().lower() for part in raw.split(",") if part.strip()}
    if not values:
        return None
    return values


def parse_int_set(raw: str | None) -> set[int] | None:
    if raw is None:
        return None
    values: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            values.add(int(token))
        except ValueError:
            continue
    if not values:
        return None
    return values


def parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def compute_backoff_seconds(consecutive_failures: int, min_seconds: int, max_seconds: int) -> int:
    min_delay = max(int(min_seconds), 1)
    max_delay = max(int(max_seconds), min_delay)
    failures = max(int(consecutive_failures), 0)
    if failures <= 0:
        return min_delay
    delay = min_delay * (2 ** (failures - 1))
    return min(delay, max_delay)


def render_notify_command(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def comment_author_username(comment: dict[str, Any]) -> str | None:
    author = comment.get("author") if isinstance(comment, dict) else None
    if not isinstance(author, dict):
        return None
    username = str(author.get("username", "")).strip()
    return username.lower() if username else None


def parse_mode_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip().lower()
    if not text:
        return None

    # Accept either `mode=ai|human` or plain `ai|human`.
    if "=" in text:
        key, value = text.split("=", 1)
        if key.strip() != "mode":
            return None
        text = value.strip()

    if text in {"ai", "human"}:
        return text
    return None


def read_mode_file(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            mode = parse_mode_value(line)
            if mode:
                return mode
    except OSError:
        return None
    return None


def task_mode(task: dict[str, Any], fallback_mode: str | None = None) -> str:
    titles = task_label_titles(task)
    if "mode/human" in titles:
        return "human"
    if "mode/ai" in titles:
        return "ai"
    if fallback_mode == "ai":
        return "ai"
    return "human"


def task_label_titles(task: dict[str, Any]) -> set[str]:
    labels = task.get("labels") or []
    return {str(label.get("title", "")).lower() for label in labels if isinstance(label, dict)}


def should_process_task(
    task: dict[str, Any],
    *,
    mode: str,
    skip_done: bool,
    allowed_bucket_ids: set[int] | None,
    required_labels: set[str] | None,
) -> tuple[bool, str]:
    if mode != "ai":
        return False, "mode"

    if skip_done and bool(task.get("done", False)):
        return False, "done"

    if allowed_bucket_ids is not None:
        bucket_id = task.get("bucket_id")
        try:
            bucket = int(bucket_id)
        except (TypeError, ValueError):
            return False, "bucket"
        if bucket not in allowed_bucket_ids:
            return False, "bucket"

    if required_labels is not None:
        titles = task_label_titles(task)
        if titles.isdisjoint(required_labels):
            return False, "labels"

    return True, "selected"


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
        notify_command: str = "",
        notify_timeout_seconds: int = 8,
        mode_file_path: Path | None = None,
        skip_done: bool = True,
        allowed_bucket_ids: set[int] | None = None,
        required_labels: set[str] | None = None,
        pending_comments_path: Path | None = None,
        pending_comments_max: int = 500,
    ) -> None:
        self.client = client
        self.project_id = project_id
        self.state = BridgeState(state_path)
        self.dry_run = dry_run
        self.confirm_ttl = timedelta(hours=max(confirm_ttl_hours, 1))
        self.confirm_allowed_users = confirm_allowed_users
        self.notify_command = notify_command.strip()
        self.notify_timeout_seconds = max(notify_timeout_seconds, 1)
        self.mode_file_path = mode_file_path
        self.skip_done = skip_done
        self.allowed_bucket_ids = allowed_bucket_ids
        self.required_labels = required_labels
        if pending_comments_path is None:
            pending_comments_path = state_path.parent / "pending-bridge-comments.jsonl"
        self.pending_comments_path = pending_comments_path
        self.pending_comments_max = max(int(pending_comments_max), 1)

    def run_once(self) -> None:
        tasks = self.client.list_tasks(project_id=self.project_id, page=1, per_page=300)
        self._flush_pending_bridge_comments(limit=50)
        fallback_mode = read_mode_file(self.mode_file_path)
        if self.mode_file_path and fallback_mode:
            LOGGER.info("Bridge mode fallback from file %s => %s", self.mode_file_path, fallback_mode)
        LOGGER.info("Found %d tasks in project %s", len(tasks), self.project_id)

        selected = 0
        skipped_mode = 0
        skipped_done = 0
        skipped_bucket = 0
        skipped_labels = 0

        for task in sorted(tasks, key=lambda t: int(t.get("id", 0))):
            mode = task_mode(task, fallback_mode=fallback_mode)
            allowed, reason = should_process_task(
                task,
                mode=mode,
                skip_done=self.skip_done,
                allowed_bucket_ids=self.allowed_bucket_ids,
                required_labels=self.required_labels,
            )
            if not allowed:
                if reason == "mode":
                    skipped_mode += 1
                elif reason == "done":
                    skipped_done += 1
                elif reason == "bucket":
                    skipped_bucket += 1
                elif reason == "labels":
                    skipped_labels += 1
                continue
            selected += 1
            self._process_task(task)

        LOGGER.info(
            "Selection summary: selected=%d skipped_mode=%d skipped_done=%d skipped_bucket=%d skipped_labels=%d",
            selected,
            skipped_mode,
            skipped_done,
            skipped_bucket,
            skipped_labels,
        )
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
            notify_error = self._notify_queue_event(
                task=task,
                comment_id=comment_id,
                command_name=command_name,
                binding=binding,
                output_path=output_path,
            )
            if notify_error:
                self._post_bridge_comment(
                    task_id,
                    f"update: notify failed command={command_name} comment_id={comment_id} reason={notify_error}",
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
        try:
            self.client.add_task_comment(task_id=task_id, comment=content)
        except Exception as exc:
            LOGGER.warning("Could not post bridge comment task#%s, queued for retry: %s", task_id, exc)
            self._append_pending_bridge_comment(task_id=task_id, content=content, error=exc)

    def _read_pending_bridge_comments(self) -> list[dict[str, Any]]:
        path = self.pending_comments_path
        if path is None or not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and "task_id" in payload and "content" in payload:
                    rows.append(payload)
        except OSError:
            return []
        return rows

    def _write_pending_bridge_comments(self, rows: list[dict[str, Any]]) -> None:
        path = self.pending_comments_path
        if path is None:
            return
        if not rows:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        body = "\n".join(json.dumps(item, separators=(",", ":")) for item in rows) + "\n"
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)

    def _append_pending_bridge_comment(self, *, task_id: int, content: str, error: Exception) -> None:
        if self.dry_run:
            return
        rows = self._read_pending_bridge_comments()
        rows.append(
            {
                "task_id": int(task_id),
                "content": content,
                "attempts": 1,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "last_error": self._one_line(error),
            }
        )
        if len(rows) > self.pending_comments_max:
            rows = rows[-self.pending_comments_max :]
        self._write_pending_bridge_comments(rows)

    def _flush_pending_bridge_comments(self, *, limit: int = 50) -> None:
        if self.dry_run:
            return
        rows = self._read_pending_bridge_comments()
        if not rows:
            return

        kept: list[dict[str, Any]] = []
        sent = 0
        flush_limit = max(int(limit), 1)
        for row in rows:
            if sent >= flush_limit:
                kept.append(row)
                continue
            try:
                task_id = int(row.get("task_id", 0))
                content = str(row.get("content", "")).strip()
                if not task_id or not content:
                    continue
                self.client.add_task_comment(task_id=task_id, comment=content)
                sent += 1
            except Exception as exc:
                row["attempts"] = int(row.get("attempts", 0)) + 1
                row["updated_at"] = _now_iso()
                row["last_error"] = self._one_line(exc)
                kept.append(row)

        self._write_pending_bridge_comments(kept)
        if sent or len(kept) != len(rows):
            LOGGER.info(
                "Pending bridge comments flush: sent=%d remaining=%d",
                sent,
                len(kept),
            )

    @staticmethod
    def _one_line(value: Any) -> str:
        return str(value).replace("\n", " ").replace("\r", " ").strip()

    def _notify_queue_event(
        self,
        *,
        task: dict[str, Any],
        comment_id: int,
        command_name: str,
        binding: dict[str, str],
        output_path: str,
    ) -> str | None:
        if not self.notify_command:
            return None

        task_id = int(task["id"])
        values = {
            "task_id": str(task_id),
            "task_title": self._one_line(task.get("title", "")),
            "comment_id": str(comment_id),
            "command": command_name,
            "node": self._one_line(binding.get("node", "")),
            "session": self._one_line(binding.get("session", "")),
            "workdir": self._one_line(binding.get("workdir", "")),
            "file": self._one_line(output_path),
        }
        command = render_notify_command(self.notify_command, values)

        if self.dry_run:
            LOGGER.info("Dry-run: notify command: %s", command)
            return None

        try:
            proc = subprocess.run(
                ["bash", "-lc", command],
                text=True,
                capture_output=True,
                timeout=self.notify_timeout_seconds,
                check=False,
            )
            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                stdout = (proc.stdout or "").strip()
                details = stderr or stdout or f"exit_code={proc.returncode}"
                return self._one_line(details)[:240]
            return None
        except Exception as exc:
            return self._one_line(exc)[:240]


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
    parser.add_argument(
        "--notify-command",
        default=os.getenv("BRIDGE_NOTIFY_COMMAND", ""),
        help="Optional shell command for queue notifications (placeholders: {task_id}, {task_title}, {comment_id}, {command}, {node}, {session}, {workdir}, {file})",
    )
    parser.add_argument(
        "--notify-timeout-seconds",
        type=int,
        default=int(os.getenv("BRIDGE_NOTIFY_TIMEOUT_SECONDS", "8")),
        help="Timeout for notify shell command execution",
    )
    parser.add_argument(
        "--mode-file",
        default=os.getenv("BRIDGE_MODE_FILE", ""),
        help="Optional fallback mode file path (supports lines like `mode=ai` or `mode=human`)",
    )
    parser.add_argument(
        "--skip-done",
        action=argparse.BooleanOptionalAction,
        default=parse_bool(os.getenv("BRIDGE_SKIP_DONE"), True),
        help="Skip tasks already marked done (default: true)",
    )
    parser.add_argument(
        "--allowed-bucket-ids",
        default=os.getenv("BRIDGE_ALLOWED_BUCKET_IDS", ""),
        help="Optional comma-separated bucket IDs to process",
    )
    parser.add_argument(
        "--required-labels",
        default=os.getenv("BRIDGE_REQUIRED_LABELS", ""),
        help="Optional comma-separated labels required for processing",
    )
    parser.add_argument(
        "--pending-comments-file",
        default=os.getenv("BRIDGE_PENDING_COMMENTS_FILE", ""),
        help="Optional JSONL file for bridge comments that failed to post",
    )
    parser.add_argument(
        "--pending-comments-max",
        type=int,
        default=int(os.getenv("BRIDGE_PENDING_COMMENTS_MAX", "500")),
        help="Maximum queued pending bridge comments retained locally",
    )
    parser.add_argument(
        "--backoff-min-seconds",
        type=int,
        default=int(os.getenv("BRIDGE_BACKOFF_MIN_SECONDS", "5")),
        help="Retry backoff minimum delay in seconds for failed cycles",
    )
    parser.add_argument(
        "--backoff-max-seconds",
        type=int,
        default=int(os.getenv("BRIDGE_BACKOFF_MAX_SECONDS", "300")),
        help="Retry backoff maximum delay in seconds for failed cycles",
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
            notify_command=args.notify_command,
            notify_timeout_seconds=args.notify_timeout_seconds,
            mode_file_path=Path(args.mode_file).expanduser() if args.mode_file else None,
            skip_done=bool(args.skip_done),
            allowed_bucket_ids=parse_int_set(args.allowed_bucket_ids),
            required_labels=parse_lower_set(args.required_labels),
            pending_comments_path=Path(args.pending_comments_file).expanduser() if args.pending_comments_file else None,
            pending_comments_max=args.pending_comments_max,
        )
        if args.once:
            worker.run_once()
            return 0

        LOGGER.info("Starting bridge worker (project_id=%s interval=%ss)", args.project_id, args.interval)
        consecutive_failures = 0
        while True:
            try:
                worker.run_once()
                consecutive_failures = 0
                time.sleep(max(args.interval, 1))
            except VikunjaApiError as exc:
                consecutive_failures += 1
                delay = compute_backoff_seconds(
                    consecutive_failures=consecutive_failures,
                    min_seconds=args.backoff_min_seconds,
                    max_seconds=args.backoff_max_seconds,
                )
                LOGGER.warning(
                    "Bridge cycle failed (%d consecutive): %s; retry in %ss",
                    consecutive_failures,
                    exc,
                    delay,
                )
                time.sleep(delay)
            except Exception as exc:  # pragma: no cover - defensive runtime handling
                consecutive_failures += 1
                delay = compute_backoff_seconds(
                    consecutive_failures=consecutive_failures,
                    min_seconds=args.backoff_min_seconds,
                    max_seconds=args.backoff_max_seconds,
                )
                LOGGER.exception(
                    "Bridge cycle failed (%d consecutive): %s; retry in %ss",
                    consecutive_failures,
                    exc,
                    delay,
                )
                time.sleep(delay)
    except Exception as exc:  # pragma: no cover - defensive entrypoint
        LOGGER.exception("Fatal bridge worker error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
