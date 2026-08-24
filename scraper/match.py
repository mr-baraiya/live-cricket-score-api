import re
from bs4 import BeautifulSoup
from .client import http_client
from .selectors import find_first_matching, find_all_matching
from .parser_utils import clean_text, safe_int, safe_float, expand_team_name, extract_teams_from_title
from models.match import MatchInfo, MatchOverviewResponse
from models.score import ScoreInfo


class MatchOverviewScraper:
    @classmethod
    async def scrape_match_overview(cls, match_id: str) -> MatchOverviewResponse:
        url = f"/live-cricket-scores/{match_id}"
        html_doc = await http_client.fetch(url)
        soup = BeautifulSoup(html_doc, "lxml")

        dropdowns = find_all_matching(soup, "dropdown_menu")
        for d in dropdowns:
            d.decompose()

        raw_title = soup.title.get_text(strip=True) if soup.title else None
        title = clean_text(raw_title)
        if title:
            title = re.sub(r"^Cricket commentary\s*\|\s*", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s*-\s*Commentary$", "", title, flags=re.IGNORECASE).strip()

        venue = None
        venue_tag = find_first_matching(soup, "venue")
        if venue_tag:
            venue = clean_text(venue_tag.get_text(" ", strip=True))

        status_text = None
        status_tag = find_first_matching(soup, "status")
        if status_tag:
            status_text = clean_text(status_tag.get_text(" ", strip=True))

        if not status_text:
            for d in soup.find_all(["div", "span"]):
                txt = clean_text(d.get_text(" ", strip=True))
                if txt and any(
                    k in txt.lower()
                    for k in ["stumps", "trail by", "lead by", "won by", "opt to", "break", "rain"]
                ):
                    if len(txt) < 80 and "Series:" not in txt and "Matches" not in txt:
                        status_text = txt
                        break

        status_short = status_text.split(" - ")[0] if status_text else None

        og_tag = soup.find("meta", property="og:title")
        og_title = og_tag.get("content", "") if og_tag else ""

        team_abbr = None
        runs = None
        wickets = None
        overs = None

        s_match = re.search(
            r"([A-Za-z0-9\s]+?)\s+(\d+)/(\d+)\s*\(([\d.]+)\)",
            og_title
        )
        if s_match:
            team_abbr = s_match.group(1).strip()
            runs = safe_int(s_match.group(2))
            wickets = safe_int(s_match.group(3))
            overs = safe_float(s_match.group(4))

        run_rate = None
        crr_m = re.search(r"CRR:\s*([\d.]+)", soup.get_text())
        if crr_m:
            run_rate = safe_float(crr_m.group(1))

        team_full = expand_team_name(team_abbr, title) if team_abbr else None

        teams = extract_teams_from_title(title)

        match_info = MatchInfo(
            id=match_id,
            title=title,
            venue=venue,
            status=status_short,
            teams=teams
        )

        score_info = ScoreInfo(
            team=team_full,
            runs=runs,
            wickets=wickets,
            overs=overs,
            run_rate=run_rate
        )

        return MatchOverviewResponse(
            status="success",
            data_status="live",
            match=match_info,
            score=score_info
        )
