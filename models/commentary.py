from typing import List, Optional
from pydantic import BaseModel, Field


class CommentaryItem(BaseModel):
    event_id: str
    over: int = Field(..., ge=0)
    ball: int = Field(..., ge=1, le=6)
    event: str  # DOT, SINGLE, TWO, THREE, FOUR, FIVE, SIX, WICKET, WIDE, NO_BALL, BYE, LEG_BYE, PENALTY, UNKNOWN
    runs: Optional[int] = None
    batsman: Optional[str] = None
    bowler: Optional[str] = None
    text: Optional[str] = None
    dismissed_batsman: Optional[str] = None
    dismissal_type: Optional[str] = None
    fielder: Optional[str] = None
    dismissal_text: Optional[str] = None


class CommentaryResponse(BaseModel):
    status: str = "success"
    commentary: List[CommentaryItem] = Field(default_factory=list)


class RecentEventResponse(BaseModel):
    status: str = "success"
    latest: Optional[CommentaryItem] = None
    recent_balls: List[CommentaryItem] = Field(default_factory=list)


class ChangeDetectionResult(BaseModel):
    changed: bool = False
    event: Optional[str] = None
    over: Optional[int] = None
    ball: Optional[int] = None
    event_id: Optional[str] = None
    details: List[str] = Field(default_factory=list)
