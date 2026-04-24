from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_L = 0x4C
VK_U = 0x55


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
        ("lPrivate", wintypes.DWORD),
    ]


user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class HotkeyManager:
    def __init__(self, on_lock: Callable[[], None], on_unlock: Callable[[], None]) -> None:
        self._on_lock = on_lock
        self._on_unlock = on_unlock
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._started = threading.Event()
        self._stop_requested = threading.Event()
        self._thread_exception: Exception | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._message_loop, name="hotkey-loop", daemon=True)
        self._thread.start()
        self._started.wait(timeout=2)
        if self._thread_exception is not None:
            raise RuntimeError("Failed to start hotkey manager") from self._thread_exception

    def stop(self) -> None:
        self._stop_requested.set()
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    def _message_loop(self) -> None:
        try:
            self._thread_id = kernel32.GetCurrentThreadId()
            if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT, VK_L):
                raise ctypes.WinError(ctypes.get_last_error())
            if not user32.RegisterHotKey(None, 2, MOD_CONTROL | MOD_ALT, VK_U):
                user32.UnregisterHotKey(None, 1)
                raise ctypes.WinError(ctypes.get_last_error())
            self._started.set()
            msg = MSG()
            while not self._stop_requested.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if msg.message == WM_HOTKEY:
                    if msg.wParam == 1:
                        self._on_lock()
                    elif msg.wParam == 2:
                        self._on_unlock()
        except Exception as exc:
            self._thread_exception = exc
            self._started.set()
        finally:
            user32.UnregisterHotKey(None, 1)
            user32.UnregisterHotKey(None, 2)
