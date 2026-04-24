from __future__ import annotations

import asyncio
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import _handle_ws_message, app, runtime
from app.models import LockedWindow
from app.relay_client import RelaySnapshot
from app.session import MobileConnection
from app.windows_control import PreviewFrame


class AppTests(TestCase):
    def setUp(self) -> None:
        runtime.session.set_locked_window(None)
        runtime.session.reset_token()
        runtime.pin_manager.rotate_pin()
        runtime._recent_issues.clear()
        runtime.session.set_preview_requested(False)
        runtime.session.set_pointer_active(False)
        runtime._last_preview_issue_signature = None

    def make_client(self) -> TestClient:
        return TestClient(app)

    def current_pin(self) -> str:
        return runtime.pin_manager.current_pin

    def test_ensure_codex_window_locked_discovers_background_codex(self) -> None:
        codex_window = LockedWindow(
            hwnd=777,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        ensure_result = type("EnsureResult", (), {"ok": True, "window": codex_window})()

        with (
            patch.object(runtime.windows, "capture_foreground_window", return_value=None),
            patch.object(runtime.windows, "find_codex_window", return_value=codex_window),
            patch.object(runtime.windows, "ensure_window_ready", return_value=ensure_result) as ensure_window_ready,
        ):
            result = runtime.ensure_codex_window_locked(focus=True)

        self.assertTrue(result.ok)
        self.assertEqual(runtime.session.snapshot().locked_window, codex_window)
        ensure_window_ready.assert_called_once_with(codex_window)

    def test_admin_state_returns_runtime_metadata(self) -> None:
        runtime.session.set_locked_window(
            LockedWindow(
                hwnd=101,
                title="VS Code",
                process_name="Code.exe",
                locked_at=datetime.now().astimezone(),
            )
        )
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch.object(runtime, "sync_foreground_codex_window", return_value=False),
            patch("app.main._open_admin_page", return_value=None),
            self.make_client() as client,
        ):
            response = client.get("/api/admin/state")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lockedWindow"]["title"], "VS Code")
        self.assertEqual(payload["currentPin"], self.current_pin())
        self.assertTrue(payload["configPath"])
        self.assertTrue(payload["logPath"])
        self.assertTrue(payload["sessionToken"])
        self.assertIn("relay", payload)
        self.assertIn("preferredConnection", payload)

    def test_admin_state_prefers_lan_direct_when_relay_is_localhost(self) -> None:
        relay_snapshot = RelaySnapshot(
            configured_url="http://127.0.0.1:8780",
            status="connected",
            session_id="relay-session",
            mobile_url="http://192.168.1.108:8780/r/test",
            qr_svg_url="http://192.168.1.108:8780/api/sessions/test/qr.svg",
            expires_at="2026-04-05T06:48:15+00:00",
            last_error=None,
        )
        fake_addresses = [
            type(
                "Candidate",
                (),
                {
                    "address": "192.168.1.108",
                    "label": "Wi-Fi",
                    "to_dict": lambda self, port, token: {
                        "address": "192.168.1.108",
                        "label": "Wi-Fi",
                        "isRecommended": False,
                        "remoteUrl": f"http://192.168.1.108:{port}/remote?token={token}",
                    },
                },
            )()
        ]
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch.object(runtime.relay_client, "snapshot", return_value=relay_snapshot),
            patch.object(runtime, "sync_foreground_codex_window", return_value=False),
            patch("app.main.list_candidate_addresses", return_value=fake_addresses),
            patch("app.main._open_admin_page", return_value=None),
            self.make_client() as client,
        ):
            response = client.get("/api/admin/state")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["preferredConnection"]["mode"], "lan-direct")
        self.assertTrue(payload["preferredConnection"]["mobileUrl"].startswith("http://192.168.1.108:8765/remote?token="))

    def test_pin_reset_rotates_pin(self) -> None:
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            self.make_client() as client,
        ):
            previous = self.current_pin()
            response = client.post("/api/admin/pin/reset")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(previous, payload["currentPin"])

    def test_invalid_token_is_rejected(self) -> None:
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            self.make_client() as client,
        ):
            with client.websocket_connect("/ws?token=wrong") as websocket:
                error = websocket.receive_json()
                self.assertEqual(error["code"], "invalid_token")

    def test_invalid_pin_is_rejected(self) -> None:
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            self.make_client() as client,
        ):
            token = runtime.session.current_token()
            with client.websocket_connect(f"/ws?token={token}") as websocket:
                websocket.send_json({"type": "hello", "client": "mobile-web", "version": 1, "pin": "000000"})
                error = websocket.receive_json()
                self.assertEqual(error["code"], "invalid_pin")

    def test_text_send_without_codex_window_returns_error(self) -> None:
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            patch.object(runtime, "sync_foreground_codex_window", return_value=False),
            self.make_client() as client,
        ):
            token = runtime.session.current_token()
            with client.websocket_connect(f"/ws?token={token}") as websocket:
                websocket.send_json(
                    {
                        "type": "hello",
                        "client": "mobile-web",
                        "version": 1,
                        "pin": self.current_pin(),
                    }
                )
                ready = websocket.receive_json()
                self.assertEqual(ready["type"], "ready")
                websocket.send_json({"type": "text.send", "id": "1", "text": "hello"})
                error = websocket.receive_json()
                self.assertEqual(error["code"], "codex_window_not_found")

    def test_second_mobile_session_is_rejected(self) -> None:
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            self.make_client() as client,
        ):
            token = runtime.session.current_token()
            with client.websocket_connect(f"/ws?token={token}") as first:
                first.send_json(
                    {
                        "type": "hello",
                        "client": "mobile-web",
                        "version": 1,
                        "pin": self.current_pin(),
                    }
                )
                first.receive_json()
                with client.websocket_connect(f"/ws?token={token}") as second:
                    second.send_json(
                        {
                            "type": "hello",
                            "client": "mobile-web",
                            "version": 1,
                            "pin": self.current_pin(),
                        }
                    )
                    error = second.receive_json()
                    self.assertEqual(error["code"], "session_busy")

    def test_text_send_acknowledges_after_paste(self) -> None:
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        runtime.session.set_locked_window(locked_window)
        ensure_result = type("EnsureResult", (), {"ok": True, "window": locked_window})()
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            patch.object(runtime, "sync_foreground_codex_window", return_value=False),
            patch.object(runtime.windows, "ensure_window_ready", return_value=ensure_result),
            patch.object(runtime.windows, "paste_text", return_value=None),
            self.make_client() as client,
        ):
            token = runtime.session.current_token()
            with client.websocket_connect(f"/ws?token={token}") as websocket:
                websocket.send_json(
                    {
                        "type": "hello",
                        "client": "mobile-web",
                        "version": 1,
                        "pin": self.current_pin(),
                    }
                )
                ready = websocket.receive_json()
                self.assertEqual(ready["lockedWindow"]["title"], "Codex")
                websocket.send_json({"type": "text.send", "id": "abc", "text": "hello", "submit": True})
                ack = websocket.receive_json()
                self.assertEqual(ack, {"type": "ack", "id": "abc"})
                state = websocket.receive_json()
                self.assertEqual(state["type"], "state")
                self.assertEqual(state["lockedWindow"]["title"], "Codex")
                runtime.windows.paste_text.assert_called_once_with("hello", submit=True, target_window=locked_window)

    def test_codex_thread_focus_acknowledges_after_sidebar_switch(self) -> None:
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        runtime.session.set_locked_window(locked_window)
        ensure_result = type("EnsureResult", (), {"ok": True, "window": locked_window})()
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            patch.object(runtime, "sync_foreground_codex_window", return_value=False),
            patch.object(runtime.windows, "ensure_window_ready", return_value=ensure_result),
            patch.object(
                runtime.windows,
                "focus_codex_thread_by_text",
                return_value=type(
                    "Match",
                    (),
                    {
                        "matched_text": "Target thread",
                        "confidence": 0.93,
                        "row_box": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                        "matched_project": "codex-mcp-mobile",
                        "matched_title": "Target thread",
                        "verified_title": "Target thread",
                    },
                )(),
            ),
            self.make_client() as client,
        ):
            token = runtime.session.current_token()
            with client.websocket_connect(f"/ws?token={token}") as websocket:
                websocket.send_json(
                    {
                        "type": "hello",
                        "client": "mobile-web",
                        "version": 1,
                        "pin": self.current_pin(),
                    }
                )
                websocket.receive_json()
                websocket.send_json(
                    {
                        "type": "codex.thread.focus",
                        "id": "focus-1",
                        "workspace": r"E:\codex-mcp-mobile",
                        "title": "Target thread",
                        "preview": "summary",
                    }
                )
                ack = websocket.receive_json()
                self.assertEqual(ack["type"], "ack")
                self.assertEqual(ack["id"], "focus-1")
                self.assertEqual(ack["matchedText"], "Target thread")
                self.assertEqual(ack["confidence"], 0.93)
                self.assertEqual(ack["matchSource"], "uia")
                self.assertEqual(ack["matchedProject"], "codex-mcp-mobile")
                self.assertEqual(ack["matchedTitle"], "Target thread")
                self.assertEqual(ack["verifiedTitle"], "Target thread")
                runtime.windows.focus_codex_thread_by_text.assert_called_once_with(
                    locked_window,
                    workspace=r"E:\codex-mcp-mobile",
                    title="Target thread",
                    preview="summary",
                )

    def test_codex_thread_new_acknowledges_after_click(self) -> None:
        locked_window = LockedWindow(
            hwnd=123,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        runtime.session.set_locked_window(locked_window)
        ensure_result = type("EnsureResult", (), {"ok": True, "window": locked_window})()
        with (
            patch.object(runtime.hotkeys, "start", return_value=None),
            patch.object(runtime.hotkeys, "stop", return_value=None),
            patch.object(runtime.relay_client, "start", return_value=None),
            patch.object(runtime.relay_client, "stop", return_value=None),
            patch("app.main._open_admin_page", return_value=None),
            patch.object(runtime, "sync_foreground_codex_window", return_value=False),
            patch.object(runtime.windows, "ensure_window_ready", return_value=ensure_result),
            patch.object(
                runtime.windows,
                "start_codex_new_thread",
                return_value=type("Started", (), {"button_name": "新线程", "verified_title": "Untitled"})(),
            ),
            self.make_client() as client,
        ):
            token = runtime.session.current_token()
            with client.websocket_connect(f"/ws?token={token}") as websocket:
                websocket.send_json(
                    {
                        "type": "hello",
                        "client": "mobile-web",
                        "version": 1,
                        "pin": self.current_pin(),
                    }
                )
                websocket.receive_json()
                websocket.send_json({"type": "codex.thread.new", "id": "new-1", "workspace": r"E:\codex-mcp-mobile"})
                ack = websocket.receive_json()
                self.assertEqual(ack["type"], "ack")
                self.assertEqual(ack["id"], "new-1")
                self.assertEqual(ack["buttonName"], "新线程")
                self.assertEqual(ack["matchSource"], "uia")
                runtime.windows.start_codex_new_thread.assert_called_once_with(
                    locked_window,
                    workspace=r"E:\codex-mcp-mobile",
                )

    def test_preview_once_sends_frame(self) -> None:
        locked_window = LockedWindow(
            hwnd=555,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        runtime.session.set_locked_window(locked_window)
        sent_payloads = []

        async def send_json(payload):
            sent_payloads.append(payload)

        async def close(reason, code):
            return None

        connection = MobileConnection(
            connection_id="test:preview",
            transport="relay",
            send_json=send_json,
            close=close,
        )
        runtime.session.register_mobile(connection)
        runtime.session.set_preview_requested(True)
        ensure_result = type("EnsureResult", (), {"ok": True, "window": locked_window})()
        with (
            patch.object(runtime.windows, "preview_supported", return_value=True),
            patch.object(runtime, "ensure_codex_window_locked", return_value=ensure_result),
            patch.object(
                runtime.windows,
                "capture_window_preview",
                return_value=PreviewFrame(width=320, height=180, jpeg_bytes=b"jpeg-bytes"),
            ),
        ):
            asyncio.run(runtime._preview_once())

        self.assertEqual(sent_payloads[-1]["type"], "preview.frame")
        self.assertEqual(sent_payloads[-1]["width"], 320)
        self.assertEqual(sent_payloads[-1]["height"], 180)

    def test_pointer_messages_toggle_drag_state(self) -> None:
        locked_window = LockedWindow(
            hwnd=777,
            title="Codex",
            process_name="Codex.exe",
            locked_at=datetime.now().astimezone(),
        )
        runtime.session.set_locked_window(locked_window)
        sent_payloads = []

        async def send_json(payload):
            sent_payloads.append(payload)

        async def close(reason, code):
            return None

        connection = MobileConnection(
            connection_id="test:pointer",
            transport="local",
            send_json=send_json,
            close=close,
        )
        runtime.session.register_mobile(connection)
        ensure_result = type("EnsureResult", (), {"ok": True, "window": locked_window})()
        with (
            patch.object(runtime, "ensure_codex_window_locked", return_value=ensure_result),
            patch.object(runtime.windows, "pointer_down_at_ratio", return_value=None),
            patch.object(runtime.windows, "pointer_move_to_ratio", return_value=None),
            patch.object(runtime.windows, "pointer_up_at_ratio", return_value=None),
            patch.object(runtime.windows, "preview_supported", return_value=True),
        ):
            asyncio.run(_handle_ws_message(connection, {"type": "pointer.down", "id": "down", "xRatio": 0.2, "yRatio": 0.4}))
            self.assertTrue(runtime.session.snapshot().pointer_active)
            asyncio.run(_handle_ws_message(connection, {"type": "pointer.move", "id": "move", "xRatio": 0.4, "yRatio": 0.6}))
            asyncio.run(_handle_ws_message(connection, {"type": "pointer.up", "id": "up", "xRatio": 0.4, "yRatio": 0.6}))

        self.assertFalse(runtime.session.snapshot().pointer_active)
        ack_ids = [item["id"] for item in sent_payloads if item.get("type") == "ack"]
        self.assertEqual(ack_ids, ["down", "move", "up"])
