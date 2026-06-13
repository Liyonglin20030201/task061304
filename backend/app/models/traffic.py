from sqlalchemy import Column, Integer, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Traffic(Base):
    __tablename__ = "traffic"
    __table_args__ = (
        UniqueConstraint("store_id", "traffic_date", "hour", name="uq_traffic_store_date_hour"),
        Index("ix_traffic_store_date", "store_id", "traffic_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    traffic_date = Column(Date, nullable=False)
    hour = Column(Integer, nullable=False)
    enter_count = Column(Integer, nullable=False)
    exit_count = Column(Integer, default=0)
    pass_by_count = Column(Integer, default=0)
    conversion_rate = Column(Float)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    store = relationship("Store", back_populates="traffic")
