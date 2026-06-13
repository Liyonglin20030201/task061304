from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("store_id", "item_id", "snapshot_date", name="uq_inventory_snapshot"),
        Index("ix_inventory_store_date", "store_id", "snapshot_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(100))
    category = Column(String(50))
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float)
    total_value = Column(Float)
    snapshot_date = Column(Date, nullable=False)
    min_stock = Column(Float, default=0)
    max_stock = Column(Float)
    status = Column(String(20), default="normal")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    store = relationship("Store", back_populates="inventory")
