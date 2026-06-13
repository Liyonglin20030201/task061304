from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from app.database import Base


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = (
        UniqueConstraint("store_id", "promo_code", name="uq_promo_store_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    promo_code = Column(String(30), nullable=False)
    name = Column(String(100), nullable=False)
    promo_type = Column(String(30), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    discount_rate = Column(Float)
    discount_amount = Column(Float)
    min_purchase = Column(Float, default=0)
    target_category = Column(String(50))
    target_items = Column(String(500))
    budget = Column(Float)
    actual_cost = Column(Float)
    status = Column(String(20), default="planned")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
