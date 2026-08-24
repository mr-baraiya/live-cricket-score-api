import logging
from typing import Dict, Any, Optional
from models.commentary import ChangeDetectionResult, CommentaryItem

logger = logging.getLogger("cricbuzz.change_detector")


class ChangeDetector:
    def __init__(self):
        # Store state per match_id: {"last_event_id": str, "runs": int, "wickets": int}
        self._history: Dict[str, Dict[str, Any]] = {}

    def detect_changes(
        self,
        match_id: str,
        current_data: Dict[str, Any],
        latest_commentary: Optional[CommentaryItem] = None
    ) -> ChangeDetectionResult:
        if match_id not in self._history:
            self._history[match_id] = {
                "last_event_id": latest_commentary.event_id if latest_commentary else None,
            }
            return ChangeDetectionResult(
                changed=False,
                event=None,
                over=None,
                ball=None,
                event_id=None,
                details=["Initial match state cached"]
            )

        prev = self._history[match_id]
        prev_event_id = prev.get("last_event_id")

        if latest_commentary and latest_commentary.event_id != prev_event_id:
            prev["last_event_id"] = latest_commentary.event_id
            details = [f"New delivery: {latest_commentary.over}.{latest_commentary.ball} ({latest_commentary.event})"]
            if latest_commentary.runs is not None:
                details.append(f"{latest_commentary.runs} runs")

            return ChangeDetectionResult(
                changed=True,
                event=latest_commentary.event,
                over=latest_commentary.over,
                ball=latest_commentary.ball,
                event_id=latest_commentary.event_id,
                details=details
            )

        return ChangeDetectionResult(
            changed=False,
            event=None,
            over=None,
            ball=None,
            event_id=None,
            details=["No new delivery"]
        )


change_detector = ChangeDetector()
