from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.weather import Weather
from app.schemas.weather import WeatherResponse
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user_with_stores

router = APIRouter(prefix="/weather", tags=["天气数据"])


@router.get("", response_model=PaginatedResponse)
async def list_weather(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    _: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    query = select(Weather)
    if city:
        query = query.where(Weather.city == city)
    if start_date:
        query = query.where(Weather.weather_date >= start_date)
    if end_date:
        query = query.where(Weather.weather_date <= end_date)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    items = (await db.execute(
        query.order_by(Weather.weather_date.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedResponse(
        items=[WeatherResponse.model_validate(item) for item in items],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
