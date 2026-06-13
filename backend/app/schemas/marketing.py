from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime


class CampaignCreate(BaseModel):
    name: str
    campaign_type: str
    trigger_type: str = "auto"
    trigger_condition: Optional[dict] = None
    target_segment: Optional[str] = None
    message_template: Optional[str] = None
    channel: str = "sms"
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    budget: float = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    trigger_condition: Optional[dict] = None
    target_segment: Optional[str] = None
    message_template: Optional[str] = None
    channel: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    budget: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CampaignStatusUpdate(BaseModel):
    status: str


class CampaignResponse(BaseModel):
    id: int
    name: str
    campaign_type: str
    trigger_type: str
    trigger_condition: Optional[dict] = None
    target_segment: Optional[str] = None
    message_template: Optional[str] = None
    channel: str
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    budget: float
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    stats: Optional[dict] = None

    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    name: str
    rule_type: str
    conditions: Optional[dict] = None
    priority: int = 0
    campaign_id: Optional[int] = None
    cooldown_days: int = 7
    max_triggers_per_member: int = 3


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[dict] = None
    priority: Optional[int] = None
    is_active: Optional[int] = None
    cooldown_days: Optional[int] = None
    max_triggers_per_member: Optional[int] = None


class RuleResponse(BaseModel):
    id: int
    name: str
    rule_type: str
    conditions: Optional[dict] = None
    priority: int
    campaign_id: Optional[int] = None
    is_active: int
    cooldown_days: int
    max_triggers_per_member: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignAnalyticsResponse(BaseModel):
    campaign_id: int
    period_date: date
    total_targeted: int
    total_sent: int
    total_delivered: int
    total_opened: int
    total_converted: int
    total_revenue: float
    total_cost: float
    roi: float
    conversion_rate: float = 0
    open_rate: float = 0

    class Config:
        from_attributes = True


class LifecycleDistribution(BaseModel):
    stage: str
    count: int
    percentage: float


class MarketingDashboard(BaseModel):
    active_campaigns: int
    members_reached_month: int
    avg_conversion_rate: float
    total_roi: float
    lifecycle_distribution: List[LifecycleDistribution]


class TriggerEvaluationResult(BaseModel):
    campaign_id: int
    campaign_name: str
    triggered_members: int
    trigger_type: str
