from __future__ import annotations

import ctypes
import io
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime

from .codex_sidebar_ocr import CodexSidebarOcr
from .codex_uia import CodexDesktopUIAutomation, ThreadFocusTarget
from .models import LockedWindow


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


CF_UNICODETEXT = 13
GA_ROOT = 2
GMEM_MOVEABLE = 0x0002
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SW_SHOW = 5
SW_RESTORE = 9
SM_CXSCREEN = 0
SM_CYSCREEN = 1
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_V = 0x56
WHEEL_DELTA = 120
CODEX_SIDEBAR_X_RATIO = 0.16
CODEX_SIDEBAR_SCROLL_Y_RATIO = 0.42
CODEX_SIDEBAR_LEFT_RATIO = 0.00
CODEX_SIDEBAR_RIGHT_RATIO = 0.32
CODEX_SIDEBAR_TOP_RATIO = 0.16
CODEX_SIDEBAR_BOTTOM_RATIO = 0.88
CODEX_SIDEBAR_ROW_HEIGHT_PX = 58
CODEX_SIDEBAR_MIN_VISIBLE_ROWS = 6
CODEX_SIDEBAR_MAX_VISIBLE_ROWS = 18
CODEX_SIDEBAR_RESET_SCROLL_STEPS = 10
CODEX_SIDEBAR_RESET_PASSES = 5
CODEX_NEW_THREAD_X_RATIO = 0.09
CODEX_NEW_THREAD_Y_RATIO = 0.06
CODEX_COMPOSER_FOCUS_POINTS = (
    (0.56, 0.84),
    (0.62, 0.86),
    (0.70, 0.84),
)


ULONG_PTR = wintypes.WPARAM
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetActiveWindow.argtypes = [wintypes.HWND]
user32.SetActiveWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.CloseClipboard.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL


@dataclass(slots=True)
class EnsureWindowResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    window: LockedWindow | None = None


@dataclass(slots=True)
class WindowRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


@dataclass(slots=True)
class PreviewFrame:
    width: int
    height: int
    jpeg_bytes: bytes


@dataclass(slots=True)
class WindowCandidate:
    hwnd: int
    visible: bool
    title: str
    rect: WindowRect


class WindowsController:
    def __init__(
        self,
        *,
        sidebar_ocr: CodexSidebarOcr | None = None,
        desktop_uia: CodexDesktopUIAutomation | None = None,
    ) -> None:
        self._preview_support: bool | None = None
        self._sidebar_ocr = sidebar_ocr or CodexSidebarOcr()
        self._desktop_uia = desktop_uia or CodexDesktopUIAutomation()
        self._enable_dpi_awareness()

    def capture_foreground_window(self) -> LockedWindow | None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        hwnd = self._canonical_lock_hwnd(hwnd)
        return self._describe_window(hwnd)

    def find_codex_window(self, *, restore: bool = False, include_restorable: bool = False) -> LockedWindow | None:
        candidates: list[tuple[int, bool, bool, LockedWindow]] = []
        seen: set[int] = set()
        for hwnd in self._top_level_windows():
            hwnd_value = _hwnd_to_int(hwnd)
            if hwnd_value in seen:
                continue
            seen.add(hwnd_value)
            candidate = self._candidate_for_hwnd(hwnd)
            if candidate is None:
                continue
            window = self._describe_window(hwnd)
            if window is None or not self._looks_like_codex_desktop_window(window):
                continue
            if not _window_rect_is_usable(candidate.rect):
                restorable = self._can_restore_codex_window(candidate, window)
                if not restore or not restorable:
                    if include_restorable and restorable:
                        candidates.append((candidate.rect.width * candidate.rect.height, candidate.visible, bool(candidate.title.strip()), window))
                    continue
                self._restore_window_to_visible_area(hwnd)
                candidate = self._candidate_for_hwnd(hwnd)
                window = self._describe_window(hwnd)
                if candidate is None or window is None or not _window_rect_is_usable(candidate.rect):
                    continue
            candidates.append((candidate.rect.width * candidate.rect.height, candidate.visible, bool(candidate.title.strip()), window))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[1], item[0], item[2]), reverse=True)
        return candidates[0][3]

    def refresh_locked_window(self, locked_window: LockedWindow | None) -> LockedWindow | None:
        if locked_window is None:
            return None
        hwnd = wintypes.HWND(locked_window.hwnd)
        if not hwnd or not user32.IsWindow(hwnd):
            return None
        hwnd = self._canonical_lock_hwnd(hwnd)
        return self._describe_window(hwnd, locked_at=locked_window.locked_at)

    def is_foreground_window(self, locked_window: LockedWindow | None) -> bool:
        if locked_window is None:
            return False
        foreground = user32.GetForegroundWindow()
        if not foreground:
            return False
        foreground = self._canonical_lock_hwnd(foreground)
        return _same_hwnd(foreground, locked_window.hwnd)

    def ensure_window_ready(self, locked_window: LockedWindow | None) -> EnsureWindowResult:
        if locked_window is None:
            return EnsureWindowResult(False, "window_not_locked", "当前还没有锁定目标窗口。")
        hwnd = wintypes.HWND(locked_window.hwnd)
        if not user32.IsWindow(hwnd):
            return EnsureWindowResult(False, "window_missing", "已锁定的窗口不存在或已被关闭。")
        hwnd = self._canonical_lock_hwnd(hwnd)
        if not user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.08)
        if not self._focus_window(hwnd):
            return EnsureWindowResult(False, "focus_failed", "Windows 拒绝将已锁定窗口切回前台。")
        if not user32.IsWindowVisible(hwnd):
            return EnsureWindowResult(False, "window_not_visible", "Codex 窗口当前不可见，请将 Codex 打开到桌面前台后重试。")
        if not _same_hwnd(self._canonical_lock_hwnd(user32.GetForegroundWindow()), hwnd):
            return EnsureWindowResult(False, "focus_failed", "Windows 拒绝将 Codex 切回前台。")
        refreshed = self._describe_window(hwnd, locked_at=locked_window.locked_at)
        if refreshed is None:
            return EnsureWindowResult(False, "window_missing", "已锁定的窗口当前不可用。")
        return EnsureWindowResult(True, window=refreshed)

    def paste_text(self, text: str, *, submit: bool = False, target_window: LockedWindow | None = None) -> None:
        self._set_clipboard_text(text)
        inputs = [
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_CONTROL, dwFlags=0)),
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_V, dwFlags=0)),
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_V, dwFlags=KEYEVENTF_KEYUP)),
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_CONTROL, dwFlags=KEYEVENTF_KEYUP)),
        ]
        if submit:
            inputs.extend(
                (
                    INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_RETURN, dwFlags=0)),
                    INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_RETURN, dwFlags=KEYEVENTF_KEYUP)),
                )
        )
        self._send_inputs(tuple(inputs))

    def focus_codex_thread_by_index(
        self,
        locked_window: LockedWindow,
        target_index: int,
        *,
        total_threads: int | None = None,
    ) -> None:
        if target_index < 0:
            raise ValueError("target_index must be >= 0")
        if total_threads is not None and target_index >= total_threads:
            raise ValueError("target_index is outside of the available thread range")
        self.release_left_button()
        visible_rows = self._codex_sidebar_visible_rows(locked_window)
        if target_index >= visible_rows:
            raise ValueError("target thread is outside of the high-confidence visible sidebar range")
        row_index = target_index
        row_span = CODEX_SIDEBAR_BOTTOM_RATIO - CODEX_SIDEBAR_TOP_RATIO
        y_ratio = CODEX_SIDEBAR_TOP_RATIO + row_span * ((row_index + 0.5) / visible_rows)
        self._tap_ratio(locked_window, CODEX_SIDEBAR_X_RATIO, y_ratio)
        time.sleep(0.18)

    def focus_codex_thread_by_text(
        self,
        locked_window: LockedWindow,
        *,
        workspace: str | None,
        title: str | None,
        preview: str | None,
    ) -> ThreadFocusTarget:
        if not isinstance(workspace, str) or not workspace.strip():
            raise ValueError("workspace must be a non-empty string")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        self.release_left_button()
        match = self._desktop_uia.find_thread_target(
            locked_window.hwnd,
            workspace=workspace,
            title=title,
        )
        self._tap_absolute(match.rect.center_x, match.rect.center_y)
        time.sleep(0.18)
        match.verified_title = self._desktop_uia.wait_for_active_title(
            locked_window.hwnd,
            expected_title=title,
        )
        return match

    def start_codex_new_thread(self, locked_window: LockedWindow, *, workspace: str | None = None):
        self.release_left_button()
        return self._desktop_uia.activate_new_thread(locked_window.hwnd, workspace=workspace)

    def focus_codex_composer(self, locked_window: LockedWindow) -> None:
        self.release_left_button()
        for x_ratio, y_ratio in CODEX_COMPOSER_FOCUS_POINTS:
            self._tap_ratio(locked_window, x_ratio, y_ratio)
            time.sleep(0.04)
        time.sleep(0.08)

    def _codex_sidebar_visible_rows(self, locked_window: LockedWindow) -> int:
        rect = self.get_window_rect(locked_window)
        row_area = rect.height * (CODEX_SIDEBAR_BOTTOM_RATIO - CODEX_SIDEBAR_TOP_RATIO)
        estimated = round(row_area / CODEX_SIDEBAR_ROW_HEIGHT_PX)
        return max(CODEX_SIDEBAR_MIN_VISIBLE_ROWS, min(CODEX_SIDEBAR_MAX_VISIBLE_ROWS, estimated))

    def _focus_codex_input_hint(self, locked_window: LockedWindow | None) -> None:
        if locked_window is None:
            return
        try:
            self.release_left_button()
            for x_ratio, y_ratio in ((0.50, 0.90), (0.50, 0.86), (0.42, 0.90)):
                self._tap_ratio(locked_window, x_ratio, y_ratio)
                time.sleep(0.06)
            time.sleep(0.08)
        except Exception:
            return

    def _tap_ratio(self, locked_window: LockedWindow, x_ratio: float, y_ratio: float) -> None:
        self.pointer_down_at_ratio(locked_window, x_ratio, y_ratio)
        time.sleep(0.025)
        self.pointer_up_at_ratio(locked_window, x_ratio, y_ratio)

    def scroll_vertical(self, steps: int) -> None:
        if steps == 0:
            return
        inputs = (
            INPUT(
                type=INPUT_MOUSE,
                mi=MOUSEINPUT(mouseData=int(steps * WHEEL_DELTA), dwFlags=MOUSEEVENTF_WHEEL),
            ),
        )
        self._send_inputs(inputs)

    def scroll_vertical_at_ratio(self, locked_window: LockedWindow, x_ratio: float, y_ratio: float, steps: int) -> None:
        self.move_pointer_to_ratio(locked_window, x_ratio, y_ratio)
        self.scroll_vertical(steps)

    def _capture_codex_sidebar_image(self, locked_window: LockedWindow):
        if not self.preview_supported():
            raise RuntimeError("当前环境缺少窗口预览依赖，请重新安装 requirements.txt。")
        rect = self.get_window_rect(locked_window)
        if rect.width < 32 or rect.height < 32:
            raise RuntimeError("锁定窗口尺寸过小，暂时无法识别线程栏。")
        left = rect.left + round(rect.width * CODEX_SIDEBAR_LEFT_RATIO)
        top = rect.top + round(rect.height * CODEX_SIDEBAR_TOP_RATIO)
        right = rect.left + round(rect.width * CODEX_SIDEBAR_RIGHT_RATIO)
        bottom = rect.top + round(rect.height * CODEX_SIDEBAR_BOTTOM_RATIO)
        width = max(1, right - left)
        height = max(1, bottom - top)

        from mss import mss
        from PIL import Image

        with mss() as capture_session:
            raw = capture_session.grab({"left": left, "top": top, "width": width, "height": height})
        return Image.frombytes("RGB", raw.size, raw.rgb), left, top

    def move_pointer_to_ratio(self, locked_window: LockedWindow, x_ratio: float, y_ratio: float) -> tuple[int, int]:
        rect = self.get_window_rect(locked_window)
        x = rect.left + round((rect.width - 1) * _normalize_ratio(x_ratio))
        y = rect.top + round((rect.height - 1) * _normalize_ratio(y_ratio))
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError(ctypes.get_last_error())
        return x, y

    def _tap_absolute(self, x: int, y: int) -> None:
        if not user32.SetCursorPos(int(x), int(y)):
            raise ctypes.WinError(ctypes.get_last_error())
        self._send_mouse_flags(MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.025)
        self._send_mouse_flags(MOUSEEVENTF_LEFTUP)

    def pointer_down_at_ratio(self, locked_window: LockedWindow, x_ratio: float, y_ratio: float) -> None:
        self.move_pointer_to_ratio(locked_window, x_ratio, y_ratio)
        self._send_mouse_flags(MOUSEEVENTF_LEFTDOWN)

    def pointer_move_to_ratio(self, locked_window: LockedWindow, x_ratio: float, y_ratio: float) -> None:
        self.move_pointer_to_ratio(locked_window, x_ratio, y_ratio)

    def pointer_up_at_ratio(self, locked_window: LockedWindow, x_ratio: float, y_ratio: float) -> None:
        self.move_pointer_to_ratio(locked_window, x_ratio, y_ratio)
        self._send_mouse_flags(MOUSEEVENTF_LEFTUP)

    def release_left_button(self) -> None:
        self._send_mouse_flags(MOUSEEVENTF_LEFTUP)

    def preview_supported(self) -> bool:
        if self._preview_support is not None:
            return self._preview_support
        try:
            import mss  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError:
            self._preview_support = False
        else:
            self._preview_support = True
        return self._preview_support

    def capture_window_preview(
        self,
        locked_window: LockedWindow,
        *,
        max_edge: int = 960,
        jpeg_quality: int = 55,
    ) -> PreviewFrame:
        if not self.preview_supported():
            raise RuntimeError("当前环境缺少窗口预览依赖，请重新安装 requirements.txt。")
        rect = self.get_window_rect(locked_window)
        if rect.width < 32 or rect.height < 32:
            raise RuntimeError("锁定窗口尺寸过小，暂时无法生成预览。")

        from mss import mss
        from PIL import Image

        with mss() as capture_session:
            raw = capture_session.grab(
                {
                    "left": rect.left,
                    "top": rect.top,
                    "width": rect.width,
                    "height": rect.height,
                }
            )
        image = Image.frombytes("RGB", raw.size, raw.rgb)
        max_dimension = max(image.width, image.height)
        if max_dimension > max_edge:
            scale = max_edge / float(max_dimension)
            image = image.resize(
                (
                    max(1, round(image.width * scale)),
                    max(1, round(image.height * scale)),
                ),
                Image.Resampling.LANCZOS,
            )

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
        return PreviewFrame(width=image.width, height=image.height, jpeg_bytes=output.getvalue())

    def get_window_rect(self, locked_window: LockedWindow) -> WindowRect:
        hwnd = wintypes.HWND(locked_window.hwnd)
        return self._window_rect_from_hwnd(hwnd)

    def _focus_window(self, hwnd: wintypes.HWND) -> bool:
        current_foreground = user32.GetForegroundWindow()
        if _same_hwnd(current_foreground, hwnd):
            return True
        if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.ShowWindow(hwnd, SW_RESTORE)
        if not _window_rect_is_usable(self._window_rect_from_hwnd(hwnd)):
            self._restore_window_to_visible_area(hwnd)
        current_thread = user32.GetWindowThreadProcessId(current_foreground, None) if current_foreground else 0
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if current_thread and target_thread and current_thread != target_thread:
            attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
        try:
            if self._attempt_focus(hwnd):
                return True
            self._nudge_foreground_permission()
            if self._attempt_focus(hwnd):
                return True
            self._toggle_topmost(hwnd)
            return self._attempt_focus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(current_thread, target_thread, False)

    def _looks_like_codex_window(self, locked_window: LockedWindow | None) -> bool:
        if locked_window is None:
            return False
        title = str(locked_window.title or "").lower()
        process_name = str(locked_window.process_name or "").lower()
        return "codex" in title or "codex" in process_name

    def _looks_like_codex_desktop_window(self, locked_window: LockedWindow | None) -> bool:
        if locked_window is None:
            return False
        title = str(locked_window.title or "").strip().lower()
        process_name = str(locked_window.process_name or "").strip().lower()
        return process_name == "codex.exe" and title == "codex"

    def _can_restore_codex_window(self, candidate: WindowCandidate, locked_window: LockedWindow) -> bool:
        title = str(candidate.title or locked_window.title or "").strip().lower()
        return candidate.visible and title == "codex"

    def _canonical_lock_hwnd(self, hwnd: wintypes.HWND) -> wintypes.HWND:
        root = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
        process_id = self._process_id_from_hwnd(root)
        candidates: list[WindowCandidate] = []
        root_candidate = self._candidate_for_hwnd(root)
        if root_candidate is not None:
            candidates.append(root_candidate)
        if process_id:
            for candidate_hwnd in self._top_level_windows_for_process(process_id):
                if _same_hwnd(candidate_hwnd, root):
                    continue
                candidate = self._candidate_for_hwnd(candidate_hwnd)
                if candidate is not None:
                    candidates.append(candidate)
        best = _pick_best_lock_candidate(candidates, _hwnd_to_int(root))
        return wintypes.HWND(best or _hwnd_to_int(root))

    def _candidate_for_hwnd(self, hwnd: wintypes.HWND) -> WindowCandidate | None:
        if not hwnd or not user32.IsWindow(hwnd):
            return None
        try:
            rect = self._window_rect_from_hwnd(hwnd)
        except Exception:
            return None
        return WindowCandidate(
            hwnd=_hwnd_to_int(hwnd),
            visible=bool(user32.IsWindowVisible(hwnd)),
            title=self._window_title(hwnd),
            rect=rect,
        )

    def _top_level_windows_for_process(self, process_id: int) -> list[wintypes.HWND]:
        matches: list[int] = []

        @WNDENUMPROC
        def callback(hwnd: wintypes.HWND, _: int) -> int:
            if self._process_id_from_hwnd(hwnd) == process_id:
                matches.append(_hwnd_to_int(hwnd))
            return 1

        user32.EnumWindows(callback, 0)
        return [wintypes.HWND(item) for item in matches]

    def _top_level_windows(self) -> list[wintypes.HWND]:
        matches: list[int] = []

        @WNDENUMPROC
        def callback(hwnd: wintypes.HWND, _: int) -> int:
            matches.append(_hwnd_to_int(hwnd))
            return 1

        user32.EnumWindows(callback, 0)
        return [wintypes.HWND(item) for item in matches]

    def _process_id_from_hwnd(self, hwnd: wintypes.HWND) -> int:
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return int(process_id.value or 0)

    def _window_title(self, hwnd: wintypes.HWND) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)
        return title_buffer.value or ""

    def _window_rect_from_hwnd(self, hwnd: wintypes.HWND) -> WindowRect:
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return WindowRect(left=rect.left, top=rect.top, right=rect.right, bottom=rect.bottom)

    def _attempt_focus(self, hwnd: wintypes.HWND) -> bool:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        time.sleep(0.05)
        return _same_hwnd(user32.GetForegroundWindow(), hwnd)

    def _nudge_foreground_permission(self) -> None:
        alt_down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_MENU, dwFlags=KEYEVENTF_EXTENDEDKEY))
        alt_up = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(wVk=VK_MENU, dwFlags=KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP),
        )
        self._send_inputs((alt_down, alt_up))
        time.sleep(0.03)

    def _toggle_topmost(self, hwnd: wintypes.HWND) -> None:
        topmost = wintypes.HWND(-1)
        not_topmost = wintypes.HWND(-2)
        flags = SWP_NOMOVE | SWP_NOSIZE
        user32.SetWindowPos(hwnd, topmost, 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, not_topmost, 0, 0, 0, 0, flags)

    def _restore_window_to_visible_area(self, hwnd: wintypes.HWND) -> None:
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.08)
        try:
            if _window_rect_is_usable(self._window_rect_from_hwnd(hwnd)):
                return
        except Exception:
            pass
        screen_width = max(1024, int(user32.GetSystemMetrics(SM_CXSCREEN) or 1440))
        screen_height = max(768, int(user32.GetSystemMetrics(SM_CYSCREEN) or 900))
        width = min(screen_width, max(960, round(screen_width * 0.82)))
        height = min(screen_height, max(720, round(screen_height * 0.86)))
        x = min(80, max(0, screen_width - width))
        y = min(40, max(0, screen_height - height))
        user32.SetWindowPos(hwnd, wintypes.HWND(0), x, y, width, height, SWP_NOZORDER | SWP_SHOWWINDOW)
        time.sleep(0.08)

    def _enable_dpi_awareness(self) -> None:
        try:
            shcore = ctypes.windll.shcore
            shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    def _describe_window(
        self,
        hwnd: wintypes.HWND,
        locked_at: datetime | None = None,
    ) -> LockedWindow | None:
        if not user32.IsWindow(hwnd):
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)

        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return LockedWindow(
            hwnd=_hwnd_to_int(hwnd),
            title=title_buffer.value or "（无标题窗口）",
            process_name=self._process_name(process_id.value),
            locked_at=locked_at or datetime.now().astimezone(),
        )

    def _process_name(self, process_id: int) -> str:
        if not process_id:
            return "未知进程"
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        if not handle:
            return "未知进程"
        try:
            size = wintypes.DWORD(260)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return os.path.basename(buffer.value)
            return "未知进程"
        finally:
            kernel32.CloseHandle(handle)

    def _set_clipboard_text(self, text: str) -> None:
        for _ in range(10):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.02)
        else:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not user32.EmptyClipboard():
                raise ctypes.WinError(ctypes.get_last_error())
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            locked = kernel32.GlobalLock(handle)
            if not locked:
                kernel32.GlobalFree(handle)
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                ctypes.memmove(locked, encoded, len(encoded))
            finally:
                kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                kernel32.GlobalFree(handle)
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            user32.CloseClipboard()

    def _send_inputs(self, inputs: tuple[INPUT, ...]) -> None:
        array_type = INPUT * len(inputs)
        input_array = array_type(*inputs)
        sent = user32.SendInput(
            len(inputs),
            ctypes.cast(input_array, ctypes.POINTER(INPUT)),
            ctypes.sizeof(INPUT),
        )
        if sent != len(inputs):
            raise ctypes.WinError(ctypes.get_last_error())

    def _send_mouse_flags(self, flags: int, mouse_data: int = 0) -> None:
        self._send_inputs(
            (
                INPUT(
                    type=INPUT_MOUSE,
                    mi=MOUSEINPUT(mouseData=mouse_data, dwFlags=flags),
                ),
            )
        )


def _hwnd_to_int(hwnd: wintypes.HWND) -> int:
    return int(getattr(hwnd, "value", hwnd))


def _same_hwnd(left: wintypes.HWND | int | None, right: wintypes.HWND | int | None) -> bool:
    return _hwnd_to_int(left or 0) == _hwnd_to_int(right or 0)


def _normalize_ratio(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _window_rect_is_usable(rect: WindowRect) -> bool:
    if rect.width < 320 or rect.height < 180:
        return False
    if rect.right <= -30000 or rect.bottom <= -30000:
        return False
    return True


def _pick_best_lock_candidate(candidates: list[WindowCandidate], current_hwnd: int) -> int | None:
    preferred = [candidate for candidate in candidates if _window_rect_is_usable(candidate.rect)]
    if not preferred:
        return current_hwnd or (candidates[0].hwnd if candidates else None)
    preferred.sort(
        key=lambda candidate: (
            candidate.rect.width * candidate.rect.height,
            candidate.visible,
            bool(candidate.title.strip()),
            candidate.hwnd == current_hwnd,
        ),
        reverse=True,
    )
    return preferred[0].hwnd

