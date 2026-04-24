from __future__ import annotations

import asyncio
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from bridge.adapter import AppServerAdapter, DemoCodexAdapter
from bridge.auth import PairingManager
from bridge.desktop_automation import NullDesktopAutomationClient
from bridge.main import build_runtime, create_app
from bridge.session_store import SessionStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fake_app_server.py"


class DesktopAutomationStub:
    def __init__(self) -> None:
        self.commands: list[dict[str, object]] = []
        self.subscribers: dict[str, asyncio.Queue[dict[str, object]]] = {}

    def snapshot(self) -> dict[str, object]:
        return {
            "baseUrl": "http://127.0.0.1:8765",
            "available": True,
            "previewSupported": True,
            "connected": True,
            "authenticated": True,
            "windowLocked": True,
            "codexWindowLocked": True,
            "lockedWindow": {"title": "Codex", "process_name": "Codex.exe"},
            "windowTitle": "Codex",
            "processName": "Codex.exe",
            "lastError": None,
        }

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def send_text(self, text: str, *, submit: bool = True) -> None:
        return None

    async def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, object]]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        subscriber_id = f"desktop-{len(self.subscribers) + 1}"
        self.subscribers[subscriber_id] = queue
        return subscriber_id, queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        self.subscribers.pop(subscriber_id, None)

    async def send_command(self, payload: dict[str, object], *, expect_ack: bool = False, timeout: float = 10.0) -> dict[str, object] | None:
        self.commands.append(dict(payload))
        message_id = payload.get("id")
        if payload.get("type") == "preview.subscribe":
            await self._broadcast({"type": "ack", "id": message_id})
            await self._broadcast(
                {
                    "type": "preview.frame",
                    "seq": 1,
                    "format": "jpeg",
                    "width": 32,
                    "height": 24,
                    "data": "ZmFrZS1mcmFtZQ==",
                    "capturedAt": "2026-04-10T12:00:00+08:00",
                }
            )
        elif message_id is not None:
            await self._broadcast({"type": "ack", "id": message_id})
        return {"type": "ack", "id": message_id}

    async def _broadcast(self, message: dict[str, object]) -> None:
        for queue in self.subscribers.values():
            await queue.put(dict(message))


class BridgeTests(TestCase):
    def setUp(self) -> None:
        self._runtime_root = tempfile.TemporaryDirectory()
        self.addCleanup(self._runtime_root.cleanup)

    def make_runtime(self, **kwargs):
        with patch.dict(
            os.environ,
            {
                "CODEX_RUNTIME_ROOT": self._runtime_root.name,
                "CODEX_CLOUD_AGENT_IDENTITY_FILE": "",
            },
            clear=False,
        ):
            return build_runtime(**kwargs)

    def create_client(self, *, adapter) -> TestClient:
        runtime = self.make_runtime(
            workspace_roots=["E:\\workspace"],
            pairing=PairingManager(),
            store=SessionStore(),
            adapter=adapter,
            desktop_automation=NullDesktopAutomationClient(),
            enable_relay=False,
        )
        return TestClient(create_app(runtime))

    def pair(self, client: TestClient) -> str:
        pair_code = client.get("/api/admin/state").json()["pairCode"]
        pair = client.post("/api/auth/pair", json={"code": pair_code})
        self.assertEqual(pair.status_code, 200)
        return pair.json()["accessToken"]

    def test_pair_and_create_session_with_demo_backend(self) -> None:
        store = SessionStore()
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=["E:\\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=DemoCodexAdapter(store),
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            created = client.post(
                "/api/sessions",
                headers={"Authorization": f"Bearer {token}"},
                json={"workspace": "E:\\workspace", "prompt": "帮我分析当前项目结构"},
            )
            self.assertEqual(created.status_code, 200)
            session_id = created.json()["sessionId"]
            time.sleep(0.25)
            details = client.get(f"/api/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(details.status_code, 200)
            self.assertIn(details.json()["status"], {"running", "completed"})

    def test_runtime_root_uses_identity_parent_when_configured(self) -> None:
        store = SessionStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            identity_file = Path(temp_dir) / "cloud-agent.json"
            identity_file.write_text("{}", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "CODEX_CLOUD_AGENT_IDENTITY_FILE": str(identity_file),
                    "CODEX_RUNTIME_ROOT": "",
                },
                clear=False,
            ):
                runtime = build_runtime(
                    workspace_roots=[r"E:\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=DemoCodexAdapter(store),
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                    enable_cloud_agent=False,
                )
            self.assertEqual(
                Path(runtime.service._default_workspace_root).resolve(),
                Path(temp_dir).resolve(),
            )

    def test_admin_state_includes_backend_status(self) -> None:
        store = SessionStore()
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=["E:\\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=DemoCodexAdapter(store),
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            response = client.get("/api/admin/state")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["backend"], "demo")
        self.assertTrue(payload["backendAvailable"])
        self.assertEqual(payload["relay"]["status"], "disabled")

    def test_local_admin_can_inject_test_approval(self) -> None:
        store = SessionStore()
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=[r"E:\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=DemoCodexAdapter(store),
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            created = client.post(
                "/api/sessions",
                headers={"Authorization": f"Bearer {token}"},
                json={"workspace": r"E:\workspace", "prompt": "approval smoke"},
            )
            self.assertEqual(created.status_code, 200)
            session_id = created.json()["sessionId"]

            injected = client.post(
                f"/api/admin/sessions/{session_id}/test-approval",
                json={"title": "测试审批"},
            )
            self.assertEqual(injected.status_code, 200)

            approvals = client.get(f"/api/sessions/{session_id}/approvals", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(approvals.status_code, 200)
            items = approvals.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "测试审批")

    def test_admin_state_and_session_payload_include_desktop_sync_metadata(self) -> None:
        store = SessionStore()
        adapter = AppServerAdapter(store, command=[sys.executable, str(FIXTURE)])
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=["E:\\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=adapter,
                    desktop_automation=DesktopAutomationStub(),
                    enable_relay=False,
                )
            )
        ) as client:
            admin = client.get("/api/admin/state")
            self.assertEqual(admin.status_code, 200)
            self.assertTrue(admin.json()["desktopAutomation"]["available"])

            token = self.pair(client)
            created = client.post(
                "/api/sessions",
                headers={"Authorization": f"Bearer {token}"},
                json={"workspace": "E:\\workspace", "prompt": "sync metadata"},
            )
            time.sleep(0.1)

        self.assertEqual(created.status_code, 200)
        payload = created.json()
        self.assertEqual(payload["deliveryRoute"], "app_server")
        self.assertTrue(payload["desktopAutomationReady"])
        self.assertIsNone(payload["lastThreadSyncAt"])
        self.assertIsNone(payload["pendingApprovalSource"])
        self.assertFalse(payload["desktopApprovalControllable"])

    def test_desktop_websocket_proxies_preview_and_pointer_messages(self) -> None:
        store = SessionStore()
        desktop = DesktopAutomationStub()
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=[r"E:\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=DemoCodexAdapter(store),
                    desktop_automation=desktop,
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            with client.websocket_connect(f"/api/desktop/ws?access_token={token}") as websocket:
                ready = websocket.receive_json()
                self.assertEqual(ready["type"], "ready")
                self.assertTrue(ready["previewEnabled"])

                websocket.send_json({"type": "preview.subscribe", "id": "preview-1"})
                ack = websocket.receive_json()
                frame = websocket.receive_json()

                self.assertEqual(ack["type"], "ack")
                self.assertEqual(ack["id"], "preview-1")
                self.assertEqual(frame["type"], "preview.frame")

                websocket.send_json({"type": "pointer.down", "id": "pointer-1", "xRatio": 0.5, "yRatio": 0.5})
                pointer_ack = websocket.receive_json()

        self.assertEqual(pointer_ack["type"], "ack")
        self.assertEqual(pointer_ack["id"], "pointer-1")
        self.assertEqual(
            [item["type"] for item in desktop.commands],
            ["preview.subscribe", "pointer.down"],
        )

    def test_admin_state_includes_windowsapps_fix_guidance(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only command resolution test")
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"APPDATA": temp, "CODEX_APP_SERVER_COMMAND": ""}):
                with patch("bridge.adapter.shutil.which", return_value=r"C:\Program Files\WindowsApps\OpenAI.Codex_x\app\resources\codex.exe"):
                    store = SessionStore()
                    adapter = AppServerAdapter(store)
                    app = create_app(
                        self.make_runtime(
                            workspace_roots=["E:\\workspace"],
                            pairing=PairingManager(),
                            store=store,
                            adapter=adapter,
                            desktop_automation=NullDesktopAutomationClient(),
                            enable_relay=False,
                        )
                    )
                    with TestClient(app) as client:
                        payload = client.get("/api/admin/state").json()
        self.assertFalse(payload["backendAvailable"])
        self.assertIn("WindowsApps", payload["backendLastError"])
        self.assertIn("setup_codex_cli.ps1", payload["backendSuggestedFix"])

    def test_create_session_returns_503_when_app_server_is_unavailable(self) -> None:
        store = SessionStore()
        adapter = AppServerAdapter(store, command=["Z:\\missing\\codex.exe"])
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=["E:\\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=adapter,
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            response = client.post(
                "/api/sessions",
                headers={"Authorization": f"Bearer {token}"},
                json={"workspace": "E:\\workspace", "prompt": "帮我创建一个真实会话"},
            )
        self.assertEqual(response.status_code, 503)

    def test_threads_resume_and_approval_resolution(self) -> None:
        store = SessionStore()
        adapter = AppServerAdapter(store, command=[sys.executable, str(FIXTURE)])
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=["E:\\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=adapter,
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            headers = {"Authorization": f"Bearer {token}"}

            threads = client.get("/api/threads", headers=headers)
            self.assertEqual(threads.status_code, 200)
            ids = {item["threadId"] for item in threads.json()["items"]}
            self.assertIn("thread-existing", ids)
            self.assertNotIn("thread-other", ids)

            detail = client.get("/api/threads/thread-existing", headers=headers)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["threadId"], "thread-existing")

            resumed = client.post("/api/threads/thread-existing/resume", headers=headers, json={})
            self.assertEqual(resumed.status_code, 200)
            session_id = resumed.json()["sessionId"]
            self.assertEqual(resumed.json()["status"], "imported")

            continued = client.post(
                f"/api/sessions/{session_id}/messages",
                headers=headers,
                json={"content": "needs approval"},
            )
            self.assertEqual(continued.status_code, 200)
            time.sleep(0.2)

            approvals = client.get(f"/api/sessions/{session_id}/approvals", headers=headers)
            self.assertEqual(approvals.status_code, 200)
            items = approvals.json()["items"]
            self.assertEqual(len(items), 1)

            resolved = client.post(
                f"/api/sessions/{session_id}/approvals/{items[0]['approvalId']}/resolve",
                headers=headers,
                json={"action": "approve"},
            )
            self.assertEqual(resolved.status_code, 200)

            time.sleep(0.2)
            session = client.get(f"/api/sessions/{session_id}", headers=headers)
            self.assertEqual(session.status_code, 200)
            self.assertEqual(session.json()["status"], "completed")

    def test_create_session_with_fake_app_server_backend(self) -> None:
        store = SessionStore()
        adapter = AppServerAdapter(store, command=[sys.executable, str(FIXTURE)])
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=["E:\\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=adapter,
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            headers = {"Authorization": f"Bearer {token}"}

            response = client.post(
                "/api/sessions",
                headers=headers,
                json={"workspace": "E:\\workspace", "prompt": "帮我分析当前项目结构"},
            )
            self.assertEqual(response.status_code, 200)
            session_id = response.json()["sessionId"]
            time.sleep(0.25)

            details = client.get(f"/api/sessions/{session_id}", headers=headers)
            self.assertEqual(details.status_code, 200)
            self.assertEqual(details.json()["status"], "completed")

    def test_discovery_mode_lists_cross_workspace_threads_and_auto_adopts_running_thread(self) -> None:
        store = SessionStore()
        adapter = AppServerAdapter(store, command=[sys.executable, str(FIXTURE)])
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=[],
                    pairing=PairingManager(),
                    store=store,
                    adapter=adapter,
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            headers = {"Authorization": f"Bearer {token}"}

            workspaces = client.get("/api/workspaces", headers=headers)
            self.assertEqual(workspaces.status_code, 200)
            self.assertEqual(
                set(workspaces.json()["items"]),
                {os.path.normcase(r"E:\workspace"), os.path.normcase(r"D:\other")},
            )

            threads = client.get("/api/threads", headers=headers)
            self.assertEqual(threads.status_code, 200)
            ids = {item["threadId"] for item in threads.json()["items"]}
            self.assertIn("thread-existing", ids)
            self.assertIn("thread-other", ids)
            self.assertIn("thread-running", ids)

            sessions = client.get("/api/sessions", headers=headers)
            self.assertEqual(sessions.status_code, 200)
            items = sessions.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["sourceThreadId"], "thread-running")
            self.assertEqual(items[0]["sessionKind"], "auto_adopted")
            self.assertEqual(items[0]["backendSessionId"], "thread-running")
            self.assertEqual(items[0]["status"], "running")

    def test_auto_adopted_session_followup_stays_on_same_thread_and_supports_approval(self) -> None:
        store = SessionStore()
        adapter = AppServerAdapter(store, command=[sys.executable, str(FIXTURE)])
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=[],
                    pairing=PairingManager(),
                    store=store,
                    adapter=adapter,
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            headers = {"Authorization": f"Bearer {token}"}

            sessions = client.get("/api/sessions", headers=headers)
            self.assertEqual(sessions.status_code, 200)
            session = sessions.json()["items"][0]
            self.assertEqual(session["sourceThreadId"], "thread-running")

            continued = client.post(
                f"/api/sessions/{session['sessionId']}/messages",
                headers=headers,
                json={"content": "needs approval"},
            )
            self.assertEqual(continued.status_code, 200)
            time.sleep(0.2)

            approvals = client.get(f"/api/sessions/{session['sessionId']}/approvals", headers=headers)
            self.assertEqual(approvals.status_code, 200)
            items = approvals.json()["items"]
            self.assertEqual(len(items), 1)

            resolved = client.post(
                f"/api/sessions/{session['sessionId']}/approvals/{items[0]['approvalId']}/resolve",
                headers=headers,
                json={"action": "approve"},
            )
            self.assertEqual(resolved.status_code, 200)
            time.sleep(0.2)

            updated = client.get(f"/api/sessions/{session['sessionId']}", headers=headers)
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["backendSessionId"], "thread-running")
            self.assertEqual(updated.json()["sourceThreadId"], "thread-running")
            self.assertEqual(updated.json()["status"], "completed")

            thread = client.get("/api/threads/thread-running", headers=headers)
            self.assertEqual(thread.status_code, 200)
            self.assertGreaterEqual(len(thread.json()["turns"]), 1)

    def test_active_session_endpoints_update_is_active_flags(self) -> None:
        store = SessionStore()
        with TestClient(
            create_app(
                self.make_runtime(
                    workspace_roots=[r"E:\workspace"],
                    pairing=PairingManager(),
                    store=store,
                    adapter=DemoCodexAdapter(store),
                    desktop_automation=NullDesktopAutomationClient(),
                    enable_relay=False,
                )
            )
        ) as client:
            token = self.pair(client)
            headers = {"Authorization": f"Bearer {token}"}

            first = client.post(
                "/api/sessions",
                headers=headers,
                json={"workspace": r"E:\workspace", "prompt": "first prompt"},
            )
            self.assertEqual(first.status_code, 200)
            second = client.post(
                "/api/sessions",
                headers=headers,
                json={"workspace": r"E:\workspace", "prompt": "second prompt"},
            )
            self.assertEqual(second.status_code, 200)

            listed = client.get("/api/sessions", headers=headers)
            self.assertEqual(listed.status_code, 200)
            items = {item["sessionId"]: item for item in listed.json()["items"]}
            self.assertFalse(items[first.json()["sessionId"]]["isActive"])
            self.assertTrue(items[second.json()["sessionId"]]["isActive"])

            switched = client.post(
                "/api/ui/active-session",
                headers=headers,
                json={"sessionId": first.json()["sessionId"], "source": "test"},
            )
            self.assertEqual(switched.status_code, 200)
            self.assertEqual(switched.json()["activeSessionId"], first.json()["sessionId"])

            active = client.get("/api/ui/active-session", headers=headers)
            self.assertEqual(active.status_code, 200)
            self.assertEqual(active.json()["activeSessionId"], first.json()["sessionId"])

            relisted = client.get("/api/sessions", headers=headers)
            self.assertEqual(relisted.status_code, 200)
            relisted_items = {item["sessionId"]: item for item in relisted.json()["items"]}
            self.assertTrue(relisted_items[first.json()["sessionId"]]["isActive"])
            self.assertFalse(relisted_items[second.json()["sessionId"]]["isActive"])
