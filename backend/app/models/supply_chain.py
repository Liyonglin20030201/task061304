from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    contact_name = Column(String(100))
    contact_phone = Column(String(50))
    email = Column(String(200))
    address = Column(String(500))
    lead_time_days = Column(Integer, default=7)
    min_order_qty = Column(Integer, default=1)
    bulk_discount_threshold = Column(Integer)
    bulk_discount_rate = Column(Float)
    payment_terms = Column(String(100))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())


class SupplierItem(Base):
    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint("supplier_id", "item_id", name="uq_supplier_item"),
    )

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    category = Column(String(100))
    unit_cost = Column(Float, nullable=False)
    moq = Column(Integer, default=1)
    bulk_price = Column(Float)
    supply_capacity_daily = Column(Integer)
    is_primary = Column(Integer, default=0)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_po_supplier_date", "supplier_id", "order_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    order_no = Column(String(50), unique=True, nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date)
    actual_delivery_date = Column(Date)
    status = Column(String(20), default="pending")
    total_amount = Column(Float, default=0)
    total_items = Column(Integer, default=0)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    received_quantity = Column(Integer, default=0)
    quality_score = Column(Float)
    notes = Column(Text)


class SupplierPerformance(Base):
    __tablename__ = "supplier_performance"
    __table_args__ = (
        UniqueConstraint("supplier_id", "period_start", name="uq_supplier_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_orders = Column(Integer, default=0)
    on_time_deliveries = Column(Integer, default=0)
    late_deliveries = Column(Integer, default=0)
    total_items_ordered = Column(Integer, default=0)
    total_items_received = Column(Integer, default=0)
    defect_items = Column(Integer, default=0)
    stockout_incidents = Column(Integer, default=0)
    avg_lead_time_actual = Column(Float)
    cost_variance_pct = Column(Float)
    overall_score = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class InventoryAdjustment(Base):
    __tablename__ = "inventory_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    adjustment_type = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text)
    source_store_id = Column(Integer, ForeignKey("stores.id"))
    approved_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
