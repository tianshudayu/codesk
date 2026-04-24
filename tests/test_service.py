from __future__ import annotations

import asyncio
import json
from datetime import datetime
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from bridge.adapter import BackendHealth, BackendUnavailableError, CodexAdapter
from bridge.auth import PairingManager
from bridge.desktop_automation import DesktopAutomationSendError, DesktopAutomationUnavailableError
from bridge.models import ApprovalRecord
from bridge.service import BridgeService, BridgeServiceError
from bridge.session_store import SessionStore


class RecordingAdapter(CodexAdapter):
    backend_name = "recording"

    def __init__(self, store: SessionStore) -> None:
        super().__init__(store)
        self.healthcheck_calls = 0
        self.start_error: Exception | None = None
        self.continue_error: Exception | None = None
        self.list_threads_error: Exception | None = None
        self.read_thread_error: Exception | None = None
        self.resume_error: Exception | None = None
        self.list_threads_calls: list[list[str]] = []
        self.read_thread_calls: list[tuple[str, list[str]]] = []
        self.resume_calls: list[tuple[str, str, str | None]] = []
        self.continue_calls: list[tuple[str, str]] = []
        self.start_calls: list[tuple[str, str]] = []
        self.thread_detail = {
            "threadId": "thread-1",
            "title": "历史线程",
            "workspace": r"E:\workspace",
            "source": "cli",
            "status": "completed",
            "turns": [],
        }
        self.thread_summaries = [
            {
                "threadId": "thread-1",
                "title": "历史线程",
                "workspace": r"E:\workspace",
                "source": "cli",
                "status": "completed",
                "preview": "历史线程",
                "createdAt": None,
                "updatedAt": None,
                "path": None,
            }
        ]

    async def start_session(self, session_id: str, prompt: str) -> None:
        self.start_calls.append((session_id, prompt))
        if self.start_error is not None:
            raise self.start_error
        await self._store.set_backend_context(
            session_id,
            backend=self.backend_name,
            backend_session_id="thread-live",
            backend_run_id="turn-live",
        )

    async def continue_session(self, session_id: str, prompt: str) -> None:
        self.continue_calls.append((session_id, prompt))
        if self.continue_error is not None:
            raise self.continue_error

    async def cancel_session(self, session_id: str) -> None:
        return None

    async def list_threads(self, workspace_roots: list[str]) -> list[dict[str, object]]:
        self.list_threads_calls.append(list(workspace_roots))
        if self.list_threads_error is not None:
            raise self.list_threads_error
        return [dict(item) for item in self.thread_summaries]

    async def read_thread(self, thread_id: str, workspace_roots: list[str]) -> dict[str, object]:
        self.read_thread_calls.append((thread_id, list(workspace_roots)))
        if self.read_thread_error is not None:
            raise self.read_thread_error
        detail = dict(self.thread_detail)
        detail["threadId"] = thread_id
        return detail

    async def resume_thread(self, session_id: str, thread_id: str, prompt: str | None = None) -> None:
        self.resume_calls.append((session_id, thread_id, prompt))
        if self.resume_error is not None:
            raise self.resume_error
        await self._store.set_backend_context(
            session_id,
            backend=self.backend_name,
            backend_session_id=thread_id,
            backend_run_id="",
            source_thread_id=thread_id,
        )

    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        action: str,
        *,
        answers: list[dict[str, object]] | None = None,
        content: str | None = None,
    ) -> ApprovalRecord:
        return ApprovalRecord(
            approval_id=approval_id,
            session_id=session_id,
            request_id="request-1",
            kind="item/commandExecution/requestApproval",
            title="approval",
            summary="approval",
            payload={},
            available_actions=["approve"],
            status="resolved",
            created_at=datetime.now().astimezone(),
            resolved_at=datetime.now().astimezone(),
            resolution=action,
        )

    async def healthcheck(self) -> BackendHealth:
        self.healthcheck_calls += 1
        return BackendHealth(backend=self.backend_name, available=True)


class DesktopAutomationStub:
    def __init__(self, *, ready: bool = False, preview_supported: bool = True) -> None:
        self.started = False
        self.closed = False
        self.send_calls: list[tuple[str, bool]] = []
        self.command_calls: list[dict[str, object]] = []
        self.send_error: Exception | None = None
        self.command_errors: dict[str, Exception] = {}
        self.snapshot_payload = {
            "baseUrl": "http://127.0.0.1:8765",
            "available": ready,
            "previewSupported": preview_supported,
            "connected": ready,
            "authenticated": ready,
            "windowLocked": ready,
            "codexWindowLocked": ready,
            "lockedWindow": {"title": "Codex", "process_name": "Codex.exe"} if ready else None,
            "windowTitle": "Codex" if ready else None,
            "processName": "Codex.exe" if ready else None,
            "lastError": None,
        }

    def snapshot(self) -> dict[str, object]:
        return dict(self.snapshot_payload)

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def send_text(self, text: str, *, submit: bool = True) -> None:
        self.send_calls.append((text, submit))
        if self.send_error is not None:
            raise self.send_error

    async def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, object]]]:
        return "desktop-stub", asyncio.Queue()

    async def unsubscribe(self, subscriber_id: str) -> None:
        return None

    async def send_command(self, payload: dict[str, object], *, expect_ack: bool = False, timeout: float = 10.0) -> dict[str, object] | None:
        self.command_calls.append(dict(payload))
        error = self.command_errors.get(str(payload.get("type") or ""))
        if error is not None:
            raise error
        if payload.get("type") == "codex.thread.focus":
            return {
                "type": "ack",
                "id": payload.get("id"),
                "matchedText": payload.get("title") or "",
                "matchedProject": payload.get("workspace") or "",
                "matchedTitle": payload.get("title") or "",
                "verifiedTitle": payload.get("title") or "",
                "confidence": 0.95,
            }
        return {"type": "ack", "id": payload.get("id")}


class BridgeServiceActionTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._runtime_root = tempfile.TemporaryDirectory()
        self.addCleanup(self._runtime_root.cleanup)

    def create_service(
        self,
        adapter: RecordingAdapter,
        *,
        workspace_roots: list[str] | None = None,
        desktop_automation=None,
        default_workspace_root: str | None = None,
    ) -> BridgeService:
        return BridgeService(
            pairing=PairingManager(),
            store=adapter._store,
            adapter=adapter,
            workspace_roots=[r"E:\workspace"] if workspace_roots is None else workspace_roots,
            default_workspace_root=default_workspace_root or self._runtime_root.name,
            desktop_automation=desktop_automation,
        )

    async def test_action_payloads_skip_preflight_healthcheck(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        service = self.create_service(adapter)

        created = await service.create_session_payload(r"E:\workspace", "分析当前项目")
        await service.continue_session_payload(created["sessionId"], "继续")
        threads = await service.list_threads_payload()
        detail = await service.get_thread_payload("thread-1")
        resumed = await service.resume_thread_payload("thread-1")

        self.assertEqual(adapter.healthcheck_calls, 0)
        self.assertEqual(len(threads["items"]), 1)
        self.assertEqual(detail["threadId"], "thread-1")
        self.assertEqual(resumed["sourceThreadId"], "thread-1")

    async def test_backend_unavailable_maps_to_503_without_healthcheck(self) -> None:
        cases = [
            ("create_session", "start_error"),
            ("continue_session", "continue_error"),
            ("list_threads", "list_threads_error"),
            ("get_thread", "read_thread_error"),
            ("resume_thread", "resume_error"),
        ]

        for name, error_attr in cases:
            with self.subTest(action=name):
                store = SessionStore()
                adapter = RecordingAdapter(store)
                setattr(adapter, error_attr, BackendUnavailableError("backend down"))
                service = self.create_service(adapter)

                if name == "create_session":
                    action = service.create_session_payload(r"E:\workspace", "分析当前项目")
                elif name == "continue_session":
                    session = await store.create_session(r"E:\workspace", "测试", "继续")
                    await store.set_backend_context(session.session_id, backend_session_id="thread-live")
                    action = service.continue_session_payload(session.session_id, "继续")
                elif name == "list_threads":
                    action = service.list_threads_payload()
                elif name == "get_thread":
                    action = service.get_thread_payload("thread-1")
                else:
                    action = service.resume_thread_payload("thread-1", "continue")

                with self.assertRaises(BridgeServiceError) as ctx:
                    await action

                self.assertEqual(ctx.exception.status_code, 503)
                self.assertEqual(adapter.healthcheck_calls, 0)

    async def test_get_thread_payload_quarantines_corrupted_thread_and_filters_future_lists(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.read_thread_error = RuntimeError(
            "state db discrepancy during find_thread_path_by_id_str_in_subdir: falling_back"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.create_service(adapter, default_workspace_root=temp_dir)

            with self.assertRaises(BridgeServiceError) as ctx:
                await service.get_thread_payload("thread-1")

            self.assertEqual(ctx.exception.status_code, 410)
            self.assertIn("hidden", ctx.exception.detail.lower())

            threads = await service.list_threads_payload()

        self.assertEqual(threads["items"], [])

    async def test_resume_thread_payload_fast_fails_for_quarantined_thread(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.read_thread_error = RuntimeError(
            "failed to open state db at C:\\Users\\administered\\.codex\\state_5.sqlite"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.create_service(adapter, default_workspace_root=temp_dir)

            with self.assertRaises(BridgeServiceError):
                await service.get_thread_payload("thread-1")

            with self.assertRaises(BridgeServiceError) as ctx:
                await service.resume_thread_payload("thread-1")

        self.assertEqual(ctx.exception.status_code, 410)
        self.assertEqual(adapter.resume_calls, [])

    async def test_get_thread_payload_quarantines_corrupted_backend_unavailable_error(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.read_thread_error = BackendUnavailableError(
            "failed to open state db at C:\\Users\\administered\\.codex\\state_5.sqlite"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.create_service(adapter, default_workspace_root=temp_dir)

            with self.assertRaises(BridgeServiceError) as ctx:
                await service.get_thread_payload("thread-1")

            threads = await service.list_threads_payload()

        self.assertEqual(ctx.exception.status_code, 410)
        self.assertEqual(threads["items"], [])

    async def test_loads_quarantine_file_with_utf8_bom(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        with tempfile.TemporaryDirectory() as temp_dir:
            quarantine_path = Path(temp_dir) / ".logs" / "thread-quarantine.json"
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            quarantine_path.write_text(
                json.dumps(
                    {
                        "thread-bom": {
                            "message": "hidden",
                            "reason": "history_corrupted",
                            "title": "bom",
                            "workspace": r"E:\workspace",
                            "updatedAt": "2026-04-22T00:00:00+08:00",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )
            service = self.create_service(adapter, default_workspace_root=temp_dir)

            threads = await service.list_threads_payload()

        self.assertEqual({item["threadId"] for item in threads["items"]}, {"thread-1"})
        self.assertIn("thread-bom", service._quarantined_threads)

    async def test_discovery_mode_lists_all_threads_and_dedupes_workspaces(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [
            {
                "threadId": "thread-1",
                "title": "workspace one",
                "workspace": r"E:\workspace",
                "source": "cli",
                "status": "completed",
                "preview": "workspace one",
                "createdAt": None,
                "updatedAt": "2026-04-07T12:00:00+08:00",
                "path": None,
            },
            {
                "threadId": "thread-2",
                "title": "workspace two",
                "workspace": r"D:\other",
                "source": "cli",
                "status": "completed",
                "preview": "workspace two",
                "createdAt": None,
                "updatedAt": "2026-04-07T12:01:00+08:00",
                "path": None,
            },
            {
                "threadId": "thread-3",
                "title": "workspace one newer",
                "workspace": r"E:\workspace",
                "source": "cli",
                "status": "completed",
                "preview": "workspace one newer",
                "createdAt": None,
                "updatedAt": "2026-04-07T12:02:00+08:00",
                "path": None,
            },
        ]
        service = self.create_service(adapter, workspace_roots=[])

        workspaces = await service.list_workspaces_payload()
        threads = await service.list_threads_payload()

        self.assertEqual(adapter.list_threads_calls, [[], []])
        self.assertEqual(workspaces["items"], [r"E:\workspace", r"D:\other"])
        self.assertEqual({item["threadId"] for item in threads["items"]}, {"thread-1", "thread-2", "thread-3"})

    async def test_discovery_mode_workspaces_fall_back_to_default_root(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = []
        service = self.create_service(adapter, workspace_roots=[])

        workspaces = await service.list_workspaces_payload()

        self.assertEqual(workspaces["items"], [self._runtime_root.name])

    async def test_auto_adopt_running_threads_only_once(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [
            {
                "threadId": "thread-running",
                "title": "running thread",
                "workspace": r"E:\workspace",
                "source": "cli",
                "status": "running",
                "preview": "running thread",
                "createdAt": None,
                "updatedAt": None,
                "path": None,
            },
            {
                "threadId": "thread-waiting",
                "title": "waiting thread",
                "workspace": r"D:\other",
                "source": "cli",
                "status": "approval-required",
                "preview": "waiting thread",
                "createdAt": None,
                "updatedAt": None,
                "path": None,
            },
            {
                "threadId": "thread-idle",
                "title": "idle thread",
                "workspace": r"E:\workspace",
                "source": "cli",
                "status": "completed",
                "preview": "idle thread",
                "createdAt": None,
                "updatedAt": None,
                "path": None,
            },
        ]
        service = self.create_service(adapter, workspace_roots=[])

        first = await service.list_sessions_payload()
        second = await service.list_sessions_payload()

        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(len(second["items"]), 2)
        self.assertEqual(len(adapter.resume_calls), 2)
        by_thread = {item["sourceThreadId"]: item for item in first["items"]}
        self.assertEqual(by_thread["thread-running"]["sessionKind"], "auto_adopted")
        self.assertEqual(by_thread["thread-running"]["status"], "running")
        self.assertEqual(by_thread["thread-waiting"]["sessionKind"], "auto_adopted")
        self.assertEqual(by_thread["thread-waiting"]["status"], "waiting")

    async def test_resume_thread_reuses_existing_auto_adopted_session(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [
            {
                "threadId": "thread-running",
                "title": "running thread",
                "workspace": r"E:\workspace",
                "source": "cli",
                "status": "running",
                "preview": "running thread",
                "createdAt": None,
                "updatedAt": None,
                "path": None,
            }
        ]
        adapter.thread_detail = {
            "threadId": "thread-running",
            "title": "running thread",
            "workspace": r"E:\workspace",
            "source": "cli",
            "status": "running",
            "turns": [],
        }
        service = self.create_service(adapter, workspace_roots=[])

        payload = await service.list_sessions_payload()
        reused = await service.resume_thread_payload("thread-running")

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(reused["sessionId"], payload["items"][0]["sessionId"])
        self.assertEqual(reused["sessionKind"], "auto_adopted")
        self.assertEqual(len(adapter.resume_calls), 1)

    async def test_resume_thread_without_prompt_skips_adapter_and_desktop_align(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        desktop.snapshot_payload["codexWindowControllable"] = True
        service = self.create_service(adapter, desktop_automation=desktop)

        resumed = await service.resume_thread_payload("thread-1")

        self.assertEqual(adapter.resume_calls, [])
        self.assertEqual(adapter.read_thread_calls, [])
        self.assertEqual(desktop.command_calls, [])
        self.assertEqual(resumed["deliveryRoute"], "app_server")
        self.assertEqual(resumed["desktopTargetState"], "unbound")

    async def test_list_sessions_marks_active_session(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        service = self.create_service(adapter)
        first = await store.create_session(r"E:\workspace", "first", "first prompt")
        second = await store.create_session(r"E:\workspace", "second", "second prompt")
        await store.set_active_session(first.session_id, source="test")

        payload = await service.list_sessions_payload()

        items = {item["sessionId"]: item for item in payload["items"]}
        self.assertTrue(items[first.session_id]["isActive"])
        self.assertFalse(items[second.session_id]["isActive"])

    async def test_session_store_broadcasts_active_session_event(self) -> None:
        store = SessionStore()
        session = await store.create_session(r"E:\workspace", "first", "first prompt")
        subscriber_id, queue = await store.subscribe_ui()

        payload = await store.set_active_session(session.session_id, source="test")
        event = await asyncio.wait_for(queue.get(), timeout=0.2)

        self.assertEqual(payload["activeSessionId"], session.session_id)
        self.assertEqual(event["type"], "activeSession.changed")
        self.assertEqual(event["activeSessionId"], session.session_id)
        await store.unsubscribe_ui(subscriber_id)

    async def test_continue_session_publishes_user_message_event(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        service = self.create_service(adapter)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live")
        subscriber_id, queue, history = await store.subscribe(session.session_id)

        await service.continue_session_payload(session.session_id, "follow up")
        event = await asyncio.wait_for(queue.get(), timeout=0.2)

        self.assertEqual(history, [])
        self.assertEqual(event["type"], "message.completed")
        self.assertEqual(event["role"], "user")
        self.assertEqual(event["content"], "follow up")
        await store.unsubscribe(session.session_id, subscriber_id)

    async def test_continue_session_uses_desktop_after_explicit_align(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [{**adapter.thread_summaries[0], "threadId": "thread-live"}]
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")

        aligned = await service.align_desktop_session_payload(session.session_id)
        payload = await service.continue_session_payload(session.session_id, "desktop send")
        updated = await store.get_session(session.session_id)
        session_payload = await service.get_session_payload(session.session_id)
        admin_payload = await service.admin_state_payload()

        self.assertEqual(aligned["desktopTargetState"], "aligned")
        self.assertEqual(payload, {"ok": True})
        self.assertEqual([item["type"] for item in desktop.command_calls], ["codex.thread.focus"])
        self.assertEqual(desktop.command_calls[0]["threadId"], "thread-live")
        self.assertEqual(desktop.command_calls[0]["workspace"], r"E:\workspace")
        self.assertIn("title", desktop.command_calls[0])
        self.assertNotIn("preview", desktop.command_calls[0])
        self.assertNotIn("targetIndex", desktop.command_calls[0])
        self.assertEqual(desktop.send_calls, [("desktop send", True)])
        self.assertEqual(adapter.continue_calls, [])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.delivery_route, "desktop_gui")
        self.assertEqual(updated.desktop_target_state, "aligned")
        self.assertEqual(updated.desktop_target_confidence, 0.95)
        self.assertEqual(updated.desktop_target_matched_text, desktop.command_calls[0]["title"])
        self.assertEqual(session_payload["deliveryRoute"], "desktop_gui")
        self.assertEqual(session_payload["desktopTargetConfidence"], 0.95)
        self.assertEqual(session_payload["desktopTargetMatchedText"], desktop.command_calls[0]["title"])
        self.assertTrue(session_payload["desktopAutomationReady"])
        self.assertTrue(admin_payload["desktopAutomation"]["available"])

    async def test_session_payload_marks_store_approval_source(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial", status="waiting")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")
        await store.set_delivery_route(session.session_id, "desktop_gui")
        await store.set_active_session(session.session_id, source="test")
        await store.add_approval(
            ApprovalRecord(
                approval_id="approval-1",
                session_id=session.session_id,
                request_id="request-1",
                kind="item/commandExecution/requestApproval",
                title="approval",
                summary="approval",
                payload={},
                available_actions=["approve"],
                status="pending",
                created_at=datetime.now().astimezone(),
            )
        )

        payload = await service.get_session_payload(session.session_id)

        self.assertEqual(payload["pendingApprovalSource"], "store")
        self.assertFalse(payload["desktopApprovalControllable"])

    async def test_plan_continue_preserves_desktop_route_for_aligned_thread(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial", status="completed")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")
        await store.set_delivery_route(session.session_id, "desktop_gui")
        await store.set_desktop_target(session.session_id, "aligned", "已切到目标线程。")
        await store.set_active_session(session.session_id, source="test")

        payload = await service.continue_session_payload(session.session_id, "plan send", interaction_mode="plan")
        updated = await store.get_session(session.session_id)

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(adapter.continue_calls), 1)
        self.assertIn("<codex-mobile-plan-mode>", adapter.continue_calls[0][1])
        self.assertEqual(desktop.send_calls, [])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.delivery_route, "desktop_gui")

    async def test_session_payload_marks_desktop_approval_source_when_waiting(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True, preview_supported=True)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial", status="waiting")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")
        await store.set_delivery_route(session.session_id, "desktop_gui")
        await store.set_active_session(session.session_id, source="test")

        payload = await service.get_session_payload(session.session_id)

        self.assertEqual(payload["pendingApprovalSource"], "desktop")
        self.assertTrue(payload["desktopApprovalControllable"])

    async def test_session_payload_marks_desktop_approval_uncontrollable_without_preview(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True, preview_supported=False)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial", status="waiting")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")
        await store.set_delivery_route(session.session_id, "desktop_gui")
        await store.set_active_session(session.session_id, source="test")

        payload = await service.get_session_payload(session.session_id)

        self.assertEqual(payload["pendingApprovalSource"], "desktop")
        self.assertFalse(payload["desktopApprovalControllable"])

    async def test_inject_test_approval_creates_store_approval_and_can_resolve(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        service = self.create_service(adapter)
        session = await store.create_session(r"E:\workspace", "demo", "initial", status="completed")

        approval = await service.inject_test_approval_payload(session.session_id)
        waiting = await service.get_session_payload(session.session_id)
        approvals = await service.list_approvals_payload(session.session_id)

        self.assertEqual(waiting["status"], "waiting")
        self.assertEqual(waiting["pendingApprovalSource"], "store")
        self.assertEqual(len(approvals["items"]), 1)
        self.assertEqual(approval["approvalId"], approvals["items"][0]["approvalId"])

        resolved = await service.resolve_approval_payload(session.session_id, approval["approvalId"], "approve")
        completed = await service.get_session_payload(session.session_id)

        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(completed["status"], "completed")
        self.assertIsNone(completed["pendingApprovalSource"])

    async def test_continue_session_falls_back_to_app_server_when_desktop_is_unavailable(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [{**adapter.thread_summaries[0], "threadId": "thread-live"}]
        desktop = DesktopAutomationStub(ready=True)
        desktop.send_error = DesktopAutomationUnavailableError("offline")
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")

        payload = await service.continue_session_payload(session.session_id, "fallback send")
        updated = await store.get_session(session.session_id)

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(desktop.send_calls, [])
        self.assertEqual(adapter.continue_calls, [(session.session_id, "fallback send")])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.delivery_route, "app_server")
        self.assertEqual([item.content for item in updated.messages].count("fallback send"), 1)

    async def test_continue_session_can_require_desktop_without_fallback(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [{**adapter.thread_summaries[0], "threadId": "thread-live"}]
        desktop = DesktopAutomationStub(ready=True)
        desktop.send_error = DesktopAutomationUnavailableError("offline")
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")

        with self.assertRaises(BridgeServiceError) as ctx:
            await service.continue_session_payload(session.session_id, "strict send", require_desktop=True)

        updated = await store.get_session(session.session_id)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(adapter.continue_calls, [])
        self.assertEqual(desktop.send_calls, [])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.desktop_target_state, "blocked")
        self.assertEqual([item.content for item in updated.messages].count("strict send"), 0)

    async def test_strict_desktop_continue_starts_new_thread_when_unbound(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_active_session(session.session_id, source="test")

        payload = await service.continue_session_payload(session.session_id, "desktop only", require_desktop=True)
        updated = await store.get_session(session.session_id)

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(desktop.command_calls[0]["type"], "codex.thread.new")
        self.assertEqual(desktop.command_calls[0]["workspace"], r"E:\workspace")
        self.assertEqual(desktop.send_calls, [("desktop only", True)])
        self.assertEqual(adapter.continue_calls, [])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.delivery_route, "desktop_gui")
        self.assertIn("desktop only", [item.content for item in updated.messages])

    async def test_create_session_can_require_desktop_without_starting_app_server(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)

        created = await service.create_session_payload(
            r"E:\workspace",
            "new desktop task",
            require_desktop=True,
        )
        session = await store.get_session(created["sessionId"])

        self.assertEqual(desktop.command_calls[0]["type"], "codex.thread.new")
        self.assertEqual(desktop.command_calls[0]["workspace"], r"E:\workspace")
        self.assertEqual(desktop.send_calls, [("new desktop task", True)])
        self.assertEqual(adapter.start_calls, [])
        self.assertIsNotNone(session)
        self.assertEqual(session.delivery_route, "desktop_gui")
        self.assertEqual([item.content for item in session.messages], ["new desktop task"])

    async def test_continue_session_raises_502_when_desktop_send_errors(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        adapter.thread_summaries = [{**adapter.thread_summaries[0], "threadId": "thread-live"}]
        desktop = DesktopAutomationStub(ready=True)
        desktop.send_error = DesktopAutomationSendError("nack")
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")

        await service.align_desktop_session_payload(session.session_id)
        with self.assertRaises(BridgeServiceError) as ctx:
            await service.continue_session_payload(session.session_id, "broken send")

        updated = await store.get_session(session.session_id)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(adapter.continue_calls, [])
        self.assertIsNotNone(updated)
        self.assertEqual([item.content for item in updated.messages].count("broken send"), 0)

    async def test_desktop_alignment_failure_blocks_before_send(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        desktop.command_errors["codex.thread.focus"] = DesktopAutomationSendError("not found")
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")

        with self.assertRaises(BridgeServiceError) as ctx:
            await service.align_desktop_session_payload(session.session_id)

        updated = await store.get_session(session.session_id)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(desktop.send_calls, [])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.desktop_target_state, "not_found")

    async def test_plan_mode_continue_forces_app_server(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)
        session = await store.create_session(r"E:\workspace", "demo", "initial")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")

        payload = await service.continue_session_payload(session.session_id, "plan please", interaction_mode="plan")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(desktop.send_calls, [])
        self.assertEqual(len(adapter.continue_calls), 1)
        self.assertIn("plan please", adapter.continue_calls[0][1])
        self.assertIn("<codex-mobile-plan-mode>", adapter.continue_calls[0][1])

    async def test_plan_mode_create_forces_app_server(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)

        created = await service.create_session_payload(
            r"E:\workspace",
            "draft a plan",
            require_desktop=True,
            interaction_mode="plan",
        )

        self.assertEqual(desktop.send_calls, [])
        self.assertEqual(len(adapter.start_calls), 1)
        self.assertIn("<codex-mobile-plan-mode>", adapter.start_calls[0][1])
        self.assertEqual(created["deliveryRoute"], "app_server")

    async def test_plan_mode_resume_uses_app_server_prompt(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        desktop = DesktopAutomationStub(ready=True)
        service = self.create_service(adapter, desktop_automation=desktop)

        resumed = await service.resume_thread_payload("thread-1", "need a plan", interaction_mode="plan")

        self.assertEqual(desktop.send_calls, [])
        self.assertEqual(len(adapter.resume_calls), 1)
        self.assertEqual(adapter.resume_calls[0][0], resumed["sessionId"])
        self.assertIn("<codex-mobile-plan-mode>", adapter.resume_calls[0][2] or "")

    async def test_thread_mirror_updates_active_session_without_duplicates(self) -> None:
        store = SessionStore()
        adapter = RecordingAdapter(store)
        service = self.create_service(adapter)
        session = await store.create_session(r"E:\workspace", "demo", status="imported")
        await store.set_backend_context(session.session_id, backend_session_id="thread-live", source_thread_id="thread-live")
        await store.set_active_session(session.session_id, source="test")
        adapter.thread_detail = {
            "threadId": "thread-live",
            "title": "Live thread",
            "workspace": r"E:\workspace",
            "source": "cli",
            "status": "running",
            "preview": "syncing",
            "turns": [
                {
                    "turnId": "turn-1",
                    "status": "running",
                    "error": None,
                    "items": [
                        {"type": "userMessage", "content": [{"type": "text", "text": "hello"}]},
                        {"type": "agentMessage", "phase": "commentary", "text": "working"},
                    ],
                }
            ],
        }
        subscriber_id, queue, _ = await store.subscribe(session.session_id)

        await service._mirror_active_session_once()
        event = await asyncio.wait_for(queue.get(), timeout=0.2)
        mirrored = await store.get_session(session.session_id)
        payload = await service.get_session_payload(session.session_id)

        self.assertEqual(event["type"], "thread.mirrored")
        self.assertIsNotNone(mirrored)
        self.assertEqual(mirrored.status, "running")
        self.assertEqual([item.role for item in mirrored.messages], ["user", "assistant"])
        self.assertEqual([item.content for item in mirrored.messages], ["hello", "working"])
        self.assertIsNotNone(mirrored.last_thread_sync_at)
        self.assertIsNotNone(payload["lastThreadSyncAt"])

        service._mirror_poll_started_at[session.session_id] = 0.0
        await service._mirror_active_session_once()
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.05)
        await store.unsubscribe(session.session_id, subscriber_id)
