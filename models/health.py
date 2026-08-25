from typing import Optional
from pydantic import BaseModel


class HealthStatusResponse(BaseModel):
    status: str = "healthy"  # healthy, degraded, unhealthy
    scraper: str = "online"  # online, offline
    live_updater: str = "running"  # running, stopped
    version: str = "0.0.1"
    last_successful_scrape: Optional[str] = None
    last_error: Optional[str] = None
    scrape_age_seconds: Optional[int] = None
    live_matches_count: Optional[int] = None
    upcoming_matches_count: Optional[int] = None
    active_live_matches: int = 0
