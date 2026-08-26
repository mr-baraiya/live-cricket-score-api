import os
import asyncio
import logging
from typing import Set, Optional
from datetime import datetime, timezone

from services.match_service import match_service
from services.websocket_manager import websocket_manager

logger = logging.getLogger("cricket.live_updater")


class BackgroundLiveUpdater:
    def __init__(self):
        self.is_running: bool = False
        self.active_live_match_ids: Set[str] = set()
        interval_env = os.getenv("SCRAPE_INTERVAL_SECONDS", "5.0")
        try:
            self.interval_seconds = max(1.0, float(interval_env))
        except ValueError:
            self.interval_seconds = 5.0
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self.is_running:
            logger.warning("Background live updater is already running.")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Background live updater started (interval: %.1fs)", self.interval_seconds)

    async def stop(self):
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Background live updater stopped.")

    async def _run_loop(self):
        while self.is_running:
            try:
                # 1. Discover current live matches using shared match_service
                live_res = await match_service.get_live_matches()
                current_live_ids = {m.id for m in live_res.matches}

                # Handle matches that completed or left active monitoring
                ended_ids = self.active_live_match_ids - current_live_ids
                for em_id in ended_ids:
                    logger.info("Match %s is no longer live. Sending match_end event.", em_id)
                    await websocket_manager.broadcast_to_match(
                        em_id,
                        {
                            "type": "match_end",
                            "match_id": em_id,
                            "status": "COMPLETED",
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                self.active_live_match_ids = current_live_ids

                # 2. Poll and update each live match
                for mid in list(self.active_live_match_ids):
                    if not self.is_running:
                        break
                    try:
                        client_count = websocket_manager.get_active_client_count(mid)
                        if client_count > 0:
                            from app import _match_control_store
                            payload = {
                                "type": "match_update",
                                "match_id": mid,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "changes": changes_res.details,
                                "data": full_match.model_dump(),
                                "control": _match_control_store.get(mid, None)
                            }
                            await websocket_manager.broadcast_to_match(mid, payload)
                    except Exception as exc:
                        logger.warning("Live updater error processing match %s: %s", mid, exc)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unexpected error in live updater loop: %s", exc)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break


live_updater = BackgroundLiveUpdater()
