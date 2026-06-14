from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class ProductResponse(BaseModel):
    id: int
    item_id: str
    item_name: str
    category: Optional[str]
    current_stage: str
    weeks_in_stage: int
    weekly_revenue: float
    growth_rate: Optional[float]

    class Config:
        from_attributes = True


class LifecycleOverviewResponse(BaseModel):
    introduction_count: int
    growth_count: int
    maturity_count: int
    decline_count: int
    total_products: int


class LifecycleCurveResponse(BaseModel):
    product_id: int
    item_name: str
    weeks: List[str]
    revenues: List[float]
    stages: List[str]
    quantities: List[int]


class RetirementRecommendationResponse(BaseModel):
    id: int
    product_id: int
    item_name: Optional[str]
    recommendation: str
    confidence: float
    reason: Optional[str]
    impact_revenue_loss: Optional[float]
    remaining_inventory: Optional[float]
    suggested_action_date: Optional[date]

    class Config:
        from_attributes = True


class StageTransitionResponse(BaseModel):
    product_id: int
    item_name: str
    from_stage: str
    to_stage: str
    transition_date: date
