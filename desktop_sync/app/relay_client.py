from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from websockets.asyncio.client import connect as websocket_connect
from websockets.exceptions import ConnectionClosed

from .version import APP_NAME, APP_VERSION


LOGGER = logging.getLogger(APP_NAME)
DEFAULT_RELAY_URL = "http://127.0.0.1:8780"


@dataclass(slots=True)
class RelaySnapshot:
    configured_url: str
    status: str
    session_id: str | None = None
    mobile_url: str | None = None
    qr_svg_url: str | None = None
    expires_at: str | None = None
    last_error: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "configuredUrl": self.configured_url,
            "status": self.status,
            "sessionId": self.session_id,
            "mobileUrl": self.mobile_url,
            "qrSvgUrl": self.qr_svg_url,
            "expiresAt": self.expires_at,
            "lastError": self.last_error,
        }


class RelayClient:
    def __init__(self, message_handler: Callable[[dict[str, object]], Awaitable[None]]) -> None:
        self._message_handler = message_handler
        self._relay_url = os.getenv("REMOTE_ASSIST_RELAY_URL", DEFAULT_RELAY_URL).rstrip("/")
        self._snapshot_lock = threading.RLock()
        self._snapshot = RelaySnapshot(configured_url=self._relay_url, status="connecting")
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._ws = None
        self._send_lock = asyncio.Lock()
        self._session_id: str | None = None
        self._desktop_token: str | None = None
        self._resume_token: str | None = None

    def snapshot(self) -> RelaySnapshot:
        with self._snapshot_lock:
            return RelaySnapshot(
                configured_url=self._snapshot.configured_url,
                status=self._snapshot.status,
                session_id=self._snapshot.session_id,
                mobile_url=self._snapshot.mobile_url,
                qr_svg_url=self._snapshot.qr_svg_url,
                expires_at=self._snapshot.expires_at,
                last_error=self._snapshot.last_error,
            )

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_forever(), name="relay-client")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        websocket = self._ws
        if websocket is not None:
            with suppress(Exception):
                await websocket.close()
        task = self._task
        self._task = None
        with suppress(asyncio.CancelledError):
            task.cancel()
            await task

    async def send_business_message(self, mobile_id: str, payload: dict[str, object]) -> None:
        await self._send(
            {
                "type": "relay.desktop.message",
                "mobile_id": mobile_id,
                "payload": payload,
            }
        )

    async def close_mobile(self, mobile_id: str, reason: str, code: int) -> None:
        await self._send(
            {
                "type": "relay.close_mobile",
                "mobile_id": mobile_id,
                "reason": reason,
                "code": code,
            }
        )

    async def _run_forever(self) -> None:
        backoff_seconds = 2.0
        while not self._stop_event.is_set():
            try:
                await self._ensure_session()
                await self._connect_desktop_socket()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._set_snapshot(status="disconnected", last_error=f"云中继连接失败：{exc}")
                LOGGER.warning("relay_client_failure: %s", exc)
                await asyncio.sleep(backoff_seconds)

    async def _ensure_session(self) -> None:
        if self._session_id and self._desktop_token and self._resume_token:
            return
        self._set_snapshot(status="connecting", last_error=None)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._relay_url}/api/sessions",
                json={
                    "client_name": APP_NAME,
                    "version": APP_VERSION,
                },
            )
            response.raise_for_status()
            payload = response.json()

        self._session_id = payload["session_id"]
        self._desktop_token = payload["desktop_token"]
        self._resume_token = payload["resume_token"]
        self._set_snapshot(
            status="connecting",
            session_id=self._session_id,
            mobile_url=payload.get("mobile_url"),
            qr_svg_url=payload.get("qr_svg_url"),
            expires_at=payload.get("expires_at"),
            last_error=None,
        )

    async def _connect_desktop_socket(self) -> None:
        if not self._session_id or not self._desktop_token or not self._resume_token:
            raise RuntimeError("云中继会话尚未初始化。")

        ws_url = self._build_websocket_url(self._session_id, self._desktop_token, self._resume_token)
        async with websocket_connect(ws_url, ping_interval=20, ping_timeout=20, open_timeout=10) as websocket:
            self._ws = websocket
            self._set_snapshot(status="connected", last_error=None)
            try:
                while not self._stop_event.is_set():
                    raw_message = await websocket.recv()
                    if isinstance(raw_message, bytes):
                        raw_message = raw_message.decode("utf-8")
                    payload = json.loads(raw_message)
                    await self._handle_relay_message(payload)
            finally:
                self._ws = None
                if not self._stop_event.is_set():
                    self._set_snapshot(status="disconnected")

    async def _handle_relay_message(self, payload: dict[str, object]) -> None:
        message_type = payload.get("type")
        if message_type == "relay.ready":
            self._set_snapshot(
                status="connected",
                session_id=payload.get("session_id"),
                mobile_url=payload.get("mobile_url"),
                qr_svg_url=payload.get("qr_svg_url"),
                expires_at=payload.get("expires_at"),
                last_error=None,
            )
            return
        if message_type == "relay.error":
            code = str(payload.get("code") or "relay_error")
            message = str(payload.get("message") or "云中继返回未知错误。")
            self._set_snapshot(status="disconnected", last_error=message)
            if code in {"session_not_found", "invalid_desktop"}:
                self._session_id = None
                self._desktop_token = None
                self._resume_token = None
            return
        await self._message_handler(payload)

    async def _send(self, payload: dict[str, object]) -> None:
        websocket = self._ws
        if websocket is None:
            raise RuntimeError("云中继当前未连接。")
        async with self._send_lock:
            await websocket.send(json.dumps(payload, ensure_ascii=False))

    def _set_snapshot(
        self,
        *,
        status: str | None = None,
        session_id: str | None = None,
        mobile_url: str | None = None,
        qr_svg_url: str | None = None,
        expires_at: str | None = None,
        last_error: str | None = None,
    ) -> None:
        with self._snapshot_lock:
            if status is not None:
                self._snapshot.status = status
            if session_id is not None:
                self._snapshot.session_id = session_id
            if mobile_url is not None:
                self._snapshot.mobile_url = mobile_url
            if qr_svg_url is not None:
                self._snapshot.qr_svg_url = qr_svg_url
            if expires_at is not None:
                self._snapshot.expires_at = expires_at
            self._snapshot.last_error = last_error

    def _build_websocket_url(self, session_id: str, desktop_token: str, resume_token: str) -> str:
        parsed = urlsplit(self._relay_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = f"{parsed.path.rstrip('/')}/ws/desktop/{session_id}"
        query = urlencode(
            {
                "desktop_token": desktop_token,
                "resume_token": resume_token,
            }
        )
        return urlunsplit((scheme, parsed.netloc, path, query, ""))
