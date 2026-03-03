#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER_PATH = ROOT / "mcp_adapter"
sys.path.insert(0, str(MCP_ADAPTER_PATH))

from vikunja_mcp.vikunja_api import VikunjaApiError, VikunjaClient  # noqa: E402


LOGGER = logging.getLogger("session-bridge-loop")
BRIDGE_PREFIX = "[bridge]"


@dataclass
class WorkOrder:
    path: Path
    task_id: int
    comment_id: int
    command: str
    session: str
    body: str


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


def parse_csv_paths(raw: str | None) -> list[Path]:
    if raw is None:
        return []
    values: list[Path] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        values.append(Path(text).expanduser())
    return values


def normalize_tmux_target(session: str | None, default_target: str | None) -> str | None:
    candidate = (session or "").strip()
    if candidate:
        if ":" in candidate:
            return candidate
        return f"{candidate}:0.0"
    fallback = (default_target or "").strip()
    if not fallback:
        return None
    return fallback


def parse_work_order(path: Path) -> WorkOrder | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    meta: dict[str, str] = {}
    body_lines: list[str] = []
    in_body = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.strip() == "## Body":
            in_body = True
            continue
        if in_body:
            body_lines.append(line)
            continue
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            meta[key.strip().lower()] = value.strip()

    try:
        task_id = int(meta.get("task_id", "0"))
        comment_id = int(meta.get("comment_id", "0"))
    except ValueError:
        return None

    if task_id <= 0 or comment_id <= 0:
        return None

    return WorkOrder(
        path=path,
        task_id=task_id,
        comment_id=comment_id,
        command=meta.get("command", "").strip().lower(),
        session=meta.get("session", "").strip(),
        body="\n".join(body_lines).strip(),
    )


def parse_reply_line(line: str, reply_prefix: str) -> tuple[int, str] | None:
    text = line.strip()
    prefix = reply_prefix.strip()
    if not prefix:
        return None
    if not text.startswith(prefix):
        return None

    # Expected: BRIDGE_REPLY task=31 message text...
    remainder = text[len(prefix) :].strip()
    if not remainder.startswith("task="):
        return None
    pieces = remainder.split(maxsplit=1)
    task_part = pieces[0]
    message = pieces[1].strip() if len(pieces) > 1 else ""
    try:
        task_id = int(task_part.split("=", 1)[1])
    except (IndexError, ValueError):
        return None
    if task_id <= 0 or not message:
        return None
    return task_id, message


class SessionBridgeState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, object] = {
            "processed_work_orders": [],
            "posted_reply_hashes": [],
            "tmux_log_offset": 0,
        }
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            LOGGER.warning("Invalid session bridge state file, starting clean: %s", self.path)
            return
        if isinstance(payload, dict):
            self._data.update(payload)

    @property
    def processed_work_orders(self) -> set[str]:
        values = self._data.get("processed_work_orders") or []
        if not isinstance(values, list):
            return set()
        return {str(v) for v in values if str(v).strip()}

    @property
    def posted_reply_hashes(self) -> set[str]:
        values = self._data.get("posted_reply_hashes") or []
        if not isinstance(values, list):
            return set()
        return {str(v) for v in values if str(v).strip()}

    @property
    def tmux_log_offset(self) -> int:
        raw = self._data.get("tmux_log_offset", 0)
        try:
            return max(int(raw), 0)
        except (TypeError, ValueError):
            return 0

    def mark_processed_work_order(self, key: str) -> None:
        current = list(self.processed_work_orders)
        if key in current:
            return
        current.append(key)
        self._data["processed_work_orders"] = current[-5000:]
        self._dirty = True

    def mark_posted_reply_hash(self, value: str) -> None:
        current = list(self.posted_reply_hashes)
        if value in current:
            return
        current.append(value)
        self._data["posted_reply_hashes"] = current[-5000:]
        self._dirty = True

    def set_tmux_log_offset(self, offset: int) -> None:
        normalized = max(int(offset), 0)
        if normalized == self.tmux_log_offset:
            return
        self._data["tmux_log_offset"] = normalized
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self._dirty = False


class SessionBridgeLoop:
    def __init__(
        self,
        *,
        client: VikunjaClient,
        state_file: Path,
        tmux_log_file: Path,
        inbox_roots: list[Path],
        default_tmux_target: str,
        reply_prefix: str,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.state = SessionBridgeState(state_file)
        self.tmux_log_file = tmux_log_file
        self.inbox_roots = inbox_roots
        self.default_tmux_target = default_tmux_target.strip()
        self.reply_prefix = reply_prefix.strip()
        self.dry_run = dry_run
        self._pipe_targets: set[str] = set()

    def run_once(self) -> None:
        self._dispatch_work_orders()
        self._sync_replies_from_tmux_log()
        self.state.save()

    def _discover_work_order_files(self) -> list[Path]:
        files: list[Path] = []
        for root in self.inbox_roots:
            if not root.exists():
                continue
            for path in root.rglob("task-*-comment-*.md"):
                if path.parent.name != "inbox":
                    continue
                files.append(path)
        files.sort(key=lambda p: str(p))
        return files

    def _dispatch_work_orders(self) -> None:
        processed = self.state.processed_work_orders
        for path in self._discover_work_order_files():
            work_order = parse_work_order(path)
            if work_order is None:
                continue
            key = f"{work_order.task_id}:{work_order.comment_id}"
            if key in processed:
                continue

            target = normalize_tmux_target(work_order.session, self.default_tmux_target)
            if not target:
                LOGGER.warning(
                    "No tmux target resolved for task#%s comment#%s (session=%r)",
                    work_order.task_id,
                    work_order.comment_id,
                    work_order.session,
                )
                continue

            if self._send_work_order_to_tmux(work_order, target):
                LOGGER.info(
                    "Dispatched work-order task#%s comment#%s to tmux target %s",
                    work_order.task_id,
                    work_order.comment_id,
                    target,
                )
                self.state.mark_processed_work_order(key)

    def _sync_replies_from_tmux_log(self) -> None:
        if not self.tmux_log_file.exists():
            return

        try:
            size = self.tmux_log_file.stat().st_size
            offset = self.state.tmux_log_offset
            if offset > size:
                offset = 0
            with self.tmux_log_file.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                lines = handle.readlines()
                new_offset = handle.tell()
        except OSError as exc:
            LOGGER.warning("Could not read tmux log file %s: %s", self.tmux_log_file, exc)
            return

        if not lines:
            self.state.set_tmux_log_offset(new_offset)
            return

        seen = self.state.posted_reply_hashes
        for line in lines:
            parsed = parse_reply_line(line, self.reply_prefix)
            if not parsed:
                continue
            task_id, message = parsed
            item_hash = hashlib.sha256(f"{task_id}:{message}".encode("utf-8")).hexdigest()
            if item_hash in seen:
                continue
            comment = (
                f"{BRIDGE_PREFIX} update: session-reply\n\n"
                f"- source: tmux\n"
                f"- bridge_reply: `{self.reply_prefix}`\n\n"
                f"{message}"
            )
            if self.dry_run:
                LOGGER.info("Dry-run: would post session reply task#%s: %s", task_id, message)
            else:
                try:
                    self.client.add_task_comment(task_id=task_id, comment=comment)
                except Exception as exc:
                    LOGGER.warning("Could not post session reply task#%s: %s", task_id, exc)
                    continue
            self.state.mark_posted_reply_hash(item_hash)
            seen.add(item_hash)

        self.state.set_tmux_log_offset(new_offset)

    def _send_work_order_to_tmux(self, work_order: WorkOrder, target: str) -> bool:
        if not self._ensure_tmux_pipe(target):
            return False
        lines = [
            (
                f"[vikunja-bridge] new work-order task={work_order.task_id} "
                f"comment={work_order.comment_id} command={work_order.command or 'n/a'}"
            ),
            f"[vikunja-bridge] file={work_order.path}",
            (
                "[vikunja-bridge] reply format: "
                f"{self.reply_prefix} task={work_order.task_id} <message>"
            ),
        ]
        if work_order.body:
            preview = work_order.body.replace("\n", " ").strip()
            if len(preview) > 220:
                preview = preview[:220] + "..."
            lines.append(f"[vikunja-bridge] body={preview}")

        if self.dry_run:
            for line in lines:
                LOGGER.info("Dry-run: tmux target=%s line=%s", target, line)
            return True

        for line in lines:
            command = f"echo {shlex.quote(line)}"
            proc = subprocess.run(
                ["tmux", "send-keys", "-t", target, command, "C-m"],
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.warning(
                    "tmux send-keys failed target=%s rc=%s stderr=%s",
                    target,
                    proc.returncode,
                    (proc.stderr or "").strip(),
                )
                return False
        return True

    def _ensure_tmux_pipe(self, target: str) -> bool:
        if target in self._pipe_targets:
            return True

        self.tmux_log_file.parent.mkdir(parents=True, exist_ok=True)
        if self.dry_run:
            self._pipe_targets.add(target)
            return True

        check_proc = subprocess.run(
            ["tmux", "list-panes", "-t", target],
            text=True,
            capture_output=True,
            check=False,
        )
        if check_proc.returncode != 0:
            LOGGER.warning(
                "tmux target not available: %s (stderr=%s)",
                target,
                (check_proc.stderr or "").strip(),
            )
            return False

        pipe_command = f"cat >> {shlex.quote(str(self.tmux_log_file))}"
        pipe_proc = subprocess.run(
            ["tmux", "pipe-pane", "-o", "-t", target, pipe_command],
            text=True,
            capture_output=True,
            check=False,
        )
        if pipe_proc.returncode != 0:
            LOGGER.warning(
                "tmux pipe-pane failed target=%s rc=%s stderr=%s",
                target,
                pipe_proc.returncode,
                (pipe_proc.stderr or "").strip(),
            )
            return False

        self._pipe_targets.add(target)
        return True


def build_client() -> VikunjaClient:
    base_url = os.getenv("VIKUNJA_URL", "http://localhost:3456/api/v1")
    token = os.getenv("VIKUNJA_API_TOKEN", "")
    timeout = float(os.getenv("VIKUNJA_TIMEOUT", "15"))
    return VikunjaClient(base_url=base_url, token=token, timeout=timeout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge Vikunja work-order inbox with tmux session replies")
    parser.add_argument(
        "--state-file",
        default=os.getenv("BRIDGE_SESSION_STATE_FILE", "/tmp/mcp-vikunja-session-bridge/state.json"),
        help="State file for processed work-orders and tmux log offsets",
    )
    parser.add_argument(
        "--tmux-log-file",
        default=os.getenv("BRIDGE_SESSION_TMUX_LOG_FILE", "/tmp/mcp-vikunja-session-bridge/tmux-output.log"),
        help="tmux pipe-pane output log file",
    )
    parser.add_argument(
        "--inbox-roots",
        default=os.getenv("BRIDGE_SESSION_INBOX_ROOTS", "./runtime/bridge-work"),
        help="Comma-separated root paths scanned recursively for inbox task files",
    )
    parser.add_argument(
        "--default-tmux-target",
        default=os.getenv("BRIDGE_SESSION_TMUX_TARGET", ""),
        help="Fallback tmux target if no session is available in work-order metadata",
    )
    parser.add_argument(
        "--reply-prefix",
        default=os.getenv("BRIDGE_SESSION_REPLY_PREFIX", "BRIDGE_REPLY"),
        help="Line prefix parsed from tmux output for ticket replies",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=int(os.getenv("BRIDGE_SESSION_POLL_INTERVAL", "5")),
        help="Polling interval in seconds",
    )
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Do not send tmux keys or post comments")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    inbox_roots = parse_csv_paths(args.inbox_roots)
    if not inbox_roots:
        LOGGER.error("No inbox roots configured. Set --inbox-roots or BRIDGE_SESSION_INBOX_ROOTS.")
        return 2

    try:
        loop = SessionBridgeLoop(
            client=build_client(),
            state_file=Path(args.state_file).expanduser(),
            tmux_log_file=Path(args.tmux_log_file).expanduser(),
            inbox_roots=inbox_roots,
            default_tmux_target=args.default_tmux_target,
            reply_prefix=args.reply_prefix,
            dry_run=args.dry_run,
        )
        if args.once:
            loop.run_once()
            return 0

        interval = max(int(args.poll_interval_seconds), 1)
        LOGGER.info(
            "Starting session bridge loop (inbox_roots=%s interval=%ss dry_run=%s)",
            [str(p) for p in inbox_roots],
            interval,
            args.dry_run,
        )
        while True:
            loop.run_once()
            time.sleep(interval)
    except VikunjaApiError as exc:
        LOGGER.error("Vikunja API error: %s", exc)
        return 1
    except KeyboardInterrupt:
        LOGGER.info("Session bridge loop interrupted")
        return 0
    except Exception as exc:  # pragma: no cover - top-level safety
        LOGGER.exception("Session bridge loop failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
