import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

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

from services import player_image_service

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
                from scraper.matches import MatchesScraper
                from scraper.match import MatchOverviewScraper
                from scraper.normalizer import MatchStatusEnum

                res = await MatchesScraper.scrape_live_matches()

                # Dynamically fetch real scraped status, venue, status_text, and live score for each match
                async def enrich_live_match(m):
                    try:
                        ov = await MatchOverviewScraper.scrape_match_overview(m.id)
                        if ov and ov.match:
                            m.status = ov.match.status
                            if ov.match.status_text:
                                m.status_text = ov.match.status_text
                            if ov.match.venue:
                                m.venue = ov.match.venue
                            if ov.score:
                                m.score = ov.score
                            self._last_good_overview[m.id] = ov
                        elif m.id in self._last_good_overview:
                            ov = self._last_good_overview[m.id]
                            if ov.match:
                                m.status = ov.match.status
                                if ov.match.status_text:
                                    m.status_text = ov.match.status_text
                                if ov.match.venue:
                                    m.venue = ov.match.venue
                            if ov.score:
                                m.score = ov.score
                    except Exception as e:
                        logger.warning("Failed to fetch dynamic overview for live match %s: %s", m.id, e)

                sem = asyncio.Semaphore(5)
                async def safe_enrich_live(m):
                    async with sem:
                        await enrich_live_match(m)

                if res.matches:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*[safe_enrich_live(m) for m in res.matches[:8]], return_exceptions=True),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Live overview enrichment timed out, serving listing cards")

                    # STRICT FILTERING: Keep ONLY matches that are actually LIVE or currently in play
                    valid_live = []
                    for m in res.matches:
                        st_text = (m.status_text or "").lower()
                        is_completed = m.status == MatchStatusEnum.COMPLETED or "won by" in st_text or "won an" in st_text
                        is_upcoming = m.status == MatchStatusEnum.UPCOMING or "match starts" in st_text or "scheduled" in st_text
                        
                        if not is_completed and not is_upcoming:
                            valid_live.append(m)

                    res.matches = valid_live

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
                from scraper.matches import MatchesScraper
                from scraper.match import MatchOverviewScraper
                from scraper.normalizer import MatchStatusEnum

                res = await MatchesScraper.scrape_upcoming_matches()

                async def enrich_upcoming_match(m):
                    try:
                        ov = await MatchOverviewScraper.scrape_match_overview(m.id)
                        if ov and ov.match:
                            m.status = ov.match.status
                            if ov.match.status_text:
                                m.status_text = ov.match.status_text
                            if ov.match.venue:
                                m.venue = ov.match.venue
                            self._last_good_overview[m.id] = ov
                    except Exception:
                        pass

                sem = asyncio.Semaphore(5)
                async def safe_enrich_upcoming(m):
                    async with sem:
                        await enrich_upcoming_match(m)

                if res.matches:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*[safe_enrich_upcoming(m) for m in res.matches[:8]], return_exceptions=True),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Upcoming overview enrichment timed out, serving listing cards")

                    valid_upcoming = []
                    for m in res.matches:
                        st_text = (m.status_text or "").lower()
                        is_completed = m.status == MatchStatusEnum.COMPLETED or "won by" in st_text or "won an" in st_text
                        is_live = m.status == MatchStatusEnum.LIVE or "trail by" in st_text or "lead by" in st_text or "day " in st_text
                        if not is_completed and not is_live:
                            valid_upcoming.append(m)

                    res.matches = valid_upcoming

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

    async def get_recent_matches(self) -> LiveMatchesResponse:
        cache_key = "recent_matches"
        cached = match_cache.get(cache_key)
        if cached:
            return cached

        async with match_cache.get_lock(cache_key):
            cached = match_cache.get(cache_key)
            if cached:
                return cached

            try:
                from scraper.matches import MatchesScraper
                from scraper.match import MatchOverviewScraper
                from scraper.normalizer import MatchStatusEnum

                res = await MatchesScraper.scrape_live_matches()

                async def enrich_recent_match(m):
                    try:
                        ov = await MatchOverviewScraper.scrape_match_overview(m.id)
                        if ov and ov.match:
                            m.status = ov.match.status
                            if ov.match.status_text:
                                m.status_text = ov.match.status_text
                            if ov.match.venue:
                                m.venue = ov.match.venue
                            if ov.score:
                                m.score = ov.score
                            self._last_good_overview[m.id] = ov
                    except Exception as e:
                        logger.warning("Failed to fetch dynamic overview for recent match %s: %s", m.id, e)

                sem = asyncio.Semaphore(6)
                async def safe_enrich_recent(m):
                    async with sem:
                        await enrich_recent_match(m)

                if res.matches:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*[safe_enrich_recent(m) for m in res.matches[:8]], return_exceptions=True),
                            timeout=12.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Recent overview enrichment timed out, serving listing cards")

                    recent_only = []
                    for m in res.matches:
                        st_text = (m.status_text or "").lower()
                        is_completed = m.status == MatchStatusEnum.COMPLETED or "won by" in st_text or "won an" in st_text
                        if is_completed:
                            recent_only.append(m)

                    res.matches = recent_only

                match_cache.set(cache_key, res)
                return res
            except Exception as exc:
                logger.error("Failed to fetch recent matches: %s", exc)
                raise exc

    async def get_match_overview(self, match_id: str) -> MatchOverviewResponse:
        from scraper.match import MatchOverviewScraper
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

                    # Enrich active batsmen & bowler images with Vercel Blob CDN URLs
                    if res.score:
                        if hasattr(res.score, "batsman1") and getattr(res.score, "batsman1", None) and getattr(res.score.batsman1, "name", None):
                            res.score.batsman1.image = player_image_service.get_or_fetch_player_blob_url(res.score.batsman1.name)
                        if hasattr(res.score, "batsman2") and getattr(res.score, "batsman2", None) and getattr(res.score.batsman2, "name", None):
                            res.score.batsman2.image = player_image_service.get_or_fetch_player_blob_url(res.score.batsman2.name)
                        if hasattr(res.score, "bowler") and getattr(res.score, "bowler", None) and getattr(res.score.bowler, "name", None):
                            res.score.bowler.image = player_image_service.get_or_fetch_player_blob_url(res.score.bowler.name)

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
        from scraper.scorecard import ScorecardScraper
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

                if res.batsmen:
                    for b in res.batsmen:
                        if b and getattr(b, "name", None):
                            b.image = player_image_service.get_or_fetch_player_blob_url(b.name)
                if res.current_batsmen:
                    for cb in res.current_batsmen:
                        if cb and getattr(cb, "name", None):
                            cb.image = player_image_service.get_or_fetch_player_blob_url(cb.name)
                if res.bowlers:
                    for bw in res.bowlers:
                        if bw and getattr(bw, "name", None):
                            bw.image = player_image_service.get_or_fetch_player_blob_url(bw.name)
                if res.current_bowler and getattr(res.current_bowler, "name", None):
                    res.current_bowler.image = player_image_service.get_or_fetch_player_blob_url(res.current_bowler.name)

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
        from scraper.commentary import CommentaryScraper
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
