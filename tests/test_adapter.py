from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from bridge.adapter import AppServerAdapter, _resolve_command, _suggested_fix_for_error
from bridge.session_store import SessionStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fake_app_server.py"


class CommandResolutionTests(TestCase):
    def test_env_override_wins_over_auto_detection(self) -> None:
        with patch.dict(os.environ, {"CODEX_APP_SERVER_COMMAND": '["custom-codex","app-server"]'}):
            resolved = _resolve_command(None)
        self.assertEqual(resolved.command, ["custom-codex", "app-server"])
        self.assertIsNone(resolved.preflight_error)

    def test_user_level_npm_codex_cmd_is_preferred_on_windows(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only command resolution test")
        with tempfile.TemporaryDirectory() as temp:
            codex_cmd = Path(temp) / "npm" / "codex.cmd"
            codex_cmd.parent.mkdir(parents=True)
            codex_cmd.write_text("@echo off\r\n", encoding="utf-8")
            with patch.dict(os.environ, {"APPDATA": temp, "CODEX_APP_SERVER_COMMAND": ""}):
                with patch("bridge.adapter.shutil.which", return_value=r"C:\Program Files\WindowsApps\OpenAI.Codex_x\app\resources\codex.exe"):
                    resolved = _resolve_command(None)
        self.assertEqual(resolved.command, [str(codex_cmd), "app-server"])
        self.assertIsNone(resolved.preflight_error)

    def test_windowsapps_codex_path_is_blocked_with_fix_guidance(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only command resolution test")
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"APPDATA": temp, "CODEX_APP_SERVER_COMMAND": ""}):
                with patch("bridge.adapter.shutil.which", return_value=r"C:\Program Files\WindowsApps\OpenAI.Codex_x\app\resources\codex.exe"):
                    resolved = _resolve_command(None)
        self.assertIsNotNone(resolved.preflight_error)
        self.assertIn("WindowsApps", resolved.preflight_error or "")
        self.assertIn("setup_codex_cli.ps1", resolved.suggested_fix or "")

    def test_windowsapps_error_suggests_user_level_install(self) -> None:
        suggestion = _suggested_fix_for_error("[WinError 5] 拒绝访问。 C:\\Program Files\\WindowsApps\\OpenAI.Codex")
        self.assertIsNotNone(suggestion)
        self.assertIn("setup_codex_cli.ps1", suggestion or "")


class AppServerAdapterTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = SessionStore()
        self.adapter = AppServerAdapter(self.store, command=[sys.executable, str(FIXTURE)])

    async def asyncTearDown(self) -> None:
        await self.adapter.close()

    async def test_healthcheck_reports_available(self) -> None:
        health = await self.adapter.healthcheck()
        self.assertTrue(health.available)
        self.assertEqual(health.backend, "app_server")

    async def test_start_session_streams_and_completes(self) -> None:
        session = await self.store.create_session("E:\\workspace", "测试", "分析当前项目")
        await self.adapter.start_session(session.session_id, "分析当前项目")
        await self._wait_for_status(session.session_id, {"completed"})

        updated = await self.store.get_session(session.session_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.backend, "app_server")
        self.assertTrue(updated.backend_session_id)
        self.assertTrue(any(item.role == "assistant" and "Codex echo" in item.content for item in updated.messages))
        self.assertTrue(any(event["type"] == "message.delta" for event in updated.event_history))
        self.assertTrue(any(event["type"] == "turn.plan.updated" for event in updated.event_history))
        self.assertTrue(any(event["type"] == "command.output.delta" for event in updated.event_history))

    async def test_continue_session_reuses_existing_thread(self) -> None:
        session = await self.store.create_session("E:\\workspace", "测试", "先做第一步")
        await self.adapter.start_session(session.session_id, "先做第一步")
        await self._wait_for_status(session.session_id, {"completed"})
        first = await self.store.get_session(session.session_id)
        assert first is not None
        thread_id = first.backend_session_id

        await self.store.add_message(session.session_id, "user", "再继续")
        await self.adapter.continue_session(session.session_id, "再继续")
        await self._wait_for_status(session.session_id, {"completed"})

        second = await self.store.get_session(session.session_id)
        assert second is not None
        self.assertEqual(second.backend_session_id, thread_id)
        self.assertTrue(any(item.role == "assistant" and "再继续" in item.content for item in second.messages))

    async def test_cancel_session_interrupts_running_turn(self) -> None:
        session = await self.store.create_session("E:\\workspace", "测试", "hold this turn")
        await self.adapter.start_session(session.session_id, "hold this turn")
        await self._wait_for_status(session.session_id, {"running"})

        await self.adapter.cancel_session(session.session_id)
        await self._wait_for_status(session.session_id, {"cancelled"})

        updated = await self.store.get_session(session.session_id)
        assert updated is not None
        self.assertEqual(updated.status, "cancelled")

    async def test_approval_notification_moves_session_to_waiting(self) -> None:
        session = await self.store.create_session("E:\\workspace", "测试", "needs approval")
        await self.adapter.start_session(session.session_id, "needs approval")
        await self._wait_for_status(session.session_id, {"waiting"})

        updated = await self.store.get_session(session.session_id)
        assert updated is not None
        self.assertEqual(updated.status, "waiting")
        self.assertTrue(any(event["type"] == "approval.required" for event in updated.event_history))

    async def test_list_threads_filters_to_whitelisted_workspaces(self) -> None:
        threads = await self.adapter.list_threads(["E:\\workspace"])
        ids = {item["threadId"] for item in threads}
        self.assertIn("thread-existing", ids)
        self.assertIn("thread-large", ids)
        self.assertNotIn("thread-other", ids)

    async def test_read_thread_supports_large_responses(self) -> None:
        detail = await self.adapter.read_thread("thread-large", ["E:\\workspace"])
        self.assertEqual(detail["threadId"], "thread-large")
        assistant_text = detail["turns"][0]["items"][1]["text"]
        self.assertGreater(len(assistant_text), 100000)

    async def test_resume_thread_imports_history(self) -> None:
        session = await self.store.create_session("E:\\workspace", "导入线程", status="imported", source_thread_id="thread-existing")
        await self.adapter.resume_thread(session.session_id, "thread-existing")
        updated = await self.store.get_session(session.session_id)
        assert updated is not None
        self.assertEqual(updated.status, "imported")
        self.assertEqual(updated.backend_session_id, "thread-existing")
        self.assertEqual(updated.source_thread_id, "thread-existing")
        self.assertTrue(any(event["type"] == "thread.imported" for event in updated.event_history))

    async def test_resolve_command_approval_completes_session(self) -> None:
        session = await self.store.create_session("E:\\workspace", "审批", "needs approval")
        await self.adapter.start_session(session.session_id, "needs approval")
        await self._wait_for_status(session.session_id, {"waiting"})
        approvals = await self.store.list_approvals(session.session_id, active_only=True)
        self.assertEqual(len(approvals), 1)
        resolved = await self.adapter.resolve_approval(session.session_id, approvals[0].approval_id, "approve")
        self.assertEqual(resolved.resolution, "approve")
        await self._wait_for_status(session.session_id, {"completed"})

    async def test_resolve_request_user_input(self) -> None:
        session = await self.store.create_session("E:\\workspace", "补充输入", "please ask user input")
        await self.adapter.start_session(session.session_id, "please ask user input")
        await self._wait_for_status(session.session_id, {"waiting"})
        approvals = await self.store.list_approvals(session.session_id, active_only=True)
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0].kind, "item/tool/requestUserInput")
        await self.adapter.resolve_approval(
            session.session_id,
            approvals[0].approval_id,
            "submit",
            answers=[{"id": "color", "answers": ["blue"]}],
        )
        await self._wait_for_status(session.session_id, {"completed"})

    async def _wait_for_status(self, session_id: str, expected: set[str], timeout: float = 3.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            session = await self.store.get_session(session_id)
            if session is not None and session.status in expected:
                return
            if asyncio.get_running_loop().time() >= deadline:
                current = session.status if session is not None else "<missing>"
                raise AssertionError(f"Timed out waiting for status {expected}; current status={current}")
            await asyncio.sleep(0.05)
