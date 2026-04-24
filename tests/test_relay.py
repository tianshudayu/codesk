from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from mcp_relay.main import create_app


class RelayTests(TestCase):
    def test_create_session_and_qr_svg(self) -> None:
        with TestClient(create_app()) as client:
            created = client.post("/api/sessions", json={"source": "test"})
            self.assertEqual(created.status_code, 200)
            payload = created.json()
            self.assertIn("sessionId", payload)
            self.assertIn("/r/", payload["mobileUrl"])
            qr = client.get(f"/api/sessions/{payload['sessionId']}/qr.svg")
            self.assertEqual(qr.status_code, 200)
            self.assertEqual(qr.headers["content-type"], "image/svg+xml")

    def test_bridge_mobile_forwarding_and_single_mobile_rule(self) -> None:
        with TestClient(create_app()) as client:
            payload = client.post("/api/sessions", json={"source": "test"}).json()
            bridge_path = f"/ws/bridge/{payload['sessionId']}?bridge_token={payload['bridgeToken']}"
            mobile_path = f"/ws/mobile/{payload['sessionId']}"

            with client.websocket_connect(bridge_path) as bridge:
                ready = bridge.receive_json()
                self.assertEqual(ready["type"], "relay.ready")

                with client.websocket_connect(mobile_path) as mobile:
                    status = mobile.receive_json()
                    self.assertEqual(status["type"], "relay.status")
                    self.assertEqual(status["status"], "ready")
                    self.assertEqual(bridge.receive_json()["type"], "relay.mobile.connected")

                    mobile.send_json({"type": "rpc.request", "id": "1", "action": "health"})
                    forwarded = bridge.receive_json()
                    self.assertEqual(forwarded["type"], "relay.mobile.message")
                    self.assertEqual(forwarded["payload"]["action"], "health")

                    bridge.send_json({"type": "rpc.response", "id": "1", "ok": True, "result": {"ok": True}})
                    response = mobile.receive_json()
                    self.assertEqual(response["type"], "rpc.response")
                    self.assertTrue(response["ok"])

                    with client.websocket_connect(mobile_path) as mobile2:
                        error = mobile2.receive_json()
                        self.assertEqual(error["type"], "relay.error")
                        self.assertEqual(error["message"], "session_busy")

                self.assertEqual(bridge.receive_json()["type"], "relay.mobile.disconnected")
