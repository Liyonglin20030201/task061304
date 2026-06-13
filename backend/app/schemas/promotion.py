from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class PromotionCreate(BaseModel):
    store_id: int
    promo_code: str
    name: str
    promo_type: str
    start_date: date
    end_date: date
    discount_rate: Optional[float] = None
    discount_amount: Optional[float] = None
    min_purchase: float = 0
    target_category: Optional[str] = None
    budget: Optional[float] = None


class PromotionResponse(BaseModel):
    id: int
    store_id: int
    promo_code: str
    name: str
    promo_type: str
    start_date: date
    end_date: date
    discount_rate: Optional[float]
    discount_amount: Optional[float]
    min_purchase: float
    target_category: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
