from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.sql import func
from app.database import Base


class StoreZone(Base):
    __tablename__ = "store_zones"
    __table_args__ = (
        UniqueConstraint("store_id", "zone_code", name="uq_store_zone_code"),
        Index("ix_zone_store", "store_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    zone_code = Column(String(30), nullable=False)
    zone_name = Column(String(100), nullable=False)
    area_sqm = Column(Float, nullable=False)
    floor = Column(Integer, default=1)
    zone_type = Column(String(30))
    category_assignment = Column(String(50), nullable=True)
    position_x = Column(Float, nullable=True)
    position_y = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())


class ZoneSalesDaily(Base):
    __tablename__ = "zone_sales_daily"
    __table_args__ = (
        UniqueConstraint("zone_id", "sale_date", name="uq_zone_sale_date"),
        Index("ix_zone_sales_date", "store_id", "sale_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("store_zones.id"), nullable=False)
    sale_date = Column(Date, nullable=False)
    revenue = Column(Float, default=0)
    transaction_count = Column(Integer, default=0)
    items_sold = Column(Float, default=0)
    traffic_count = Column(Integer, default=0)


class ZoneItemMapping(Base):
    __tablename__ = "zone_item_mapping"
    __table_args__ = (
        UniqueConstraint("zone_id", "category", "item_id", name="uq_zone_category_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("store_zones.id"), nullable=False)
    category = Column(String(50), nullable=False)
    item_id = Column(String(50), nullable=True)


class StoreFloorPlan(Base):
    __tablename__ = "store_floor_plans"
    __table_args__ = (
        UniqueConstraint("store_id", "floor", name="uq_store_floor_plan"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    floor = Column(Integer, default=1)
    plan_width = Column(Float, nullable=False)   # physical width in meters
    plan_height = Column(Float, nullable=False)  # physical height in meters
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
