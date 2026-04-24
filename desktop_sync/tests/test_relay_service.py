from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models import CandidateAddress
from relay_service.main import app, store


class RelayServiceTests(TestCase):
    def setUp(self) -> None:
        store._sessions.clear()

    def make_client(self) -> TestClient:
        return TestClient(app)

    def test_create_session_returns_qr_and_mobile_url(self) -> None:
        with self.make_client() as client:
            response = client.post("/api/sessions", json={"client_name": "Desktop", "version": "0.3.0"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["session_id"])
        self.assertTrue(payload["desktop_token"])
        self.assertTrue(payload["resume_token"])
        self.assertIn("/r/", payload["mobile_url"])
        self.assertIn("/qr.svg", payload["qr_svg_url"])

    @patch("relay_service.main.list_candidate_addresses")
    def test_localhost_relay_generates_lan_mobile_url(self, mock_candidates) -> None:
        mock_candidates.return_value = [
            CandidateAddress(address="100.68.1.2", label="Tailscale", is_recommended=True),
            CandidateAddress(address="192.168.1.108", label="Wi-Fi"),
        ]
        with TestClient(app, base_url="http://127.0.0.1:8780") as client:
            response = client.post("/api/sessions", json={})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["mobile_url"].startswith("http://192.168.1.108:8780/r/"))
        self.assertTrue(payload["qr_svg_url"].startswith("http://192.168.1.108:8780/api/sessions/"))

    def test_qr_endpoint_returns_svg(self) -> None:
        with self.make_client() as client:
            payload = client.post("/api/sessions", json={}).json()
            response = client.get(f"/api/sessions/{payload['session_id']}/qr.svg")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/svg+xml")
        self.assertIn("<svg", response.text)

    def test_mobile_messages_forward_through_desktop_channel(self) -> None:
        with self.make_client() as client:
            payload = client.post("/api/sessions", json={}).json()
            session_id = payload["session_id"]
            desktop_path = (
                f"/ws/desktop/{session_id}?desktop_token={payload['desktop_token']}"
                f"&resume_token={payload['resume_token']}"
            )
            with client.websocket_connect(desktop_path) as desktop:
                ready = desktop.receive_json()
                self.assertEqual(ready["type"], "relay.ready")

                with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
                    connected = desktop.receive_json()
                    self.assertEqual(connected["type"], "relay.mobile.connected")
                    mobile_id = connected["mobile_id"]

                    mobile.send_json({"type": "hello", "pin": "123456"})
                    forwarded = desktop.receive_json()
                    self.assertEqual(forwarded["type"], "relay.mobile.message")
                    self.assertEqual(forwarded["mobile_id"], mobile_id)
                    self.assertEqual(forwarded["payload"]["type"], "hello")

                    desktop.send_json(
                        {
                            "type": "relay.desktop.message",
                            "mobile_id": mobile_id,
                            "payload": {"type": "ready", "windowLocked": False, "title": None},
                        }
                    )
                    self.assertEqual(mobile.receive_json()["type"], "ready")

    def test_second_mobile_is_rejected(self) -> None:
        with self.make_client() as client:
            payload = client.post("/api/sessions", json={}).json()
            session_id = payload["session_id"]
            desktop_path = (
                f"/ws/desktop/{session_id}?desktop_token={payload['desktop_token']}"
                f"&resume_token={payload['resume_token']}"
            )
            with client.websocket_connect(desktop_path) as desktop:
                desktop.receive_json()
                with client.websocket_connect(f"/ws/mobile/{session_id}") as first:
                    desktop.receive_json()
                    with client.websocket_connect(f"/ws/mobile/{session_id}") as second:
                        error = second.receive_json()
                        self.assertEqual(error["code"], "session_busy")
                    first.close()

    def test_mobile_is_rejected_when_desktop_offline(self) -> None:
        with self.make_client() as client:
            payload = client.post("/api/sessions", json={}).json()
            with client.websocket_connect(f"/ws/mobile/{payload['session_id']}") as mobile:
                error = mobile.receive_json()
                self.assertEqual(error["code"], "desktop_offline")

    def test_desktop_can_resume_same_session(self) -> None:
        with self.make_client() as client:
            payload = client.post("/api/sessions", json={}).json()
            session_id = payload["session_id"]
            desktop_path = (
                f"/ws/desktop/{session_id}?desktop_token={payload['desktop_token']}"
                f"&resume_token={payload['resume_token']}"
            )
            with client.websocket_connect(desktop_path) as desktop:
                self.assertEqual(desktop.receive_json()["type"], "relay.ready")

            with client.websocket_connect(desktop_path) as desktop_again:
                self.assertEqual(desktop_again.receive_json()["type"], "relay.ready")
