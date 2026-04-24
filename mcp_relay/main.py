from __future__ import annotations

import io
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import segno
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "bridge" / "static"


@dataclass(slots=True)
class RelaySession:
    session_id: str
    bridge_token: str
    mobile_url: str
    qr_svg_url: str
    expires_at: str
    created_at: str
    bridge_ws: WebSocket | None = None
    mobile_ws: WebSocket | None = None


@dataclass(slots=True)
class RelayState:
    sessions: dict[str, RelaySession] = field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="Codex MCP Relay")
    app.state.relay = RelayState()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "sessions": len(app.state.relay.sessions)}

    @app.post("/api/sessions")
    async def create_session(request: Request) -> dict[str, Any]:
        _cleanup_expired(app.state.relay)
        session_id = secrets.token_urlsafe(9)
        bridge_token = secrets.token_urlsafe(18)
        base_url = _public_base_url(request)
        created_at = _now_iso()
        expires_at = (datetime.now().astimezone() + timedelta(hours=2)).isoformat()
        mobile_url = f"{base_url}/r/{session_id}"
        qr_svg_url = f"{base_url}/api/sessions/{session_id}/qr.svg"
        app.state.relay.sessions[session_id] = RelaySession(
            session_id=session_id,
            bridge_token=bridge_token,
            mobile_url=mobile_url,
            qr_svg_url=qr_svg_url,
            expires_at=expires_at,
            created_at=created_at,
        )
        return {
            "sessionId": session_id,
            "bridgeToken": bridge_token,
            "mobileUrl": mobile_url,
            "qrSvgUrl": qr_svg_url,
            "expiresAt": expires_at,
        }

    @app.get("/api/sessions/{session_id}/qr.svg")
    async def qr_code(session_id: str, request: Request) -> Response:
        session = _require_session(app.state.relay, session_id)
        output = io.BytesIO()
        segno.make(session.mobile_url).save(output, kind="svg", scale=4)
        return Response(content=output.getvalue(), media_type="image/svg+xml")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/r/{session_id}")
    async def relay_page(session_id: str) -> FileResponse:
        _require_session(app.state.relay, session_id)
        return FileResponse(STATIC_DIR / "index.html")

    @app.websocket("/ws/bridge/{session_id}")
    async def bridge_socket(session_id: str, websocket: WebSocket) -> None:
        session = _require_session(app.state.relay, session_id)
        bridge_token = websocket.query_params.get("bridge_token")
        if bridge_token != session.bridge_token:
            await websocket.close(code=4401, reason="invalid bridge token")
            return
        await websocket.accept()
        session.bridge_ws = websocket
        await websocket.send_json(
            {
                "type": "relay.ready",
                "sessionId": session.session_id,
                "mobileUrl": session.mobile_url,
                "qrSvgUrl": session.qr_svg_url,
                "expiresAt": session.expires_at,
            }
        )
        if session.mobile_ws is not None:
            await websocket.send_json({"type": "relay.mobile.connected", "sessionId": session.session_id})
            await session.mobile_ws.send_json({"type": "relay.status", "status": "ready"})
        try:
            while True:
                message = await websocket.receive_json()
                if session.mobile_ws is not None:
                    await session.mobile_ws.send_json(message)
        except WebSocketDisconnect:
            pass
        finally:
            if session.bridge_ws is websocket:
                session.bridge_ws = None
            if session.mobile_ws is not None:
                await session.mobile_ws.send_json({"type": "relay.status", "status": "bridge_offline"})

    @app.websocket("/ws/mobile/{session_id}")
    async def mobile_socket(session_id: str, websocket: WebSocket) -> None:
        session = _require_session(app.state.relay, session_id)
        await websocket.accept()
        if session.mobile_ws is not None:
            await websocket.send_json({"type": "relay.error", "message": "session_busy"})
            await websocket.close(code=4409, reason="session busy")
            return
        session.mobile_ws = websocket
        if session.bridge_ws is not None:
            await session.bridge_ws.send_json({"type": "relay.mobile.connected", "sessionId": session.session_id})
            await websocket.send_json({"type": "relay.status", "status": "ready"})
        else:
            await websocket.send_json({"type": "relay.status", "status": "bridge_offline"})
        try:
            while True:
                payload = await websocket.receive_json()
                if session.bridge_ws is None:
                    await websocket.send_json({"type": "relay.status", "status": "bridge_offline"})
                    continue
                await session.bridge_ws.send_json({"type": "relay.mobile.message", "payload": payload})
        except WebSocketDisconnect:
            pass
        finally:
            if session.mobile_ws is websocket:
                session.mobile_ws = None
            if session.bridge_ws is not None:
                await session.bridge_ws.send_json({"type": "relay.mobile.disconnected", "sessionId": session.session_id})

    return app


def _require_session(state: RelayState, session_id: str) -> RelaySession:
    _cleanup_expired(state)
    session = state.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="relay session not found")
    return session


def _cleanup_expired(state: RelayState) -> None:
    now = datetime.now().astimezone()
    expired = [session_id for session_id, session in state.sessions.items() if datetime.fromisoformat(session.expires_at) <= now]
    for session_id in expired:
        state.sessions.pop(session_id, None)


def _public_base_url(request: Request) -> str:
    configured = os.getenv("CODEX_MCP_RELAY_PUBLIC_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


app = create_app()


def main() -> None:
    port = int(os.getenv("CODEX_MCP_RELAY_PORT", "8891"))
    uvicorn.run("mcp_relay.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
