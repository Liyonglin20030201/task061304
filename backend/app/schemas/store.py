from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StoreCreate(BaseModel):
    code: str
    name: str
    region: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    area_sqm: Optional[float] = None
    store_type: Optional[str] = None


class StoreResponse(BaseModel):
    id: int
    code: str
    name: str
    region: Optional[str]
    city: Optional[str]
    district: Optional[str]
    address: Optional[str]
    area_sqm: Optional[float]
    store_type: Optional[str]
    is_active: bool
    opened_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
