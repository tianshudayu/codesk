from __future__ import annotations

import asyncio
import io
import ipaddress
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import segno
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect
import uvicorn

from app.networking import list_candidate_addresses


SESSION_TTL_MINUTES = 30
DESKTOP_GRACE_SECONDS = 120
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "app" / "static"
PUBLIC_BASE_URL = os.getenv("REMOTE_ASSIST_RELAY_PUBLIC_URL", "").rstrip("/")


class SessionCreateRequest(BaseModel):
    client_name: str | None = None
    version: str | None = None


@dataclass(slots=True)
class RelaySession:
    session_id: str
    desktop_token: str
    resume_token: str
    mobile_url: str
    qr_svg_url: str
    created_at: datetime
    expires_at: datetime
    desktop_websocket: WebSocket | None = None
    mobile_websocket: WebSocket | None = None
    mobile_id: str | None = None
    desktop_disconnected_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def desktop_is_online(self) -> bool:
        return self.desktop_websocket is not None


class RelayStore:
    def __init__(self) -> None:
        self._sessions: dict[str, RelaySession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, public_base_url: str) -> RelaySession:
        async with self._lock:
            self._cleanup_locked()
            session_id = secrets.token_urlsafe(9)
            mobile_url = f"{public_base_url}/r/{session_id}"
            qr_svg_url = f"{public_base_url}/api/sessions/{session_id}/qr.svg"
            now = _utc_now()
            session = RelaySession(
                session_id=session_id,
                desktop_token=secrets.token_urlsafe(18),
                resume_token=secrets.token_urlsafe(18),
                mobile_url=mobile_url,
                qr_svg_url=qr_svg_url,
                created_at=now,
                expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
            )
            self._sessions[session_id] = session
            return session

    async def get_session(self, session_id: str) -> RelaySession | None:
        async with self._lock:
            self._cleanup_locked()
            return self._sessions.get(session_id)

    async def attach_desktop(
        self,
        session_id: str,
        desktop_token: str,
        resume_token: str,
        websocket: WebSocket,
    ) -> tuple[RelaySession | None, str | None]:
        mobile_to_close: WebSocket | None = None
        async with self._lock:
            self._cleanup_locked()
            session = self._sessions.get(session_id)
            if session is None:
                return None, "session_not_found"
            if desktop_token != session.desktop_token or resume_token != session.resume_token:
                return None, "invalid_desktop"
            if session.mobile_websocket is not None:
                mobile_to_close = session.mobile_websocket
                session.mobile_websocket = None
                session.mobile_id = None
            session.desktop_websocket = websocket
            session.desktop_disconnected_at = None
        if mobile_to_close is not None:
            await mobile_to_close.close(code=4012, reason="电脑端正在重新连接。")
        return session, None

    async def detach_desktop(self, session_id: str, websocket: WebSocket) -> tuple[WebSocket | None, str | None]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.desktop_websocket is not websocket:
                return None, None
            session.desktop_websocket = None
            session.desktop_disconnected_at = _utc_now()
            mobile = session.mobile_websocket
            mobile_id = session.mobile_id
            session.mobile_websocket = None
            session.mobile_id = None
            return mobile, mobile_id

    async def attach_mobile(self, session_id: str, websocket: WebSocket) -> tuple[RelaySession | None, str | None, str | None]:
        async with self._lock:
            self._cleanup_locked()
            session = self._sessions.get(session_id)
            if session is None:
                return None, None, "session_not_found"
            if not session.desktop_is_online():
                return None, None, "desktop_offline"
            if session.mobile_websocket is not None:
                return None, None, "session_busy"
            mobile_id = secrets.token_urlsafe(8)
            session.mobile_websocket = websocket
            session.mobile_id = mobile_id
            return session, mobile_id, None

    async def detach_mobile(self, session_id: str, websocket: WebSocket) -> str | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.mobile_websocket is not websocket:
                return None
            mobile_id = session.mobile_id
            session.mobile_websocket = None
            session.mobile_id = None
            return mobile_id

    async def desktop_socket_for(self, session_id: str) -> WebSocket | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            return session.desktop_websocket if session else None

    async def mobile_socket_for(self, session_id: str, mobile_id: str) -> WebSocket | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.mobile_id != mobile_id:
                return None
            return session.mobile_websocket

    async def current_mobile_id(self, session_id: str) -> str | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            return session.mobile_id if session else None

    async def close_mobile(self, session_id: str, mobile_id: str) -> WebSocket | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.mobile_id != mobile_id:
                return None
            websocket = session.mobile_websocket
            session.mobile_websocket = None
            session.mobile_id = None
            return websocket

    def _cleanup_locked(self) -> None:
        now = _utc_now()
        expired_ids = []
        for session_id, session in self._sessions.items():
            if session.is_expired(now):
                expired_ids.append(session_id)
                continue
            if (
                session.desktop_websocket is None
                and session.desktop_disconnected_at is not None
                and now - session.desktop_disconnected_at > timedelta(seconds=DESKTOP_GRACE_SECONDS)
            ):
                expired_ids.append(session_id)
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)


store = RelayStore()
app = FastAPI(title="RemoteCodingAssistRelay")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.post("/api/sessions")
async def create_session(request: Request, payload: SessionCreateRequest) -> JSONResponse:
    public_base_url = _public_base_url(request)
    session = await store.create_session(public_base_url)
    return JSONResponse(_session_payload(session))


@app.get("/api/sessions/{session_id}/qr.svg")
async def session_qr(session_id: str) -> Response:
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期。")
    output = io.BytesIO()
    segno.make(session.mobile_url, micro=False).save(output, kind="svg", scale=4, border=2)
    return Response(content=output.getvalue(), media_type="image/svg+xml")


@app.get("/r/{session_id}")
async def relay_remote_page(session_id: str) -> FileResponse:
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期。")
    return FileResponse(STATIC_DIR / "remote.html")


@app.websocket("/ws/desktop/{session_id}")
async def desktop_socket(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    desktop_token = websocket.query_params.get("desktop_token", "")
    resume_token = websocket.query_params.get("resume_token", "")
    session, error_code = await store.attach_desktop(session_id, desktop_token, resume_token, websocket)
    if session is None:
        await websocket.send_json(
            {
                "type": "relay.error",
                "code": error_code,
                "message": _relay_error_message(error_code),
            }
        )
        await websocket.close(code=4404)
        return

    await websocket.send_json(
        {
            "type": "relay.ready",
            "session_id": session.session_id,
            "mobile_url": session.mobile_url,
            "qr_svg_url": session.qr_svg_url,
            "expires_at": session.expires_at.isoformat(),
        }
    )

    try:
        while True:
            message = await websocket.receive_json()
            await _handle_desktop_message(session_id, message)
    except WebSocketDisconnect:
        pass
    finally:
        mobile_socket, mobile_id = await store.detach_desktop(session_id, websocket)
        if mobile_socket is not None:
            await mobile_socket.close(code=4011, reason="电脑端暂未在线。")


@app.websocket("/ws/mobile/{session_id}")
async def mobile_socket(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session, mobile_id, error_code = await store.attach_mobile(session_id, websocket)
    if session is None or mobile_id is None:
        await websocket.send_json(
            {
                "type": "error",
                "id": None,
                "code": error_code,
                "message": _mobile_error_message(error_code),
            }
        )
        await websocket.close(code=4404 if error_code == "desktop_offline" else 4409)
        return

    desktop_websocket = await store.desktop_socket_for(session_id)
    if desktop_websocket is not None:
        await desktop_websocket.send_json({"type": "relay.mobile.connected", "mobile_id": mobile_id})

    try:
        while True:
            payload = await websocket.receive_json()
            desktop_websocket = await store.desktop_socket_for(session_id)
            if desktop_websocket is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "id": None,
                        "code": "desktop_offline",
                        "message": _mobile_error_message("desktop_offline"),
                    }
                )
                await websocket.close(code=4410, reason="电脑端暂未在线。")
                return
            await desktop_websocket.send_json(
                {
                    "type": "relay.mobile.message",
                    "mobile_id": mobile_id,
                    "payload": payload,
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        detached_mobile_id = await store.detach_mobile(session_id, websocket)
        if detached_mobile_id:
            desktop_websocket = await store.desktop_socket_for(session_id)
            if desktop_websocket is not None:
                await desktop_websocket.send_json(
                    {
                        "type": "relay.mobile.disconnected",
                        "mobile_id": detached_mobile_id,
                    }
                )


async def _handle_desktop_message(session_id: str, message: Any) -> None:
    if not isinstance(message, dict):
        return
    message_type = message.get("type")
    if message_type == "relay.desktop.message":
        mobile_id = str(message.get("mobile_id") or "")
        payload = message.get("payload")
        mobile_socket = await store.mobile_socket_for(session_id, mobile_id)
        if mobile_socket is not None and isinstance(payload, dict):
            await mobile_socket.send_json(payload)
        return
    if message_type == "relay.close_mobile":
        mobile_id = str(message.get("mobile_id") or "")
        mobile_socket = await store.close_mobile(session_id, mobile_id)
        if mobile_socket is not None:
            code = int(message.get("code") or 4401)
            reason = str(message.get("reason") or "连接已关闭。")
            await mobile_socket.close(code=code, reason=reason)


def _session_payload(session: RelaySession) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "desktop_token": session.desktop_token,
        "resume_token": session.resume_token,
        "mobile_url": session.mobile_url,
        "qr_svg_url": session.qr_svg_url,
        "expires_at": session.expires_at.isoformat(),
    }


def _mobile_error_message(code: str | None) -> str:
    if code == "desktop_offline":
        return "电脑端暂未在线，正在等待重新连接。"
    if code == "session_busy":
        return "当前已有另一台手机连接。"
    return "会话不存在或已过期。"


def _relay_error_message(code: str | None) -> str:
    if code == "invalid_desktop":
        return "桌面端凭证无效。"
    return "会话不存在或已过期。"


def _public_base_url(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    parsed = urlsplit(str(request.base_url))
    host = parsed.hostname or ""
    if host in {"127.0.0.1", "::1", "localhost"}:
        reachable_host = _pick_reachable_host()
        if reachable_host:
            netloc = reachable_host
            if parsed.port is not None:
                netloc = f"{reachable_host}:{parsed.port}"
            return urlunsplit((parsed.scheme, netloc, "", "", "")).rstrip("/")
    return str(request.base_url).rstrip("/")


def _pick_reachable_host() -> str | None:
    private_candidates: list[str] = []
    overlay_candidates: list[str] = []
    public_candidates: list[str] = []

    for candidate in list_candidate_addresses():
        address = candidate.address
        if not address:
            continue
        if _looks_like_overlay_address(address, candidate.label):
            overlay_candidates.append(address)
            continue
        if _is_private_ipv4(address):
            private_candidates.append(address)
            continue
        public_candidates.append(address)

    if private_candidates:
        return private_candidates[0]
    if public_candidates:
        return public_candidates[0]
    if overlay_candidates:
        return overlay_candidates[0]
    return None


def _is_private_ipv4(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_private
    except ValueError:
        return False


def _looks_like_overlay_address(address: str, label: str) -> bool:
    lowered = label.lower()
    return "tailscale" in lowered or "zerotier" in lowered or address.startswith("100.")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    host = os.getenv("REMOTE_ASSIST_RELAY_HOST", "0.0.0.0")
    port = int(os.getenv("REMOTE_ASSIST_RELAY_PORT", "8780"))
    uvicorn.run("relay_service.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
