from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ZoneCreate(BaseModel):
    store_id: int
    zone_code: str
    zone_name: str
    area_sqm: float
    floor: Optional[int] = 1
    zone_type: Optional[str] = None
    category_assignment: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class ZoneUpdate(BaseModel):
    zone_code: Optional[str] = None
    zone_name: Optional[str] = None
    area_sqm: Optional[float] = None
    floor: Optional[int] = None
    zone_type: Optional[str] = None
    category_assignment: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class ZoneResponse(BaseModel):
    id: int
    store_id: int
    zone_code: str
    zone_name: str
    area_sqm: float
    floor: Optional[int] = None
    zone_type: Optional[str] = None
    category_assignment: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    is_active: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ZoneKPI(BaseModel):
    zone_id: int
    zone_name: str
    zone_type: Optional[str] = None
    area_sqm: float
    revenue: float
    transaction_count: int
    items_sold: float
    traffic_count: int
    revenue_per_sqm: float
    items_per_sqm: float
    traffic_conversion: float


class HeatmapCell(BaseModel):
    zone_id: int
    zone_name: str
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    intensity: float
    revenue: float


class ZoneRanking(BaseModel):
    zone_id: int
    zone_name: str
    store_name: str
    zone_type: Optional[str] = None
    metric_value: float
    rank: int


class ZoneTrend(BaseModel):
    date: str
    revenue: float
    transaction_count: int
    items_sold: float
    revenue_per_sqm: float


class LayoutRecommendation(BaseModel):
    zone_id: int
    zone_name: str
    current_performance: str
    issue: str
    suggestion: str
    estimated_impact: str
    priority: str


class ZoneItemMappingCreate(BaseModel):
    zone_id: int
    category: str
    item_id: Optional[str] = None


class FloorPlanCreate(BaseModel):
    store_id: int
    floor: int = 1
    plan_width: float
    plan_height: float
    image_url: Optional[str] = None


class FloorPlanResponse(BaseModel):
    id: int
    store_id: int
    floor: int
    plan_width: float
    plan_height: float
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class HeatmapResponse(BaseModel):
    plan_width: float
    plan_height: float
    cells: List[HeatmapCell]
