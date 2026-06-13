from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class InventoryCreate(BaseModel):
    store_id: int
    item_id: str
    item_name: Optional[str] = None
    category: Optional[str] = None
    quantity: float
    unit_cost: Optional[float] = None
    total_value: Optional[float] = None
    snapshot_date: date
    min_stock: float = 0
    max_stock: Optional[float] = None


class InventoryResponse(BaseModel):
    id: int
    store_id: int
    item_id: str
    item_name: Optional[str]
    category: Optional[str]
    quantity: float
    unit_cost: Optional[float]
    total_value: Optional[float]
    snapshot_date: date
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
