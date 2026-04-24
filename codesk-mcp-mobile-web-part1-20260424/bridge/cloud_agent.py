from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import platform
import secrets
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import websockets

from .cloud_identity import CloudAgentIdentity, CloudIdentityStore
from .service import BridgeService, BridgeServiceError
from .session_store import SessionStore

logger = logging.getLogger(__name__)


def _default_cloud_url() -> str:
    return os.getenv("CODEX_CLOUD_URL", "https://codesk.lensseekapp.com").rstrip("/")


@dataclass(slots=True)
class CloudAgentSnapshot:
    enabled: bool = False
    connected: bool = False
    registered: bool = False
    claimed: bool = False
    device_id: str | None = None
    claim_code: str | None = None
    claim_token: str | None = None
    claim_url: str | None = None
    claim_expires_at: str | None = None
    cloud_url: str | None = None
    owner_email: str | None = None
    last_error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "registered": self.registered,
            "claimed": self.claimed,
            "deviceId": self.device_id,
            "claimCode": self.claim_code,
            "claimToken": self.claim_token,
            "claimUrl": self.claim_url,
            "claimExpiresAt": self.claim_expires_at,
            "cloudUrl": self.cloud_url,
            "ownerEmail": self.owner_email,
            "lastError": self.last_error,
        }


class NullCloudAgentClient:
    def snapshot(self) -> dict[str, Any]:
        return CloudAgentSnapshot(enabled=False, last_error="cloud agent disabled").to_public_dict()

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None


class CloudAgentClient:
    def __init__(
        self,
        *,
        service: BridgeService,
        store: SessionStore,
        desktop_automation: Any,
        cloud_url: str | None = None,
        identity_store: CloudIdentityStore | None = None,
    ) -> None:
        self._service = service
        self._store = store
        self._desktop_automation = desktop_automation
        self._cloud_url = (cloud_url or _default_cloud_url()).rstrip("/")
        self._identity_store = identity_store or CloudIdentityStore()
        self._snapshot = CloudAgentSnapshot(enabled=True, cloud_url=self._cloud_url)
        self._identity: CloudAgentIdentity | None = None
        self._closed = False
        self._task: asyncio.Task[None] | None = None
        self._websocket = None
        self._desktop_websocket = None
        self._desktop_send_lock = asyncio.Lock()
        self._send_queue: asyncio.PriorityQueue[tuple[int, int, dict[str, Any]]] | None = None
        self._send_task: asyncio.Task[None] | None = None
        self._send_seq = 0
        self._connection_broken: asyncio.Event | None = None
        self._keepalive_seq = 0
        self._last_keepalive_ack = 0
        self._desktop_forward_task: asyncio.Task[None] | None = None
        self._desktop_channel_task: asyncio.Task[None] | None = None
        self._status_task: asyncio.Task[None] | None = None
        self._desktop_subscriber_id: str | None = None
        self._desktop_queue: asyncio.Queue[dict[str, Any]] | None = None
        self._ui_event_task: asyncio.Task[None] | None = None
        self._ui_subscriber_id: str | None = None
        self._session_event_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_subscriber_ids: dict[str, str] = {}

    def _persist_identity(self) -> None:
        if self._identity is None:
            return
        self._identity.claim_code = self._snapshot.claim_code
        self._identity.claim_token = self._snapshot.claim_token
        self._identity.claim_url = self._snapshot.claim_url
        self._identity.claim_expires_at = self._snapshot.claim_expires_at
        self._identity.cloud_url = self._snapshot.cloud_url or self._cloud_url
        self._identity.claimed = self._snapshot.claimed
        self._identity.owner_email = self._snapshot.owner_email
        self._identity.connected = self._snapshot.connected
        self._identity.last_error = self._snapshot.last_error
        if self._snapshot.connected:
            self._identity.last_connected_at = datetime.now().astimezone().isoformat()
        self._identity_store.save(self._identity)

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot.to_public_dict()

    async def start(self) -> None:
        if self._task is None:
            self._closed = False
            self._task = asyncio.create_task(self._run(), name="cloud-agent")

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._stop_status_loop()
        await self._stop_desktop_forwarding()
        await self._stop_desktop_channel()
        await self._stop_ui_event_forwarding()
        await self._stop_all_session_event_forwarding()
        await self._stop_send_loop()
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()
        desktop_websocket = self._desktop_websocket
        self._desktop_websocket = None
        if desktop_websocket is not None:
            with contextlib.suppress(Exception):
                await desktop_websocket.close()
        self._snapshot.connected = False

    async def _run(self) -> None:
        while not self._closed:
            try:
                await self._ensure_registration()
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._snapshot.connected = False
                self._snapshot.last_error = str(exc)
                self._persist_identity()
                logger.warning("cloud agent iteration failed: %s", exc, exc_info=True)
                await asyncio.sleep(2.0)

    async def _ensure_registration(self) -> None:
        identity = self._identity_store.load()
        if identity is None:
            identity = await self._register_device()
            self._identity_store.save(identity)
        self._identity = identity
        self._snapshot.registered = True
        self._snapshot.device_id = identity.device_id
        self._snapshot.claim_code = identity.claim_code
        self._snapshot.claim_token = identity.claim_token
        self._snapshot.claim_url = identity.claim_url
        self._snapshot.claim_expires_at = identity.claim_expires_at
        self._snapshot.cloud_url = identity.cloud_url or self._cloud_url
        self._snapshot.claimed = identity.claimed
        self._snapshot.owner_email = identity.owner_email
        self._snapshot.connected = identity.connected
        self._snapshot.last_error = identity.last_error
        logger.info(
            "cloud device registered deviceId=%s cloudUrl=%s claimed=%s",
            identity.device_id,
            self._snapshot.cloud_url,
            self._snapshot.claimed,
        )

    async def _register_device(self) -> CloudAgentIdentity:
        enrollment_token = os.getenv("CODEX_CLOUD_ENROLLMENT_TOKEN", "").strip()
        payload = {
            "machineName": socket.gethostname(),
            "platform": platform.platform(),
            "alias": f"{socket.gethostname()} / Codex Desktop",
            "clientNonce": secrets.token_urlsafe(8),
        }
        path = "/api/agent/register"
        if enrollment_token:
            payload["enrollmentToken"] = enrollment_token
            path = "/api/agent/enroll"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{self._cloud_url}{path}", json=payload)
            response.raise_for_status()
            result = response.json()
        identity = CloudAgentIdentity(
            device_id=str(result["deviceId"]),
            agent_token=str(result["agentToken"]),
            claim_code=result.get("claimCode"),
            claim_token=result.get("claimToken"),
            claim_url=result.get("claimUrl"),
            claim_expires_at=result.get("claimExpiresAt"),
            cloud_url=self._cloud_url,
        )
        return identity

    async def _connect_once(self) -> None:
        assert self._identity is not None
        ws_url = self._cloud_url.replace("http://", "ws://").replace("https://", "wss://")
        target = f"{ws_url}/ws/agent/{self._identity.device_id}?agent_token={self._identity.agent_token}"
        broken = asyncio.Event()
        self._connection_broken = broken
        try:
            async with websockets.connect(
                target,
                max_size=16 * 1024 * 1024,
                open_timeout=10,
                close_timeout=5,
                ping_interval=None,
                ping_timeout=None,
            ) as websocket:
                self._websocket = websocket
                self._snapshot.connected = True
                self._snapshot.last_error = None
                self._keepalive_seq = 0
                self._last_keepalive_ack = 0
                self._persist_identity()
                logger.info("cloud ws connected target=%s", target)
                await self._start_send_loop()
                await self._start_status_loop()
                asyncio.create_task(self._safe_send_status_update(priority=1), name="cloud-agent-initial-status")
                while True:
                    receive_task = asyncio.create_task(websocket.recv(), name="cloud-agent-recv")
                    broken_task = asyncio.create_task(broken.wait(), name="cloud-agent-broken")
                    done, pending = await asyncio.wait(
                        {receive_task, broken_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    if broken_task in done:
                        with contextlib.suppress(asyncio.CancelledError):
                            await receive_task
                        raise ConnectionError(self._snapshot.last_error or "cloud websocket send path failed")
                    with contextlib.suppress(asyncio.CancelledError):
                        await broken_task
                    raw = receive_task.result()
                    message = json.loads(raw)
                    if isinstance(message, dict):
                        await self._handle_message(message)
        finally:
            if self._connection_broken is broken:
                self._connection_broken = None
            self._snapshot.connected = False
            self._websocket = None
            self._persist_identity()
            logger.info("cloud ws disconnected")
            await self._stop_status_loop()
            await self._stop_desktop_channel()
            await self._stop_ui_event_forwarding()
            await self._stop_all_session_event_forwarding()
            await self._stop_send_loop()

    async def _mark_connection_broken(self, reason: str) -> None:
        self._snapshot.connected = False
        self._snapshot.last_error = reason
        event = self._connection_broken
        if event is not None and not event.is_set():
            event.set()
        websocket = self._websocket
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()

    async def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type") or "")
        if message_type == "agent.welcome":
            self._snapshot.claimed = bool(message.get("claimed"))
            self._snapshot.owner_email = message.get("ownerEmail") if isinstance(message.get("ownerEmail"), str) else None
            claim_code = message.get("claimCode")
            if isinstance(claim_code, str) and claim_code:
                self._snapshot.claim_code = claim_code
            claim_token = message.get("claimToken")
            if isinstance(claim_token, str):
                self._snapshot.claim_token = claim_token or None
            claim_url = message.get("claimUrl")
            if isinstance(claim_url, str):
                self._snapshot.claim_url = claim_url or None
            claim_expires_at = message.get("claimExpiresAt")
            if isinstance(claim_expires_at, str):
                self._snapshot.claim_expires_at = claim_expires_at or None
            if self._identity is not None:
                self._persist_identity()
            return
        if message_type == "agent.keepalive.ack":
            seq = message.get("seq")
            if isinstance(seq, int):
                self._last_keepalive_ack = max(self._last_keepalive_ack, seq)
            return
        if message_type == "error":
            error_message = str(message.get("message") or "")
            self._snapshot.last_error = error_message
            if "invalid agent token" in error_message.lower():
                self._identity_store.clear()
                self._identity = None
                self._snapshot.registered = False
                self._snapshot.device_id = None
                self._snapshot.claim_code = None
                self._snapshot.claim_token = None
                self._snapshot.claim_url = None
                self._snapshot.claim_expires_at = None
            self._persist_identity()
            return
        if message_type == "rpc.request":
            await self._handle_rpc_request(message)
            return
        if message_type == "event.subscribe_ui":
            await self._start_ui_event_forwarding()
            return
        if message_type == "event.unsubscribe_ui":
            await self._stop_ui_event_forwarding()
            return
        if message_type == "event.subscribe_session":
            session_id = message.get("sessionId") if isinstance(message.get("sessionId"), str) else ""
            await self._start_session_event_forwarding(session_id)
            return
        if message_type == "event.unsubscribe_session":
            session_id = message.get("sessionId") if isinstance(message.get("sessionId"), str) else ""
            await self._stop_session_event_forwarding(session_id)
            return
        if message_type == "agent.status.request":
            await self._send_status_update(priority=1)
            return
        if message_type == "desktop.channel.open":
            await self._start_desktop_channel()
            return
        if message_type == "desktop.channel.close":
            await self._stop_desktop_channel()

    async def _handle_rpc_request(self, message: dict[str, Any]) -> None:
        request_id = str(message.get("id") or "")
        action = str(message.get("action") or "")
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        started = time.perf_counter()
        logger.info("cloud rpc start id=%s action=%s", request_id, action)
        try:
            result = await self._dispatch_rpc(action, payload)
            response = {"type": "rpc.response", "id": request_id, "ok": True, "result": result}
        except BridgeServiceError as exc:
            response = {"type": "rpc.response", "id": request_id, "ok": False, "error": {"code": exc.status_code, "message": exc.detail}}
        except Exception as exc:  # pragma: no cover - defensive
            response = {"type": "rpc.response", "id": request_id, "ok": False, "error": {"code": 500, "message": str(exc)}}
        dispatched = time.perf_counter()
        logger.info(
            "cloud rpc dispatched id=%s action=%s elapsed=%.3fs ok=%s",
            request_id,
            action,
            dispatched - started,
            bool(response.get("ok")),
        )
        await self._send(response, priority=0)
        logger.info(
            "cloud rpc queued-response id=%s action=%s total=%.3fs",
            request_id,
            action,
            time.perf_counter() - started,
        )
        await self._send_status_update(priority=2)

    async def _dispatch_rpc(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "health":
            return await self._service.health_payload()
        if action == "get_active_session":
            return await self._service.get_active_session_payload()
        if action == "set_active_session":
            session_id = payload.get("sessionId") if isinstance(payload.get("sessionId"), str) else None
            source = payload.get("source") if isinstance(payload.get("source"), str) else "cloud_ui"
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
                require_desktop=bool(payload.get("requireDesktop")),
                interaction_mode=payload.get("interactionMode"),
                attachment_ids=payload.get("attachmentIds") if isinstance(payload.get("attachmentIds"), list) else None,
            )
        if action == "continue_session":
            return await self._service.continue_session_payload(
                str(payload.get("sessionId") or ""),
                str(payload.get("content") or ""),
                require_desktop=bool(payload.get("requireDesktop")),
                interaction_mode=payload.get("interactionMode"),
                attachment_ids=payload.get("attachmentIds") if isinstance(payload.get("attachmentIds"), list) else None,
            )
        if action == "upload_attachment":
            raw = payload.get("dataBase64") if isinstance(payload.get("dataBase64"), str) else ""
            try:
                data = base64.b64decode(raw, validate=True)
            except Exception as exc:
                raise BridgeServiceError(400, "附件编码无效。") from exc
            return await self._service.upload_attachment_payload(
                file_name=str(payload.get("fileName") or "image"),
                mime_type=str(payload.get("mimeType") or ""),
                data=data,
            )
        if action == "get_attachment_preview":
            attachment, path = await self._service.get_attachment_preview_payload(str(payload.get("attachmentId") or ""))
            return {
                "attachment": attachment.to_public_dict(),
                "mimeType": attachment.mime_type,
                "fileName": attachment.file_name,
                "dataBase64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
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
                attachment_ids=payload.get("attachmentIds") if isinstance(payload.get("attachmentIds"), list) else None,
            )
        if action == "list_approvals":
            return await self._service.list_approvals_payload(str(payload.get("sessionId") or ""))
        if action == "resolve_approval":
            answers = payload.get("answers") if isinstance(payload.get("answers"), list) else None
            content = payload.get("content") if isinstance(payload.get("content"), str) else None
            return await self._service.resolve_approval_payload(
                str(payload.get("sessionId") or ""),
                str(payload.get("approvalId") or ""),
                str(payload.get("action") or payload.get("actionValue") or ""),
                answers=answers,
                content=content,
            )
        raise BridgeServiceError(400, f"Unsupported cloud action: {action}")

    async def _handle_desktop_command(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        try:
            response = await self._desktop_automation.send_command(payload, expect_ack=True)
            await self._send_desktop({"type": "desktop.event", "payload": response or {"type": "ack", "id": request_id}})
        except Exception as exc:
            await self._send_desktop(
                {
                    "type": "desktop.event",
                    "payload": {
                        "type": "error",
                        "id": request_id,
                        "code": "desktop_command_failed",
                        "message": str(exc),
                    },
                }
            )

    async def _start_desktop_channel(self) -> None:
        if self._desktop_channel_task is not None:
            return

        async def run() -> None:
            while not self._closed and self._websocket is not None:
                try:
                    await self._connect_desktop_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("cloud desktop channel failed: %s", exc, exc_info=True)
                    await asyncio.sleep(1.0)

        self._desktop_channel_task = asyncio.create_task(run(), name="cloud-agent-desktop-channel")

    async def _stop_desktop_channel(self) -> None:
        if self._desktop_channel_task is not None:
            self._desktop_channel_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._desktop_channel_task
            self._desktop_channel_task = None
        await self._stop_desktop_forwarding()
        websocket = self._desktop_websocket
        self._desktop_websocket = None
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()

    async def _connect_desktop_once(self) -> None:
        assert self._identity is not None
        ws_url = self._cloud_url.replace("http://", "ws://").replace("https://", "wss://")
        target = f"{ws_url}/ws/agent-desktop/{self._identity.device_id}?agent_token={self._identity.agent_token}"
        async with websockets.connect(
            target,
            max_size=16 * 1024 * 1024,
            open_timeout=10,
            close_timeout=5,
            ping_interval=None,
            ping_timeout=None,
        ) as websocket:
            self._desktop_websocket = websocket
            logger.info("cloud desktop ws connected target=%s", target)
            await self._start_desktop_forwarding()
            async for raw in websocket:
                message = json.loads(raw)
                if isinstance(message, dict) and str(message.get("type") or "") == "desktop.command":
                    await self._handle_desktop_command(message)
        self._desktop_websocket = None
        await self._stop_desktop_forwarding()

    async def _start_desktop_forwarding(self) -> None:
        if self._desktop_forward_task is not None:
            return
        subscriber_id, queue = await self._desktop_automation.subscribe()
        self._desktop_subscriber_id = subscriber_id
        self._desktop_queue = queue

        async def forward() -> None:
            while True:
                message = await queue.get()
                await self._send_desktop({"type": "desktop.event", "payload": message})

        self._desktop_forward_task = asyncio.create_task(forward(), name="cloud-agent-desktop")

    async def _stop_desktop_forwarding(self) -> None:
        if self._desktop_forward_task is not None:
            self._desktop_forward_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._desktop_forward_task
            self._desktop_forward_task = None
        if self._desktop_subscriber_id is not None:
            with contextlib.suppress(Exception):
                await self._desktop_automation.unsubscribe(self._desktop_subscriber_id)
        self._desktop_subscriber_id = None
        self._desktop_queue = None

    async def _start_ui_event_forwarding(self) -> None:
        if self._ui_event_task is not None:
            return
        subscriber_id, queue = await self._store.subscribe_ui()
        self._ui_subscriber_id = subscriber_id

        async def forward() -> None:
            while True:
                event = await queue.get()
                await self._send({"type": "ui.event", "event": event}, priority=3)

        self._ui_event_task = asyncio.create_task(forward(), name="cloud-agent-ui-events")

    async def _stop_ui_event_forwarding(self) -> None:
        if self._ui_event_task is not None:
            self._ui_event_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ui_event_task
            self._ui_event_task = None
        if self._ui_subscriber_id is not None:
            with contextlib.suppress(Exception):
                await self._store.unsubscribe_ui(self._ui_subscriber_id)
        self._ui_subscriber_id = None

    async def _start_session_event_forwarding(self, session_id: str) -> None:
        if not session_id or session_id in self._session_event_tasks:
            return
        subscriber_id, queue, history = await self._store.subscribe(session_id)
        if subscriber_id is None or queue is None:
            await self._send(
                {"type": "session.event", "sessionId": session_id, "event": {"type": "session.missing", "sessionId": session_id}},
                priority=2,
            )
            return
        self._session_subscriber_ids[session_id] = subscriber_id
        for event in history:
            await self._send({"type": "session.event", "sessionId": session_id, "event": event}, priority=2)

        async def forward() -> None:
            while True:
                event = await queue.get()
                await self._send({"type": "session.event", "sessionId": session_id, "event": event}, priority=3)

        self._session_event_tasks[session_id] = asyncio.create_task(forward(), name=f"cloud-agent-session-events:{session_id}")

    async def _stop_session_event_forwarding(self, session_id: str) -> None:
        task = self._session_event_tasks.pop(session_id, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        subscriber_id = self._session_subscriber_ids.pop(session_id, None)
        if subscriber_id is not None:
            with contextlib.suppress(Exception):
                await self._store.unsubscribe(session_id, subscriber_id)

    async def _stop_all_session_event_forwarding(self) -> None:
        for session_id in list(self._session_event_tasks):
            await self._stop_session_event_forwarding(session_id)

    async def _start_status_loop(self) -> None:
        if self._status_task is not None:
            return

        async def heartbeat() -> None:
            last_full_status_at = 0.0
            while True:
                self._keepalive_seq += 1
                seq = self._keepalive_seq
                try:
                    await asyncio.wait_for(
                        self._send({"type": "agent.keepalive", "seq": seq, "ts": time.time()}, priority=0),
                        timeout=2.0,
                    )
                except Exception as exc:
                    logger.warning("cloud keepalive failed: %s", exc, exc_info=True)
                    await self._mark_connection_broken(str(exc))
                    return
                deadline = time.monotonic() + 8.0
                while self._last_keepalive_ack < seq and time.monotonic() < deadline:
                    await asyncio.sleep(0.5)
                if self._last_keepalive_ack < seq:
                    logger.warning("cloud keepalive ack timeout seq=%s lastAck=%s", seq, self._last_keepalive_ack)
                    await self._mark_connection_broken("cloud keepalive ack timeout")
                    return
                now = time.monotonic()
                if now - last_full_status_at < 10.0:
                    continue
                last_full_status_at = now
                await self._safe_send_status_update(priority=2)

        self._status_task = asyncio.create_task(heartbeat(), name="cloud-agent-status")

    async def _stop_status_loop(self) -> None:
        if self._status_task is None:
            return
        self._status_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._status_task
        self._status_task = None

    async def _send_status_update(self, *, priority: int = 2) -> None:
        try:
            payload = await asyncio.wait_for(
                self._service.admin_state_payload(relay={"status": "cloud_agent"}),
                timeout=4.0,
            )
        except Exception as exc:
            logger.warning("cloud status snapshot failed: %s", exc)
            payload = {
                "backend": "unknown",
                "backendAvailable": False,
                "sessionCount": None,
                "activeSessionId": None,
                "desktopAutomation": {
                    "available": False,
                    "connected": False,
                    "authenticated": False,
                    "codexWindowControllable": False,
                    "codexWindowLocked": False,
                    "codexForeground": False,
                    "lastError": str(exc),
                },
            }
        desktop = payload.get("desktopAutomation") if isinstance(payload.get("desktopAutomation"), dict) else {}
        desktop_controllable = bool(desktop.get("codexWindowControllable") or desktop.get("codexWindowLocked"))
        status_payload = {
            "type": "agent.status",
            "payload": {
                "backend": payload.get("backend"),
                "backendAvailable": payload.get("backendAvailable"),
                "desktopServiceReady": bool(
                    desktop.get("available")
                    and desktop.get("connected")
                    and desktop.get("authenticated")
                ),
                "desktopReady": bool(
                    desktop.get("available")
                    and desktop.get("connected")
                    and desktop.get("authenticated")
                    and desktop_controllable
                ),
                "codexForeground": bool(desktop.get("codexForeground")),
                "codexWindowControllable": desktop_controllable,
                "fullscreenSuggested": True,
                "desktopAutomation": desktop,
                "sessionCount": payload.get("sessionCount"),
                "activeSessionId": payload.get("activeSessionId"),
            },
        }
        await self._send(status_payload, priority=priority)

    async def _safe_send_status_update(self, *, priority: int = 2) -> None:
        try:
            await self._send_status_update(priority=priority)
        except Exception as exc:
            logger.warning("cloud status update failed: %s", exc, exc_info=True)

    async def _start_send_loop(self) -> None:
        if self._send_task is not None and self._send_task.done():
            with contextlib.suppress(Exception):
                self._send_task.result()
            self._send_task = None
        if self._send_task is not None:
            return
        self._send_queue = asyncio.PriorityQueue()
        self._send_seq = 0

        async def writer() -> None:
            logger.info("cloud send loop started")
            try:
                while True:
                    queue = self._send_queue
                    if queue is None:
                        await asyncio.sleep(0.05)
                        continue
                    _priority, _seq, payload = await queue.get()
                    websocket = self._websocket
                    if websocket is None:
                        continue
                    try:
                        await websocket.send(json.dumps(payload, ensure_ascii=False))
                        if payload.get("type") == "rpc.response":
                            logger.info("cloud rpc response sent id=%s", payload.get("id"))
                    except Exception as exc:
                        logger.warning("cloud agent send loop failed: %s", exc, exc_info=True)
                        await self._mark_connection_broken(str(exc))
                        return
            finally:
                logger.info("cloud send loop stopped")
                if self._send_task is asyncio.current_task():
                    self._send_task = None

        self._send_task = asyncio.create_task(writer(), name="cloud-agent-send")

    async def _stop_send_loop(self) -> None:
        if self._send_task is not None:
            self._send_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._send_task
            self._send_task = None
        self._send_queue = None
        self._send_seq = 0

    async def _send(self, payload: dict[str, Any], *, priority: int = 2) -> None:
        websocket = self._websocket
        if websocket is None:
            return
        queue = self._send_queue
        task = self._send_task
        if queue is not None and (task is None or task.done()):
            await self._start_send_loop()
            queue = self._send_queue
        if queue is None:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            if payload.get("type") == "rpc.response":
                logger.info("cloud rpc response sent directly id=%s", payload.get("id"))
            return
        self._send_seq += 1
        await queue.put((priority, self._send_seq, payload))

    async def _send_desktop(self, payload: dict[str, Any]) -> None:
        websocket = self._desktop_websocket
        if websocket is None:
            return
        async with self._desktop_send_lock:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
