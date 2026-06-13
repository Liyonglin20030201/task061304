from sqlalchemy import Column, Integer, String, Float, DateTime, Date, UniqueConstraint, Index
from datetime import datetime, timezone
from app.database import Base


class Weather(Base):
    __tablename__ = "weather"
    __table_args__ = (
        UniqueConstraint("city", "weather_date", name="uq_weather_city_date"),
        Index("ix_weather_city_date", "city", "weather_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(50), nullable=False)
    weather_date = Column(Date, nullable=False)
    condition = Column(String(30))
    temp_high = Column(Float)
    temp_low = Column(Float)
    humidity = Column(Float)
    wind_speed = Column(Float)
    precipitation = Column(Float, default=0)
    aqi = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
