from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.sql import func
from app.database import Base


class AssociationRule(Base):
    __tablename__ = "association_rules"
    __table_args__ = (
        Index("ix_assoc_store_period", "store_id", "period_start", "period_end"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    antecedent_items = Column(JSON, nullable=False)
    consequent_items = Column(JSON, nullable=False)
    antecedent_names = Column(JSON)
    consequent_names = Column(JSON)
    support = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    lift = Column(Float, nullable=False)
    conviction = Column(Float, nullable=True)
    leverage = Column(Float, nullable=True)
    transaction_count = Column(Integer)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    category_filter = Column(String(50), nullable=True)
    computed_at = Column(DateTime, server_default=func.now())


class AssociationAnalysisJob(Base):
    __tablename__ = "association_analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    min_support = Column(Float, nullable=False)
    min_confidence = Column(Float, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    category_filter = Column(String(50), nullable=True)
    min_transactions = Column(Integer, default=2)
    status = Column(String(20), default="pending")
    rules_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
