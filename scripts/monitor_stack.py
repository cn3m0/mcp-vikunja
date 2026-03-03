#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    elapsed_ms: int


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


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def run_cmd(cmd: list[str], *, cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def check_compose_services(required: list[str]) -> CheckResult:
    start = time.perf_counter()
    proc = run_cmd(["docker", "compose", "ps", "--status", "running", "--services"], cwd=ROOT)
    elapsed = int((time.perf_counter() - start) * 1000)

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "docker compose ps failed"
        return CheckResult("compose-services", False, detail, elapsed)

    running = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    missing = [svc for svc in required if svc not in running]
    if missing:
        return CheckResult(
            "compose-services",
            False,
            f"missing running services: {', '.join(missing)} (running: {', '.join(sorted(running))})",
            elapsed,
        )
    return CheckResult("compose-services", True, f"running: {', '.join(sorted(running))}", elapsed)


def check_vikunja_info(base_public_url: str, timeout: float) -> CheckResult:
    start = time.perf_counter()
    info_url = f"{base_public_url.rstrip('/')}/api/v1/info"
    req = urllib.request.Request(info_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        version = str(payload.get("version", "unknown"))
        detail = f"reachable version={version}"
        ok = True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        ok = False
        detail = f"vikunja info check failed: {exc}"

    elapsed = int((time.perf_counter() - start) * 1000)
    return CheckResult("vikunja-info", ok, detail, elapsed)


def check_http_health(name: str, url: str, timeout: float) -> CheckResult:
    start = time.perf_counter()
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read().decode("utf-8", errors="replace")
        ok = 200 <= status < 300
        detail = f"status={status}"
        if raw:
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict) and payload:
                    preview = ", ".join(sorted(list(payload.keys()))[:4])
                    detail = f"{detail} keys={preview}"
            except json.JSONDecodeError:
                detail = f"{detail} body={raw[:80]}"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        ok = False
        detail = f"http health check failed: {exc}"
    elapsed = int((time.perf_counter() - start) * 1000)
    return CheckResult(name, ok, detail, elapsed)


def check_mcp_port(mcp_url: str, timeout: float) -> CheckResult:
    start = time.perf_counter()
    parsed = urllib.parse.urlparse(mcp_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        ok = True
        detail = f"tcp reachable at {host}:{port}"
    except OSError as exc:
        ok = False
        detail = f"tcp connect failed to {host}:{port}: {exc}"
    finally:
        sock.close()

    elapsed = int((time.perf_counter() - start) * 1000)
    return CheckResult("mcp-port", ok, detail, elapsed)


def check_full_smoke() -> list[CheckResult]:
    checks: list[CheckResult] = []

    start = time.perf_counter()
    verify = run_cmd(["python3", "scripts/verify_poc.py"], cwd=ROOT, timeout=120)
    elapsed = int((time.perf_counter() - start) * 1000)
    checks.append(
        CheckResult(
            "verify-poc",
            verify.returncode == 0,
            verify.stdout.strip().splitlines()[-1] if verify.stdout.strip() else (verify.stderr.strip() or "verify_poc failed"),
            elapsed,
        )
    )

    start = time.perf_counter()
    test_mcp = run_cmd(["python3", "scripts/test_mcp_adapter.py"], cwd=ROOT, timeout=120)
    elapsed = int((time.perf_counter() - start) * 1000)
    checks.append(
        CheckResult(
            "test-mcp-adapter",
            test_mcp.returncode == 0,
            test_mcp.stdout.strip().splitlines()[-1] if test_mcp.stdout.strip() else (test_mcp.stderr.strip() or "test_mcp_adapter failed"),
            elapsed,
        )
    )

    return checks


def maybe_alert(alert_command: str | None, overall_ok: bool, summary: str) -> None:
    if overall_ok or not alert_command:
        return
    env = os.environ.copy()
    env["MONITOR_SUMMARY"] = summary
    cmd = alert_command.replace("{summary}", summary)
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT), env=env, check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local health monitor for mcp-vikunja stack")
    parser.add_argument("--full", action="store_true", help="Also run verify_poc.py and test_mcp_adapter.py")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP/TCP timeout seconds")
    parser.add_argument(
        "--check-webhook",
        action="store_true",
        help="Also check bridge-webhook service and its /healthz endpoint",
    )
    parser.add_argument(
        "--alert-command",
        default="",
        help="Optional shell command executed on failure. Placeholder: {summary}",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    vikunja_public_url = os.getenv("VIKUNJA_PUBLIC_URL", "http://localhost:3456/")
    mcp_url = os.getenv("MCP_URL", "http://localhost:8000/mcp")
    check_webhook = args.check_webhook or parse_bool(os.getenv("BRIDGE_WEBHOOK_MONITOR"), False)
    webhook_health_url = os.getenv("BRIDGE_WEBHOOK_HEALTH_URL", "http://localhost:8090/healthz")

    required_services = ["db", "vikunja", "mcp-adapter"]
    if check_webhook:
        required_services.append("bridge-webhook")

    results: list[CheckResult] = [
        check_compose_services(required_services),
        check_vikunja_info(vikunja_public_url, timeout=args.timeout),
        check_mcp_port(mcp_url, timeout=args.timeout),
    ]
    if check_webhook:
        results.append(check_http_health("bridge-webhook-health", webhook_health_url, timeout=args.timeout))

    if args.full:
        results.extend(check_full_smoke())

    overall_ok = all(r.ok for r in results)
    summary = "; ".join([f"{r.name}={'ok' if r.ok else 'fail'}" for r in results])

    if args.json:
        payload = {
            "ok": overall_ok,
            "timestamp": int(time.time()),
            "summary": summary,
            "checks": [r.__dict__ for r in results],
        }
        print(json.dumps(payload, indent=2))
    else:
        for result in results:
            status = "OK" if result.ok else "FAIL"
            print(f"[{status}] {result.name} ({result.elapsed_ms}ms): {result.detail}")
        print(f"[SUMMARY] {'OK' if overall_ok else 'FAIL'} {summary}")

    maybe_alert(args.alert_command or None, overall_ok, summary)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
