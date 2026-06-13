from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("store_id", "receipt_no", "item_id", name="uq_sale_receipt_item"),
        Index("ix_sales_store_date", "store_id", "sale_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    sale_date = Column(Date, nullable=False, index=True)
    sale_time = Column(DateTime(timezone=True))
    receipt_no = Column(String(50), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_name = Column(String(100))
    category = Column(String(50))
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0)
    payment_method = Column(String(30))
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    store = relationship("Store", back_populates="sales")
    member = relationship("Member", back_populates="sales")
