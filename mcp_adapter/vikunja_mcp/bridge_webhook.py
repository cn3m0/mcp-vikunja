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
            "event": self.headers.get("X-Vikunja-Event", ""),
        }

        if body:
            try:
                parsed = json.loads(body.decode("utf-8"))
                if isinstance(parsed, dict):
                    payload["body"] = parsed
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload["body_raw"] = body.decode("utf-8", errors="replace")[:2048]

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
        now_fn,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.webhook_path = webhook_path
        self.webhook_token = webhook_token
        self.trigger_file = trigger_file
        self.max_body_bytes = max(int(max_body_bytes), 1024)
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
        now_fn=_now_iso,
    )
    LOGGER.info(
        "Starting bridge-webhook on %s:%s path=%s trigger_file=%s token=%s",
        args.host,
        args.port,
        webhook_path,
        server.trigger_file,
        "set" if args.token else "off",
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
