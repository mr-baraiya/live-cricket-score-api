import re
import logging
from bs4 import BeautifulSoup
from .client import http_client
from .selectors import find_all_matching
from .parser_utils import clean_text, extract_teams_from_title, deduplicate_repeated_text
from .normalizer import normalize_status, is_live_status, is_upcoming_status, MatchStatusEnum
from models.match import LiveMatchItem, LiveMatchesResponse, UpcomingMatchItem, UpcomingMatchesResponse

logger = logging.getLogger("cricket.matches_scraper")


class MatchesScraper:
    @classmethod
    async def scrape_live_matches(cls) -> LiveMatchesResponse:
        html_doc = await http_client.fetch("/cricket-match/live-scores")
        soup = BeautifulSoup(html_doc, "lxml")
        matches = []

        links = find_all_matching(soup, "live_matches")
        for a in links:
            try:
                href = a.get("href", "")
                m = re.search(r"/live-cricket-scores/(\d+)/([^/]+)", href)
                if not m:
                    continue

                mid = m.group(1)
                slug = m.group(2)

                # Skip if already added
                if any(x.id == mid for x in matches):
                    continue

                title_attr = clean_text(a.get("title", ""))
                if not title_attr:
                    title_attr = slug.replace("-", " ").title()

                clean_title = title_attr.split(" - ")[0].strip()
                clean_title = deduplicate_repeated_text(clean_title) or clean_title
                teams = extract_teams_from_title(clean_title)

                # Extract status text from surrounding card context
                parent_txt = ""
                if a.parent and a.parent.parent:
                    parent_txt = clean_text(" ".join(a.parent.parent.get_text(" ", strip=True).split())) or ""

                status_enum, clean_status_text = normalize_status(parent_txt or "Live")

                # STRICT FILTERING: Exclude completed or upcoming matches from live endpoint
                if not is_live_status(status_enum):
                    continue

                if len(clean_title) > 3:
                    matches.append(
                        LiveMatchItem(
                            id=mid,
                            title=clean_title,
                            teams=teams,
                            status=status_enum,
                            status_text=clean_status_text,
                            url=f"/match/{mid}"
                        )
                    )
            except Exception as exc:
                logger.warning("Error parsing live match card element: %s", exc)
                continue

        return LiveMatchesResponse(status="success", matches=matches)

    @classmethod
    async def scrape_upcoming_matches(cls) -> UpcomingMatchesResponse:
        html_doc = await http_client.fetch("/cricket-schedule/upcoming-series/international")
        soup = BeautifulSoup(html_doc, "lxml")
        upcoming = []

        for a in soup.find_all("a", href=True):
            try:
                href = a["href"]
                if "/cricket-match-facts/" in href or "/live-cricket-scores/" in href:
                    m = re.search(r"/(\d+)/", href)
                    if not m:
                        continue
                    mid = m.group(1)
                    if any(x.id == mid for x in upcoming):
                        continue

                    txt = clean_text(" ".join(a.get_text(" ", strip=True).split()))
                    if not txt or len(txt) <= 3:
                        continue

                    txt = deduplicate_repeated_text(txt) or txt
                    teams = extract_teams_from_title(txt)

                    # Extract context status
                    parent_txt = ""
                    if a.parent and a.parent.parent:
                        parent_txt = clean_text(" ".join(a.parent.parent.get_text(" ", strip=True).split())) or ""

                    status_enum, clean_status_text = normalize_status(parent_txt or "Upcoming")

                    # If text explicitly indicates completed or live, skip from upcoming
                    if status_enum in (MatchStatusEnum.COMPLETED, MatchStatusEnum.LIVE):
                        continue

                    # Attempt date and venue parsing from parent card
                    date_val = None
                    venue_val = None
                    if parent_txt:
                        m_date = re.search(r"\b(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?|\b[A-Za-z]{3}\s+\d{1,2})\b", parent_txt)
                        if m_date:
                            date_val = m_date.group(1)

                    upcoming.append(
                        UpcomingMatchItem(
                            id=mid,
                            title=txt,
                            teams=teams,
                            status=MatchStatusEnum.UPCOMING,
                            status_text=clean_status_text or "Scheduled",
                            date=date_val,
                            venue=venue_val
                        )
                    )
            except Exception as exc:
                logger.warning("Error parsing upcoming match element: %s", exc)
                continue

        return UpcomingMatchesResponse(status="success", matches=upcoming)
