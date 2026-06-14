from pydantic import BaseModel
from typing import List, Optional


class ChannelKPI(BaseModel):
    channel: str
    gmv: float
    order_count: int
    avg_ticket: float
    member_count: int
    growth_rate_pct: Optional[float] = None

    class Config:
        from_attributes = True


class ChannelKPIComparison(BaseModel):
    period: str
    channels: List[ChannelKPI]
    total_gmv: float
    total_orders: int

    class Config:
        from_attributes = True


class ChannelTrendPoint(BaseModel):
    date: str
    channel: str
    gmv: float
    order_count: int

    class Config:
        from_attributes = True


class AttributionResult(BaseModel):
    channel: str
    attributed_gmv: float
    attributed_orders: int
    weight: float

    class Config:
        from_attributes = True


class FunnelStep(BaseModel):
    step_name: str
    count: int
    conversion_rate: Optional[float] = None

    class Config:
        from_attributes = True


class ChannelFunnel(BaseModel):
    channel: str
    steps: List[FunnelStep]

    class Config:
        from_attributes = True


class MemberChannelBehavior(BaseModel):
    member_id: int
    events: List[dict]
    channels_used: List[str]
    total_spend_by_channel: dict
    first_channel: str
    last_channel: str

    class Config:
        from_attributes = True


class MemberOverlap(BaseModel):
    online_only: int
    offline_only: int
    both_channels: int
    o2o_members: int
    total_members: int

    class Config:
        from_attributes = True


class ChannelInventoryItem(BaseModel):
    item_id: str
    item_name: Optional[str] = None
    online_available: float
    offline_available: float
    online_reserved: float
    offline_reserved: float

    class Config:
        from_attributes = True


class UnifiedMemberStats(BaseModel):
    total_members: int
    cross_channel_pct: float
    avg_ltv: float
    by_channel: List[dict]

    class Config:
        from_attributes = True
