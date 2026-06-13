from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class ReplenishmentSuggestionResponse(BaseModel):
    id: int
    store_id: int
    item_id: str
    item_name: str
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    current_stock: int
    safety_stock: int
    reorder_point: int
    suggested_qty: int
    optimal_order_date: Optional[date] = None
    estimated_cost: float
    bulk_discount_applied: int
    demand_velocity: float
    status: str
    created_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReplenishmentConfigUpdate(BaseModel):
    service_level: Optional[float] = None
    review_period_days: Optional[int] = None
    max_stock_days: Optional[int] = None
    weather_sensitivity: Optional[float] = None
    promo_boost_factor: Optional[float] = None


class ReplenishmentConfigResponse(BaseModel):
    id: int
    store_id: int
    item_id: str
    service_level: float
    review_period_days: int
    max_stock_days: int
    weather_sensitivity: float
    promo_boost_factor: float

    class Config:
        from_attributes = True


class GenerateSuggestionsRequest(BaseModel):
    store_id: int
    item_ids: Optional[List[str]] = None


class ApproveSuggestionRequest(BaseModel):
    pass


class ReplenishmentDashboard(BaseModel):
    items_below_rop: int
    coverage_rate: float
    pending_orders_value: float
    pending_count: int
    approved_count: int
    urgent_items: List[dict]


class ReplenishmentTimeline(BaseModel):
    item_id: str
    item_name: str
    current_stock: int
    daily_consumption: float
    days_until_stockout: int
    reorder_date: Optional[date] = None
    delivery_date: Optional[date] = None
