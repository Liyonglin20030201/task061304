from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class WeatherCreate(BaseModel):
    city: str
    weather_date: date
    condition: Optional[str] = None
    temp_high: Optional[float] = None
    temp_low: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    precipitation: float = 0
    aqi: Optional[int] = None


class WeatherResponse(BaseModel):
    id: int
    city: str
    weather_date: date
    condition: Optional[str]
    temp_high: Optional[float]
    temp_low: Optional[float]
    humidity: Optional[float]
    precipitation: float
    aqi: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
