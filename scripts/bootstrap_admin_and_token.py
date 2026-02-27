#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ensure_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        if not ENV_EXAMPLE_PATH.exists():
            print("ERROR: Missing .env.example", file=sys.stderr)
            sys.exit(1)
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print("Created .env from .env.example")
    return load_env_file(ENV_PATH)


def write_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def run_compose(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", *args]
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def wait_for_vikunja(api_base: str, timeout_seconds: int = 180) -> None:
    info_url = f"{api_base.rstrip('/')}/info"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(info_url, timeout=5) as response:
                if response.status < 500:
                    print("Vikunja API reachable.")
                    return
        except Exception:
            pass
        time.sleep(3)
    print(f"ERROR: Vikunja API not reachable within {timeout_seconds}s at {info_url}", file=sys.stderr)
    sys.exit(1)


def json_request(
    method: str,
    url: str,
    payload: dict | None = None,
    token: str | None = None,
) -> dict:
    data = None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} on {url}: {body}") from exc


def create_or_verify_admin(username: str, email: str, password: str) -> None:
    result = run_compose(
        [
            "exec",
            "-T",
            "vikunja",
            "/app/vikunja/vikunja",
            "user",
            "create",
            "--username",
            username,
            "--email",
            email,
            "--password",
            password,
        ],
        check=False,
    )
    if result.returncode == 0:
        print(f"Admin user '{username}' created.")
        return

    output = f"{result.stdout}\n{result.stderr}".lower()
    if "already exists" in output or "already taken" in output:
        print(f"Admin user '{username}' already exists.")
        return

    print("ERROR: could not create admin user", file=sys.stderr)
    print(result.stdout, file=sys.stderr)
    print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)


def main() -> None:
    env = ensure_env_file()

    username = env.get("VIKUNJA_ADMIN_USERNAME", "admin")
    email = env.get("VIKUNJA_ADMIN_EMAIL", "admin@example.local")
    password = env.get("VIKUNJA_ADMIN_PASSWORD", "ChangeMe123!")
    token_title = env.get("VIKUNJA_API_TOKEN_TITLE", "codex-mcp-token")
    public_url = env.get("VIKUNJA_PUBLIC_URL", "http://localhost:3456/").rstrip("/")
    api_base = f"{public_url}/api/v1"

    print("Waiting for Vikunja API...")
    wait_for_vikunja(api_base)
    create_or_verify_admin(username, email, password)

    login = json_request(
        "POST",
        f"{api_base}/login",
        payload={"username": username, "password": password, "long_token": True},
    )
    jwt_token = login.get("token")
    if not jwt_token:
        print("ERROR: Login succeeded but no JWT token returned.", file=sys.stderr)
        sys.exit(1)

    routes = json_request("GET", f"{api_base}/routes", token=jwt_token)
    if not isinstance(routes, dict) or not routes:
        print("ERROR: Could not fetch token permissions from /routes.", file=sys.stderr)
        sys.exit(1)
    permissions = {
        resource: list(actions.keys())
        for resource, actions in routes.items()
        if isinstance(actions, dict) and actions
    }

    expires_at = (datetime.now(UTC) + timedelta(days=3650)).replace(microsecond=0).isoformat()
    if expires_at.endswith("+00:00"):
        expires_at = expires_at.replace("+00:00", "Z")

    created_token = json_request(
        "PUT",
        f"{api_base}/tokens",
        payload={
            "title": token_title,
            "expires_at": expires_at,
            "permissions": permissions,
        },
        token=jwt_token,
    )
    api_token = created_token.get("token")
    if not api_token:
        print("ERROR: API token was not returned from /tokens.", file=sys.stderr)
        sys.exit(1)

    write_env_value(ENV_PATH, "VIKUNJA_API_TOKEN", api_token)
    print("VIKUNJA_API_TOKEN was written to .env")


if __name__ == "__main__":
    main()
