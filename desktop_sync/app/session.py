from __future__ import annotations

import asyncio
import secrets
import threading
from dataclasses import dataclass
from typing import Awaitable, Callable, Coroutine

from .models import LockedWindow


SendJsonCallable = Callable[[dict[str, object]], Awaitable[None]]
CloseCallable = Callable[[str, int], Awaitable[None]]


@dataclass(slots=True)
class MobileConnection:
    connection_id: str
    transport: str
    send_json: SendJsonCallable
    close: CloseCallable


@dataclass(slots=True)
class SessionSnapshot:
    session_token: str
    locked_window: LockedWindow | None
    mobile_connected: bool
    mobile_transport: str | None
    preview_requested: bool
    pointer_active: bool


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session_token = self._generate_token()
        self._locked_window: LockedWindow | None = None
        self._active_connection: MobileConnection | None = None
        self._scroll_residual = 0.0
        self._preview_requested = False
        self._pointer_active = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def snapshot(self) -> SessionSnapshot:
        with self._lock:
            return SessionSnapshot(
                session_token=self._session_token,
                locked_window=self._locked_window,
                mobile_connected=self._active_connection is not None,
                mobile_transport=self._active_connection.transport if self._active_connection else None,
                preview_requested=self._preview_requested,
                pointer_active=self._pointer_active,
            )

    def current_token(self) -> str:
        with self._lock:
            return self._session_token

    def set_locked_window(self, locked_window: LockedWindow | None) -> None:
        with self._lock:
            self._locked_window = locked_window
            self._scroll_residual = 0.0
            if locked_window is None:
                self._pointer_active = False

    def consume_scroll_steps(self, dy: float, pixels_per_step: float = 28.0) -> int:
        with self._lock:
            self._scroll_residual += dy
            steps = int(self._scroll_residual / pixels_per_step)
            self._scroll_residual -= steps * pixels_per_step
            return steps

    def register_mobile(self, connection: MobileConnection) -> bool:
        with self._lock:
            if (
                self._active_connection is not None
                and self._active_connection.connection_id != connection.connection_id
            ):
                return False
            self._active_connection = connection
            self._scroll_residual = 0.0
            self._preview_requested = False
            self._pointer_active = False
            return True

    def active_connection(self) -> MobileConnection | None:
        with self._lock:
            return self._active_connection

    def clear_mobile(self, connection_id: str) -> bool:
        with self._lock:
            if self._active_connection and self._active_connection.connection_id == connection_id:
                self._active_connection = None
                self._scroll_residual = 0.0
                self._preview_requested = False
                self._pointer_active = False
                return True
            return False

    def reset_token(self) -> tuple[str, MobileConnection | None]:
        with self._lock:
            self._session_token = self._generate_token()
            self._scroll_residual = 0.0
            self._preview_requested = False
            self._pointer_active = False
            connection = self._active_connection
            self._active_connection = None
            return self._session_token, connection

    def set_preview_requested(self, value: bool) -> None:
        with self._lock:
            self._preview_requested = value

    def set_pointer_active(self, value: bool) -> None:
        with self._lock:
            self._pointer_active = value

    def run_coro_threadsafe(self, coroutine: Coroutine[object, object, object]) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(18)
