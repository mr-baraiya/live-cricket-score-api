from typing import List, Optional
from pydantic import BaseModel, Field
from .score import ScoreInfo
from .player import Batsman, Bowler
from .commentary import CommentaryItem


class InningsInfo(BaseModel):
    number: Optional[int] = None
    batting_team: Optional[str] = None
    bowling_team: Optional[str] = None


class MatchInfo(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    venue: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None
    status_text: Optional[str] = None
    teams: List[str] = Field(default_factory=list)


class LiveMatchItem(BaseModel):
    id: str
    title: str
    teams: List[str] = Field(default_factory=list)
    status: str
    status_text: Optional[str] = None
    date: Optional[str] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    score: Optional[ScoreInfo] = None


class LiveMatchesResponse(BaseModel):
    status: str = "success"
    matches: List[LiveMatchItem] = Field(default_factory=list)


class UpcomingMatchItem(BaseModel):
    id: str
    title: str
    teams: List[str] = Field(default_factory=list)
    status: str = "UPCOMING"
    status_text: Optional[str] = None
    date: Optional[str] = None
    venue: Optional[str] = None


class UpcomingMatchesResponse(BaseModel):
    status: str = "success"
    matches: List[UpcomingMatchItem] = Field(default_factory=list)


class MatchOverviewResponse(BaseModel):
    status: str = "success"
    data_status: str = "fresh"  # "fresh", "stale", "partial"
    match: MatchInfo
    score: Optional[ScoreInfo] = None
    innings: Optional[InningsInfo] = None


class ScorecardResponse(BaseModel):
    status: str = "success"
    data_status: str = "fresh"
    batsmen: List[Batsman] = Field(default_factory=list)
    current_batsmen: List[Batsman] = Field(default_factory=list)
    bowlers: List[Bowler] = Field(default_factory=list)
    current_bowler: Optional[Bowler] = None
    innings: Optional[InningsInfo] = None
    partnership: Optional[str] = None
    last_wicket: Optional[str] = None
    extras: Optional[str] = None
    fall_of_wickets: Optional[str] = None
    toss: Optional[str] = None
    crr: Optional[float] = None
    rrr: Optional[float] = None


class FullMatchResponse(BaseModel):
    status: str = "success"
    data_status: str = "fresh"  # "fresh", "stale", "partial"
    match: MatchInfo
    score: Optional[ScoreInfo] = None
    innings: Optional[InningsInfo] = None
    batsmen: List[Batsman] = Field(default_factory=list)
    current_batsmen: List[Batsman] = Field(default_factory=list)
    bowlers: List[Bowler] = Field(default_factory=list)
    current_bowler: Optional[Bowler] = None
    partnership: Optional[str] = None
    last_wicket: Optional[str] = None
    recent_balls: List[CommentaryItem] = Field(default_factory=list)
    commentary: List[CommentaryItem] = Field(default_factory=list)
