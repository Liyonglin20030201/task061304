from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class MemberCreate(BaseModel):
    member_no: str
    name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    register_date: date
    register_store_id: Optional[int] = None
    level: str = "normal"


class MemberResponse(BaseModel):
    id: int
    member_no: str
    name: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    birthday: Optional[date]
    register_date: date
    level: str
    total_points: int
    tags: List[str] = []
    rfm_segment: Optional[str]
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True
