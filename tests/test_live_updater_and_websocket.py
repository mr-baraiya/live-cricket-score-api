import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app import app
from services.websocket_manager import WebSocketManager
from services.live_updater import BackgroundLiveUpdater


class TestWebSocketAndLiveUpdater(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_websocket_manager_registration(self):
        async def run_test():
            wm = WebSocketManager()
            mock_ws1 = AsyncMock()
            mock_ws2 = AsyncMock()

            await wm.connect("1001", mock_ws1)
            await wm.connect("1001", mock_ws2)
            self.assertEqual(wm.get_active_client_count("1001"), 2)

            await wm.broadcast_to_match("1001", {"type": "test", "data": "hello"})
            mock_ws1.send_json.assert_called_once_with({"type": "test", "data": "hello"})
            mock_ws2.send_json.assert_called_once_with({"type": "test", "data": "hello"})

            await wm.disconnect("1001", mock_ws1)
            self.assertEqual(wm.get_active_client_count("1001"), 1)

            await wm.disconnect("1001", mock_ws2)
            self.assertEqual(wm.get_active_client_count("1001"), 0)

        asyncio.run(run_test())

    def test_live_updater_start_stop(self):
        async def run_test():
            updater = BackgroundLiveUpdater()
            self.assertFalse(updater.is_running)

            await updater.start()
            self.assertTrue(updater.is_running)

            await updater.stop()
            self.assertFalse(updater.is_running)

        asyncio.run(run_test())

    def test_websocket_endpoint_connect_and_snapshot(self):
        with self.client.websocket_connect("/ws/match/163017") as websocket:
            data = websocket.receive_json()
            self.assertEqual(data.get("type"), "match_snapshot")
            self.assertEqual(data.get("match_id"), "163017")
            self.assertIn("data", data)

    def test_cached_state_endpoint(self):
        response = self.client.get("/match/163017/state")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data.get("status"), "success")
        self.assertIn("match", json_data)


if __name__ == "__main__":
    unittest.main()
