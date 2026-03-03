from __future__ import annotations

import argparse
import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("vikunja-bridge-webhook")


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


def parse_lower_csv_set(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    values = {part.strip().lower() for part in raw.split(",") if part.strip()}
    if not values:
        return None
    return values


def parse_int_csv_set(raw: str | None) -> set[int] | None:
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


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_project_ids(payload: dict[str, Any]) -> set[int]:
    project_ids: set[int] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_l = str(key).lower()
                if key_l in {"project_id", "projectid"}:
                    parsed = _as_int(value)
                    if parsed is not None:
                        project_ids.add(parsed)
                elif key_l == "project" and isinstance(value, dict):
                    parsed = _as_int(value.get("id"))
                    if parsed is not None:
                        project_ids.add(parsed)
                elif key_l == "task" and isinstance(value, dict):
                    parsed = _as_int(value.get("project_id"))
                    if parsed is not None:
                        project_ids.add(parsed)
                    project_obj = value.get("project")
                    if isinstance(project_obj, dict):
                        parsed = _as_int(project_obj.get("id"))
                        if parsed is not None:
                            project_ids.add(parsed)
                walk(value)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return project_ids


def resolve_event_name(header_event: str | None, payload: dict[str, Any]) -> str:
    header = (header_event or "").strip()
    if header:
        return header.lower()
    for key in ("event", "event_name", "type"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def should_accept_webhook(
    *,
    event_name: str,
    project_ids: set[int],
    allowed_events: set[str] | None,
    allowed_project_ids: set[int] | None,
    require_project_match: bool,
) -> tuple[bool, str]:
    if allowed_events is not None:
        if not event_name or event_name not in allowed_events:
            return False, "event"

    if allowed_project_ids is not None:
        if not project_ids:
            if require_project_match:
                return False, "project_missing"
        elif project_ids.isdisjoint(allowed_project_ids):
            return False, "project"

    return True, "accepted"


def parse_bearer_token(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    if not text:
        return ""
    prefix = "bearer "
    if text.lower().startswith(prefix):
        return text[len(prefix) :].strip()
    return ""


def is_authorized(*, expected_token: str, header_token: str | None, authorization_header: str | None) -> bool:
    token = expected_token.strip()
    if not token:
        return True

    direct = (header_token or "").strip()
    if direct and direct == token:
        return True

    bearer = parse_bearer_token(authorization_header)
    if bearer and bearer == token:
        return True

    return False


def write_trigger_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(path)


class BridgeWebhookHandler(BaseHTTPRequestHandler):
    server: "BridgeWebhookServer"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json(HTTPStatus.OK, {"ok": True, "service": "bridge-webhook"})
            return
        self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != self.server.webhook_path:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return

        if not is_authorized(
            expected_token=self.server.webhook_token,
            header_token=self.headers.get("X-Bridge-Webhook-Token"),
            authorization_header=self.headers.get("Authorization"),
        ):
            self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length < 0:
            content_length = 0
        if content_length > self.server.max_body_bytes:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "payload_too_large"})
            return

        body = self.rfile.read(content_length) if content_length else b""
        payload: dict[str, Any] = {
            "received_at": self.server.now_fn(),
            "source_ip": self.client_address[0] if self.client_address else "",
            "content_length": content_length,
            "event": "",
        }
        body_payload: dict[str, Any] = {}

        if body:
            try:
                parsed = json.loads(body.decode("utf-8"))
                if isinstance(parsed, dict):
                    body_payload = parsed
                    payload["body"] = parsed
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload["body_raw"] = body.decode("utf-8", errors="replace")[:2048]

        event_name = resolve_event_name(self.headers.get("X-Vikunja-Event"), body_payload)
        project_ids = extract_project_ids(body_payload)
        payload["event"] = event_name
        if project_ids:
            payload["project_ids"] = sorted(project_ids)

        accepted, reason = should_accept_webhook(
            event_name=event_name,
            project_ids=project_ids,
            allowed_events=self.server.allowed_events,
            allowed_project_ids=self.server.allowed_project_ids,
            require_project_match=self.server.require_project_match,
        )
        if not accepted:
            LOGGER.info(
                "Webhook ignored: reason=%s event=%s projects=%s",
                reason,
                event_name or "<none>",
                sorted(project_ids) if project_ids else [],
            )
            self._json(HTTPStatus.ACCEPTED, {"ok": True, "queued": False, "ignored": True, "reason": reason})
            return

        try:
            write_trigger_file(self.server.trigger_file, payload)
        except Exception as exc:  # pragma: no cover - io/runtime safety
            LOGGER.warning("Could not write trigger file %s: %s", self.server.trigger_file, exc)
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "trigger_write_failed"})
            return

        LOGGER.info("Webhook accepted; trigger file updated: %s", self.server.trigger_file)
        self._json(HTTPStatus.ACCEPTED, {"ok": True, "queued": True})

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        LOGGER.info("%s - %s", self.address_string(), fmt % args)


class BridgeWebhookServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        webhook_path: str,
        webhook_token: str,
        trigger_file: Path,
        max_body_bytes: int,
        allowed_events: set[str] | None,
        allowed_project_ids: set[int] | None,
        require_project_match: bool,
        now_fn,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.webhook_path = webhook_path
        self.webhook_token = webhook_token
        self.trigger_file = trigger_file
        self.max_body_bytes = max(int(max_body_bytes), 1024)
        self.allowed_events = allowed_events
        self.allowed_project_ids = allowed_project_ids
        self.require_project_match = require_project_match
        self.now_fn = now_fn


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Webhook trigger for Vikunja bridge worker")
    parser.add_argument("--host", default=os.getenv("BRIDGE_WEBHOOK_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BRIDGE_WEBHOOK_PORT", "8090")))
    parser.add_argument("--path", default=os.getenv("BRIDGE_WEBHOOK_PATH", "/vikunja/webhook"))
    parser.add_argument(
        "--token",
        default=os.getenv("BRIDGE_WEBHOOK_TOKEN", ""),
        help="Optional shared token (header X-Bridge-Webhook-Token or Authorization: Bearer <token>)",
    )
    parser.add_argument(
        "--trigger-file",
        default=os.getenv("BRIDGE_TRIGGER_FILE", "/var/lib/vikunja-bridge/trigger.signal"),
        help="Trigger file to touch for bridge-worker wakeup",
    )
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=int(os.getenv("BRIDGE_WEBHOOK_MAX_BODY_BYTES", "1048576")),
        help="Maximum accepted webhook payload size in bytes",
    )
    parser.add_argument(
        "--allowed-events",
        default=os.getenv("BRIDGE_WEBHOOK_ALLOWED_EVENTS", ""),
        help="Optional comma-separated webhook event names to accept",
    )
    parser.add_argument(
        "--allowed-project-ids",
        default=os.getenv("BRIDGE_WEBHOOK_ALLOWED_PROJECT_IDS", ""),
        help="Optional comma-separated project IDs to accept",
    )
    parser.add_argument(
        "--require-project-match",
        action=argparse.BooleanOptionalAction,
        default=parse_bool(os.getenv("BRIDGE_WEBHOOK_REQUIRE_PROJECT_MATCH"), False),
        help="If true, reject webhooks with no detectable project id when project filter is enabled",
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")

    webhook_path = str(args.path).strip() or "/vikunja/webhook"
    if not webhook_path.startswith("/"):
        webhook_path = f"/{webhook_path}"

    server = BridgeWebhookServer(
        (args.host, int(args.port)),
        BridgeWebhookHandler,
        webhook_path=webhook_path,
        webhook_token=str(args.token or ""),
        trigger_file=Path(args.trigger_file).expanduser(),
        max_body_bytes=args.max_body_bytes,
        allowed_events=parse_lower_csv_set(args.allowed_events),
        allowed_project_ids=parse_int_csv_set(args.allowed_project_ids),
        require_project_match=bool(args.require_project_match),
        now_fn=_now_iso,
    )
    LOGGER.info(
        "Starting bridge-webhook on %s:%s path=%s trigger_file=%s token=%s allowed_events=%s allowed_project_ids=%s require_project_match=%s",
        args.host,
        args.port,
        webhook_path,
        server.trigger_file,
        "set" if args.token else "off",
        sorted(server.allowed_events) if server.allowed_events else None,
        sorted(server.allowed_project_ids) if server.allowed_project_ids else None,
        server.require_project_match,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping bridge-webhook")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
