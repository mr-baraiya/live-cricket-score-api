from typing import Optional
from pydantic import BaseModel, Field


class Batsman(BaseModel):
    name: str
    runs: Optional[int] = Field(default=None, ge=0)
    balls: Optional[int] = Field(default=None, ge=0)
    fours: Optional[int] = Field(default=None, ge=0)
    sixes: Optional[int] = Field(default=None, ge=0)
    strike_rate: Optional[float] = Field(default=None, ge=0.0)
    dismissal: Optional[str] = None
    active: bool = False


class Bowler(BaseModel):
    name: str
    overs: Optional[float] = Field(default=None, ge=0.0)
    maidens: Optional[int] = Field(default=None, ge=0)
    runs: Optional[int] = Field(default=None, ge=0)
    wickets: Optional[int] = Field(default=None, ge=0, le=10)
    economy: Optional[float] = Field(default=None, ge=0.0)
