import re
import logging
from bs4 import BeautifulSoup
from .client import http_client
from .selectors import find_first_matching, find_all_matching
from .parser_utils import (
    clean_text,
    safe_int,
    safe_float,
    expand_team_name,
    extract_teams_from_title,
    build_clean_title,
    deduplicate_repeated_text,
)
from .normalizer import normalize_status
from services.cricket_math import calculate_run_rate, validate_runs, validate_wickets
from models.match import MatchInfo, MatchOverviewResponse
from models.score import ScoreInfo

logger = logging.getLogger("cricket.match_scraper")


class MatchOverviewScraper:
    @classmethod
    async def scrape_match_overview(cls, match_id: str) -> MatchOverviewResponse:
        url = f"/live-cricket-scores/{match_id}"
        html_doc = await http_client.fetch(url)
        soup = BeautifulSoup(html_doc, "lxml")

        # Clean dropdowns / role menus
        for d in soup.find_all(attrs={"role": "menu"}):
            try:
                d.decompose()
            except Exception:
                pass

        # 1. Title Extraction
        raw_title = soup.title.get_text(strip=True) if soup.title else None
        clean_title_str = clean_text(raw_title)
        if clean_title_str:
            clean_title_str = re.sub(r"^Cricket commentary\s*\|\s*", "", clean_title_str, flags=re.IGNORECASE)
            clean_title_str = re.sub(r"\s*-\s*Commentary$", "", clean_title_str, flags=re.IGNORECASE).strip()
            clean_title_str = deduplicate_repeated_text(clean_title_str) or clean_title_str

        # 2. Team Extraction
        teams = extract_teams_from_title(clean_title_str)

        # 3. Venue Extraction
        venue = None
        venue_tag = find_first_matching(soup, "venue")
        if venue_tag:
            venue = clean_text(venue_tag.get_text(" ", strip=True))
            venue = deduplicate_repeated_text(venue)

        # 4. Date Extraction
        date_str = None
        for meta_item in soup.find_all("meta"):
            name_attr = meta_item.get("name", "").lower()
            prop_attr = meta_item.get("property", "").lower()
            if "date" in name_attr or "date" in prop_attr or "time" in prop_attr:
                val = meta_item.get("content")
                if val:
                    date_str = clean_text(val)
                    break

        # 5. Status Extraction & Normalization
        raw_status_text = None
        status_tag = find_first_matching(soup, "status")
        if status_tag:
            raw_status_text = clean_text(status_tag.get_text(" ", strip=True))

        if not raw_status_text:
            for d in soup.find_all(["div", "span"]):
                try:
                    txt = clean_text(d.get_text(" ", strip=True))
                    if txt and any(
                        k in txt.lower()
                        for k in ["stumps", "trail by", "lead by", "won by", "opt to", "break", "rain", "delay", "abandon"]
                    ):
                        if len(txt) < 100 and "Series:" not in txt and "Matches" not in txt:
                            raw_status_text = txt
                            break
                except Exception:
                    continue

        status_enum, clean_status_text = normalize_status(raw_status_text)

        # 6. Score Extraction
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
            runs = validate_runs(safe_int(s_match.group(2)))
            wickets = validate_wickets(safe_int(s_match.group(3)))
            overs = safe_float(s_match.group(4))

        run_rate = calculate_run_rate(runs, overs)
        if run_rate is None:
            crr_m = re.search(r"CRR:\s*([\d.]+)", soup.get_text())
            if crr_m:
                run_rate = safe_float(crr_m.group(1))

        team_full = expand_team_name(team_abbr, clean_title_str) if team_abbr else None

        final_title = build_clean_title(teams) if teams else (clean_title_str or "Cricket Match")

        match_info = MatchInfo(
            id=match_id,
            title=final_title,
            venue=venue,
            date=date_str,
            status=status_enum,
            status_text=clean_status_text,
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
            data_status="fresh",
            match=match_info,
            score=score_info
        )
