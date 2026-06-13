from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    campaign_type = Column(String(30), nullable=False)
    trigger_type = Column(String(20), default="auto")
    trigger_condition = Column(JSON)
    target_segment = Column(String(50))
    message_template = Column(Text)
    channel = Column(String(20), default="sms")
    discount_type = Column(String(20))
    discount_value = Column(Float)
    budget = Column(Float, default=0)
    status = Column(String(20), default="draft")
    start_date = Column(Date)
    end_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


class CampaignExecution(Base):
    __tablename__ = "campaign_executions"
    __table_args__ = (
        Index("ix_exec_campaign_member", "campaign_id", "member_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("marketing_campaigns.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"))
    triggered_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime)
    channel = Column(String(20))
    message_content = Column(Text)
    status = Column(String(20), default="pending")
    converted_at = Column(DateTime)
    conversion_amount = Column(Float)
    error_message = Column(Text)


class MarketingRule(Base):
    __tablename__ = "marketing_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    rule_type = Column(String(30), nullable=False)
    conditions = Column(JSON)
    priority = Column(Integer, default=0)
    campaign_id = Column(Integer, ForeignKey("marketing_campaigns.id"))
    is_active = Column(Integer, default=1)
    cooldown_days = Column(Integer, default=7)
    max_triggers_per_member = Column(Integer, default=3)
    created_at = Column(DateTime, server_default=func.now())


class CampaignAnalytics(Base):
    __tablename__ = "campaign_analytics"
    __table_args__ = (
        UniqueConstraint("campaign_id", "period_date", name="uq_campaign_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("marketing_campaigns.id"), nullable=False)
    period_date = Column(Date, nullable=False)
    total_targeted = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_converted = Column(Integer, default=0)
    total_revenue = Column(Float, default=0)
    total_cost = Column(Float, default=0)
    roi = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
