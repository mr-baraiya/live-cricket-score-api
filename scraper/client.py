import asyncio
import logging
from typing import Optional
import httpx

import os

logger = logging.getLogger("cricket.http_client")


class CricketHTTPClient:
    BASE_URL = os.getenv("TARGET_BASE_URL", "https://www.cricbuzz.com")

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        "Referer": f"{BASE_URL}/",
        "Origin": BASE_URL,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    def __init__(self, timeout: float = 10.0, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch(self, url: str) -> str:
        full_url = url if url.startswith("http") else f"{self.BASE_URL}{url}"

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True
                ) as client:
                    logger.debug("Fetching URL [attempt %d]: %s", attempt + 1, full_url)
                    response = await client.get(full_url, headers=self.DEFAULT_HEADERS)
                    response.raise_for_status()
                    return response.text

            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError) as exc:
                logger.warning(
                    "HTTP fetch failed for %s [attempt %d/%d]: %s",
                    full_url, attempt + 1, self.max_retries + 1, exc
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                else:
                    raise exc

        raise RuntimeError("Unexpected error in HTTP client retry loop")


timeout_env = float(os.getenv("SCRAPER_TIMEOUT", "10.0"))
retries_env = int(os.getenv("SCRAPER_MAX_RETRIES", "2"))

http_client = CricketHTTPClient(timeout=timeout_env, max_retries=retries_env)
