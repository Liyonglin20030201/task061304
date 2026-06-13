from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class SaleCreate(BaseModel):
    store_id: int
    sale_date: date
    sale_time: Optional[datetime] = None
    receipt_no: str
    item_id: str
    item_name: Optional[str] = None
    category: Optional[str] = None
    quantity: float
    unit_price: float
    total_amount: float
    discount_amount: float = 0
    payment_method: Optional[str] = None
    member_id: Optional[int] = None


class SaleResponse(BaseModel):
    id: int
    store_id: int
    sale_date: date
    receipt_no: str
    item_id: str
    item_name: Optional[str]
    category: Optional[str]
    quantity: float
    unit_price: float
    total_amount: float
    discount_amount: float
    payment_method: Optional[str]
    member_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class SaleFilter(BaseModel):
    store_ids: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
