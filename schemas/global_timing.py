from pydantic import BaseModel
from typing import Optional


class GlobalTimingUpdate(BaseModel):
    manual_peak_override: Optional[bool] = None
    morning_start: int
    morning_end: int
    evening_start: int
    evening_end: int
    night_start: int
    night_end: int


class GlobalTimingRead(GlobalTimingUpdate):
    id: str

    class Config:
        from_attributes = True
