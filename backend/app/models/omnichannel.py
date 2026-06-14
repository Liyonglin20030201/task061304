from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, ForeignKey,
    UniqueConstraint, Index, JSON,
)
from sqlalchemy.sql import func
from app.database import Base


class ChannelSale(Base):
    __tablename__ = "channel_sales"
    __table_args__ = (
        UniqueConstraint("store_id", "receipt_no", "item_id", "channel", name="uq_channel_sale_receipt_item"),
        Index("ix_channel_sales_store_date", "store_id", "sale_date", "channel"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    sale_date = Column(Date, nullable=False)
    receipt_no = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)  # online/offline/o2o
    sub_channel = Column(String(30), nullable=True)  # app/wechat/website/pos/delivery
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(100))
    category = Column(String(50))
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    order_source = Column(String(50), nullable=True)
    fulfillment_type = Column(String(20), nullable=True)  # ship_to_home/pickup_in_store/deliver_from_store
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChannelInventory(Base):
    __tablename__ = "channel_inventory"
    __table_args__ = (
        UniqueConstraint("store_id", "item_id", "channel", "snapshot_date", name="uq_channel_inventory_snapshot"),
        Index("ix_channel_inventory_store_date", "store_id", "snapshot_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)
    allocated_qty = Column(Float, nullable=False)
    available_qty = Column(Float, nullable=False)
    reserved_qty = Column(Float, default=0)
    snapshot_date = Column(Date, nullable=False)


class ChannelMemberEvent(Base):
    __tablename__ = "channel_member_events"
    __table_args__ = (
        Index("ix_channel_events_member", "member_id", "event_date"),
        Index("ix_channel_events_store", "store_id", "event_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    channel = Column(String(20), nullable=False)
    event_type = Column(String(30), nullable=False)  # browse/add_cart/purchase/return/review
    event_date = Column(DateTime(timezone=True), nullable=False)
    item_id = Column(String(50), nullable=True)
    amount = Column(Float, nullable=True)
    session_id = Column(String(50), nullable=True)
    device_type = Column(String(20), nullable=True)


class ChannelAttribution(Base):
    __tablename__ = "channel_attribution"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    conversion_receipt = Column(String(50), nullable=False)
    conversion_channel = Column(String(20), nullable=False)
    conversion_date = Column(Date, nullable=False)
    touchpoints = Column(JSON)  # list of {channel, event_type, timestamp}
    attribution_model = Column(String(20), nullable=False)  # last_touch/first_touch/linear/time_decay
    attributed_channels = Column(JSON)  # {channel: weight}
    conversion_amount = Column(Float, nullable=False)
