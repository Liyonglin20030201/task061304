from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, UniqueConstraint, Index,
)
from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_product_item_id"),
        Index("ix_products_category", "category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(50), nullable=False, unique=True)
    item_name = Column(String(100), nullable=False)
    category = Column(String(50))
    subcategory = Column(String(50))
    brand = Column(String(50))
    unit_cost = Column(Float)
    launch_date = Column(Date)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProductLifecycleSnapshot(Base):
    __tablename__ = "product_lifecycle_snapshots"
    __table_args__ = (
        UniqueConstraint("product_id", "snapshot_week", "store_id", name="uq_plc_snap"),
        Index("ix_plc_snap_product_week", "product_id", "snapshot_week"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    snapshot_week = Column(Date, nullable=False)
    stage = Column(String(20), nullable=False)
    weekly_revenue = Column(Float, default=0)
    weekly_quantity = Column(Integer, default=0)
    growth_rate = Column(Float)
    adoption_rate = Column(Float)
    market_share = Column(Float)
    margin_rate = Column(Float)
    velocity = Column(Float)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProductRetirementRecommendation(Base):
    __tablename__ = "product_retirement_recommendations"
    __table_args__ = (
        Index("ix_prr_product", "product_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    recommendation = Column(String(30))
    confidence = Column(Float)
    reason = Column(String(500))
    impact_revenue_loss = Column(Float)
    impact_margin_saved = Column(Float)
    remaining_inventory = Column(Float)
    suggested_action_date = Column(Date)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
