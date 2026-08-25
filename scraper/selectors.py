import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger("cricket.selectors")

# Centralized Selector Dictionary with Primary & Fallback Selectors
SELECTORS: Dict[str, List[Dict[str, Any]]] = {
    "live_matches": [
        {"name": "score_card_link", "type": "css", "value": "a[href*='/live-cricket-scores/']"},
        {"name": "match_facts_link", "type": "css", "value": "a[href*='/cricket-match-facts/']"},
        {"name": "general_link", "type": "css", "value": "a[href*='/cricket-scores/']"},
    ],
    "upcoming_matches": [
        {"name": "preview_link", "type": "css", "value": "a[href*='/live-cricket-scores/']"},
        {"name": "facts_link", "type": "css", "value": "a[href*='/cricket-match-facts/']"},
    ],
    "score_grid": [
        {"name": "bat_grid", "type": "class_contains", "value": "scorecard-bat-grid"},
        {"name": "min_bat_rw", "type": "class_contains", "value": "cb-min-bat-rw"},
        {"name": "col_100", "type": "class_contains", "value": "cb-col-100"},
    ],
    "venue": [
        {"name": "venue_link", "type": "css", "value": "a[href*='/venues/']"},
        {"name": "venue_span", "type": "class_contains", "value": "cb-venue"},
    ],
    "status": [
        {"name": "live_text", "type": "class_contains", "value": "text-cbTxtLive"},
        {"name": "status_text", "type": "class_contains", "value": "cb-text-complete"},
        {"name": "red_text", "type": "class_contains", "value": "text-cbRed"},
    ],
    "dropdown_menu": [
        {"name": "role_menu", "type": "attrs", "value": {"role": "menu"}},
        {"name": "menu_class", "type": "class_contains", "value": "cb-menu"},
    ],
}


def find_first_matching(soup: BeautifulSoup, selector_key: str) -> Optional[Tag]:
    if selector_key not in SELECTORS:
        logger.error("Selector key '%s' not registered in SELECTORS dictionary", selector_key)
        return None

    selectors = SELECTORS[selector_key]
    for idx, s in enumerate(selectors):
        tag = None
        stype = s.get("type")
        sval = s.get("value")

        if stype == "css":
            tag = soup.select_one(sval)
        elif stype == "class_contains":
            tag = soup.find(class_=lambda c: c and sval in c)
        elif stype == "attrs":
            tag = soup.find(attrs=sval)

        if tag:
            if idx > 0:
                logger.warning(
                    "[SCRAPER WARNING] Primary selector for '%s' failed. Used fallback selector #%d (%s: %s)",
                    selector_key, idx + 1, stype, sval
                )
            return tag

    logger.warning("[SCRAPER WARNING] All selectors failed for '%s'", selector_key)
    return None


def find_all_matching(soup: BeautifulSoup, selector_key: str) -> List[Tag]:
    if selector_key not in SELECTORS:
        logger.error("Selector key '%s' not registered in SELECTORS dictionary", selector_key)
        return []

    selectors = SELECTORS[selector_key]
    for idx, s in enumerate(selectors):
        tags = []
        stype = s.get("type")
        sval = s.get("value")

        if stype == "css":
            tags = soup.select(sval)
        elif stype == "class_contains":
            tags = soup.find_all(class_=lambda c: c and sval in c)
        elif stype == "attrs":
            tags = soup.find_all(attrs=sval)

        if tags:
            if idx > 0:
                logger.warning(
                    "[SCRAPER WARNING] Primary selector for '%s' failed. Used fallback selector #%d (%s: %s)",
                    selector_key, idx + 1, stype, sval
                )
            return tags

    logger.warning("[SCRAPER WARNING] All selectors failed for '%s'", selector_key)
    return []
