from __future__ import annotations

import asyncio
import io
import os
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from cloud_gateway.main import (
    AgentConnection,
    CloudState,
    DeviceRecord,
    create_app,
    ensure_session_subscription,
    ensure_ui_subscription,
    handle_agent_message,
)


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)


class CloudGatewayTests(TestCase):
    def setUp(self) -> None:
        self._tempdirs: list[tempfile.TemporaryDirectory[str]] = []

    def tearDown(self) -> None:
        for tempdir in self._tempdirs:
            tempdir.cleanup()

    def make_db_path(self) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self._tempdirs.append(tempdir)
        return Path(tempdir.name) / "cloud.sqlite3"

    def make_download_root(self) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self._tempdirs.append(tempdir)
        return Path(tempdir.name)

    def make_client(self) -> TestClient:
        return TestClient(create_app(persistence_path=self.make_db_path(), download_root=self.make_download_root()))

    def make_client_with_db(self, db_path: Path) -> TestClient:
        return TestClient(create_app(persistence_path=db_path, download_root=self.make_download_root()))

    def issue_user_token(self, client: TestClient, email: str = "user@example.com") -> str:
        issued = client.post("/api/auth/magic-link", json={"email": email})
        self.assertEqual(issued.status_code, 200)
        link = issued.json()["magicLink"]
        parsed = urlsplit(link)
        verified = client.get(f"{parsed.path}?{parsed.query}", follow_redirects=False)
        self.assertEqual(verified.status_code, 302)
        redirect = urlsplit(verified.headers["location"])
        return parse_qs(redirect.query)["access_token"][0]

    def auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def register_device(self, client: TestClient) -> dict[str, Any]:
        response = client.post(
            "/api/agent/register",
            json={
                "machineName": "DESKTOP-TEST",
                "platform": "Windows-11",
                "alias": "My Codex PC",
                "clientNonce": "nonce-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_magic_link_claim_and_device_listing(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)

            listed_before = client.get("/api/devices", headers=self.auth_headers(token))
            self.assertEqual(listed_before.status_code, 200)
            self.assertEqual(listed_before.json()["items"], [])

            claimed = client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )
            self.assertEqual(claimed.status_code, 200)

            listed_after = client.get("/api/devices", headers=self.auth_headers(token))
            self.assertEqual(listed_after.status_code, 200)
            items = listed_after.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["deviceId"], registered["deviceId"])
            self.assertEqual(items[0]["alias"], "My Codex PC")
            self.assertEqual(items[0]["ownerEmail"], "user@example.com")
            self.assertEqual(items[0]["deviceState"], "offline")
            self.assertEqual(items[0]["recommendedAction"], "open_client")

    def test_pair_code_connect_returns_device_access_token_and_bootstrap(self) -> None:
        with self.make_client() as client:
            registered = self.register_device(client)

            pair_response = client.post(
                "/api/pairing/code",
                json={
                    "deviceId": registered["deviceId"],
                    "agentToken": registered["agentToken"],
                    "refresh": False,
                },
            )
            self.assertEqual(pair_response.status_code, 200)
            pair_code = pair_response.json()["pairCode"]
            self.assertEqual(len(pair_code), 6)

            connected = client.post(
                "/api/pairing/connect",
                json={
                    "pairCode": pair_code,
                    "clientName": "Pixel 10",
                    "platform": "android",
                },
            )
            self.assertEqual(connected.status_code, 200)
            payload = connected.json()
            self.assertEqual(payload["device"]["deviceId"], registered["deviceId"])
            self.assertTrue(payload["device"]["paired"])

            device_token = payload["accessToken"]
            bootstrap = client.get(
                f"/api/bootstrap?deviceId={registered['deviceId']}",
                headers=self.auth_headers(device_token),
            )
            self.assertEqual(bootstrap.status_code, 200)
            bootstrap_payload = bootstrap.json()
            self.assertEqual(bootstrap_payload["authMode"], "device")
            self.assertEqual(bootstrap_payload["device"]["deviceId"], registered["deviceId"])

            devices = client.get("/api/devices", headers=self.auth_headers(device_token))
            self.assertEqual(devices.status_code, 200)
            self.assertEqual(len(devices.json()["items"]), 1)
            self.assertEqual(devices.json()["items"][0]["deviceId"], registered["deviceId"])

    def test_pairing_disconnect_invalidates_device_access_token(self) -> None:
        with self.make_client() as client:
            registered = self.register_device(client)
            pair_code = client.post(
                "/api/pairing/code",
                json={
                    "deviceId": registered["deviceId"],
                    "agentToken": registered["agentToken"],
                    "refresh": False,
                },
            ).json()["pairCode"]
            connected = client.post(
                "/api/pairing/connect",
                json={"pairCode": pair_code, "clientName": "Pixel 10", "platform": "android"},
            )
            self.assertEqual(connected.status_code, 200)
            device_token = connected.json()["accessToken"]

            disconnected = client.post(
                "/api/pairing/disconnect",
                headers=self.auth_headers(device_token),
                json={"deviceId": registered["deviceId"]},
            )
            self.assertEqual(disconnected.status_code, 200)
            self.assertFalse(disconnected.json()["device"]["paired"])

            bootstrap = client.get(
                f"/api/bootstrap?deviceId={registered['deviceId']}",
                headers=self.auth_headers(device_token),
            )
            self.assertEqual(bootstrap.status_code, 401)

    def test_agent_status_reflects_server_online_state(self) -> None:
        with self.make_client() as client:
            registered = self.register_device(client)
            state = client.app.state.cloud
            device = state.devices[registered["deviceId"]]
            device.online = True
            device.last_status = {
                "desktopServiceReady": True,
                "desktopReady": True,
                "codexForeground": True,
                "codexWindowControllable": True,
                "backendAvailable": True,
            }

            response = client.post(
                "/api/agent/status",
                json={
                    "deviceId": registered["deviceId"],
                    "agentToken": registered["agentToken"],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["online"])
        self.assertTrue(payload["device"]["cloudConnected"])
        self.assertEqual(payload["device"]["deviceState"], "ready")

    def test_user_can_unbind_owned_device(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            claimed = client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )
            self.assertEqual(claimed.status_code, 200)

            unbound = client.post(
                f"/api/devices/{registered['deviceId']}/unbind",
                headers=self.auth_headers(token),
            )
            self.assertEqual(unbound.status_code, 200)
            payload = unbound.json()["device"]
            self.assertFalse(payload["claimed"])
            self.assertIsNone(payload["ownerEmail"])

            listed = client.get("/api/devices", headers=self.auth_headers(token))
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["items"], [])

    def test_agent_can_unbind_and_receive_fresh_claim_ticket(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            claimed = client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )
            self.assertEqual(claimed.status_code, 200)

            unbound = client.post(
                "/api/agent/unbind",
                json={
                    "deviceId": registered["deviceId"],
                    "agentToken": registered["agentToken"],
                },
            )
            self.assertEqual(unbound.status_code, 200)
            payload = unbound.json()
            self.assertFalse(payload["claimed"])
            self.assertTrue(str(payload["claimUrl"]).endswith(str(payload["claimToken"])))

    def test_http_accepts_query_access_token_for_eventsource_clients(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            listed = client.get(f"/api/devices?access_token={token}")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"], [])

    def test_auth_config_and_enrollment_bind_device_to_user(self) -> None:
        with self.make_client() as client:
            config = client.get("/api/auth/config")
            self.assertEqual(config.status_code, 200)
            self.assertEqual(config.json()["authMode"], "dev")

            token = self.issue_user_token(client)
            enrollment = client.post("/api/enrollments", headers=self.auth_headers(token))
            self.assertEqual(enrollment.status_code, 200)
            enrollment_payload = enrollment.json()
            self.assertIn("installCommand", enrollment_payload)
            self.assertIn("clientDownloadUrl", enrollment_payload)

            script = client.get(enrollment_payload["downloadUrl"].replace("http://testserver", ""))
            self.assertEqual(script.status_code, 200)
            self.assertIn("CODEX_CLOUD_ENROLLMENT_TOKEN", script.text)
            bundle = client.get(enrollment_payload["clientDownloadUrl"].replace("http://testserver", ""))
            self.assertEqual(bundle.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
                self.assertIn("install.ps1", archive.namelist())
                self.assertIn("client/codesk_tray.py", archive.namelist())

            enrolled = client.post(
                "/api/agent/enroll",
                json={
                    "enrollmentToken": enrollment_payload["enrollmentToken"],
                    "machineName": "DESKTOP-NEW",
                    "platform": "Windows-11",
                    "alias": "New PC",
                    "clientNonce": "nonce-2",
                },
            )
            self.assertEqual(enrolled.status_code, 200)
            listed = client.get("/api/devices", headers=self.auth_headers(token))
            self.assertEqual(listed.status_code, 200)
            items = listed.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["deviceId"], enrolled.json()["deviceId"])
            self.assertEqual(items[0]["ownerEmail"], "user@example.com")

            reused = client.post(
                "/api/agent/enroll",
                json={
                    "enrollmentToken": enrollment_payload["enrollmentToken"],
                    "machineName": "DESKTOP-OTHER",
                    "platform": "Windows-11",
                },
            )
            self.assertEqual(reused.status_code, 409)

    def test_generic_windows_client_bundle_download_works_without_enrollment(self) -> None:
        with self.make_client() as client:
            bundle = client.get("/api/downloads/windows-client/latest")
            self.assertEqual(bundle.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
                self.assertIn("install.ps1", archive.namelist())
                tray_script = archive.read("client/codesk_tray.py").decode("utf-8")
                self.assertIn("Enter this code on your phone", tray_script)
                self.assertNotIn("{config.get(", tray_script)

    def test_windows_client_download_serves_prebuilt_installer_when_available(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self._tempdirs.append(tempdir)
        download_root = Path(tempdir.name)
        installer_path = download_root / "windows" / "Codesk-Setup.exe"
        installer_path.parent.mkdir(parents=True, exist_ok=True)
        installer_path.write_bytes(b"MZ-fake-installer")

        with TestClient(create_app(persistence_path=self.make_db_path(), download_root=download_root)) as client:
            response = client.get("/api/downloads/windows-client/latest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/vnd.microsoft.portable-executable")
        self.assertEqual(response.content, b"MZ-fake-installer")

    def test_android_download_serves_prebuilt_apk_when_available(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self._tempdirs.append(tempdir)
        download_root = Path(tempdir.name)
        apk_path = download_root / "android" / "Codesk-Android.apk"
        apk_path.parent.mkdir(parents=True, exist_ok=True)
        apk_path.write_bytes(b"PK-fake-apk")

        with TestClient(create_app(persistence_path=self.make_db_path(), download_root=download_root)) as client:
            response = client.get("/api/downloads/android/latest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/vnd.android.package-archive")
        self.assertEqual(response.content, b"PK-fake-apk")

    def test_claim_token_redirect_and_claim_flow(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)

            redirected = client.get(f"/claim?token={registered['claimToken']}", follow_redirects=False)
            self.assertEqual(redirected.status_code, 302)
            self.assertIn(f"claim={registered['claimToken']}", redirected.headers["location"])

            claimed = client.post(
                "/api/devices/claim-token",
                headers=self.auth_headers(token),
                json={"claimToken": registered["claimToken"]},
            )
            self.assertEqual(claimed.status_code, 200)
            self.assertTrue(claimed.json()["device"]["claimed"])

    def test_agent_claim_link_refresh_returns_claim_url(self) -> None:
        with self.make_client() as client:
            registered = self.register_device(client)
            response = client.post(
                "/api/agent/claim-link",
                json={"deviceId": registered["deviceId"], "agentToken": registered["agentToken"]},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("claimToken", payload)
        self.assertIn("/claim?token=", payload["claimUrl"])

    def test_agent_claim_link_refresh_rewrites_stale_public_base(self) -> None:
        with patch.dict(os.environ, {"CODEX_CLOUD_PUBLIC_URL": "https://codesk.lensseekapp.com"}, clear=False):
            with self.make_client() as client:
                registered = self.register_device(client)
                state = client.app.state.cloud
                device = state.devices[registered["deviceId"]]
                device.claim_url = f"http://stale-host.example/claim?token={device.claim_token}"

                response = client.post(
                    "/api/agent/claim-link",
                    json={"deviceId": registered["deviceId"], "agentToken": registered["agentToken"]},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["claimUrl"].startswith("https://codesk.lensseekapp.com/claim?token="))

    def test_bootstrap_returns_device_snapshot_without_blocking_on_session_detail(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )
            state = client.app.state.cloud
            device = state.devices[registered["deviceId"]]
            device.online = True
            device.last_status = {
                "desktopReady": True,
                "codexForeground": True,
                "codexWindowControllable": True,
                "backendAvailable": True,
            }

            async def fake_dispatch(_state, device_id, action, payload, timeout=20.0):
                mapping = {
                    "list_workspaces": {"items": [r"E:\workspace"]},
                    "get_active_session": {"activeSessionId": "session-1", "source": "mobile_open"},
                    "list_sessions": {"items": [{"sessionId": "session-1", "title": "hello", "status": "running"}]},
                    "list_threads": {"items": [{"threadId": "thread-1", "title": "hello", "status": "running"}]},
                }
                return mapping[action]

            with patch("cloud_gateway.main.dispatch_rpc", side_effect=fake_dispatch):
                response = client.get(
                    f"/api/bootstrap?deviceId={registered['deviceId']}",
                    headers=self.auth_headers(token),
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selectedDeviceId"], registered["deviceId"])
        self.assertEqual(payload["activeSession"]["activeSessionId"], "session-1")
        self.assertIsNone(payload["currentSession"])
        self.assertEqual(payload["approvals"]["items"], [])
        self.assertTrue(payload["device"]["cloudConnected"])
        self.assertTrue(payload["device"]["desktopControllable"])

    def test_device_binding_survives_gateway_restart(self) -> None:
        db_path = self.make_db_path()
        with self.make_client_with_db(db_path) as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            claimed = client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )
            self.assertEqual(claimed.status_code, 200)

        with self.make_client_with_db(db_path) as client:
            listed = client.get("/api/devices", headers=self.auth_headers(token))
            self.assertEqual(listed.status_code, 200)
            items = listed.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["deviceId"], registered["deviceId"])

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                welcome = agent_socket.receive_json()

        self.assertEqual(welcome["type"], "agent.welcome")
        self.assertTrue(welcome["claimed"])
        self.assertEqual(welcome["ownerEmail"], "user@example.com")

    def test_unified_event_watchers_receive_device_ui_and_session_events(self) -> None:
        async def run() -> list[dict[str, Any]]:
            state = CloudState()
            state.devices["device-1"] = DeviceRecord(
                device_id="device-1",
                agent_token="agent-token",
                claim_code="123456",
                claim_token="claim-token-1",
                claim_url="http://example.test/?claim=123456",
                claim_expires_at="2026-04-20T00:00:00+08:00",
                alias="Codex PC",
                machine_name="DESKTOP",
                platform="Windows",
                created_at="2026-04-13T00:00:00+08:00",
            )
            fake_socket = FakeWebSocket()
            connection = AgentConnection(websocket=fake_socket)  # type: ignore[arg-type]
            state.agent_connections["device-1"] = connection
            watcher: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            connection.event_watchers.add(watcher)

            await handle_agent_message(
                state,
                "device-1",
                {
                    "type": "agent.status",
                    "payload": {
                        "desktopReady": True,
                        "codexForeground": True,
                        "codexWindowControllable": True,
                        "backendAvailable": True,
                    },
                },
            )
            await handle_agent_message(
                state,
                "device-1",
                {"type": "ui.event", "event": {"type": "sessions.changed", "reason": "test"}},
            )
            await handle_agent_message(
                state,
                "device-1",
                {"type": "session.event", "sessionId": "session-1", "event": {"type": "approval.required"}},
            )
            return [watcher.get_nowait(), watcher.get_nowait(), watcher.get_nowait()]

        events = asyncio.run(run())
        self.assertEqual(events[0]["type"], "device.status")
        self.assertEqual(events[1]["type"], "ui.event")
        self.assertEqual(events[2]["type"], "session.event")

    def test_session_rpc_proxy_includes_device_control_state(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                welcome = agent_socket.receive_json()
                self.assertEqual(welcome["type"], "agent.welcome")
                agent_socket.send_json(
                    {
                        "type": "agent.status",
                        "payload": {
                            "desktopReady": True,
                            "codexForeground": True,
                            "codexWindowControllable": True,
                            "fullscreenSuggested": True,
                            "backendAvailable": True,
                        },
                    }
                )

                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.get(
                        f"/api/sessions?deviceId={registered['deviceId']}",
                        headers=self.auth_headers(token),
                    )

                worker = threading.Thread(target=call_api)
                worker.start()

                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "list_sessions")
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {
                            "items": [
                                {
                                    "sessionId": "session-1",
                                    "title": "Cloud Session",
                                    "status": "running",
                                }
                            ]
                        },
                    }
                )
                worker.join(timeout=5.0)

        response = result["response"]
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["deviceId"], registered["deviceId"])
        self.assertTrue(item["deviceOnline"])
        self.assertTrue(item["desktopReady"])
        self.assertTrue(item["codexForeground"])
        self.assertTrue(item["codexControllable"])
        self.assertTrue(item["fullscreenSuggested"])

    def test_continue_session_requests_strict_desktop_delivery(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.post(
                        "/api/sessions/session-1/messages",
                        headers=self.auth_headers(token),
                        json={"deviceId": registered["deviceId"], "content": "hello from cloud"},
                    )

                worker = threading.Thread(target=call_api)
                worker.start()
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "get_session")
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"sessionId": "session-1", "deliveryRoute": "desktop_gui"},
                    }
                )
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "continue_session")
                self.assertTrue(request["payload"]["requireDesktop"])
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"ok": True},
                    }
                )
                worker.join(timeout=5.0)

        self.assertEqual(result["response"].status_code, 200)

    def test_continue_session_app_server_session_skips_strict_desktop_delivery(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.post(
                        "/api/sessions/session-1/messages",
                        headers=self.auth_headers(token),
                        json={"deviceId": registered["deviceId"], "content": "hello from cloud"},
                    )

                worker = threading.Thread(target=call_api)
                worker.start()
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "get_session")
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"sessionId": "session-1", "deliveryRoute": "app_server"},
                    }
                )
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "continue_session")
                self.assertFalse(request["payload"]["requireDesktop"])
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"ok": True},
                    }
                )
                worker.join(timeout=5.0)

        self.assertEqual(result["response"].status_code, 200)

    def test_continue_session_plan_mode_skips_strict_desktop_delivery(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.post(
                        "/api/sessions/session-1/messages",
                        headers=self.auth_headers(token),
                        json={
                            "deviceId": registered["deviceId"],
                            "content": "hello from cloud",
                            "interactionMode": "plan",
                        },
                    )

                worker = threading.Thread(target=call_api)
                worker.start()
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "continue_session")
                self.assertFalse(request["payload"]["requireDesktop"])
                self.assertEqual(request["payload"]["interactionMode"], "plan")
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"ok": True},
                    }
                )
                worker.join(timeout=5.0)

        self.assertEqual(result["response"].status_code, 200)

    def test_align_desktop_session_rpc_proxy(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.post(
                        f"/api/sessions/session-1/desktop-align?deviceId={registered['deviceId']}",
                        headers=self.auth_headers(token),
                    )

                worker = threading.Thread(target=call_api)
                worker.start()
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "align_desktop_session")
                self.assertEqual(request["payload"]["sessionId"], "session-1")
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"sessionId": "session-1", "desktopTargetState": "aligned"},
                    }
                )
                worker.join(timeout=5.0)

        self.assertEqual(result["response"].status_code, 200)
        self.assertEqual(result["response"].json()["desktopTargetState"], "aligned")

    def test_create_session_requests_strict_desktop_delivery(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.post(
                        "/api/sessions",
                        headers=self.auth_headers(token),
                        json={
                            "deviceId": registered["deviceId"],
                            "workspace": r"E:\workspace",
                            "prompt": "hello from cloud",
                            "title": "hello",
                        },
                    )

                worker = threading.Thread(target=call_api)
                worker.start()
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "create_session")
                self.assertTrue(request["payload"]["requireDesktop"])
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"sessionId": "session-1", "title": "hello", "status": "running"},
                    }
                )
                worker.join(timeout=5.0)

        self.assertEqual(result["response"].status_code, 200)

    def test_create_session_plan_mode_skips_strict_desktop_delivery(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                result: dict[str, Any] = {}

                def call_api() -> None:
                    result["response"] = client.post(
                        "/api/sessions",
                        headers=self.auth_headers(token),
                        json={
                            "deviceId": registered["deviceId"],
                            "workspace": r"E:\workspace",
                            "prompt": "hello from cloud",
                            "title": "hello",
                            "interactionMode": "plan",
                        },
                    )

                worker = threading.Thread(target=call_api)
                worker.start()
                request = agent_socket.receive_json()
                self.assertEqual(request["type"], "rpc.request")
                self.assertEqual(request["action"], "create_session")
                self.assertFalse(request["payload"]["requireDesktop"])
                self.assertEqual(request["payload"]["interactionMode"], "plan")
                agent_socket.send_json(
                    {
                        "type": "rpc.response",
                        "id": request["id"],
                        "ok": True,
                        "result": {"sessionId": "session-1", "title": "hello", "status": "running"},
                    }
                )
                worker.join(timeout=5.0)

        self.assertEqual(result["response"].status_code, 200)

    def test_ui_event_subscription_forwards_agent_events(self) -> None:
        async def run() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            state = CloudState()
            state.devices["device-1"] = DeviceRecord(
                device_id="device-1",
                agent_token="agent-token",
                claim_code="123456",
                claim_token="claim-token-1",
                claim_url="http://example.test/?claim=123456",
                claim_expires_at="2026-04-20T00:00:00+08:00",
                alias="Codex PC",
                machine_name="DESKTOP",
                platform="Windows",
                created_at="2026-04-13T00:00:00+08:00",
            )
            fake_socket = FakeWebSocket()
            connection = AgentConnection(websocket=fake_socket)  # type: ignore[arg-type]
            state.agent_connections["device-1"] = connection
            watcher: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            connection.ui_watchers.add(watcher)

            await ensure_ui_subscription(connection)
            await handle_agent_message(
                state,
                "device-1",
                {"type": "ui.event", "event": {"type": "sessions.changed", "reason": "test"}},
            )
            return fake_socket.sent, watcher.get_nowait()

        sent, event = asyncio.run(run())
        self.assertEqual(sent[0]["type"], "event.subscribe_ui")
        self.assertEqual(event["type"], "sessions.changed")

    def test_session_event_subscription_forwards_agent_events(self) -> None:
        async def run() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            state = CloudState()
            state.devices["device-1"] = DeviceRecord(
                device_id="device-1",
                agent_token="agent-token",
                claim_code="123456",
                claim_token="claim-token-1",
                claim_url="http://example.test/?claim=123456",
                claim_expires_at="2026-04-20T00:00:00+08:00",
                alias="Codex PC",
                machine_name="DESKTOP",
                platform="Windows",
                created_at="2026-04-13T00:00:00+08:00",
            )
            fake_socket = FakeWebSocket()
            connection = AgentConnection(websocket=fake_socket)  # type: ignore[arg-type]
            state.agent_connections["device-1"] = connection
            watcher: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            connection.session_watchers.setdefault("session-1", set()).add(watcher)

            await ensure_session_subscription(connection, "session-1")
            await handle_agent_message(
                state,
                "device-1",
                {
                    "type": "session.event",
                    "sessionId": "session-1",
                    "event": {"type": "message.completed", "role": "assistant", "content": "hello"},
                },
            )
            return fake_socket.sent, watcher.get_nowait()

        sent, event = asyncio.run(run())
        self.assertEqual(sent[0]["type"], "event.subscribe_session")
        self.assertEqual(sent[0]["sessionId"], "session-1")
        self.assertEqual(event["type"], "message.completed")
        self.assertEqual(event["content"], "hello")

    def test_desktop_websocket_proxies_commands_and_events(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                agent_socket.send_json(
                    {
                        "type": "agent.status",
                        "payload": {
                            "desktopReady": True,
                            "codexForeground": True,
                            "codexWindowControllable": True,
                            "fullscreenSuggested": True,
                        },
                    }
                )

                with client.websocket_connect(
                    f"/ws/agent-desktop/{registered['deviceId']}?agent_token={registered['agentToken']}"
                ) as desktop_agent_socket:
                    desktop_agent_socket.receive_json()
                    with client.websocket_connect(
                        f"/api/desktop/ws?deviceId={registered['deviceId']}",
                        headers=self.auth_headers(token),
                    ) as desktop_socket:
                        ready = desktop_socket.receive_json()
                        self.assertEqual(ready["type"], "ready")
                        self.assertEqual(ready["deviceId"], registered["deviceId"])

                        desktop_socket.send_json({"type": "preview.subscribe", "id": "preview-1"})
                        command = desktop_agent_socket.receive_json()
                        self.assertEqual(command["type"], "desktop.command")
                        self.assertEqual(command["payload"]["type"], "preview.subscribe")
                        desktop_agent_socket.send_json({"type": "desktop.event", "payload": {"type": "ack", "id": "preview-1"}})
                        desktop_agent_socket.send_json(
                            {
                                "type": "desktop.event",
                                "payload": {
                                    "type": "preview.frame",
                                    "format": "jpeg",
                                    "seq": 1,
                                    "width": 16,
                                    "height": 16,
                                    "data": "ZmFrZQ==",
                                },
                            }
                        )

                        ack = desktop_socket.receive_json()
                        frame = desktop_socket.receive_json()

        self.assertEqual(ack["type"], "ack")
        self.assertEqual(ack["id"], "preview-1")
        self.assertEqual(frame["type"], "preview.frame")

    def test_desktop_websocket_accepts_query_access_token(self) -> None:
        with self.make_client() as client:
            token = self.issue_user_token(client)
            registered = self.register_device(client)
            client.post(
                "/api/devices/claim",
                headers=self.auth_headers(token),
                json={"claimCode": registered["claimCode"]},
            )

            with client.websocket_connect(
                f"/ws/agent/{registered['deviceId']}?agent_token={registered['agentToken']}"
            ) as agent_socket:
                agent_socket.receive_json()
                with client.websocket_connect(
                    f"/ws/agent-desktop/{registered['deviceId']}?agent_token={registered['agentToken']}"
                ) as desktop_agent_socket:
                    desktop_agent_socket.receive_json()
                    with client.websocket_connect(
                        f"/api/desktop/ws?deviceId={registered['deviceId']}&access_token={token}"
                    ) as desktop_socket:
                        ready = desktop_socket.receive_json()

        self.assertEqual(ready["type"], "ready")
        self.assertEqual(ready["deviceId"], registered["deviceId"])

