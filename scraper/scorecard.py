import re
from bs4 import BeautifulSoup
from .client import http_client
from .selectors import find_all_matching
from .parser_utils import clean_text, safe_int, safe_float
from models.match import ScorecardResponse, InningsInfo
from models.player import Batsman, Bowler


class ScorecardScraper:
    @classmethod
    async def scrape_scorecard(cls, match_id: str) -> ScorecardResponse:
        url = f"/live-cricket-scores/{match_id}"
        html_doc = await http_client.fetch(url)
        soup = BeautifulSoup(html_doc, "lxml")

        for m in soup.find_all(attrs={"role": "menu"}):
            m.decompose()

        grids = find_all_matching(soup, "score_grid")
        current_section = None
        batsmen = []
        bowlers = []

        for g in grids:
            txt = g.get_text(" | ", strip=True)
            if "Batter" in txt and "R" in txt:
                current_section = "batsmen"
                continue
            elif "Bowler" in txt and "O" in txt:
                current_section = "bowlers"
                continue
            elif any(k in txt for k in ["Key Stats", "Partnership", "Last Wkt", "Last Wicket"]):
                current_section = None
                continue

            children = [c for c in g.children if getattr(c, "name", None)]
            if not children:
                continue

            first_col = children[0]
            raw_name = clean_text(" ".join(first_col.get_text(" ", strip=True).split()))
            if not raw_name:
                continue

            is_active = "*" in raw_name
            clean_name = raw_name.replace("*", "").strip()

            if current_section == "batsmen":
                runs = safe_int(children[1].get_text(strip=True)) if len(children) >= 2 else None
                balls = safe_int(children[2].get_text(strip=True)) if len(children) >= 3 else None
                fours = safe_int(children[3].get_text(strip=True)) if len(children) >= 4 else None
                sixes = safe_int(children[4].get_text(strip=True)) if len(children) >= 5 else None
                sr = safe_float(children[5].get_text(strip=True)) if len(children) >= 6 else None

                # Check dismissal text if available in next cell or child
                dismissal = None
                if len(children) > 1 and not is_active:
                    possible_d = clean_text(children[1].get_text(strip=True))
                    if possible_d and not possible_d.isdigit():
                        dismissal = possible_d

                batsmen.append(
                    Batsman(
                        name=clean_name,
                        runs=runs,
                        balls=balls,
                        fours=fours,
                        sixes=sixes,
                        strike_rate=sr,
                        dismissal=dismissal,
                        active=is_active
                    )
                )

            elif current_section == "bowlers":
                if len(children) >= 6:
                    bowlers.append(
                        Bowler(
                            name=clean_name,
                            overs=safe_float(children[1].get_text(strip=True)),
                            maidens=safe_int(children[2].get_text(strip=True)),
                            runs=safe_int(children[3].get_text(strip=True)),
                            wickets=safe_int(children[4].get_text(strip=True)),
                            economy=safe_float(children[5].get_text(strip=True))
                        )
                    )

        current_batsmen = [b for b in batsmen if b.active]
        current_bowler = bowlers[0] if bowlers else None

        partnership = None
        last_wicket = None
        toss = None

        for d in soup.find_all(["div", "p"]):
            t = clean_text(" ".join(d.get_text(" ", strip=True).split()))
            if not t:
                continue
            if "Partnership:" in t:
                p_val = t.split("Partnership:")[-1].split("Last Wkt")[0].strip()
                p_val = re.sub(r"\s*\(\s*", "(", p_val)
                p_val = re.sub(r"\s*\)\s*", ")", p_val)
                partnership = p_val
            if "Last Wkt:" in t or "Last Wicket:" in t:
                lw_val = t.split("Last Wkt:")[-1] if "Last Wkt:" in t else t.split("Last Wicket:")[-1]
                lw_val = lw_val.split("Toss:")[0].strip()
                lw_match = re.match(
                    r"^([A-Za-z\s.'-]+?)(?:\s+lbw|\s+b\s+|\s+c\s+|\s+run out|\s+st|\s+\d|\s+-|$)",
                    lw_val
                )
                if lw_match:
                    last_wicket = lw_match.group(1).strip()
                else:
                    last_wicket = lw_val
            if "Toss:" in t:
                toss_val = t.split("Toss:")[-1].strip()
                toss = toss_val

        crr = None
        crr_m = re.search(r"CRR:\s*([\d.]+)", soup.get_text())
        if crr_m:
            crr = safe_float(crr_m.group(1))

        # Determine Innings
        innings_info = None
        og_tag = soup.find("meta", property="og:title")
        og_title = og_tag.get("content", "") if og_tag else ""
        s_match = re.search(r"([A-Za-z0-9\s]+?)\s+(\d+)/(\d+)", og_title)
        if s_match:
            batting_team_abbr = s_match.group(1).strip()
            innings_info = InningsInfo(number=1, batting_team=batting_team_abbr, bowling_team=None)

        return ScorecardResponse(
            status="success",
            batsmen=batsmen,
            current_batsmen=current_batsmen,
            bowlers=bowlers,
            current_bowler=current_bowler,
            innings=innings_info,
            partnership=partnership,
            last_wicket=last_wicket,
            toss=toss,
            crr=crr,
            rrr=None
        )
