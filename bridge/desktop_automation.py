from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import ProxyHandler, build_opener, urlopen

import websockets


def _default_base_url() -> str:
    return os.getenv("CODEX_DESKTOP_AUTOMATION_URL", "http://127.0.0.1:8765").rstrip("/")


def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _urlopen_with_local_bypass(url: str, *, timeout: float):
    if _is_loopback_url(url):
        opener = build_opener(ProxyHandler({}))
        return opener.open(url, timeout=timeout)
    return urlopen(url, timeout=timeout)


def _desktop_automation_autostart_enabled() -> bool:
    return os.getenv("CODEX_DESKTOP_AUTOMATION_AUTOSTART", "1").strip().lower() not in {"0", "false", "off"}


def _default_launch_target() -> tuple[list[str] | None, str | None]:
    configured_command = os.getenv("CODEX_DESKTOP_AUTOMATION_COMMAND", "").strip()
    configured_cwd = os.getenv("CODEX_DESKTOP_AUTOMATION_CWD", "").strip()
    if configured_command:
        return shlex.split(configured_command, posix=False), configured_cwd or None

    repo_root = Path(__file__).resolve().parent.parent
    sibling_root = repo_root.parent / "远程桌面"
    entrypoint = sibling_root / "app" / "main.py"
    venv_python = sibling_root / ".venv" / "Scripts" / "python.exe"
    if entrypoint.exists():
        python_executable = venv_python if venv_python.exists() else Path(sys.executable)
        return [str(python_executable), "-m", "app.main"], str(sibling_root)
    return None, None


def _default_launch_target() -> tuple[list[str] | None, str | None]:  # type: ignore[no-redef]
    configured_command = os.getenv("CODEX_DESKTOP_AUTOMATION_COMMAND", "").strip()
    configured_cwd = os.getenv("CODEX_DESKTOP_AUTOMATION_CWD", "").strip()
    if configured_command:
        return shlex.split(configured_command, posix=False), configured_cwd or None

    repo_root = Path(__file__).resolve().parent.parent
    for candidate in (repo_root / "desktop_sync", repo_root.parent / "远程桌面"):
        entrypoint = candidate / "app" / "main.py"
        venv_python = candidate / ".venv" / "Scripts" / "python.exe"
        if entrypoint.exists():
            python_executable = venv_python if venv_python.exists() else Path(sys.executable)
            return [str(python_executable), "-m", "app.main"], str(candidate)
    return None, None


def _launch_desktop_automation_process(command: list[str], cwd: str | None) -> subprocess.Popen[bytes]:
    creation_flags = 0
    if os.name == "nt":
        creation_flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        creation_flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


class DesktopAutomationUnavailableError(RuntimeError):
    pass


class DesktopAutomationSendError(RuntimeError):
    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class DesktopAutomationSnapshot:
    base_url: str
    available: bool = False
    preview_supported: bool = False
    connected: bool = False
    authenticated: bool = False
    window_locked: bool = False
    codex_window_locked: bool = False
    codex_window_found: bool = False
    codex_foreground: bool = False
    codex_window_controllable: bool = False
    locked_window: dict[str, Any] | None = None
    window_title: str | None = None
    process_name: str | None = None
    session_token: str | None = None
    current_pin: str | None = None
    last_error: str | None = None
    desktop_control_message: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "baseUrl": self.base_url,
            "available": self.available,
            "previewSupported": self.preview_supported,
            "connected": self.connected,
            "authenticated": self.authenticated,
            "windowLocked": self.window_locked,
            "codexWindowLocked": self.codex_window_locked,
            "codexWindowFound": self.codex_window_found,
            "codexForeground": self.codex_foreground,
            "codexWindowControllable": self.codex_window_controllable,
            "lockedWindow": self.locked_window,
            "windowTitle": self.window_title,
            "processName": self.process_name,
            "lastError": self.last_error,
            "desktopControlMessage": self.desktop_control_message,
        }


class DesktopAutomationClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self._snapshot = DesktopAutomationSnapshot(base_url=(base_url or _default_base_url()))
        self._closed = False
        self._task: asyncio.Task[None] | None = None
        self._websocket = None
        self._send_lock = asyncio.Lock()
        self._refresh_state_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._subscriber_lock = asyncio.Lock()
        self._launch_lock = asyncio.Lock()
        self._autostart_enabled = _desktop_automation_autostart_enabled()
        self._launch_command, self._launch_cwd = _default_launch_target()
        self._launcher_process: subprocess.Popen[bytes] | None = None
        self._last_launch_attempt_at = 0.0

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot.to_public_dict()

    async def refresh_state(self) -> dict[str, Any]:
        async with self._refresh_state_lock:
            await self._refresh_admin_state()
        return self.snapshot()

    async def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        subscriber_id = secrets.token_urlsafe(6)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._subscriber_lock:
            self._subscribers[subscriber_id] = queue
        return subscriber_id, queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        async with self._subscriber_lock:
            self._subscribers.pop(subscriber_id, None)

    async def start(self) -> None:
        if self._task is None:
            self._closed = False
            self._task = asyncio.create_task(self._run(), name="desktop-automation")

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._close_socket()

    async def send_text(self, text: str, *, submit: bool = True) -> None:
        await self.send_command({"type": "text.send", "text": text, "submit": bool(submit)}, expect_ack=True)

    async def send_command(
        self,
        payload: dict[str, Any],
        *,
        expect_ack: bool = False,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        websocket = self._websocket
        if websocket is None or not self._snapshot.connected or not self._snapshot.authenticated:
            raise DesktopAutomationUnavailableError("desktop automation is not connected")
        message = dict(payload)
        message_id = None
        future: asyncio.Future[dict[str, Any]] | None = None
        if expect_ack:
            message_id = str(message.get("id") or f"desktop-{asyncio.get_running_loop().time():.6f}")
            future = asyncio.get_running_loop().create_future()
            self._pending[message_id] = future
            message["id"] = message_id
        try:
            async with self._send_lock:
                await websocket.send(json.dumps(message, ensure_ascii=False))
        except Exception as exc:  # pragma: no cover - defensive
            if message_id is not None:
                self._pending.pop(message_id, None)
            raise DesktopAutomationUnavailableError(f"desktop automation send failed: {exc}") from exc
        if not future:
            return None
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(message_id, None)
            raise DesktopAutomationSendError("desktop automation ack timed out") from exc
        except DesktopAutomationSendError:
            raise

    async def _run(self) -> None:
        while not self._closed:
            try:
                await self._refresh_admin_state()
                if not self._snapshot.session_token or not self._snapshot.current_pin:
                    await asyncio.sleep(1.5)
                    continue
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._snapshot.last_error = str(exc)
                self._snapshot.connected = False
                self._snapshot.authenticated = False
                await asyncio.sleep(1.5)

    async def _refresh_admin_state(self) -> None:
        try:
            payload = await asyncio.to_thread(_fetch_admin_state, f"{self._snapshot.base_url}/api/admin/state")
        except Exception:
            self._snapshot.available = False
            launched = await self._maybe_launch_service()
            if not launched:
                raise
            await asyncio.sleep(1.0)
            payload = await asyncio.to_thread(_fetch_admin_state, f"{self._snapshot.base_url}/api/admin/state")
        locked_window = payload.get("lockedWindow") if isinstance(payload.get("lockedWindow"), dict) else None
        self._snapshot.available = True
        self._snapshot.preview_supported = bool(payload.get("previewSupported"))
        self._snapshot.session_token = payload.get("sessionToken") if isinstance(payload.get("sessionToken"), str) else None
        self._snapshot.current_pin = payload.get("currentPin") if isinstance(payload.get("currentPin"), str) else None
        self._update_locked_window(locked_window)
        self._update_desktop_status(payload)
        self._snapshot.last_error = None

    async def _maybe_launch_service(self) -> bool:
        if not self._autostart_enabled or not self._launch_command:
            return False
        async with self._launch_lock:
            if self._launcher_process is not None and self._launcher_process.poll() is None:
                return True
            now = time.monotonic()
            if now - self._last_launch_attempt_at < 4.0:
                return True
            self._last_launch_attempt_at = now
            try:
                self._launcher_process = await asyncio.to_thread(
                    _launch_desktop_automation_process,
                    list(self._launch_command),
                    self._launch_cwd,
                )
                return True
            except Exception as exc:
                self._snapshot.last_error = f"desktop automation autostart failed: {exc}"
                return False

    async def _connect_once(self) -> None:
        assert self._snapshot.session_token is not None
        ws_url = _http_to_ws(self._snapshot.base_url)
        query = urlencode({"token": self._snapshot.session_token})
        target = f"{ws_url}/ws?{query}"
        async with websockets.connect(
            target,
            max_size=2 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=30,
        ) as websocket:
            self._websocket = websocket
            self._snapshot.connected = True
            self._snapshot.authenticated = False
            self._snapshot.last_error = None
            await websocket.send(
                json.dumps(
                    {
                        "type": "hello",
                        "client": "bridge-desktop-automation",
                        "version": 1,
                        "pin": self._snapshot.current_pin,
                    },
                    ensure_ascii=False,
                )
            )
            async for raw in websocket:
                message = json.loads(raw)
                await self._handle_message(message)
        await self._close_socket()

    async def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type") or "")
        if message_type == "ready":
            self._snapshot.authenticated = True
            locked_window = message.get("lockedWindow") if isinstance(message.get("lockedWindow"), dict) else None
            self._update_locked_window(locked_window)
            self._update_desktop_status(message)
            await self._broadcast(message)
            return
        if message_type == "state":
            locked_window = message.get("lockedWindow") if isinstance(message.get("lockedWindow"), dict) else None
            self._update_locked_window(locked_window)
            self._update_desktop_status(message)
            await self._broadcast(message)
            return
        if message_type == "ack":
            future = self._pending.pop(str(message.get("id") or ""), None)
            if future is not None and not future.done():
                future.set_result(message)
            await self._broadcast(message)
            return
        if message_type == "error":
            self._snapshot.last_error = str(message.get("message") or message.get("code") or "desktop automation error")
            future = self._pending.pop(str(message.get("id") or ""), None)
            if future is not None and not future.done():
                code = message.get("code") if isinstance(message.get("code"), str) else None
                future.set_exception(DesktopAutomationSendError(self._snapshot.last_error, code=code))
            await self._broadcast(message)
            return
        if message_type in {"preview.frame", "preview.unavailable"}:
            await self._broadcast(message)
            return

    async def _close_socket(self) -> None:
        pending = list(self._pending.values())
        self._pending.clear()
        for future in pending:
            if not future.done():
                future.set_exception(DesktopAutomationUnavailableError("desktop automation disconnected"))
        websocket = self._websocket
        self._websocket = None
        self._snapshot.connected = False
        self._snapshot.authenticated = False
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()

    async def _broadcast(self, message: dict[str, Any]) -> None:
        async with self._subscriber_lock:
            subscribers = list(self._subscribers.values())
        for queue in subscribers:
            queue.put_nowait(message)

    def _update_locked_window(self, locked_window: dict[str, Any] | None) -> None:
        self._snapshot.locked_window = locked_window
        self._snapshot.window_locked = locked_window is not None
        self._snapshot.window_title = locked_window.get("title") if isinstance(locked_window, dict) else None
        self._snapshot.process_name = locked_window.get("process_name") if isinstance(locked_window, dict) else None
        self._snapshot.codex_window_locked = _is_codex_window(locked_window)
        if self._snapshot.codex_window_locked:
            self._snapshot.codex_window_found = True
            self._snapshot.codex_window_controllable = True
        elif locked_window is None:
            self._snapshot.codex_window_found = False
            self._snapshot.codex_window_controllable = False

    def _update_desktop_status(self, payload: dict[str, Any]) -> None:
        if "codexWindowFound" in payload:
            self._snapshot.codex_window_found = bool(payload.get("codexWindowFound"))
        if "codexForeground" in payload:
            self._snapshot.codex_foreground = bool(payload.get("codexForeground"))
        if "codexWindowControllable" in payload:
            self._snapshot.codex_window_controllable = bool(payload.get("codexWindowControllable"))
        elif self._snapshot.codex_window_locked:
            self._snapshot.codex_window_controllable = True
        message = payload.get("desktopControlMessage")
        self._snapshot.desktop_control_message = message if isinstance(message, str) and message else None


def _http_to_ws(url: str) -> str:
    parsed = urlparse(url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _is_codex_window(locked_window: dict[str, Any] | None) -> bool:
    if not isinstance(locked_window, dict):
        return False
    title = str(locked_window.get("title") or "").lower()
    process_name = str(locked_window.get("process_name") or "").lower()
    return "codex" in title or "codex" in process_name


def _fetch_admin_state(url: str) -> dict[str, Any]:
    with _urlopen_with_local_bypass(url, timeout=3.0) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


class NullDesktopAutomationClient:
    def snapshot(self) -> dict[str, Any]:
        return DesktopAutomationSnapshot(base_url=_default_base_url(), last_error="desktop automation disabled").to_public_dict()

    async def refresh_state(self) -> dict[str, Any]:
        return self.snapshot()

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        return "", asyncio.Queue()

    async def unsubscribe(self, subscriber_id: str) -> None:
        return None

    async def send_text(self, text: str, *, submit: bool = True) -> None:
        raise DesktopAutomationUnavailableError("desktop automation is disabled")

    async def send_command(
        self,
        payload: dict[str, Any],
        *,
        expect_ack: bool = False,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        raise DesktopAutomationUnavailableError("desktop automation is disabled")
