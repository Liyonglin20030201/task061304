from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, JSON,
    ForeignKey, UniqueConstraint, Index,
)
from app.database import Base


class DataQualityRule(Base):
    __tablename__ = "data_quality_rules"
    __table_args__ = (
        Index("ix_dqr_table_dimension", "target_table", "dimension"),
    )

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False)
    target_table = Column(String(50), nullable=False)
    dimension = Column(String(20), nullable=False)
    check_type = Column(String(30), nullable=False)
    column_name = Column(String(50))
    condition = Column(JSON)
    threshold_warn = Column(Float, default=0.05)
    threshold_error = Column(Float, default=0.15)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DataQualityScore(Base):
    __tablename__ = "data_quality_scores"
    __table_args__ = (
        UniqueConstraint("store_id", "target_table", "dimension", "score_date", name="uq_dqs_unique"),
        Index("ix_dqs_store_date", "store_id", "score_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    target_table = Column(String(50), nullable=False)
    dimension = Column(String(20), nullable=False)
    score_date = Column(Date, nullable=False)
    score = Column(Float, nullable=False)
    total_records = Column(Integer, default=0)
    passed_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DataQualityAlert(Base):
    __tablename__ = "data_quality_alerts"
    __table_args__ = (
        Index("ix_dqa_store_status", "store_id", "status"),
        Index("ix_dqa_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("data_quality_rules.id"), nullable=False)
    target_table = Column(String(50), nullable=False)
    dimension = Column(String(20), nullable=False)
    severity = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    metric_value = Column(Float)
    threshold_value = Column(Float)
    status = Column(String(20), default="open")
    acknowledged_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DataQualityCheckRun(Base):
    __tablename__ = "data_quality_check_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_type = Column(String(20), default="scheduled")
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    total_rules_run = Column(Integer, default=0)
    alerts_generated = Column(Integer, default=0)
    overall_score = Column(Float)
    status = Column(String(20), default="running")
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
