import re
import html
from typing import Optional, Any


def clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(text.split())
    for extra in ["View match performance", "View profile"]:
        cleaned = cleaned.replace(extra, "").strip()
    cleaned = " ".join(cleaned.split())
    return html.unescape(cleaned) if cleaned else None


def safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    if val is None:
        return default
    try:
        s = str(val).strip()
        digits = re.sub(r"[^\d-]", "", s)
        if not digits:
            return default
        return int(digits)
    except Exception:
        return default


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None:
        return default
    try:
        s = str(val).strip()
        m = re.search(r"[-+]?\d*\.?\d+", s)
        if not m:
            return default
        return float(m.group(0))
    except Exception:
        return default


def expand_team_name(team_abbr: Optional[str], title: Optional[str]) -> Optional[str]:
    if not team_abbr or not title:
        return team_abbr
    teams_part = title.split(",")[0]
    if " vs " in teams_part:
        teams = [t.strip() for t in teams_part.split(" vs ")]
        for t in teams:
            inits = "".join(w[0] for w in t.split() if w and w[0].isalnum()).upper()
            if team_abbr.upper() == inits or team_abbr.upper() in t.upper():
                return t
    return team_abbr


def extract_teams_from_title(title: Optional[str]) -> list[str]:
    if not title or " vs " not in title:
        return []
    match_part = title.split(",")[0].strip()
    if " vs " in match_part:
        return [t.strip() for t in match_part.split(" vs ") if t.strip()]
    return []


def categorize_ball_event(comm_text: str, event_tag: Optional[str] = None) -> str:
    text_upper = comm_text.upper() if comm_text else ""
    tag_upper = event_tag.upper() if event_tag else ""

    if "WICKET" in tag_upper or "OUT" in tag_upper:
        return "WICKET"
    if "FOUR" in tag_upper:
        return "FOUR"
    if "SIX" in tag_upper:
        return "SIX"

    # Avoid matching 'MID-WICKET'
    cleaned_for_wicket = re.sub(r"\bMID-WICKET\b|\bMID WICKET\b", "", text_upper)

    if re.search(r"\b(OUT|WICKET|LBW|BOWLED|CAUGHT|STUMPED|RUN OUT)\b", cleaned_for_wicket):
        return "WICKET"
    if re.search(r"\bWIDE\b|\bWD\b", text_upper):
        return "WIDE"
    if re.search(r"\bNO BALL\b|\bNB\b", text_upper):
        return "NO_BALL"
    if re.search(r"\bBYE\b", text_upper) and "LEG BYE" not in text_upper:
        return "BYE"
    if "LEG BYE" in text_upper:
        return "LEG_BYE"
    if re.search(r"\bFOUR\b|4 RUNS", text_upper):
        return "FOUR"
    if re.search(r"\bSIX\b|6 RUNS", text_upper):
        return "SIX"
    if re.search(r"\b3 RUNS\b|THREE", text_upper):
        return "THREE"
    if re.search(r"\b2 RUNS\b|TWO", text_upper):
        return "TWO"
    if re.search(r"\b1 RUN\b|\bSINGLE\b", text_upper):
        return "SINGLE"
    if re.search(r"\bNO RUN\b|\bDOT\b", text_upper):
        return "DOT"

    # Fallback checking number at start
    m = re.match(r"^(\d+)", comm_text.strip())
    if m:
        num = m.group(1)
        mapping = {
            "0": "DOT",
            "1": "SINGLE",
            "2": "TWO",
            "3": "THREE",
            "4": "FOUR",
            "6": "SIX",
        }
        return mapping.get(num, "UNKNOWN")

    return "UNKNOWN"
