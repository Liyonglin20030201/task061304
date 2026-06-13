from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class ReplenishmentSuggestion(Base):
    __tablename__ = "replenishment_suggestions"
    __table_args__ = (
        Index("ix_repl_store_status", "store_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    current_stock = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    suggested_qty = Column(Integer, nullable=False)
    optimal_order_date = Column(Date)
    estimated_cost = Column(Float, default=0)
    bulk_discount_applied = Column(Integer, default=0)
    demand_velocity = Column(Float, default=0)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)


class ReplenishmentConfig(Base):
    __tablename__ = "replenishment_config"
    __table_args__ = (
        UniqueConstraint("store_id", "item_id", name="uq_repl_config"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    service_level = Column(Float, default=0.95)
    review_period_days = Column(Integer, default=7)
    max_stock_days = Column(Integer, default=30)
    weather_sensitivity = Column(Float, default=0.1)
    promo_boost_factor = Column(Float, default=1.3)
