import re
import html
from typing import Optional, Any, List


def clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(text.split())
    for extra in ["View match performance", "View profile"]:
        cleaned = cleaned.replace(extra, "").strip()
    cleaned = " ".join(cleaned.split())
    return html.unescape(cleaned) if cleaned else None


def deduplicate_repeated_text(text: Optional[str]) -> Optional[str]:
    """
    Removes duplicated consecutive words/tokens from scraped DOM text.
    Example: "England England Pakistan Pakistan" -> "England Pakistan"
    """
    if not text:
        return None
    words = text.strip().split()
    if not words:
        return None

    deduped = []
    for word in words:
        if not deduped or deduped[-1].lower() != word.lower():
            deduped.append(word)

    result = " ".join(deduped)
    return result if result else None


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


def clean_team_name(name: str) -> str:
    """
    Strips status noise and result text from team names.
    Example:
      "SL - Stumps" -> "SL"
      "NEZONE - EZONE won" -> "NEZONE"
      "India Women" -> "India Women"
    """
    if not name:
        return ""
    cleaned = name.strip()

    if "-" in cleaned:
        parts = cleaned.split("-")
        suffix = parts[-1].strip().lower()
        if any(k in suffix for k in ["won", "lost", "stumps", "live", "completed", "delay", "rain", "day"]):
            cleaned = "-".join(parts[:-1]).strip()

    cleaned = re.sub(r"\s+(won|lost|by\s+\d+.*|stumps)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_teams_from_title(title: Optional[str]) -> List[str]:
    """
    Safely extracts clean team names from a match title string without status text corruption.
    """
    if not title:
        return []

    clean_title = clean_text(title)
    if not clean_title:
        return []

    clean_title = re.sub(r"^Cricket commentary\s*\|\s*", "", clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r"\s*-\s*(Commentary|Stumps|Live|Scorecard)$", "", clean_title, flags=re.IGNORECASE)

    teams_part = clean_title.split(",")[0].strip()

    vs_match = re.search(r"\s+(?:vs|v)\s+", teams_part, flags=re.IGNORECASE)
    if vs_match:
        parts = re.split(r"\s+(?:vs|v)\s+", teams_part, flags=re.IGNORECASE)
        teams = [clean_team_name(p) for p in parts if p.strip()]
        return [t for t in teams if len(t) >= 2]

    return []


def expand_team_name(team_abbr: Optional[str], title: Optional[str]) -> Optional[str]:
    if not team_abbr or not title:
        return team_abbr
    teams = extract_teams_from_title(title)
    for t in teams:
        inits = "".join(w[0] for w in t.split() if w and w[0].isalnum()).upper()
        if team_abbr.upper() == inits or team_abbr.upper() in t.upper():
            return t
    return team_abbr


def build_clean_title(teams: List[str], match_details: Optional[str] = None) -> str:
    if not teams:
        return match_details if match_details else "Cricket Match"
    
    vs_str = " vs ".join(teams)
    if match_details:
        return f"{vs_str}, {match_details}"
    return vs_str


def categorize_ball_event(comm_text: str, event_tag: Optional[str] = None) -> str:
    text_upper = comm_text.upper() if comm_text else ""
    tag_upper = event_tag.upper() if event_tag else ""

    if "WICKET" in tag_upper or "OUT" in tag_upper:
        return "WICKET"
    if "FOUR" in tag_upper:
        return "FOUR"
    if "SIX" in tag_upper:
        return "SIX"

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
