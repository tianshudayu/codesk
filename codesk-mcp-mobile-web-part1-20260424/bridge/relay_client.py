from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
import websockets

from .service import BridgeService, BridgeServiceError
from .session_store import SessionStore


def _default_relay_url() -> str:
    return os.getenv("CODEX_MCP_RELAY_URL", "http://127.0.0.1:8891").strip()


class RelayClient:
    def __init__(
        self,
        *,
        service: BridgeService,
        store: SessionStore,
        verify_token,
        snapshot: dict[str, Any],
        relay_url: str | None = None,
    ) -> None:
        self._service = service
        self._store = store
        self._verify_token = verify_token
        self._snapshot = snapshot
        self._relay_url = (relay_url or _default_relay_url()).rstrip("/")
        self._closed = False
        self._task: asyncio.Task[None] | None = None
        self._websocket = None
        self._send_lock = asyncio.Lock()
        self._subscriptions: dict[str, tuple[str, asyncio.Task[None]]] = {}
        self._ui_subscription: tuple[str, asyncio.Task[None]] | None = None
        self._session_id: str | None = None
        self._bridge_token: str | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._clear_subscriptions()
        if self._websocket is not None:
            await self._websocket.close()

    async def _run(self) -> None:
        while not self._closed:
            try:
                await self._ensure_session()
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._snapshot.update({"status": "error", "lastError": str(exc)})
                await asyncio.sleep(2.0)

    async def _ensure_session(self) -> None:
        if self._session_id and self._bridge_token:
            return
        self._snapshot.update({"status": "creating", "lastError": None})
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{self._relay_url}/api/sessions", json={"source": "bridge"})
            response.raise_for_status()
            payload = response.json()
        self._session_id = payload["sessionId"]
        self._bridge_token = payload["bridgeToken"]
        self._snapshot.update(
            {
                "status": "created",
                "sessionId": self._session_id,
                "mobileUrl": payload.get("mobileUrl"),
                "qrSvgUrl": payload.get("qrSvgUrl"),
                "expiresAt": payload.get("expiresAt"),
                "lastError": None,
            }
        )

    async def _connect_once(self) -> None:
        assert self._session_id is not None
        assert self._bridge_token is not None
        ws_url = _http_to_ws(self._relay_url)
        query = urlencode({"bridge_token": self._bridge_token})
        target = f"{ws_url}/ws/bridge/{self._session_id}?{query}"
        self._snapshot.update({"status": "connecting"})
        async with websockets.connect(target, max_size=16 * 1024 * 1024) as websocket:
            self._websocket = websocket
            self._snapshot.update({"status": "connected", "lastError": None})
            async for raw in websocket:
                message = json.loads(raw)
                await self._handle_message(message)
        self._websocket = None
        self._snapshot.update({"status": "disconnected"})

    async def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type") or "")
        if message_type == "relay.ready":
            self._snapshot.update(
                {
                    "status": "connected",
                    "mobileUrl": message.get("mobileUrl", self._snapshot.get("mobileUrl")),
                    "qrSvgUrl": message.get("qrSvgUrl", self._snapshot.get("qrSvgUrl")),
                    "expiresAt": message.get("expiresAt", self._snapshot.get("expiresAt")),
                }
            )
            return
        if message_type == "relay.mobile.connected":
            self._snapshot.update({"mobileStatus": "connected"})
            return
        if message_type == "relay.mobile.disconnected":
            self._snapshot.update({"mobileStatus": "disconnected"})
            await self._clear_subscriptions()
            return
        if message_type == "relay.error":
            self._snapshot.update({"status": "error", "lastError": message.get("message")})
            return
        if message_type == "relay.mobile.message":
            payload = message.get("payload")
            if isinstance(payload, dict):
                await self._handle_mobile_payload(payload)

    async def _handle_mobile_payload(self, payload: dict[str, Any]) -> None:
        payload_type = str(payload.get("type") or "")
        if payload_type == "rpc.request":
            await self._handle_rpc_request(payload)
            return
        if payload_type == "rpc.subscribe":
            await self._handle_subscribe(payload)
            return
        if payload_type == "rpc.unsubscribe":
            session_id = str(payload.get("sessionId") or "")
            if session_id:
                await self._unsubscribe(session_id)
            return
        if payload_type == "rpc.subscribe_ui":
            await self._handle_subscribe_ui(payload)
            return
        if payload_type == "rpc.unsubscribe_ui":
            await self._unsubscribe_ui()

    async def _handle_rpc_request(self, payload: dict[str, Any]) -> None:
        request_id = str(payload.get("id") or "")
        action = str(payload.get("action") or "")
        access_token = payload.get("accessToken")
        body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        try:
            result = await self._dispatch_rpc(action, body, access_token if isinstance(access_token, str) else None)
            response = {"type": "rpc.response", "id": request_id, "ok": True, "result": result}
        except BridgeServiceError as exc:
            response = {"type": "rpc.response", "id": request_id, "ok": False, "error": {"code": exc.status_code, "message": exc.detail}}
        except Exception as exc:  # pragma: no cover - defensive
            response = {"type": "rpc.response", "id": request_id, "ok": False, "error": {"code": 500, "message": str(exc)}}
        await self._send_to_mobile(response)

    async def _dispatch_rpc(self, action: str, payload: dict[str, Any], access_token: str | None) -> dict[str, Any]:
        if action == "pair_device":
            return self._service.pair_device(str(payload.get("code") or ""))
        if action == "health":
            return await self._service.health_payload()

        self._require_token(access_token)
        if action == "get_active_session":
            return await self._service.get_active_session_payload()
        if action == "set_active_session":
            session_id = payload.get("sessionId") if isinstance(payload.get("sessionId"), str) else None
            source = payload.get("source") if isinstance(payload.get("source"), str) else "relay_ui"
            return await self._service.set_active_session_payload(session_id, source=source)
        if action == "list_workspaces":
            return await self._service.list_workspaces_payload()
        if action == "list_sessions":
            return await self._service.list_sessions_payload()
        if action == "get_session":
            return await self._service.get_session_payload(str(payload.get("sessionId") or ""))
        if action == "create_session":
            return await self._service.create_session_payload(
                str(payload.get("workspace") or ""),
                str(payload.get("prompt") or ""),
                payload.get("title") if isinstance(payload.get("title"), str) else None,
                interaction_mode=payload.get("interactionMode"),
            )
        if action == "continue_session":
            return await self._service.continue_session_payload(
                str(payload.get("sessionId") or ""),
                str(payload.get("content") or ""),
                interaction_mode=payload.get("interactionMode"),
            )
        if action == "align_desktop_session":
            return await self._service.align_desktop_session_payload(str(payload.get("sessionId") or ""))
        if action == "cancel_session":
            return await self._service.cancel_session_payload(str(payload.get("sessionId") or ""))
        if action == "list_threads":
            return await self._service.list_threads_payload()
        if action == "get_thread":
            return await self._service.get_thread_payload(str(payload.get("threadId") or ""))
        if action == "resume_thread":
            prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else None
            return await self._service.resume_thread_payload(
                str(payload.get("threadId") or ""),
                prompt,
                interaction_mode=payload.get("interactionMode"),
            )
        if action == "list_approvals":
            return await self._service.list_approvals_payload(str(payload.get("sessionId") or ""))
        if action == "resolve_approval":
            answers = payload.get("answers") if isinstance(payload.get("answers"), list) else None
            content = payload.get("content") if isinstance(payload.get("content"), str) else None
            return await self._service.resolve_approval_payload(
                str(payload.get("sessionId") or ""),
                str(payload.get("approvalId") or ""),
                str(payload.get("actionValue") or payload.get("action") or ""),
                answers=answers,
                content=content,
            )
        raise BridgeServiceError(400, f"Unsupported relay action: {action}")

    async def _handle_subscribe(self, payload: dict[str, Any]) -> None:
        request_id = str(payload.get("id") or "")
        session_id = str(payload.get("sessionId") or "")
        access_token = payload.get("accessToken")
        try:
            self._require_token(access_token if isinstance(access_token, str) else None)
            await self._service.get_session_payload(session_id)
            await self._unsubscribe(session_id)
            subscriber_id, queue, history = await self._store.subscribe(session_id)
            if subscriber_id is None or queue is None:
                raise BridgeServiceError(404, "会话不存在。")
            task = asyncio.create_task(self._forward_session_events(session_id, queue, history))
            self._subscriptions[session_id] = (subscriber_id, task)
            await self._send_to_mobile({"type": "rpc.response", "id": request_id, "ok": True, "result": {"sessionId": session_id}})
        except BridgeServiceError as exc:
            await self._send_to_mobile(
                {
                    "type": "rpc.response",
                    "id": request_id,
                    "ok": False,
                    "error": {"code": exc.status_code, "message": exc.detail},
                }
            )

    async def _handle_subscribe_ui(self, payload: dict[str, Any]) -> None:
        request_id = str(payload.get("id") or "")
        access_token = payload.get("accessToken")
        try:
            self._require_token(access_token if isinstance(access_token, str) else None)
            await self._unsubscribe_ui()
            subscriber_id, queue = await self._store.subscribe_ui()
            task = asyncio.create_task(self._forward_ui_events(queue))
            self._ui_subscription = (subscriber_id, task)
            await self._send_to_mobile({"type": "rpc.response", "id": request_id, "ok": True, "result": {"ok": True}})
        except BridgeServiceError as exc:
            await self._send_to_mobile(
                {
                    "type": "rpc.response",
                    "id": request_id,
                    "ok": False,
                    "error": {"code": exc.status_code, "message": exc.detail},
                }
            )

    async def _forward_session_events(
        self,
        session_id: str,
        queue: asyncio.Queue[dict[str, Any]],
        history: list[dict[str, Any]],
    ) -> None:
        for item in history:
            await self._send_to_mobile({"type": "session.event", "sessionId": session_id, "event": item})
        while True:
            event = await queue.get()
            await self._send_to_mobile({"type": "session.event", "sessionId": session_id, "event": event})

    async def _forward_ui_events(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        while True:
            event = await queue.get()
            await self._send_to_mobile({"type": "ui.event", "event": event})

    async def _unsubscribe(self, session_id: str) -> None:
        existing = self._subscriptions.pop(session_id, None)
        if existing is None:
            return
        subscriber_id, task = existing
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await self._store.unsubscribe(session_id, subscriber_id)

    async def _clear_subscriptions(self) -> None:
        for session_id in list(self._subscriptions.keys()):
            await self._unsubscribe(session_id)
        await self._unsubscribe_ui()

    async def _unsubscribe_ui(self) -> None:
        existing = self._ui_subscription
        if existing is None:
            return
        self._ui_subscription = None
        subscriber_id, task = existing
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await self._store.unsubscribe_ui(subscriber_id)

    async def _send_to_mobile(self, payload: dict[str, Any]) -> None:
        websocket = self._websocket
        if websocket is None:
            return
        async with self._send_lock:
            await websocket.send(json.dumps(payload, ensure_ascii=False))

    def _require_token(self, access_token: str | None) -> None:
        if not access_token or not self._verify_token(access_token):
            raise BridgeServiceError(401, "访问令牌无效或已过期。")


def _http_to_ws(url: str) -> str:
    parsed = urlparse(url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))
