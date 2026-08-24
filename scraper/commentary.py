import re
from bs4 import BeautifulSoup
from .client import http_client
from .parser_utils import clean_text, safe_int
from .event_parser import EventParser
from models.commentary import CommentaryItem, CommentaryResponse, RecentEventResponse


class CommentaryScraper:
    @classmethod
    async def scrape_commentary(cls, match_id: str, innings_number: int = 1) -> CommentaryResponse:
        url = f"/live-cricket-scores/{match_id}"
        html_doc = await http_client.fetch(url)
        soup = BeautifulSoup(html_doc, "lxml")

        for m in soup.find_all(attrs={"role": "menu"}):
            m.decompose()

        commentary = []
        for p in soup.find_all(["div", "p"]):
            txt = clean_text(" ".join(p.get_text(" ", strip=True).split()))
            if not txt:
                continue

            m = re.match(
                r"^(\d+)\.(\d+)\s+(?:(OUT|WICKET|FOUR|SIX)\s+)?([A-Za-z.\'-]+\s+[A-Za-z.\'-]+)\s+to\s+([A-Za-z.\'-]+\s+[A-Za-z.\'-]+),\s*(.*)",
                txt
            )
            if m:
                over_num = safe_int(m.group(1), 0)
                ball_num = safe_int(m.group(2), 1)
                event_tag = m.group(3)
                bowler_name = m.group(4).strip()
                batsman_name = m.group(5).strip()

                event_type, runs_val, dismissal_info = EventParser.parse_delivery_event(txt, event_tag)
                event_id = EventParser.generate_event_id(match_id, innings_number, over_num, ball_num, txt)

                item = CommentaryItem(
                    event_id=event_id,
                    over=over_num,
                    ball=ball_num,
                    event=event_type,
                    runs=runs_val,
                    batsman=batsman_name,
                    bowler=bowler_name,
                    text=txt,
                    dismissed_batsman=dismissal_info.get("dismissed_batsman"),
                    dismissal_type=dismissal_info.get("dismissal_type"),
                    fielder=dismissal_info.get("fielder"),
                    dismissal_text=dismissal_info.get("dismissal_text"),
                )
                if not any(x.event_id == event_id for x in commentary):
                    commentary.append(item)

        return CommentaryResponse(status="success", commentary=commentary)

    @classmethod
    async def scrape_recent_events(cls, match_id: str) -> RecentEventResponse:
        comm_res = await cls.scrape_commentary(match_id)
        items = comm_res.commentary
        latest = items[0] if items else None
        recent_balls = items[:6] if items else []
        return RecentEventResponse(status="success", latest=latest, recent_balls=recent_balls)
