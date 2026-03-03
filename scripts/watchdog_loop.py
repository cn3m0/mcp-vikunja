#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_monitor(full: bool) -> tuple[bool, dict]:
    cmd = ["python3", "scripts/monitor_stack.py", "--json"]
    if full:
        cmd.append("--full")
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, check=False)

    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "summary": "invalid json from monitor_stack", "raw": proc.stdout}
            return False, payload
        return True, payload

    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if not payload:
        payload = {
            "ok": False,
            "summary": "monitor_stack failed",
            "stderr": proc.stderr.strip(),
            "stdout": proc.stdout.strip(),
        }
    return False, payload


def write_status(path: Path, status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp.replace(path)


def maybe_notify(notify_command: str, status: dict) -> None:
    if not notify_command:
        return
    summary = str(status.get("summary", "watchdog failure"))
    cmd = notify_command.replace("{summary}", summary)
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT), check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodic watchdog loop for mcp-vikunja monitoring")
    parser.add_argument("--interval-seconds", type=int, default=120, help="Loop interval in seconds")
    parser.add_argument(
        "--full-every",
        type=int,
        default=15,
        help="Run full smoke every N cycles (0 disables full mode)",
    )
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument(
        "--status-file",
        default="/tmp/mcp-vikunja-watchdog/status.json",
        help="Path to write latest watchdog status JSON",
    )
    parser.add_argument(
        "--notify-command",
        default="",
        help="Optional shell command on failure. Placeholder: {summary}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cycle = 0
    failures = 0

    while True:
        cycle += 1
        full = args.full_every > 0 and (cycle % args.full_every == 0)
        ok, payload = run_monitor(full=full)

        now = datetime.now(timezone.utc).isoformat()
        status = {
            "timestamp": now,
            "cycle": cycle,
            "full": full,
            "ok": ok and bool(payload.get("ok", True)),
            "summary": payload.get("summary", "no summary"),
            "monitor": payload,
        }

        if status["ok"]:
            failures = 0
            print(f"[{now}] [OK] cycle={cycle} full={full} summary={status['summary']}")
        else:
            failures += 1
            status["consecutive_failures"] = failures
            print(f"[{now}] [FAIL] cycle={cycle} full={full} summary={status['summary']}")
            maybe_notify(args.notify_command, status)

        write_status(Path(args.status_file), status)

        if args.once:
            return 0 if status["ok"] else 1

        time.sleep(max(args.interval_seconds, 5))


if __name__ == "__main__":
    raise SystemExit(main())
