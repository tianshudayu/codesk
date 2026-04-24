from __future__ import annotations

import asyncio
import contextlib
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketDisconnect
import uvicorn

from .adapter import CodexAdapter, create_adapter
from .auth import PairingManager
from .cloud_agent import CloudAgentClient, NullCloudAgentClient
from .desktop_automation import DesktopAutomationClient, DesktopAutomationSendError, DesktopAutomationUnavailableError
from .relay_client import RelayClient
from .service import BridgeService, BridgeServiceError
from .session_store import SessionStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "bridge" / "static"


def _default_runtime_root() -> Path:
    configured = os.getenv("CODEX_RUNTIME_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    identity_file = os.getenv("CODEX_CLOUD_AGENT_IDENTITY_FILE", "").strip()
    if identity_file:
        try:
            return Path(identity_file).expanduser().resolve().parent
        except Exception:
            pass
    return PROJECT_ROOT


@dataclass(slots=True)
class BridgeRuntime:
    pairing: PairingManager
    store: SessionStore
    adapter: CodexAdapter
    workspace_roots: list[str]
    service: BridgeService
    relay_snapshot: dict[str, Any]
    desktop_automation: Any | None = None
    relay_client: Any | None = None
    cloud_agent: Any | None = None


class PairRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class SessionCreateRequest(BaseModel):
    workspace: str
    prompt: str = Field(min_length=1)
    title: str | None = None
    interaction_mode: str | None = Field(default=None, alias="interactionMode")
    attachment_ids: list[str] | None = Field(default=None, alias="attachmentIds")


class SessionMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    interaction_mode: str | None = Field(default=None, alias="interactionMode")
    attachment_ids: list[str] | None = Field(default=None, alias="attachmentIds")


class ThreadResumeRequest(BaseModel):
    prompt: str | None = None
    interaction_mode: str | None = Field(default=None, alias="interactionMode")
    attachment_ids: list[str] | None = Field(default=None, alias="attachmentIds")


class ApprovalResolveRequest(BaseModel):
    action: str = Field(min_length=1)
    answers: list[dict[str, Any]] | None = None
    content: str | None = None


class TestApprovalRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


class ActiveSessionRequest(BaseModel):
    session_id: str | None = Field(default=None, alias="sessionId")
    source: str | None = None


def _workspace_roots_from_env() -> list[str]:
    configured = os.getenv("CODEX_MCP_WORKSPACES", "").strip()
    if configured:
        return [item.strip() for item in configured.split(";") if item.strip()]
    return []


def build_runtime(
    *,
    workspace_roots: list[str] | None = None,
    pairing: PairingManager | None = None,
    store: SessionStore | None = None,
    adapter: CodexAdapter | None = None,
    desktop_automation: Any | None = None,
    enable_relay: bool | None = None,
    enable_cloud_agent: bool | None = None,
) -> BridgeRuntime:
    runtime_store = store or SessionStore()
    runtime_pairing = pairing or PairingManager()
    runtime_adapter = adapter or create_adapter(runtime_store)
    runtime_desktop_automation = desktop_automation or DesktopAutomationClient()
    roots = _workspace_roots_from_env() if workspace_roots is None else workspace_roots
    service = BridgeService(
        pairing=runtime_pairing,
        store=runtime_store,
        adapter=runtime_adapter,
        workspace_roots=roots,
        default_workspace_root=str(_default_runtime_root()),
        desktop_automation=runtime_desktop_automation,
    )
    relay_snapshot: dict[str, Any] = {"status": "disabled"}
    relay_client = None
    cloud_agent = None
    relay_enabled = enable_relay
    if relay_enabled is None:
        relay_enabled = os.getenv("CODEX_MCP_RELAY_ENABLED", "1").strip().lower() not in {"0", "false", "off"}
    if relay_enabled:
        relay_snapshot = {"status": "starting"}
        relay_client = RelayClient(
            service=service,
            store=runtime_store,
            verify_token=runtime_pairing.verify_token,
            snapshot=relay_snapshot,
        )
    cloud_enabled = enable_cloud_agent
    if cloud_enabled is None:
        cloud_enabled = os.getenv("CODEX_CLOUD_ENABLED", "1").strip().lower() not in {"0", "false", "off"}
    if cloud_enabled:
        cloud_agent = CloudAgentClient(
            service=service,
            store=runtime_store,
            desktop_automation=runtime_desktop_automation,
        )
    else:
        cloud_agent = NullCloudAgentClient()
    return BridgeRuntime(
        pairing=runtime_pairing,
        store=runtime_store,
        adapter=runtime_adapter,
        workspace_roots=roots,
        service=service,
        relay_snapshot=relay_snapshot,
        desktop_automation=runtime_desktop_automation,
        relay_client=relay_client,
        cloud_agent=cloud_agent,
    )


def _ensure_local_request(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="管理接口仅允许本机访问。")


def _extract_token(
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
) -> str:
    if access_token:
        return access_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    raise HTTPException(status_code=401, detail="缺少访问令牌。")


def _runtime_from_request(request: Request) -> BridgeRuntime:
    return request.app.state.runtime


def require_auth(request: Request, token: str = Depends(_extract_token)) -> str:
    runtime = _runtime_from_request(request)
    if not runtime.pairing.verify_token(token):
        raise HTTPException(status_code=401, detail="访问令牌无效或已过期。")
    return token


def _extract_ws_token(websocket: WebSocket) -> str | None:
    token = websocket.query_params.get("access_token")
    if token:
        return token
    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _desktop_ws_ready_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "ready",
        "windowLocked": bool(snapshot.get("windowLocked")),
        "title": snapshot.get("windowTitle"),
        "lockedWindow": snapshot.get("lockedWindow"),
        "previewEnabled": bool(snapshot.get("previewSupported")),
        "connected": bool(snapshot.get("connected")),
        "authenticated": bool(snapshot.get("authenticated")),
        "codexWindowLocked": bool(snapshot.get("codexWindowLocked")),
    }


def _raise_service_error(exc: BridgeServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def create_app(runtime: BridgeRuntime | None = None) -> FastAPI:
    app_runtime = runtime or build_runtime()

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        try:
            await app_instance.state.runtime.service.start_background_tasks()
            if app_instance.state.runtime.relay_client is not None:
                await app_instance.state.runtime.relay_client.start()
            if app_instance.state.runtime.cloud_agent is not None:
                await app_instance.state.runtime.cloud_agent.start()
            yield
        finally:
            if app_instance.state.runtime.cloud_agent is not None:
                await app_instance.state.runtime.cloud_agent.close()
            if app_instance.state.runtime.relay_client is not None:
                await app_instance.state.runtime.relay_client.close()
            await app_instance.state.runtime.service.stop_background_tasks()
            await app_instance.state.runtime.adapter.close()

    app = FastAPI(title="Codex MCP Mobile Bridge", lifespan=lifespan)
    app.state.runtime = app_runtime
    app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")

    @app.middleware("http")
    async def cache_control(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health(request: Request) -> JSONResponse:
        payload = await _runtime_from_request(request).service.health_payload()
        return JSONResponse(payload)

    @app.get("/api/admin/state")
    async def admin_state(request: Request) -> JSONResponse:
        _ensure_local_request(request)
        runtime_state = _runtime_from_request(request)
        payload = await runtime_state.service.admin_state_payload(relay=runtime_state.relay_snapshot)
        payload["cloudAgent"] = runtime_state.cloud_agent.snapshot() if runtime_state.cloud_agent is not None else NullCloudAgentClient().snapshot()
        return JSONResponse(payload)

    @app.post("/api/admin/pair/reset")
    async def reset_pair_code(request: Request) -> JSONResponse:
        _ensure_local_request(request)
        return JSONResponse(_runtime_from_request(request).service.reset_pair_code())

    @app.post("/api/admin/sessions/{session_id}/test-approval")
    async def inject_test_approval(
        session_id: str,
        payload: TestApprovalRequest,
        request: Request,
    ) -> JSONResponse:
        _ensure_local_request(request)
        try:
            result = await _runtime_from_request(request).service.inject_test_approval_payload(
                session_id,
                title=payload.title,
                summary=payload.summary,
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.post("/api/auth/pair")
    async def pair_device(payload: PairRequest, request: Request) -> JSONResponse:
        try:
            result = _runtime_from_request(request).service.pair_device(payload.code)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/workspaces")
    async def list_workspaces(request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        return JSONResponse(await _runtime_from_request(request).service.list_workspaces_payload())

    @app.get("/api/ui/active-session")
    async def get_active_session(request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        payload = await _runtime_from_request(request).service.get_active_session_payload()
        return JSONResponse(payload)

    @app.post("/api/attachments")
    async def upload_attachment(
        request: Request,
        file: UploadFile = File(...),
        _: str = Depends(require_auth),
    ) -> JSONResponse:
        data = await file.read()
        try:
            result = await _runtime_from_request(request).service.upload_attachment_payload(
                file_name=file.filename or "image",
                mime_type=file.content_type or "",
                data=data,
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/attachments/{attachment_id}/preview")
    async def attachment_preview(
        attachment_id: str,
        request: Request,
        _: str = Depends(require_auth),
    ) -> FileResponse:
        try:
            attachment, path = await _runtime_from_request(request).service.get_attachment_preview_payload(attachment_id)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return FileResponse(path, media_type=attachment.mime_type, filename=attachment.file_name)

    @app.post("/api/ui/active-session")
    async def set_active_session(
        payload: ActiveSessionRequest,
        request: Request,
        _: str = Depends(require_auth),
    ) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.set_active_session_payload(
                payload.session_id,
                source=payload.source or "ui",
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/sessions")
    async def list_sessions(request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        payload = await _runtime_from_request(request).service.list_sessions_payload()
        return JSONResponse(payload)

    @app.post("/api/sessions")
    async def create_session(payload: SessionCreateRequest, request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.create_session_payload(
                payload.workspace,
                payload.prompt,
                payload.title,
                interaction_mode=payload.interaction_mode,
                attachment_ids=payload.attachment_ids,
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str, request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.get_session_payload(session_id)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.post("/api/sessions/{session_id}/messages")
    async def continue_session(
        session_id: str,
        payload: SessionMessageRequest,
        request: Request,
        _: str = Depends(require_auth),
    ) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.continue_session_payload(
                session_id,
                payload.content,
                interaction_mode=payload.interaction_mode,
                attachment_ids=payload.attachment_ids,
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.post("/api/sessions/{session_id}/desktop-align")
    async def align_desktop_session(
        session_id: str,
        request: Request,
        _: str = Depends(require_auth),
    ) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.align_desktop_session_payload(session_id)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.post("/api/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str, request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.cancel_session_payload(session_id)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/sessions/{session_id}/approvals")
    async def list_approvals(session_id: str, request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.list_approvals_payload(session_id)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.post("/api/sessions/{session_id}/approvals/{approval_id}/resolve")
    async def resolve_approval(
        session_id: str,
        approval_id: str,
        payload: ApprovalResolveRequest,
        request: Request,
        _: str = Depends(require_auth),
    ) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.resolve_approval_payload(
                session_id,
                approval_id,
                payload.action,
                answers=payload.answers,
                content=payload.content,
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/threads")
    async def list_threads(request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.list_threads_payload()
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/threads/{thread_id}")
    async def get_thread(thread_id: str, request: Request, _: str = Depends(require_auth)) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.get_thread_payload(thread_id)
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.post("/api/threads/{thread_id}/resume")
    async def resume_thread(
        thread_id: str,
        payload: ThreadResumeRequest,
        request: Request,
        _: str = Depends(require_auth),
    ) -> JSONResponse:
        try:
            result = await _runtime_from_request(request).service.resume_thread_payload(
                thread_id,
                payload.prompt,
                interaction_mode=payload.interaction_mode,
                attachment_ids=payload.attachment_ids,
            )
        except BridgeServiceError as exc:
            _raise_service_error(exc)
        return JSONResponse(result)

    @app.get("/api/sessions/{session_id}/events")
    async def session_events(session_id: str, request: Request, _: str = Depends(require_auth)) -> StreamingResponse:
        runtime_state = _runtime_from_request(request)
        subscriber_id, queue, history = await runtime_state.store.subscribe(session_id)
        if subscriber_id is None or queue is None:
            raise HTTPException(status_code=404, detail="会话不存在。")

        async def stream():
            try:
                for item in history:
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            finally:
                await runtime_state.store.unsubscribe(session_id, subscriber_id)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/ui/events")
    async def ui_events(request: Request, _: str = Depends(require_auth)) -> StreamingResponse:
        runtime_state = _runtime_from_request(request)
        subscriber_id, queue = await runtime_state.store.subscribe_ui()

        async def stream():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            finally:
                await runtime_state.store.unsubscribe_ui(subscriber_id)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.websocket("/api/desktop/ws")
    async def desktop_events(websocket: WebSocket) -> None:
        runtime_state = websocket.app.state.runtime
        token = _extract_ws_token(websocket)
        await websocket.accept()
        if not token or not runtime_state.pairing.verify_token(token):
            await websocket.send_json({"type": "error", "code": "invalid_token", "message": "访问令牌无效或已过期。"})
            await websocket.close(code=4401)
            return

        desktop = runtime_state.desktop_automation
        subscriber_id, queue = await desktop.subscribe()
        forward_task: asyncio.Task[None] | None = None

        async def forward_messages() -> None:
            while True:
                message = await queue.get()
                await websocket.send_json(message)

        try:
            await websocket.send_json(_desktop_ws_ready_payload(desktop.snapshot()))
            forward_task = asyncio.create_task(forward_messages(), name="desktop-ws-forward")
            while True:
                payload = await websocket.receive_json()
                if not isinstance(payload, dict):
                    await websocket.send_json({"type": "error", "code": "invalid_message", "message": "desktop websocket message must be a JSON object"})
                    continue
                message_type = str(payload.get("type") or "")
                if message_type not in {"preview.subscribe", "pointer.down", "pointer.move", "pointer.up", "gesture.scroll"}:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "id": payload.get("id"),
                            "code": "invalid_message",
                            "message": f"unsupported desktop websocket message: {message_type or 'unknown'}",
                        }
                    )
                    continue
                try:
                    await desktop.send_command(payload, expect_ack=True)
                except DesktopAutomationUnavailableError as exc:
                    await websocket.send_json({"type": "error", "id": payload.get("id"), "code": "desktop_unavailable", "message": str(exc)})
                except DesktopAutomationSendError as exc:
                    await websocket.send_json({"type": "error", "id": payload.get("id"), "code": "desktop_send_failed", "message": str(exc)})
        except WebSocketDisconnect:
            return
        finally:
            await desktop.unsubscribe(subscriber_id)
            if forward_task is not None:
                forward_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await forward_task

    return app


runtime = build_runtime()
pairing = runtime.pairing
store = runtime.store
app = create_app(runtime)


def main() -> None:
    port = int(os.getenv("CODEX_MCP_BRIDGE_PORT", "8890"))
    uvicorn.run("bridge.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
