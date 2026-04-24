from __future__ import annotations

import asyncio
import base64
import io
import ipaddress
import logging
import os
import secrets
import threading
import webbrowser
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import segno
from starlette.websockets import WebSocketDisconnect
import uvicorn

from .config_store import ConfigStore
from .codex_uia import UIAutomationError, UIAutomationUnavailableError
from .hotkeys import HotkeyManager
from .logging_utils import configure_logging, log_event
from .networking import list_candidate_addresses
from .paths import resolve_runtime_paths
from .relay_client import RelayClient
from .security import PinManager
from .session import MobileConnection, SessionStore
from .version import APP_NAME, APP_VERSION
from .windows_control import EnsureWindowResult, WindowsController


LOGGER = logging.getLogger(APP_NAME)
TEXT_LIMIT_BYTES = 64 * 1024
PREVIEW_FRAME_INTERVAL_SECONDS = 0.25
FOREGROUND_SYNC_INTERVAL_SECONDS = 0.35


@dataclass(slots=True)
class RecentIssue:
    timestamp: str
    code: str
    message: str
    stage: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp,
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
        }


class AppRuntime:
    def __init__(self) -> None:
        self.paths = resolve_runtime_paths()
        self.config_store = ConfigStore(self.paths)
        self.pin_manager = PinManager(self.config_store)
        self.port = self.config_store.port
        configure_logging(self.paths.log_file)

        self.session = SessionStore()
        self.windows = WindowsController()
        self.hotkeys = HotkeyManager(self.lock_foreground_window, self.unlock_window)
        self.relay_client = RelayClient(self.handle_relay_message)
        self._recent_issues: deque[RecentIssue] = deque(maxlen=8)
        self._recent_lock = threading.Lock()
        self._preview_task: asyncio.Task[None] | None = None
        self._preview_stop = asyncio.Event()
        self._foreground_task: asyncio.Task[None] | None = None
        self._foreground_stop = asyncio.Event()
        self._preview_sequence = 0
        self._last_preview_issue_signature: tuple[str, str] | None = None

        log_event(
            LOGGER,
            logging.INFO,
            "app_initialized",
            version=APP_VERSION,
            port=self.port,
            config_path=str(self.paths.config_file),
            log_path=str(self.paths.log_file),
        )

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.session.attach_loop(loop)

    async def start_background_tasks(self) -> None:
        if self._preview_task is not None:
            return
        self._preview_stop.clear()
        self._foreground_stop.clear()
        self._preview_task = asyncio.create_task(self._preview_loop(), name="preview-loop")
        self._foreground_task = asyncio.create_task(self._foreground_loop(), name="foreground-sync-loop")

    async def stop_background_tasks(self) -> None:
        preview_task = self._preview_task
        foreground_task = self._foreground_task
        if preview_task is None and foreground_task is None:
            return
        self._preview_stop.set()
        self._foreground_stop.set()
        self._preview_task = None
        self._foreground_task = None
        if preview_task is not None:
            preview_task.cancel()
            try:
                await preview_task
            except asyncio.CancelledError:
                pass
        if foreground_task is not None:
            foreground_task.cancel()
            try:
                await foreground_task
            except asyncio.CancelledError:
                pass

    def admin_state(self) -> dict[str, object]:
        self.sync_foreground_codex_window(discover_background=True, include_restorable=True)
        snapshot = self.session.snapshot()
        token = snapshot.session_token
        address_models = list_candidate_addresses()
        addresses = [item.to_dict(self.port, token) for item in address_models]
        relay_snapshot = self.relay_client.snapshot()
        preferred_connection = _build_preferred_connection(self.port, token, address_models, relay_snapshot)
        codex_window = snapshot.locked_window if self.windows._looks_like_codex_desktop_window(snapshot.locked_window) else None
        codex_found = codex_window is not None
        codex_foreground = self.windows.is_foreground_window(codex_window)
        desktop_message = _desktop_control_message(codex_found, codex_foreground)
        return {
            "version": APP_VERSION,
            "port": self.port,
            "sessionToken": token,
            "currentPin": self.pin_manager.current_pin,
            "pinEnabled": True,
            "pinLastRotatedAt": self.pin_manager.pin_last_rotated_at,
            "mobileConnected": snapshot.mobile_connected,
            "mobileTransport": snapshot.mobile_transport,
            "previewSupported": self.windows.preview_supported(),
            "lockedWindow": snapshot.locked_window.to_public_dict() if snapshot.locked_window else None,
            "codexWindowFound": codex_found,
            "codexForeground": codex_foreground,
            "codexWindowControllable": codex_found,
            "desktopControlMessage": desktop_message,
            "candidateAddresses": addresses,
            "relay": relay_snapshot.to_public_dict(),
            "preferredConnection": preferred_connection,
            "configPath": str(self.paths.config_file),
            "logPath": str(self.paths.log_file),
            "recentErrors": [item.to_public_dict() for item in self.recent_issues()],
        }

    def lock_foreground_window(self) -> None:
        window = self.windows.capture_foreground_window()
        self.session.set_locked_window(window)
        self.session.run_coro_threadsafe(self.broadcast_state())
        if window:
            log_event(
                LOGGER,
                logging.INFO,
                "window_locked",
                hwnd=window.hwnd,
                title=window.title,
                process_name=window.process_name,
            )
        else:
            self.record_issue("window_lock_failed", "锁定当前前台窗口失败。", "window")

    def unlock_window(self) -> None:
        self.session.set_locked_window(None)
        self.session.run_coro_threadsafe(self.broadcast_state())
        log_event(LOGGER, logging.INFO, "window_unlocked")

    def sync_foreground_codex_window(
        self,
        *,
        discover_background: bool = True,
        restore_background: bool = False,
        include_restorable: bool = False,
    ) -> bool:
        snapshot = self.session.snapshot()
        previous = snapshot.locked_window
        if snapshot.pointer_active and previous is not None:
            return False
        if previous is not None and not self.windows._looks_like_codex_desktop_window(previous):
            self.session.set_locked_window(None)
            previous = None
        window = self.windows.capture_foreground_window()
        if window is not None and self.windows._looks_like_codex_desktop_window(window):
            if previous and previous.hwnd == window.hwnd:
                return False
            self.session.set_locked_window(window)
            return True
        refreshed = self.windows.refresh_locked_window(previous)
        if refreshed is not None and self.windows._looks_like_codex_desktop_window(refreshed):
            if previous and previous.hwnd == refreshed.hwnd:
                return False
            self.session.set_locked_window(refreshed)
            return True
        if discover_background:
            discovered = self.windows.find_codex_window(restore=restore_background, include_restorable=include_restorable)
            if discovered is not None:
                if previous and previous.hwnd == discovered.hwnd:
                    return False
                self.session.set_locked_window(discovered)
                return True
        if previous is not None:
            self.session.set_locked_window(None)
            return True
        return False

    def ensure_codex_window_locked(self, *, focus: bool) -> EnsureWindowResult:
        self.sync_foreground_codex_window(discover_background=True, restore_background=focus)
        snapshot = self.session.snapshot()
        locked_window = snapshot.locked_window
        if locked_window is None or not self.windows._looks_like_codex_desktop_window(locked_window):
            return EnsureWindowResult(
                False,
                "codex_window_not_found",
                "未发现可见的 Codex 主窗口，请打开 Codex 并保持窗口可见。",
            )
        if not focus:
            return EnsureWindowResult(True, window=locked_window)
        result = self.windows.ensure_window_ready(locked_window)
        if result.ok and result.window is not None and self.windows._looks_like_codex_desktop_window(result.window):
            self.session.set_locked_window(result.window)
            return result
        if result.error_code == "window_missing":
            self.session.set_locked_window(None)
        return result

    def rotate_pin(self) -> dict[str, str]:
        pin = self.pin_manager.rotate_pin()
        log_event(LOGGER, logging.INFO, "pin_rotated")
        return {
            "currentPin": pin,
            "pinLastRotatedAt": self.pin_manager.pin_last_rotated_at,
        }

    def recent_issues(self) -> list[RecentIssue]:
        with self._recent_lock:
            return list(self._recent_issues)

    def record_issue(
        self,
        code: str,
        message: str,
        stage: str,
        level: int = logging.WARNING,
        **context: object,
    ) -> None:
        issue = RecentIssue(
            timestamp=_now_iso(),
            code=code,
            message=message,
            stage=stage,
        )
        with self._recent_lock:
            self._recent_issues.appendleft(issue)
        log_event(
            LOGGER,
            level,
            "runtime_issue",
            code=code,
            message=message,
            stage=stage,
            **context,
        )

    async def disconnect_active_mobile(self, reason: str, code: int = 4001) -> None:
        connection = self.session.active_connection()
        if connection is None:
            return
        self.session.clear_mobile(connection.connection_id)
        self.release_pointer_if_needed()
        try:
            await connection.close(reason, code)
        except RuntimeError:
            pass

    def release_pointer_if_needed(self) -> None:
        snapshot = self.session.snapshot()
        if not snapshot.pointer_active:
            return
        try:
            self.windows.release_left_button()
        except Exception as exc:
            self.record_issue("pointer_release_failed", str(exc), "pointer", level=logging.ERROR)
        finally:
            self.session.set_pointer_active(False)

    async def broadcast_state(self) -> None:
        connection = self.session.active_connection()
        if connection is None:
            return
        snapshot = self.session.snapshot()
        codex_found = self.windows._looks_like_codex_desktop_window(snapshot.locked_window)
        codex_foreground = self.windows.is_foreground_window(snapshot.locked_window)
        payload = {
            "type": "state",
            "windowLocked": snapshot.locked_window is not None,
            "title": snapshot.locked_window.title if snapshot.locked_window else None,
            "lockedWindow": snapshot.locked_window.to_public_dict() if snapshot.locked_window else None,
            "previewEnabled": self.windows.preview_supported(),
            "codexWindowFound": codex_found,
            "codexForeground": codex_foreground,
            "codexWindowControllable": codex_found,
            "desktopControlMessage": _desktop_control_message(codex_found, codex_foreground),
        }
        try:
            await connection.send_json(payload)
        except Exception:
            self.session.clear_mobile(connection.connection_id)

    async def authenticate_mobile(
        self,
        connection: MobileConnection,
        hello_message: object,
        client_host: str,
    ) -> bool:
        if not isinstance(hello_message, dict):
            await _send_error(connection, None, "invalid_message", "第一条消息必须是 JSON 对象。")
            await connection.close("第一条消息必须是 hello。", 4002)
            return False
        if hello_message.get("type") != "hello":
            await _send_error(connection, hello_message.get("id"), "invalid_message", "第一条消息必须是 hello。")
            await connection.close("第一条消息必须是 hello。", 4002)
            return False

        client_name = hello_message.get("client") if isinstance(hello_message.get("client"), str) else ""
        if client_name == "bridge-desktop-automation":
            await self.disconnect_active_mobile("Bridge desktop automation connected.", 4001)

        active = self.session.active_connection()
        if active is not None and active.connection_id != connection.connection_id:
            self.record_issue("session_busy", "当前已有一台手机连接，已拒绝新的连接。", "auth", client_host=client_host)
            await _send_error(connection, hello_message.get("id"), "session_busy", "当前已有另一台手机连接。")
            await connection.close("当前已有另一台手机连接。", 4009)
            return False

        pin = hello_message.get("pin", "")
        verification = self.pin_manager.verify_pin(client_host, pin.strip() if isinstance(pin, str) else "")
        if not verification.ok:
            self.record_issue(
                verification.code or "invalid_pin",
                verification.message or "会话 PIN 无效。",
                "auth",
                client_host=client_host,
            )
            await _send_error(connection, hello_message.get("id"), verification.code, verification.message)
            await connection.close(
                verification.message or "会话 PIN 无效。",
                4010 if verification.code == "pin_throttled" else 4004,
            )
            return False

        if not self.session.register_mobile(connection):
            self.record_issue("session_busy", "当前已有一台手机连接，已拒绝新的连接。", "auth", client_host=client_host)
            await _send_error(connection, hello_message.get("id"), "session_busy", "当前已有另一台手机连接。")
            await connection.close("当前已有另一台手机连接。", 4009)
            return False

        log_event(
            LOGGER,
            logging.INFO,
            "mobile_authenticated",
            client_host=client_host,
            transport=connection.transport,
        )
        await asyncio.to_thread(self.sync_foreground_codex_window, discover_background=True, include_restorable=True)
        await connection.send_json(_ready_payload())
        return True

    async def handle_authenticated_message(self, connection: MobileConnection, message: object) -> None:
        if not isinstance(message, dict):
            await _send_error(connection, None, "invalid_message", "消息必须是 JSON 对象。")
            return
        await _handle_ws_message(connection, message)

    async def handle_relay_message(self, payload: dict[str, object]) -> None:
        message_type = payload.get("type")
        if message_type == "relay.mobile.connected":
            log_event(LOGGER, logging.INFO, "relay_mobile_connected", mobile_id=payload.get("mobile_id"))
            return
        if message_type == "relay.mobile.disconnected":
            mobile_id = str(payload.get("mobile_id") or "")
            if mobile_id:
                if self.session.clear_mobile(f"relay:{mobile_id}"):
                    self.release_pointer_if_needed()
            log_event(LOGGER, logging.INFO, "relay_mobile_disconnected", mobile_id=mobile_id)
            return
        if message_type != "relay.mobile.message":
            return

        mobile_id = str(payload.get("mobile_id") or "")
        inner_payload = payload.get("payload")
        if not mobile_id:
            return
        connection = self.build_relay_mobile_connection(mobile_id)
        active = self.session.active_connection()
        if active is None or active.connection_id != connection.connection_id:
            if isinstance(inner_payload, dict) and inner_payload.get("type") == "hello":
                await self.authenticate_mobile(connection, inner_payload, client_host=f"relay:{mobile_id}")
                return
            await _send_error(connection, None, "invalid_message", "第一条消息必须是 hello。")
            await connection.close("第一条消息必须是 hello。", 4002)
            return
        await self.handle_authenticated_message(connection, inner_payload)

    def build_relay_mobile_connection(self, mobile_id: str) -> MobileConnection:
        async def send_json(payload: dict[str, object]) -> None:
            await self.relay_client.send_business_message(mobile_id, payload)

        async def close(reason: str, code: int) -> None:
            await self.relay_client.close_mobile(mobile_id, reason, code)

        return MobileConnection(
            connection_id=f"relay:{mobile_id}",
            transport="relay",
            send_json=send_json,
            close=close,
        )

    async def _preview_loop(self) -> None:
        while not self._preview_stop.is_set():
            try:
                await self._preview_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.record_issue(
                    "preview_loop_failed",
                    str(exc) or repr(exc),
                    "preview",
                    level=logging.ERROR,
                )
            await asyncio.sleep(PREVIEW_FRAME_INTERVAL_SECONDS)

    async def _foreground_loop(self) -> None:
        while not self._foreground_stop.is_set():
            try:
                if await asyncio.to_thread(self.sync_foreground_codex_window, discover_background=False):
                    await self.broadcast_state()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.record_issue(
                    "foreground_sync_failed",
                    str(exc) or repr(exc),
                    "window",
                    level=logging.ERROR,
                )
            await asyncio.sleep(FOREGROUND_SYNC_INTERVAL_SECONDS)

    async def _preview_once(self) -> None:
        snapshot = self.session.snapshot()
        connection = self.session.active_connection()
        if connection is None or not snapshot.preview_requested:
            self._last_preview_issue_signature = None
            return
        if snapshot.locked_window is None:
            await self._send_preview_unavailable(connection, "window_not_locked", "当前还没有锁定目标窗口。")
            return
        if not self.windows.preview_supported():
            await self._send_preview_unavailable(connection, "preview_unsupported", "当前环境缺少窗口预览依赖。")
            return

        result = await asyncio.to_thread(self.ensure_codex_window_locked, focus=False)
        if not result.ok or result.window is None:
            if result.error_code == "window_missing":
                self.session.set_locked_window(None)
                await self.broadcast_state()
            await self._send_preview_unavailable(
                connection,
                result.error_code or "preview_unavailable",
                result.message or "当前无法生成窗口预览。",
            )
            return

        self.session.set_locked_window(result.window)
        try:
            frame = await asyncio.to_thread(self.windows.capture_window_preview, result.window)
        except Exception as exc:
            self.record_issue("preview_capture_failed", str(exc), "preview", level=logging.ERROR)
            await self._send_preview_unavailable(connection, "capture_failed", str(exc))
            return

        self._last_preview_issue_signature = None
        self._preview_sequence += 1
        await connection.send_json(
            {
                "type": "preview.frame",
                "seq": self._preview_sequence,
                "format": "jpeg",
                "width": frame.width,
                "height": frame.height,
                "data": base64.b64encode(frame.jpeg_bytes).decode("ascii"),
                "capturedAt": _now_iso(),
            }
        )

    async def _send_preview_unavailable(self, connection: MobileConnection, code: str, message: str) -> None:
        signature = (code, message)
        if self._last_preview_issue_signature == signature:
            return
        self._last_preview_issue_signature = signature
        await connection.send_json({"type": "preview.unavailable", "code": code, "message": message})


runtime = AppRuntime()
app = FastAPI(title=APP_NAME, lifespan=None)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    runtime.attach_loop(asyncio.get_running_loop())
    runtime.hotkeys.start()
    await runtime.relay_client.start()
    await runtime.start_background_tasks()
    log_event(LOGGER, logging.INFO, "app_started", port=runtime.port)
    threading.Thread(target=_open_admin_page, args=(runtime.port,), daemon=True).start()
    try:
        yield
    finally:
        await runtime.stop_background_tasks()
        await runtime.relay_client.stop()
        runtime.hotkeys.stop()
        log_event(LOGGER, logging.INFO, "app_stopped")


app.router.lifespan_context = lifespan
app.mount("/static", StaticFiles(directory=runtime.paths.static_dir), name="static")


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "version": APP_VERSION,
            "admin": f"http://127.0.0.1:{runtime.port}/admin",
        }
    )


@app.get("/admin")
async def admin_page(request: Request) -> FileResponse:
    _ensure_local_request(request)
    return FileResponse(runtime.paths.static_dir / "admin.html")


@app.get("/remote")
async def remote_page() -> FileResponse:
    return FileResponse(runtime.paths.static_dir / "remote.html")


@app.get("/api/admin/state")
async def admin_state(request: Request) -> JSONResponse:
    _ensure_local_request(request)
    return JSONResponse(await asyncio.to_thread(runtime.admin_state))


@app.get("/api/admin/connect-qr.svg")
async def connect_qr(request: Request) -> Response:
    _ensure_local_request(request)
    state = await asyncio.to_thread(runtime.admin_state)
    preferred_connection = state.get("preferredConnection") or {}
    mobile_url = preferred_connection.get("mobileUrl")
    if not isinstance(mobile_url, str) or not mobile_url:
        raise HTTPException(status_code=404, detail="当前没有可用的手机连接地址。")
    output = io.BytesIO()
    segno.make(mobile_url, micro=False).save(output, kind="svg", scale=4, border=2)
    return Response(content=output.getvalue(), media_type="image/svg+xml")


@app.post("/api/admin/token/reset")
async def reset_token(request: Request) -> JSONResponse:
    _ensure_local_request(request)
    token, connection = runtime.session.reset_token()
    if connection is not None:
        await _close_connection(connection, "会话 Token 已重置。", 4001)
    log_event(LOGGER, logging.INFO, "token_rotated")
    return JSONResponse({"sessionToken": token})


@app.post("/api/admin/pin/reset")
async def reset_pin(request: Request) -> JSONResponse:
    _ensure_local_request(request)
    payload = runtime.rotate_pin()
    await runtime.disconnect_active_mobile("会话 PIN 已重置。", code=4005)
    return JSONResponse(payload)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client_host = _resolve_client_host(websocket)
    await websocket.accept()

    token = websocket.query_params.get("token", "")
    if token != runtime.session.current_token():
        runtime.record_issue("invalid_token", "检测到无效 Token，连接已拒绝。", "auth", client_host=client_host)
        await websocket.send_json(
            {
                "type": "error",
                "id": None,
                "code": "invalid_token",
                "message": "会话 Token 无效。",
            }
        )
        await websocket.close(code=4003)
        return

    connection = _build_local_mobile_connection(websocket)
    try:
        hello_message = await websocket.receive_json()
        authenticated = await runtime.authenticate_mobile(connection, hello_message, client_host)
        if not authenticated:
            return

        while True:
            message = await websocket.receive_json()
            await runtime.handle_authenticated_message(connection, message)
    except WebSocketDisconnect:
        log_event(
            LOGGER,
            logging.INFO,
            "mobile_disconnected",
            client_host=client_host,
            transport=connection.transport,
        )
    finally:
        if runtime.session.clear_mobile(connection.connection_id):
            runtime.release_pointer_if_needed()


async def _handle_ws_message(connection: MobileConnection, message: dict[str, object]) -> None:
    message_type = message.get("type")
    message_id = message.get("id")

    if message_type == "preview.subscribe":
        await _handle_preview_subscribe(connection, message_id)
        return
    if message_type == "text.send":
        await _handle_text_send(connection, message_id, message.get("text"), message.get("submit"))
        return
    if message_type == "codex.thread.focus":
        await _handle_codex_thread_focus(
            connection,
            message_id,
            message.get("workspace"),
            message.get("title"),
            message.get("preview"),
        )
        return
    if message_type == "codex.thread.new":
        await _handle_codex_thread_new(connection, message_id, message.get("workspace"))
        return
    if message_type == "gesture.scroll":
        await _handle_scroll(connection, message_id, message.get("dy"), message.get("xRatio"), message.get("yRatio"))
        return
    if message_type == "pointer.down":
        await _handle_pointer_down(connection, message_id, message.get("xRatio"), message.get("yRatio"))
        return
    if message_type == "pointer.move":
        await _handle_pointer_move(connection, message_id, message.get("xRatio"), message.get("yRatio"))
        return
    if message_type == "pointer.up":
        await _handle_pointer_up(connection, message_id, message.get("xRatio"), message.get("yRatio"))
        return

    await _send_error(connection, message_id, "invalid_message", f"不支持的消息类型：{message_type}")


async def _handle_preview_subscribe(connection: MobileConnection, message_id: object) -> None:
    await asyncio.to_thread(runtime.ensure_codex_window_locked, focus=False)
    runtime.session.set_preview_requested(True)
    runtime._last_preview_issue_signature = None
    await connection.send_json({"type": "ack", "id": message_id})


async def _handle_text_send(connection: MobileConnection, message_id: object, text: object, submit: object) -> None:
    if not isinstance(text, str):
        await _send_error(connection, message_id, "invalid_message", "text 字段必须是字符串。")
        return
    if len(text.encode("utf-8")) > TEXT_LIMIT_BYTES:
        await _send_error(connection, message_id, "payload_too_large", "文本长度不能超过 64 KiB。")
        return

    result = await asyncio.to_thread(runtime.ensure_codex_window_locked, focus=True)
    if not result.ok:
        await _handle_window_failure(connection, message_id, result)
        return

    runtime.session.set_locked_window(result.window)
    try:
        await asyncio.to_thread(runtime.windows.paste_text, text, submit=bool(submit), target_window=result.window)
        log_event(
            LOGGER,
            logging.INFO,
            "text_pasted",
            text_bytes=len(text.encode("utf-8")),
            window_title=result.window.title if result.window else "",
            transport=connection.transport,
            submit=bool(submit),
        )
    except Exception as exc:
        runtime.record_issue("action_failed", str(exc), "paste", level=logging.ERROR)
        await _send_error(connection, message_id, "action_failed", str(exc))
        return

    await connection.send_json({"type": "ack", "id": message_id})
    await runtime.broadcast_state()


async def _handle_codex_thread_focus(
    connection: MobileConnection,
    message_id: object,
    workspace: object,
    title: object,
    preview: object,
) -> None:
    normalized_workspace = workspace if isinstance(workspace, str) else None
    normalized_title = title if isinstance(title, str) else None
    normalized_preview = preview if isinstance(preview, str) else None
    if not (normalized_workspace and normalized_workspace.strip()):
        await _send_error(connection, message_id, "invalid_message", "workspace must be a non-empty string.")
        return
    if not (normalized_title and normalized_title.strip()):
        await _send_error(connection, message_id, "invalid_message", "title must be a non-empty string.")
        return
        await _send_error(connection, message_id, "invalid_message", "title 或 preview 至少需要提供一个。")
        return
    result = await asyncio.to_thread(runtime.ensure_codex_window_locked, focus=True)
    if not result.ok or result.window is None:
        await _handle_window_failure(connection, message_id, result)
        return
    runtime.session.set_locked_window(result.window)
    try:
        match = await asyncio.to_thread(
            runtime.windows.focus_codex_thread_by_text,
            result.window,
            workspace=normalized_workspace,
            title=normalized_title,
            preview=normalized_preview,
        )
    except UIAutomationUnavailableError as exc:
        await _send_error(connection, message_id, "uia_unavailable", str(exc))
        return
    except UIAutomationError as exc:
        await _send_error(connection, message_id, exc.code, str(exc))
        return
    except ValueError as exc:
        await _send_error(connection, message_id, "invalid_message", str(exc))
        return
    except Exception as exc:
        runtime.record_issue("action_failed", str(exc), "thread_focus", level=logging.ERROR)
        await _send_error(connection, message_id, "action_failed", str(exc))
        return
    await connection.send_json(
        {
            "type": "ack",
            "id": message_id,
            "matchedText": match.matched_text,
            "confidence": match.confidence,
            "rowBox": match.row_box,
            "matchSource": "uia",
            "matchedProject": match.matched_project,
            "matchedTitle": match.matched_title,
            "verifiedTitle": match.verified_title,
        }
    )
    await runtime.broadcast_state()


async def _handle_codex_thread_new(connection: MobileConnection, message_id: object, workspace: object) -> None:
    normalized_workspace = workspace if isinstance(workspace, str) else None
    result = await asyncio.to_thread(runtime.ensure_codex_window_locked, focus=True)
    if not result.ok or result.window is None:
        await _handle_window_failure(connection, message_id, result)
        return
    runtime.session.set_locked_window(result.window)
    try:
        started = await asyncio.to_thread(
            runtime.windows.start_codex_new_thread,
            result.window,
            workspace=normalized_workspace,
        )
    except UIAutomationUnavailableError as exc:
        await _send_error(connection, message_id, "uia_unavailable", str(exc))
        return
    except UIAutomationError as exc:
        await _send_error(connection, message_id, exc.code, str(exc))
        return
    except Exception as exc:
        runtime.record_issue("action_failed", str(exc), "thread_new", level=logging.ERROR)
        await _send_error(connection, message_id, "action_failed", str(exc))
        return
    await connection.send_json(
        {
            "type": "ack",
            "id": message_id,
            "buttonName": getattr(started, "button_name", "新线程"),
            "verifiedTitle": getattr(started, "verified_title", None),
            "matchSource": "uia",
        }
    )
    await runtime.broadcast_state()


async def _handle_scroll(
    connection: MobileConnection,
    message_id: object,
    dy: object,
    x_ratio: object,
    y_ratio: object,
) -> None:
    if not isinstance(dy, (int, float)):
        await _send_error(connection, message_id, "invalid_message", "dy 字段必须是数字。")
        return

    result = await asyncio.to_thread(runtime.ensure_codex_window_locked, focus=True)
    if not result.ok or result.window is None:
        await _handle_window_failure(connection, message_id, result)
        return

    try:
        normalized_x, normalized_y = _normalize_pointer_ratios(x_ratio, y_ratio)
    except ValueError as exc:
        await _send_error(connection, message_id, "invalid_message", str(exc))
        return

    runtime.session.set_locked_window(result.window)
    steps = runtime.session.consume_scroll_steps(float(dy))
    if steps != 0:
        try:
            await asyncio.to_thread(runtime.windows.scroll_vertical_at_ratio, result.window, normalized_x, normalized_y, steps)
            log_event(
                LOGGER,
                logging.INFO,
                "window_scrolled",
                steps=steps,
                window_title=result.window.title if result.window else "",
                transport=connection.transport,
            )
        except Exception as exc:
            runtime.record_issue("action_failed", str(exc), "scroll", level=logging.ERROR)
            await _send_error(connection, message_id, "action_failed", str(exc))
            return

    await connection.send_json({"type": "ack", "id": message_id})
    await runtime.broadcast_state()


async def _handle_pointer_down(
    connection: MobileConnection,
    message_id: object,
    x_ratio: object,
    y_ratio: object,
) -> None:
    result = await asyncio.to_thread(runtime.ensure_codex_window_locked, focus=True)
    if not result.ok or result.window is None:
        await _handle_window_failure(connection, message_id, result)
        return
    try:
        normalized_x, normalized_y = _normalize_pointer_ratios(x_ratio, y_ratio)
        await asyncio.to_thread(runtime.windows.pointer_down_at_ratio, result.window, normalized_x, normalized_y)
    except ValueError as exc:
        await _send_error(connection, message_id, "invalid_message", str(exc))
        return
    except Exception as exc:
        runtime.record_issue("action_failed", str(exc), "pointer", level=logging.ERROR)
        await _send_error(connection, message_id, "action_failed", str(exc))
        return

    runtime.session.set_locked_window(result.window)
    runtime.session.set_pointer_active(True)
    await connection.send_json({"type": "ack", "id": message_id})
    await runtime.broadcast_state()


async def _handle_pointer_move(
    connection: MobileConnection,
    message_id: object,
    x_ratio: object,
    y_ratio: object,
) -> None:
    await asyncio.to_thread(runtime.sync_foreground_codex_window, discover_background=False)
    snapshot = runtime.session.snapshot()
    if not snapshot.pointer_active:
        await _send_error(connection, message_id, "pointer_inactive", "当前没有正在进行的拖拽操作。")
        return
    if snapshot.locked_window is None:
        runtime.session.set_pointer_active(False)
        await _send_error(connection, message_id, "window_not_locked", "当前还没有锁定目标窗口。")
        return
    try:
        normalized_x, normalized_y = _normalize_pointer_ratios(x_ratio, y_ratio)
        await asyncio.to_thread(runtime.windows.pointer_move_to_ratio, snapshot.locked_window, normalized_x, normalized_y)
    except ValueError as exc:
        await _send_error(connection, message_id, "invalid_message", str(exc))
        return
    except Exception as exc:
        runtime.record_issue("action_failed", str(exc), "pointer", level=logging.ERROR)
        await _send_error(connection, message_id, "action_failed", str(exc))
        return

    await connection.send_json({"type": "ack", "id": message_id})


async def _handle_pointer_up(
    connection: MobileConnection,
    message_id: object,
    x_ratio: object,
    y_ratio: object,
) -> None:
    await asyncio.to_thread(runtime.sync_foreground_codex_window, discover_background=False)
    snapshot = runtime.session.snapshot()
    if snapshot.locked_window is None:
        runtime.session.set_pointer_active(False)
        await _send_error(connection, message_id, "window_not_locked", "当前还没有锁定目标窗口。")
        return
    try:
        normalized_x, normalized_y = _normalize_pointer_ratios(x_ratio, y_ratio)
        await asyncio.to_thread(runtime.windows.pointer_up_at_ratio, snapshot.locked_window, normalized_x, normalized_y)
    except ValueError as exc:
        await _send_error(connection, message_id, "invalid_message", str(exc))
        return
    except Exception as exc:
        runtime.record_issue("action_failed", str(exc), "pointer", level=logging.ERROR)
        await _send_error(connection, message_id, "action_failed", str(exc))
        return
    finally:
        runtime.session.set_pointer_active(False)

    await connection.send_json({"type": "ack", "id": message_id})


def _normalize_pointer_ratios(x_ratio: object, y_ratio: object) -> tuple[float, float]:
    if not isinstance(x_ratio, (int, float)) or not isinstance(y_ratio, (int, float)):
        raise ValueError("xRatio 和 yRatio 必须是 0 到 1 之间的数字。")
    return min(1.0, max(0.0, float(x_ratio))), min(1.0, max(0.0, float(y_ratio)))


def _desktop_control_message(codex_found: bool, codex_foreground: bool) -> str:
    if not codex_found:
        return "未发现可见的 Codex 主窗口，请打开 Codex 并保持窗口可见。"
    if not codex_foreground:
        return "已发现 Codex，发送或切换线程时会自动置前。"
    return "Codex 已在前台，可远程控制。"


async def _handle_window_failure(
    connection: MobileConnection,
    message_id: object,
    result: EnsureWindowResult,
) -> None:
    runtime.release_pointer_if_needed()
    runtime.record_issue(result.error_code or "window_error", result.message or "窗口操作失败。", "window")
    await _send_error(connection, message_id, result.error_code, result.message)
    if result.error_code == "window_missing":
        runtime.session.set_locked_window(None)
        await runtime.broadcast_state()


def _ready_payload() -> dict[str, object]:
    snapshot = runtime.session.snapshot()
    codex_found = runtime.windows._looks_like_codex_desktop_window(snapshot.locked_window)
    codex_foreground = runtime.windows.is_foreground_window(snapshot.locked_window)
    return {
        "type": "ready",
        "windowLocked": snapshot.locked_window is not None,
        "title": snapshot.locked_window.title if snapshot.locked_window else None,
        "lockedWindow": snapshot.locked_window.to_public_dict() if snapshot.locked_window else None,
        "previewEnabled": runtime.windows.preview_supported(),
        "codexWindowFound": codex_found,
        "codexForeground": codex_foreground,
        "codexWindowControllable": codex_found,
        "desktopControlMessage": _desktop_control_message(codex_found, codex_foreground),
    }


async def _send_error(
    connection: MobileConnection,
    message_id: object,
    code: str | None,
    message: str | None,
) -> None:
    await connection.send_json({"type": "error", "id": message_id, "code": code, "message": message})


async def _close_connection(connection: MobileConnection, reason: str, code: int) -> None:
    try:
        await connection.close(reason, code)
    except RuntimeError:
        pass


def _build_local_mobile_connection(websocket: WebSocket) -> MobileConnection:
    connection_id = f"local:{secrets.token_urlsafe(8)}"
    send_lock = asyncio.Lock()

    async def send_json(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    async def close(reason: str, code: int) -> None:
        async with send_lock:
            await websocket.close(code=code, reason=reason)

    return MobileConnection(
        connection_id=connection_id,
        transport="local",
        send_json=send_json,
        close=close,
    )


def _ensure_local_request(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="管理接口仅允许本机访问。")


def _resolve_client_host(websocket: WebSocket) -> str:
    if websocket.client and websocket.client.host:
        return websocket.client.host
    return "未知来源"


def _open_admin_page(port: int) -> None:
    if os.getenv("REMOTE_ASSIST_NO_BROWSER") == "1":
        return
    import time

    time.sleep(1.0)
    webbrowser.open(f"http://127.0.0.1:{port}/admin")


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat()


def _build_preferred_connection(port: int, token: str, addresses, relay_snapshot) -> dict[str, object]:
    direct_url = _pick_direct_mobile_url(port, token, addresses)
    relay_url = relay_snapshot.mobile_url
    relay_host = _extract_host(relay_snapshot.configured_url)

    if relay_url and _host_looks_public(relay_host):
        return {
            "mode": "relay",
            "label": "公网扫码连接",
            "mobileUrl": relay_url,
            "qrSvgUrl": "/api/admin/connect-qr.svg",
            "note": "当前已连接公网 relay，手机可直接扫码访问。",
        }
    if direct_url:
        return {
            "mode": "lan-direct",
            "label": "同一 Wi-Fi 直连",
            "mobileUrl": direct_url,
            "qrSvgUrl": "/api/admin/connect-qr.svg",
            "note": "当前二维码将直接连接电脑端本地服务。请确认手机与电脑连接在同一个 Wi-Fi 下。",
        }
    if relay_url:
        return {
            "mode": "relay-fallback",
            "label": "本地 relay 调试地址",
            "mobileUrl": relay_url,
            "qrSvgUrl": "/api/admin/connect-qr.svg",
            "note": "当前仅检测到本地 relay 地址。若手机无法访问，请优先改用同一 Wi-Fi 直连，或配置公网 relay。",
        }
    return {
        "mode": "unavailable",
        "label": "暂无可用连接",
        "mobileUrl": None,
        "qrSvgUrl": None,
        "note": "当前还没有生成可供手机访问的连接地址。",
    }


def _pick_direct_mobile_url(port: int, token: str, addresses) -> str | None:
    for candidate in addresses:
        if getattr(candidate, "address", "").startswith(("127.", "169.254.")):
            continue
        host = getattr(candidate, "address", "")
        label = getattr(candidate, "label", "")
        if _address_looks_overlay(host, label):
            continue
        return f"http://{host}:{port}/remote?token={token}"
    return None


def _extract_host(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def _address_looks_overlay(host: str, label: str) -> bool:
    lowered = label.lower()
    return "tailscale" in lowered or "zerotier" in lowered or host.startswith("100.")


def _host_looks_public(host: str) -> bool:
    if not host:
        return False
    if host in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        return not ipaddress.ip_address(host).is_private
    except ValueError:
        return True


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=runtime.port, reload=False)


if __name__ == "__main__":
    main()
