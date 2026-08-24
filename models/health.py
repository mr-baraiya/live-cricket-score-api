from typing import Optional
from pydantic import BaseModel


class HealthStatusResponse(BaseModel):
    status: str = "healthy"  # healthy, degraded, error
    scraper: str = "online"  # online, offline
    version: str = "0.0.1"
    last_successful_scrape: Optional[str] = None
    last_error: Optional[str] = None
