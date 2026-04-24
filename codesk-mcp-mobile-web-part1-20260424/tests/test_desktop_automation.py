from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from bridge.desktop_automation import DesktopAutomationClient


class FakeProcess:
    def poll(self) -> None:
        return None


class DesktopAutomationClientTests(IsolatedAsyncioTestCase):
    async def test_refresh_admin_state_autostarts_remote_service(self) -> None:
        client = DesktopAutomationClient(base_url="http://127.0.0.1:8765")
        client._autostart_enabled = True
        client._launch_command = ["python", "-m", "app.main"]
        client._launch_cwd = r"E:\远程桌面"

        with (
            patch(
                "bridge.desktop_automation._fetch_admin_state",
                side_effect=[
                    OSError("offline"),
                    {
                        "previewSupported": True,
                        "sessionToken": "session-token",
                        "currentPin": "123456",
                        "lockedWindow": {"title": "Codex", "process_name": "Codex.exe"},
                    },
                ],
            ),
            patch("bridge.desktop_automation._launch_desktop_automation_process", return_value=FakeProcess()) as launch,
            patch("bridge.desktop_automation.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await client._refresh_admin_state()

        self.assertTrue(client.snapshot()["available"])
        self.assertTrue(client.snapshot()["windowLocked"])
        self.assertTrue(client.snapshot()["codexWindowLocked"])
        launch.assert_called_once_with(["python", "-m", "app.main"], r"E:\远程桌面")
        sleep_mock.assert_awaited()

    async def test_refresh_admin_state_raises_when_autostart_disabled(self) -> None:
        client = DesktopAutomationClient(base_url="http://127.0.0.1:8765")
        client._autostart_enabled = False
        client._launch_command = ["python", "-m", "app.main"]

        with (
            patch("bridge.desktop_automation._fetch_admin_state", side_effect=OSError("offline")),
            patch("bridge.desktop_automation._launch_desktop_automation_process") as launch,
        ):
            with self.assertRaises(OSError):
                await client._refresh_admin_state()

        launch.assert_not_called()
