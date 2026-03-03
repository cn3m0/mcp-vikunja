#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class DrillResult:
    backup_file: str
    sha256: str
    file_size_bytes: int
    restore_db: str
    counts: dict[str, int]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=input_bytes,
        text=input_bytes is None,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def docker_psql(user: str, password: str, db: str, sql: str, *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return run_cmd(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            f"PGPASSWORD={password}",
            "db",
            "psql",
            "-U",
            user,
            "-d",
            db,
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
            "-F",
            ",",
            "-c",
            sql,
        ],
        cwd=ROOT,
        timeout=timeout,
    )


def create_backup(backup_dir: Path, *, user: str, password: str, db_name: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_file = backup_dir / f"vikunja_{timestamp}.sql"

    with backup_file.open("wb") as handle:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "-e",
                f"PGPASSWORD={password}",
                "db",
                "pg_dump",
                "-U",
                user,
                "-d",
                db_name,
            ],
            cwd=str(ROOT),
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )

    if proc.returncode != 0:
        backup_file.unlink(missing_ok=True)
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "pg_dump failed")

    return backup_file


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def restore_and_verify(backup_file: Path, *, user: str, password: str, keep_restore_db: bool) -> tuple[str, dict[str, int]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    restore_db = f"vikunja_restore_drill_{stamp}"

    drop_sql = f'DROP DATABASE IF EXISTS "{restore_db}";'
    create_sql = f'CREATE DATABASE "{restore_db}";'

    for sql in (drop_sql, create_sql):
        proc = docker_psql(user, password, "postgres", sql)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"failed to run SQL: {sql}")

    restore_proc = run_cmd(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            f"PGPASSWORD={password}",
            "db",
            "psql",
            "-U",
            user,
            "-d",
            restore_db,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        cwd=ROOT,
        input_bytes=backup_file.read_bytes(),
        timeout=240,
    )

    if restore_proc.returncode != 0:
        raise RuntimeError(restore_proc.stderr.strip() or "restore failed")

    count_sql = (
        "SELECT "
        "(SELECT COUNT(*) FROM projects),"
        "(SELECT COUNT(*) FROM tasks),"
        "(SELECT COUNT(*) FROM task_comments);"
    )
    count_proc = docker_psql(user, password, restore_db, count_sql)
    if count_proc.returncode != 0:
        raise RuntimeError(count_proc.stderr.strip() or "count verification failed")

    line = next((ln.strip() for ln in count_proc.stdout.splitlines() if ln.strip()), "")
    parts = line.split(",") if line else []
    if len(parts) != 3:
        raise RuntimeError(f"unexpected verification output: {count_proc.stdout.strip()}")

    counts = {
        "projects": int(parts[0]),
        "tasks": int(parts[1]),
        "task_comments": int(parts[2]),
    }

    if not keep_restore_db:
        cleanup = docker_psql(user, password, "postgres", drop_sql)
        if cleanup.returncode != 0:
            raise RuntimeError(cleanup.stderr.strip() or "failed to drop restore database")

    return restore_db, counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup + restore drill for mcp-vikunja PostgreSQL")
    parser.add_argument(
        "--backup-dir",
        default="/tmp/mcp-vikunja-backups",
        help="Directory to write SQL dumps",
    )
    parser.add_argument(
        "--backup-file",
        default="",
        help="Use existing SQL dump file instead of creating a new backup",
    )
    parser.add_argument("--skip-restore", action="store_true", help="Only create backup and checksum")
    parser.add_argument("--keep-restore-db", action="store_true", help="Keep temporary restore DB for inspection")
    parser.add_argument("--report-file", default="", help="Optional path to write JSON report")
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    try:
        user = required_env("POSTGRES_USER")
        password = required_env("POSTGRES_PASSWORD")
        db_name = required_env("POSTGRES_DB")

        backup_file: Path
        if args.backup_file:
            backup_file = Path(args.backup_file).expanduser().resolve()
            if not backup_file.exists():
                raise RuntimeError(f"backup file does not exist: {backup_file}")
        else:
            backup_file = create_backup(Path(args.backup_dir).expanduser(), user=user, password=password, db_name=db_name)

        digest = sha256_file(backup_file)
        size = backup_file.stat().st_size

        restore_db = ""
        counts: dict[str, int] = {}
        if not args.skip_restore:
            restore_db, counts = restore_and_verify(
                backup_file,
                user=user,
                password=password,
                keep_restore_db=args.keep_restore_db,
            )

        result = DrillResult(
            backup_file=str(backup_file),
            sha256=digest,
            file_size_bytes=size,
            restore_db=restore_db,
            counts=counts,
        )

        print(f"[OK] backup: {result.backup_file}")
        print(f"[OK] sha256: {result.sha256}")
        print(f"[OK] size_bytes: {result.file_size_bytes}")
        if not args.skip_restore:
            print(f"[OK] restore_db: {result.restore_db or '(dropped)'}")
            print(f"[OK] counts: {json.dumps(result.counts)}")

        if args.report_file:
            report_path = Path(args.report_file).expanduser()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(result.__dict__, indent=2), encoding="utf-8")
            print(f"[OK] report: {report_path}")

        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
