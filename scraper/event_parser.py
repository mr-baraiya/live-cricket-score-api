import re
import hashlib
from typing import Optional, Tuple, Dict, Any


class EventParser:
    @staticmethod
    def generate_event_id(match_id: str, innings: int, over: int, ball: int, text: str) -> str:
        clean_text = " ".join(text.split()) if text else ""
        hash_digest = hashlib.md5(clean_text.encode("utf-8")).hexdigest()[:6]
        return f"{match_id}-{innings}-{over}.{ball}-{hash_digest}"

    @classmethod
    def parse_delivery_event(
        cls,
        comm_text: str,
        event_tag: Optional[str] = None
    ) -> Tuple[str, Optional[int], Dict[str, Optional[str]]]:
        text_upper = comm_text.upper() if comm_text else ""
        tag_upper = event_tag.upper() if event_tag else ""

        dismissal_info: Dict[str, Optional[str]] = {
            "dismissed_batsman": None,
            "dismissal_type": None,
            "fielder": None,
            "dismissal_text": None,
        }

        # Remove MID-WICKET so it doesn't trigger false WICKET
        clean_for_wicket = re.sub(r"\bMID-WICKET\b|\bMID WICKET\b", "", text_upper)

        # 1. Check explicit WICKET dismissal first
        is_real_wicket = False
        if "WICKET" in tag_upper or "OUT" in tag_upper:
            is_real_wicket = True
        elif re.search(r"\b(OUT|WICKET)\b", clean_for_wicket) and not any(k in clean_for_wicket for k in ["NOT OUT", "APPEAL"]):
            is_real_wicket = True
        elif re.search(r"\b(C\s+[A-ZA-Z.'-]+\s+B\s+|LBW\s+B\s+|B\s+[A-ZA-Z.'-]+|\bRUN OUT\b|\bSTUMPED\b)", clean_for_wicket):
            if "APPEAL" not in clean_for_wicket and "UMPIRE'S CALL" not in clean_for_wicket and "NOT OUT" not in clean_for_wicket:
                is_real_wicket = True

        if is_real_wicket:
            dismissal_info["dismissal_text"] = comm_text
            m_c = re.search(r"\bc\s+([A-Za-z.'\s-]+?)\s+b\s+([A-Za-z.'\s-]+)", comm_text, re.I)
            if m_c:
                dismissal_info["fielder"] = m_c.group(1).strip()
                dismissal_info["dismissal_type"] = "caught"
            elif re.search(r"\blbw\b", comm_text, re.I):
                dismissal_info["dismissal_type"] = "lbw"
            elif re.search(r"\b(b|bowled)\b", comm_text, re.I):
                dismissal_info["dismissal_type"] = "bowled"
            elif re.search(r"\brun out\b", comm_text, re.I):
                dismissal_info["dismissal_type"] = "run out"
            elif re.search(r"\bstumped\b", comm_text, re.I):
                dismissal_info["dismissal_type"] = "stumped"

            m_batsman = re.search(r"^(\d+\.\d+)\s+[^to]+to\s+([A-Za-z.'\s-]+?),", comm_text)
            if m_batsman:
                dismissal_info["dismissed_batsman"] = m_batsman.group(2).strip()

            return "WICKET", 0, dismissal_info

        # 2. Explicit runs parser from commentary header line e.g., "2.5 ... 5 runs, ..." or "2.1 ... no run, ..."
        m_runs = re.search(r"^\d+\.\d+\s+[^,]+,\s*(no run|\d+\s+runs?|\d+\s+wides?|\d+\s+no-balls?|\d+\s+byes?|\d+\s+leg-byes?)", comm_text, re.I)
        run_str = m_runs.group(1).lower() if m_runs else ""

        # Extras checks
        if "wide" in text_upper or "wide" in run_str:
            num = re.search(r"(\d+)\s+wide", run_str)
            r = int(num.group(1)) if num else 1
            return "WIDE", r, dismissal_info

        if "no ball" in text_upper or "no-ball" in run_str:
            num = re.search(r"(\d+)\s+no-ball", run_str)
            r = int(num.group(1)) if num else 1
            return "NO_BALL", r, dismissal_info

        if "leg bye" in text_upper or "leg-bye" in run_str:
            num = re.search(r"(\d+)\s+leg-bye", run_str)
            r = int(num.group(1)) if num else 1
            return "LEG_BYE", r, dismissal_info

        if "bye" in text_upper or "bye" in run_str:
            num = re.search(r"(\d+)\s+bye", run_str)
            r = int(num.group(1)) if num else 1
            return "BYE", r, dismissal_info

        # Direct run matching
        if "5 runs" in run_str or "5 runs" in text_upper[:80]:
            return "FIVE", 5, dismissal_info
        if "6 runs" in run_str or "SIX" in tag_upper or "six" in run_str:
            return "SIX", 6, dismissal_info
        if "4 runs" in run_str or "FOUR" in tag_upper or "four" in run_str:
            return "FOUR", 4, dismissal_info
        if "3 runs" in run_str or "3 runs" in text_upper[:80]:
            return "THREE", 3, dismissal_info
        if "2 runs" in run_str or "2 runs" in text_upper[:80]:
            return "TWO", 2, dismissal_info
        if "1 run" in run_str or "1 run" in text_upper[:80] or "single" in text_upper[:80]:
            return "SINGLE", 1, dismissal_info
        if "no run" in run_str or "dot" in tag_upper:
            return "DOT", 0, dismissal_info

        # Fallback number at start
        m_num = re.match(r"^(\d+)", comm_text.strip())
        if m_num:
            n = int(m_num.group(1))
            mapping = {0: "DOT", 1: "SINGLE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 6: "SIX"}
            return mapping.get(n, "UNKNOWN"), n, dismissal_info

        return "UNKNOWN", None, dismissal_info
