from __future__ import annotations

from ctypes import wintypes
from datetime import datetime
from unittest import TestCase
from unittest.mock import call, patch

from app.models import LockedWindow
from app.codex_sidebar_ocr import CodexSidebarOcr, SidebarTargetAmbiguousError, SidebarTargetNotVisibleError
from app.codex_uia import CodexDesktopUIAutomation, ThreadFocusTarget, UIARect, UIASidebarItem, UIAutomationError
from app.windows_control import WindowCandidate, WindowRect, WindowsController, _pick_best_lock_candidate, _window_rect_is_usable


class WindowsControlTests(TestCase):
    def test_window_rect_is_usable_rejects_hidden_shell_window(self) -> None:
        self.assertFalse(_window_rect_is_usable(WindowRect(-32000, -32000, -31840, -31972)))
        self.assertTrue(_window_rect_is_usable(WindowRect(100, 100, 1200, 900)))

    def test_pick_best_lock_candidate_prefers_large_visible_window(self) -> None:
        candidates = [
            WindowCandidate(
                hwnd=10,
                visible=True,
                title="Codex",
                rect=WindowRect(-32000, -32000, -31840, -31972),
            ),
            WindowCandidate(
                hwnd=20,
                visible=True,
                title="Codex",
                rect=WindowRect(80, 60, 1440, 980),
            ),
        ]
        self.assertEqual(_pick_best_lock_candidate(candidates, 10), 20)

    def test_pick_best_lock_candidate_prefers_large_shell_host(self) -> None:
        candidates = [
            WindowCandidate(
                hwnd=10,
                visible=True,
                title="Codex",
                rect=WindowRect(-32000, -32000, -31840, -31972),
            ),
            WindowCandidate(
                hwnd=30,
                visible=False,
                title="",
                rect=WindowRect(78, 78, 1158, 702),
            ),
        ]
        self.assertEqual(_pick_best_lock_candidate(candidates, 10), 30)

    def test_find_codex_window_prefers_real_codex_process(self) -> None:
        controller = WindowsController()
        candidates = {
            10: WindowCandidate(10, True, "Codex Cloud Remote", WindowRect(0, 0, 1200, 800)),
            20: WindowCandidate(20, True, "Codex", WindowRect(0, 0, 1400, 900)),
        }
        windows = {
            10: LockedWindow(10, "Codex Cloud Remote", "chrome.exe", datetime.now().astimezone()),
            20: LockedWindow(20, "Codex", "Codex.exe", datetime.now().astimezone()),
        }

        with (
            patch.object(controller, "_top_level_windows", return_value=[wintypes.HWND(10), wintypes.HWND(20)]),
            patch.object(controller, "_canonical_lock_hwnd", side_effect=lambda hwnd: hwnd),
            patch.object(controller, "_candidate_for_hwnd", side_effect=lambda hwnd: candidates[int(hwnd.value)]),
            patch.object(controller, "_describe_window", side_effect=lambda hwnd: windows[int(hwnd.value)]),
            patch.object(controller, "get_window_rect", side_effect=lambda window: candidates[window.hwnd].rect),
        ):
            found = controller.find_codex_window()

        self.assertIsNotNone(found)
        self.assertEqual(found.hwnd, 20)

    def test_find_codex_window_can_recover_hidden_usable_codex_window(self) -> None:
        controller = WindowsController()
        candidates = {
            20: WindowCandidate(20, False, "Codex", WindowRect(0, 0, 1400, 900)),
            30: WindowCandidate(30, True, "Browser", WindowRect(0, 0, 1500, 950)),
        }
        windows = {
            20: LockedWindow(20, "Codex", "Codex.exe", datetime.now().astimezone()),
            30: LockedWindow(30, "Browser", "chrome.exe", datetime.now().astimezone()),
        }

        with (
            patch.object(controller, "_top_level_windows", return_value=[wintypes.HWND(20), wintypes.HWND(30)]),
            patch.object(controller, "_canonical_lock_hwnd", side_effect=lambda hwnd: hwnd),
            patch.object(controller, "_candidate_for_hwnd", side_effect=lambda hwnd: candidates[int(hwnd.value)]),
            patch.object(controller, "_describe_window", side_effect=lambda hwnd: windows[int(hwnd.value)]),
        ):
            found = controller.find_codex_window()

        self.assertIsNotNone(found)
        self.assertEqual(found.hwnd, 20)

    def test_find_codex_window_can_restore_offscreen_codex_for_command(self) -> None:
        controller = WindowsController()
        candidates = {
            20: WindowCandidate(20, True, "Codex", WindowRect(-32000, -32000, -31840, -31972)),
        }
        windows = {
            20: LockedWindow(20, "Codex", "Codex.exe", datetime.now().astimezone()),
        }

        def restore(hwnd: wintypes.HWND) -> None:
            candidates[int(hwnd.value)] = WindowCandidate(20, True, "Codex", WindowRect(80, 40, 1400, 900))

        with (
            patch.object(controller, "_top_level_windows", return_value=[wintypes.HWND(20)]),
            patch.object(controller, "_canonical_lock_hwnd", side_effect=lambda hwnd: hwnd),
            patch.object(controller, "_candidate_for_hwnd", side_effect=lambda hwnd: candidates[int(hwnd.value)]),
            patch.object(controller, "_describe_window", side_effect=lambda hwnd: windows[int(hwnd.value)]),
            patch.object(controller, "_restore_window_to_visible_area", side_effect=restore) as restore_window,
        ):
            found = controller.find_codex_window(restore=True)

        self.assertIsNotNone(found)
        self.assertEqual(found.hwnd, 20)
        restore_window.assert_called_once()

    def test_focus_codex_input_hint_taps_multiple_points(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "release_left_button") as release_left_button,
            patch.object(controller, "pointer_down_at_ratio") as pointer_down,
            patch.object(controller, "pointer_up_at_ratio") as pointer_up,
            patch("app.windows_control.time.sleep", return_value=None),
        ):
            controller._focus_codex_input_hint(locked_window)

        release_left_button.assert_called_once_with()
        self.assertEqual(
            pointer_down.call_args_list,
            [
                call(locked_window, 0.50, 0.90),
                call(locked_window, 0.50, 0.86),
                call(locked_window, 0.42, 0.90),
            ],
        )
        self.assertEqual(
            pointer_up.call_args_list,
            [
                call(locked_window, 0.50, 0.90),
                call(locked_window, 0.50, 0.86),
                call(locked_window, 0.42, 0.90),
            ],
        )

    def test_paste_text_does_not_use_codex_mouse_focus_hint(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "_focus_codex_input_hint") as focus_hint,
            patch.object(controller, "focus_codex_composer") as focus_composer,
            patch.object(controller, "_set_clipboard_text") as set_clipboard_text,
            patch.object(controller, "_send_inputs") as send_inputs,
        ):
            controller.paste_text("test-0410", submit=True, target_window=locked_window)

        focus_hint.assert_not_called()
        focus_composer.assert_not_called()
        set_clipboard_text.assert_called_once_with("test-0410")
        send_inputs.assert_called_once()

    def test_paste_text_without_codex_target_does_not_focus_composer(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Editor",
            process_name="notepad.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "focus_codex_composer") as focus_composer,
            patch.object(controller, "_set_clipboard_text") as set_clipboard_text,
            patch.object(controller, "_send_inputs") as send_inputs,
        ):
            controller.paste_text("plain", submit=False, target_window=locked_window)

        focus_composer.assert_not_called()
        set_clipboard_text.assert_called_once_with("plain")
        send_inputs.assert_called_once()

    def test_focus_codex_thread_by_index_uses_visible_sidebar_click_only(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "release_left_button") as release_left_button,
            patch.object(controller, "get_window_rect", return_value=WindowRect(0, 0, 1280, 900)),
            patch.object(controller, "scroll_vertical_at_ratio") as scroll_at_ratio,
            patch.object(controller, "_tap_ratio") as tap_ratio,
            patch.object(controller, "focus_codex_composer") as focus_composer,
            patch("app.windows_control.time.sleep", return_value=None),
        ):
            controller.focus_codex_thread_by_index(locked_window, 5, total_threads=30)

        release_left_button.assert_called_once_with()
        scroll_at_ratio.assert_not_called()
        tap_ratio.assert_called_once()
        self.assertEqual(tap_ratio.call_args.args[0], locked_window)
        self.assertEqual(tap_ratio.call_args.args[1], 0.16)
        focus_composer.assert_not_called()

    def test_focus_codex_thread_by_index_rejects_non_visible_targets(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "get_window_rect", return_value=WindowRect(0, 0, 1280, 700)),
            patch.object(controller, "_tap_ratio") as tap_ratio,
            patch("app.windows_control.time.sleep", return_value=None),
        ):
            with self.assertRaises(ValueError):
                controller.focus_codex_thread_by_index(locked_window, 20, total_threads=30)

        tap_ratio.assert_not_called()

    def test_focus_codex_thread_by_text_taps_uia_target_center(self) -> None:
        class FakeDesktopUIA:
            def __init__(self) -> None:
                self.find_args = None
                self.verify_args = None

            def find_thread_target(self, hwnd: int, *, workspace: str, title: str) -> ThreadFocusTarget:
                self.find_args = (hwnd, workspace, title)
                return ThreadFocusTarget(
                    matched_project="codex-mcp-mobile",
                    matched_title="Target thread",
                    rect=UIARect(x=120, y=260, width=140, height=30),
                    raw_name="Target thread 1 周",
                )

            def wait_for_active_title(self, hwnd: int, *, expected_title: str, timeout: float = 1.6, interval: float = 0.16) -> str:
                self.verify_args = (hwnd, expected_title)
                return expected_title

        fake_uia = FakeDesktopUIA()
        controller = WindowsController(desktop_uia=fake_uia)
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "release_left_button") as release_left_button,
            patch.object(controller, "_tap_absolute") as tap_absolute,
            patch("app.windows_control.time.sleep", return_value=None),
        ):
            match = controller.focus_codex_thread_by_text(
                locked_window,
                workspace=r"E:\codex-mcp-mobile",
                title="Target thread",
                preview="summary",
            )

        release_left_button.assert_called_once_with()
        self.assertEqual(fake_uia.find_args, (123, r"E:\codex-mcp-mobile", "Target thread"))
        self.assertEqual(fake_uia.verify_args, (123, "Target thread"))
        tap_absolute.assert_called_once_with(190, 275)
        self.assertEqual(match.matched_text, "Target thread")
        self.assertEqual(match.verified_title, "Target thread")

    def test_sidebar_ocr_matches_unique_visible_row(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "Alpha plan 已完成", "left": 0, "top": 0, "right": 100, "bottom": 20})(),
            type("Row", (), {"text": "Target switch thread summary", "left": 0, "top": 30, "right": 100, "bottom": 50})(),
        ]

        match = ocr._match_rows(rows, title="Target switch thread", preview="summary")

        self.assertEqual(match.matched_text, "Target switch thread summary")
        self.assertGreaterEqual(match.confidence, 0.72)

    def test_sidebar_ocr_rejects_ambiguous_rows(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "Target switch thread A", "left": 0, "top": 0, "right": 100, "bottom": 20})(),
            type("Row", (), {"text": "Target switch thread B", "left": 0, "top": 30, "right": 100, "bottom": 50})(),
        ]

        with self.assertRaises(SidebarTargetAmbiguousError):
            ocr._match_rows(rows, title="Target switch thread", preview=None)

    def test_sidebar_ocr_rejects_missing_target(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "Completely different", "left": 0, "top": 0, "right": 100, "bottom": 20})(),
        ]

        with self.assertRaises(SidebarTargetNotVisibleError):
            ocr._match_rows(rows, title="Target switch thread", preview=None)

    def test_sidebar_ocr_short_title_does_not_match_longer_prefix_title(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "你好2 completed", "left": 0, "top": 0, "right": 100, "bottom": 20})(),
            type("Row", (), {"text": "你好 completed", "left": 0, "top": 30, "right": 100, "bottom": 50})(),
        ]

        match = ocr._match_rows(rows, title="你好", preview=None)

        self.assertEqual(match.matched_text, "你好 completed")

    def test_sidebar_ocr_short_title_rejects_prefix_only_match(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "你好2 completed", "left": 0, "top": 0, "right": 100, "bottom": 20})(),
        ]

        with self.assertRaises(SidebarTargetNotVisibleError):
            ocr._match_rows(rows, title="你好", preview=None)

    def test_sidebar_ocr_short_title_does_not_match_preview_token(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "1周 远程codex 你好2 1天", "left": 0, "top": 0, "right": 120, "bottom": 20})(),
        ]

        with self.assertRaises(SidebarTargetNotVisibleError):
            ocr._match_rows(rows, title="你好2", preview=None)

    def test_sidebar_ocr_prefers_exact_leading_title_token_after_meta_prefix(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"row_index": 2, "text": "Re 1周 远程codex 你好 1天", "left": 0, "top": 0, "right": 140, "bottom": 20})(),
            type("Row", (), {"row_index": 3, "text": "你好 1天 远程桌面", "left": 0, "top": 30, "right": 120, "bottom": 50})(),
        ]

        match = ocr._match_rows(rows, title="远程codex", preview=None)

        self.assertEqual(match.matched_text, "Re 1周 远程codex 你好 1天")
        self.assertEqual(match.row_index, 2)

    def test_sidebar_ocr_short_title_rejects_duplicate_exact_matches(self) -> None:
        ocr = CodexSidebarOcr()
        rows = [
            type("Row", (), {"text": "你好 completed", "left": 0, "top": 0, "right": 100, "bottom": 20})(),
            type("Row", (), {"text": "你好 running", "left": 0, "top": 30, "right": 100, "bottom": 50})(),
        ]

        with self.assertRaises(SidebarTargetAmbiguousError):
            ocr._match_rows(rows, title="你好", preview=None)

    def test_sidebar_visible_rows_uses_window_height(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with patch.object(controller, "get_window_rect", return_value=WindowRect(0, 0, 1600, 1080)):
            self.assertEqual(controller._codex_sidebar_visible_rows(locked_window), 13)

    def test_ensure_window_ready_rejects_invisible_window_after_focus(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch("app.windows_control.user32.IsWindow", return_value=True),
            patch("app.windows_control.user32.IsWindowVisible", return_value=False),
            patch("app.windows_control.user32.ShowWindow", return_value=True),
            patch.object(controller, "_canonical_lock_hwnd", side_effect=lambda hwnd: hwnd),
            patch.object(controller, "_focus_window", return_value=True),
            patch("app.windows_control.time.sleep", return_value=None),
        ):
            result = controller.ensure_window_ready(locked_window)

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "window_not_visible")

    def test_start_codex_new_thread_uses_uia_button(self) -> None:
        class FakeDesktopUIA:
            def __init__(self) -> None:
                self.args = None

            def activate_new_thread(self, hwnd: int, *, workspace: str | None = None):
                self.args = (hwnd, workspace)
                return type("Started", (), {"button_name": "在 codex-mcp-mobile 中开始新线程", "verified_title": "Untitled"})()

        fake_uia = FakeDesktopUIA()
        controller = WindowsController(desktop_uia=fake_uia)
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "release_left_button") as release_left_button,
        ):
            started = controller.start_codex_new_thread(locked_window, workspace=r"E:\codex-mcp-mobile")

        release_left_button.assert_called_once_with()
        self.assertEqual(fake_uia.args, (123, r"E:\codex-mcp-mobile"))
        self.assertEqual(started.button_name, "在 codex-mcp-mobile 中开始新线程")

    def test_focus_codex_composer_taps_right_side_input_area(self) -> None:
        controller = WindowsController()
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        with (
            patch.object(controller, "release_left_button") as release_left_button,
            patch.object(controller, "_tap_ratio") as tap_ratio,
            patch("app.windows_control.time.sleep", return_value=None),
        ):
            controller.focus_codex_composer(locked_window)

        release_left_button.assert_called_once_with()
        self.assertEqual(
            tap_ratio.call_args_list,
            [
                call(locked_window, 0.56, 0.84),
                call(locked_window, 0.62, 0.86),
                call(locked_window, 0.70, 0.84),
            ],
        )


class CodexDesktopUIAutomationTests(TestCase):
    def make_project(self, name: str) -> UIASidebarItem:
        return UIASidebarItem(
            name=name,
            control_type="ControlType.ListItem",
            rect=UIARect(8, 210, 260, 80),
            offscreen=False,
            parent_name="",
            parent_control_type="ControlType.List",
            grandparent_name="自动化操作文件夹",
            grandparent_control_type="ControlType.Group",
        )

    def make_thread(
        self,
        *,
        name: str,
        project: str,
        offscreen: bool = False,
        scrollable: bool = False,
    ) -> UIASidebarItem:
        return UIASidebarItem(
            name=name,
            control_type="ControlType.ListItem",
            rect=UIARect(8, 240, 260, 32),
            offscreen=offscreen,
            parent_name=f"“{project}”中的自动化操作",
            parent_control_type="ControlType.List",
            grandparent_name=project,
            grandparent_control_type="ControlType.ListItem",
            scrollable=scrollable,
        )

    def make_content_item(self, name: str) -> UIASidebarItem:
        return UIASidebarItem(
            name=name,
            control_type="ControlType.ListItem",
            rect=UIARect(534, -4929, 688, 125),
            offscreen=True,
            parent_name="",
            parent_control_type="ControlType.List",
            grandparent_name='包含“远程桌面”的正文项目',
            grandparent_control_type="ControlType.Group",
        )

    def test_find_thread_target_scopes_match_to_workspace_project(self) -> None:
        class FakeUIA(CodexDesktopUIAutomation):
            def list_sidebar_items(self, hwnd: int) -> list[UIASidebarItem]:
                return [
                    self_case.make_project("codex-mcp-mobile"),
                    self_case.make_project("远程桌面"),
                    self_case.make_thread(name="远程codex1 周", project="codex-mcp-mobile"),
                    self_case.make_thread(name="开发面向编程场景的手机远程辅助输入层1 周", project="远程桌面"),
                ]

        self_case = self
        target = FakeUIA().find_thread_target(123, workspace=r"E:\远程桌面", title="开发面向编程场景的手机远程辅助输入层")

        self.assertEqual(target.matched_project, "远程桌面")
        self.assertEqual(target.matched_title, "开发面向编程场景的手机远程辅助输入层")

    def test_find_thread_target_ignores_right_pane_list_items(self) -> None:
        class FakeUIA(CodexDesktopUIAutomation):
            def list_sidebar_items(self, hwnd: int) -> list[UIASidebarItem]:
                return [
                    self_case.make_project("远程桌面"),
                    self_case.make_content_item("远程桌面"),
                    self_case.make_thread(name="远程codex1 周", project="远程桌面"),
                    self_case.make_content_item("远程codex"),
                ]

        self_case = self
        target = FakeUIA().find_thread_target(123, workspace=r"E:\远程桌面", title="远程codex")

        self.assertEqual(target.matched_project, "远程桌面")
        self.assertEqual(target.matched_title, "远程codex")

    def test_find_thread_target_rejects_duplicate_titles_in_same_project(self) -> None:
        class FakeUIA(CodexDesktopUIAutomation):
            def list_sidebar_items(self, hwnd: int) -> list[UIASidebarItem]:
                return [
                    self_case.make_project("codex-mcp-mobile"),
                    self_case.make_thread(name="你好1 天", project="codex-mcp-mobile"),
                    self_case.make_thread(name="你好2 天", project="codex-mcp-mobile"),
                ]

        self_case = self
        with self.assertRaises(UIAutomationError) as ctx:
            FakeUIA().find_thread_target(123, workspace=r"E:\codex-mcp-mobile", title="你好")

        self.assertEqual(ctx.exception.code, "ambiguous_target")

    def test_find_thread_target_scrolls_offscreen_match_into_view(self) -> None:
        class FakeUIA(CodexDesktopUIAutomation):
            def __init__(self) -> None:
                self.calls = 0
                self.scrolled = None

            def list_sidebar_items(self, hwnd: int) -> list[UIASidebarItem]:
                self.calls += 1
                if self.calls == 1:
                    return [
                        self_case.make_project("codex-mcp-mobile"),
                        self_case.make_thread(name="远程codex1 周", project="codex-mcp-mobile", offscreen=True, scrollable=True),
                    ]
                return [
                    self_case.make_project("codex-mcp-mobile"),
                    self_case.make_thread(name="远程codex1 周", project="codex-mcp-mobile", offscreen=False, scrollable=True),
                ]

            def scroll_item_into_view(self, hwnd: int, *, item_name: str, project_name: str) -> None:
                self.scrolled = (hwnd, item_name, project_name)

        self_case = self
        helper = FakeUIA()
        target = helper.find_thread_target(123, workspace=r"E:\codex-mcp-mobile", title="远程codex")

        self.assertEqual(helper.scrolled, (123, "远程codex1 周", "codex-mcp-mobile"))
        self.assertEqual(target.matched_title, "远程codex")

