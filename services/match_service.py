import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from scraper.matches import MatchesScraper
from scraper.match import MatchOverviewScraper
from scraper.scorecard import ScorecardScraper
from scraper.commentary import CommentaryScraper
from .cache import match_cache
from .change_detector import change_detector
from models.match import (
    LiveMatchesResponse,
    UpcomingMatchesResponse,
    MatchOverviewResponse,
    ScorecardResponse,
    FullMatchResponse,
    MatchInfo,
)
from models.commentary import CommentaryResponse, RecentEventResponse, ChangeDetectionResult
from models.health import HealthStatusResponse

logger = logging.getLogger("cricket.match_service")


class MatchService:
    def __init__(self):
        # Store Last Known Good Data per match_id
        self._last_good_overview: Dict[str, MatchOverviewResponse] = {}
        self._last_good_scorecard: Dict[str, ScorecardResponse] = {}
        self._last_good_commentary: Dict[str, CommentaryResponse] = {}

        # Health tracking
        self.last_successful_dt: Optional[datetime] = None
        self.last_successful_scrape: Optional[str] = None
        self.last_error: Optional[str] = None
        self.live_matches_count: Optional[int] = None
        self.upcoming_matches_count: Optional[int] = None

    def get_health(self) -> HealthStatusResponse:
        from services.live_updater import live_updater
        now = datetime.now(timezone.utc)
        scrape_age_seconds = None
        if self.last_successful_dt:
            scrape_age_seconds = int((now - self.last_successful_dt).total_seconds())

        if self.last_successful_scrape and (scrape_age_seconds is not None and scrape_age_seconds <= 300):
            status_str = "healthy" if not self.last_error else "degraded"
        elif self.last_successful_scrape:
            status_str = "degraded"
        else:
            status_str = "unhealthy" if self.last_error else "degraded"

        updater_status = "running" if live_updater.is_running else "stopped"
        active_count = len(live_updater.active_live_match_ids)

        return HealthStatusResponse(
            status=status_str,
            scraper="online",
            live_updater=updater_status,
            version="0.0.1",
            last_successful_scrape=self.last_successful_scrape,
            last_error=self.last_error,
            scrape_age_seconds=scrape_age_seconds,
            live_matches_count=self.live_matches_count,
            upcoming_matches_count=self.upcoming_matches_count,
            active_live_matches=active_count,
        )

    async def get_cached_match_state(self, match_id: str) -> FullMatchResponse:
        """Returns latest cached match state without triggering a new scrape."""
        return await self.get_full_match(match_id)

    async def get_live_matches(self) -> LiveMatchesResponse:
        cache_key = "live_matches"
        cached = match_cache.get(cache_key)
        if cached:
            return cached

        async with match_cache.get_lock(cache_key):
            cached = match_cache.get(cache_key)
            if cached:
                return cached

            try:
                res = await MatchesScraper.scrape_live_matches()
                match_cache.set(cache_key, res)
                self.last_successful_dt = datetime.now(timezone.utc)
                self.last_successful_scrape = self.last_successful_dt.isoformat()
                self.live_matches_count = len(res.matches)
                self.last_error = None
                return res
            except Exception as exc:
                logger.error("Failed to fetch live matches: %s", exc)
                self.last_error = str(exc)
                raise exc

    async def get_upcoming_matches(self) -> UpcomingMatchesResponse:
        cache_key = "upcoming_matches"
        cached = match_cache.get(cache_key)
        if cached:
            return cached

        async with match_cache.get_lock(cache_key):
            cached = match_cache.get(cache_key)
            if cached:
                return cached

            try:
                res = await MatchesScraper.scrape_upcoming_matches()
                match_cache.set(cache_key, res)
                self.last_successful_dt = datetime.now(timezone.utc)
                self.last_successful_scrape = self.last_successful_dt.isoformat()
                self.upcoming_matches_count = len(res.matches)
                self.last_error = None
                return res
            except Exception as exc:
                logger.error("Failed to fetch upcoming matches: %s", exc)
                self.last_error = str(exc)
                raise exc

    async def get_match_overview(self, match_id: str) -> MatchOverviewResponse:
        cache_key = f"overview_{match_id}"
        cached = match_cache.get(cache_key)
        if cached:
            return cached

        async with match_cache.get_lock(cache_key):
            cached = match_cache.get(cache_key)
            if cached:
                return cached

            try:
                res = await MatchOverviewScraper.scrape_match_overview(match_id)
                if res and res.match and res.match.title:
                    res.data_status = "fresh"
                    self._last_good_overview[match_id] = res
                    match_cache.set(cache_key, res)
                    self.last_successful_dt = datetime.now(timezone.utc)
                    self.last_successful_scrape = self.last_successful_dt.isoformat()
                    self.last_error = None
                    return res
                else:
                    raise ValueError("Empty match overview parsed")

            except Exception as exc:
                logger.warning("Scrape match overview failed for %s: %s", match_id, exc)
                self.last_error = str(exc)
                if match_id in self._last_good_overview:
                    stale = self._last_good_overview[match_id].model_copy()
                    stale.data_status = "stale"
                    logger.info("Serving Last Known Good Data (stale) for match %s", match_id)
                    return stale
                raise exc

    async def get_scorecard(self, match_id: str) -> ScorecardResponse:
        cache_key = f"scorecard_{match_id}"
        cached = match_cache.get(cache_key)
        if cached:
            return cached

        async with match_cache.get_lock(cache_key):
            cached = match_cache.get(cache_key)
            if cached:
                return cached

            try:
                res = await ScorecardScraper.scrape_scorecard(match_id)
                res.data_status = "fresh"
                self._last_good_scorecard[match_id] = res
                match_cache.set(cache_key, res)
                self.last_successful_dt = datetime.now(timezone.utc)
                self.last_successful_scrape = self.last_successful_dt.isoformat()
                self.last_error = None
                return res
            except Exception as exc:
                logger.warning("Scrape scorecard failed for %s: %s", match_id, exc)
                self.last_error = str(exc)
                if match_id in self._last_good_scorecard:
                    stale = self._last_good_scorecard[match_id].model_copy()
                    stale.data_status = "stale"
                    logger.info("Serving Last Known Good Scorecard (stale) for match %s", match_id)
                    return stale
                # Return empty response instead of failing
                return ScorecardResponse(status="success", data_status="fresh", batsmen=[], bowlers=[])

    async def get_commentary(self, match_id: str) -> CommentaryResponse:
        cache_key = f"commentary_{match_id}"
        cached = match_cache.get(cache_key)
        if cached:
            return cached

        async with match_cache.get_lock(cache_key):
            cached = match_cache.get(cache_key)
            if cached:
                return cached

            try:
                res = await CommentaryScraper.scrape_commentary(match_id)
                self._last_good_commentary[match_id] = res
                match_cache.set(cache_key, res)
                self.last_successful_dt = datetime.now(timezone.utc)
                self.last_successful_scrape = self.last_successful_dt.isoformat()
                self.last_error = None
                return res
            except Exception as exc:
                logger.warning("Scrape commentary failed for %s: %s", match_id, exc)
                self.last_error = str(exc)
                if match_id in self._last_good_commentary:
                    logger.info("Serving Last Known Good Commentary (stale) for match %s", match_id)
                    return self._last_good_commentary[match_id]
                return CommentaryResponse(status="success", commentary=[])

    async def get_recent_event(self, match_id: str) -> RecentEventResponse:
        comm_res = await self.get_commentary(match_id)
        items = comm_res.commentary
        latest = items[0] if items else None
        recent_balls = items[:6] if items else []
        return RecentEventResponse(status="success", latest=latest, recent_balls=recent_balls)

    async def get_full_match(self, match_id: str) -> FullMatchResponse:
        data_status = "fresh"
        try:
            overview = await self.get_match_overview(match_id)
        except Exception:
            overview = MatchOverviewResponse(
                status="success",
                data_status="partial",
                match=MatchInfo(id=match_id, title=f"Match {match_id}")
            )
            data_status = "partial"

        try:
            scorecard = await self.get_scorecard(match_id)
        except Exception:
            scorecard = ScorecardResponse(status="success", data_status="partial")
            data_status = "partial"

        try:
            comm = await self.get_commentary(match_id)
        except Exception:
            comm = CommentaryResponse(status="success", commentary=[])
            data_status = "partial"

        if overview.data_status == "stale" or scorecard.data_status == "stale":
            data_status = "stale"

        return FullMatchResponse(
            status="success",
            data_status=data_status,
            match=overview.match,
            score=overview.score,
            innings=scorecard.innings,
            batsmen=scorecard.batsmen,
            current_batsmen=scorecard.current_batsmen,
            bowlers=scorecard.bowlers,
            current_bowler=scorecard.current_bowler,
            partnership=scorecard.partnership,
            last_wicket=scorecard.last_wicket,
            recent_balls=comm.commentary[:12] if comm.commentary else [],
            commentary=comm.commentary,
        )

    async def detect_match_changes(self, match_id: str) -> ChangeDetectionResult:
        overview = await self.get_match_overview(match_id)
        comm = await self.get_commentary(match_id)
        latest_comm = comm.commentary[0] if comm.commentary else None

        current_dict = {
            "score": overview.score,
            "status": overview.match.status if overview.match else None
        }
        return change_detector.detect_changes(match_id, current_dict, latest_comm)


match_service = MatchService()
