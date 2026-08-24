import re
from bs4 import BeautifulSoup
from .client import http_client
from .selectors import find_all_matching
from .parser_utils import clean_text, extract_teams_from_title
from models.match import LiveMatchItem, LiveMatchesResponse, UpcomingMatchItem, UpcomingMatchesResponse


class MatchesScraper:
    @classmethod
    async def scrape_live_matches(cls) -> LiveMatchesResponse:
        html_doc = await http_client.fetch("/cricket-match/live-scores")
        soup = BeautifulSoup(html_doc, "lxml")
        matches = []

        links = find_all_matching(soup, "live_matches")
        for a in links:
            href = a.get("href", "")
            m = re.search(r"/live-cricket-scores/(\d+)/([^/]+)", href)
            if not m:
                continue

            mid = m.group(1)
            slug = m.group(2)
            title_attr = clean_text(a.get("title", ""))
            if not title_attr:
                title_attr = slug.replace("-", " ").title()

            clean_title = title_attr.split(" - ")[0].strip()
            teams = extract_teams_from_title(clean_title)

            status_str = "Live"
            parent_txt = clean_text(
                " ".join(a.parent.parent.get_text(" ", strip=True).split())
            ) if a.parent and a.parent.parent else ""

            if parent_txt:
                if "Stumps" in parent_txt:
                    status_str = "Stumps"
                elif "won" in parent_txt.lower():
                    status_str = "Completed"

            if not any(x.id == mid for x in matches) and len(clean_title) > 3:
                matches.append(
                    LiveMatchItem(
                        id=mid,
                        title=clean_title,
                        teams=teams,
                        status=status_str,
                        url=f"https://www.cricbuzz.com{href}"
                    )
                )

        return LiveMatchesResponse(status="success", matches=matches)

    @classmethod
    async def scrape_upcoming_matches(cls) -> UpcomingMatchesResponse:
        html_doc = await http_client.fetch("/cricket-schedule/upcoming-series/international")
        soup = BeautifulSoup(html_doc, "lxml")
        upcoming = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/cricket-match-facts/" in href or "/live-cricket-scores/" in href:
                m = re.search(r"/(\d+)/", href)
                if m:
                    mid = m.group(1)
                    txt = clean_text(" ".join(a.get_text(" ", strip=True).split()))
                    if txt and not any(x.id == mid for x in upcoming) and len(txt) > 3:
                        teams = extract_teams_from_title(txt)
                        upcoming.append(
                            UpcomingMatchItem(
                                id=mid,
                                title=txt,
                                teams=teams,
                                date=None,
                                venue=None
                            )
                        )

        return UpcomingMatchesResponse(status="success", matches=upcoming)
