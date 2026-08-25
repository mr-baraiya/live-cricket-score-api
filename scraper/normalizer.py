import re
from typing import Optional, Tuple


class MatchStatusEnum:
    LIVE = "LIVE"
    UPCOMING = "UPCOMING"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    ABANDONED = "ABANDONED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


def normalize_status(raw_status: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Normalizes a raw status string into a tuple of (status_enum, clean_status_text).
    Example:
      "Stumps" -> ("COMPLETED", "Stumps")
      "India won by 6 wickets" -> ("COMPLETED", "India won by 6 wickets")
      "Delayed due to rain" -> ("DELAYED", "Delayed due to rain")
    """
    if not raw_status:
        return MatchStatusEnum.UNKNOWN, None

    clean = " ".join(raw_status.strip().split())
    if not clean:
        return MatchStatusEnum.UNKNOWN, None

    lower = clean.lower()

    # 1. Check for Completed status
    completed_keywords = [
        "stumps", "won by", "won", "lost by", "lost", "completed",
        "finished", "concluded", "drawn", "match drawn", "tie", "tied"
    ]
    if any(k in lower for k in completed_keywords):
        return MatchStatusEnum.COMPLETED, clean

    # 2. Check for Abandoned / Cancelled
    if any(k in lower for k in ["abandoned", "no result", "n/r"]):
        return MatchStatusEnum.ABANDONED, clean
    if "cancelled" in lower or "canceled" in lower:
        return MatchStatusEnum.CANCELLED, clean

    # 3. Check for Delayed / Interruptions
    if any(k in lower for k in ["delayed", "delay", "rain", "wet outfield", "bad light"]):
        return MatchStatusEnum.DELAYED, clean

    # 4. Check for Live status
    live_keywords = [
        "live", "in progress", "innings break", "break", "lunch", "tea",
        "opt to", "trail by", "lead by", "need ", "overs left", "day "
    ]
    if any(k in lower for k in live_keywords):
        return MatchStatusEnum.LIVE, clean

    # 5. Check for Upcoming status
    upcoming_keywords = [
        "upcoming", "scheduled", "preview", "starts in", "starts at",
        "yet to start", "match starts", "pm", "am", "gmt", "ist"
    ]
    if any(k in lower for k in upcoming_keywords):
        return MatchStatusEnum.UPCOMING, clean

    # Fallback default
    return MatchStatusEnum.LIVE, clean


def is_live_status(status_enum: str) -> bool:
    return status_enum in (MatchStatusEnum.LIVE, MatchStatusEnum.DELAYED)


def is_upcoming_status(status_enum: str) -> bool:
    return status_enum == MatchStatusEnum.UPCOMING
