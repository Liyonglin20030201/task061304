from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.traffic import Traffic
from app.schemas.traffic import TrafficResponse
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user_with_stores
from app.core.permissions import filter_by_authorized_stores

router = APIRouter(prefix="/traffic", tags=["客流数据"])


@router.get("", response_model=PaginatedResponse)
async def list_traffic(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    query = select(Traffic)
    query = filter_by_authorized_stores(query, Traffic.store_id, authorized_stores)
    if store_id:
        query = query.where(Traffic.store_id == store_id)
    if start_date:
        query = query.where(Traffic.traffic_date >= start_date)
    if end_date:
        query = query.where(Traffic.traffic_date <= end_date)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    items = (await db.execute(
        query.order_by(Traffic.traffic_date.desc(), Traffic.hour.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedResponse(
        items=[TrafficResponse.model_validate(item) for item in items],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
