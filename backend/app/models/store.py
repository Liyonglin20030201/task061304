from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    region = Column(String(50))
    city = Column(String(50))
    district = Column(String(50))
    address = Column(String(200))
    area_sqm = Column(Float)
    store_type = Column(String(30))
    is_active = Column(Boolean, default=True)
    opened_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_permissions = relationship("UserStorePermission", back_populates="store")
    sales = relationship("Sale", back_populates="store")
    inventory = relationship("Inventory", back_populates="store")
    traffic = relationship("Traffic", back_populates="store")
