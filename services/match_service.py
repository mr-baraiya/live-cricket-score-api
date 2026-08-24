import logging
from typing import Dict, Any, Optional
from datetime import datetime

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
)
from models.commentary import CommentaryResponse, RecentEventResponse, ChangeDetectionResult
from models.health import HealthStatusResponse

logger = logging.getLogger("cricbuzz.match_service")


class MatchService:
    def __init__(self):
        # Store Last Known Good Data per match_id
        self._last_good_overview: Dict[str, MatchOverviewResponse] = {}
        self._last_good_scorecard: Dict[str, ScorecardResponse] = {}
        self._last_good_commentary: Dict[str, CommentaryResponse] = {}

        # Health tracking
        self.last_successful_scrape: Optional[str] = None
        self.last_error: Optional[str] = None

    def get_health(self) -> HealthStatusResponse:
        status_str = "healthy" if not self.last_error else "degraded"
        return HealthStatusResponse(
            status=status_str,
            scraper="online",
            version="0.0.1",
            last_successful_scrape=self.last_successful_scrape,
            last_error=self.last_error,
        )

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
                self.last_successful_scrape = datetime.now().isoformat()
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
                self.last_successful_scrape = datetime.now().isoformat()
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
                    self.last_successful_scrape = datetime.now().isoformat()
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
                if res and (res.batsmen or res.bowlers):
                    self._last_good_scorecard[match_id] = res
                    match_cache.set(cache_key, res)
                    self.last_successful_scrape = datetime.now().isoformat()
                    self.last_error = None
                    return res
                else:
                    raise ValueError("Empty scorecard parsed")

            except Exception as exc:
                logger.warning("Scrape scorecard failed for %s: %s", match_id, exc)
                self.last_error = str(exc)
                if match_id in self._last_good_scorecard:
                    logger.info("Serving Last Known Good Scorecard (stale) for match %s", match_id)
                    return self._last_good_scorecard[match_id]
                raise exc

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
                if res and res.commentary:
                    self._last_good_commentary[match_id] = res
                    match_cache.set(cache_key, res)
                    self.last_successful_scrape = datetime.now().isoformat()
                    self.last_error = None
                    return res
                else:
                    raise ValueError("Empty commentary parsed")

            except Exception as exc:
                logger.warning("Scrape commentary failed for %s: %s", match_id, exc)
                self.last_error = str(exc)
                if match_id in self._last_good_commentary:
                    logger.info("Serving Last Known Good Commentary (stale) for match %s", match_id)
                    return self._last_good_commentary[match_id]
                raise exc

    async def get_recent_event(self, match_id: str) -> RecentEventResponse:
        comm_res = await self.get_commentary(match_id)
        items = comm_res.commentary
        latest = items[0] if items else None
        recent_balls = items[:6] if items else []
        return RecentEventResponse(status="success", latest=latest, recent_balls=recent_balls)

    async def get_full_match(self, match_id: str) -> FullMatchResponse:
        overview = await self.get_match_overview(match_id)
        scorecard = await self.get_scorecard(match_id)
        comm = await self.get_commentary(match_id)

        return FullMatchResponse(
            status="success",
            data_status=overview.data_status,
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
            "score": overview.score
        }
        return change_detector.detect_changes(match_id, current_dict, latest_comm)


match_service = MatchService()
