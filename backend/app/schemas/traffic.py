from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class TrafficCreate(BaseModel):
    store_id: int
    traffic_date: date
    hour: int
    enter_count: int
    exit_count: int = 0
    pass_by_count: int = 0
    conversion_rate: Optional[float] = None


class TrafficResponse(BaseModel):
    id: int
    store_id: int
    traffic_date: date
    hour: int
    enter_count: int
    exit_count: int
    pass_by_count: int
    conversion_rate: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
