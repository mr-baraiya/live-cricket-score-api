from typing import Optional
from pydantic import BaseModel, Field


class ScoreInfo(BaseModel):
    team: Optional[str] = None
    runs: Optional[int] = Field(default=None, ge=0)
    wickets: Optional[int] = Field(default=None, ge=0, le=10)
    overs: Optional[float] = Field(default=None, ge=0.0)
    run_rate: Optional[float] = Field(default=None, ge=0.0)
    required_run_rate: Optional[float] = Field(default=None, ge=0.0)
    target: Optional[int] = Field(default=None, ge=0)
