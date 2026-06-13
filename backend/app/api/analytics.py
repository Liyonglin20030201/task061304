from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.services.analytics_service import (
    calculate_kpi, get_store_ranking, detect_missing_periods,
)
from app.services.segmentation_service import get_rfm_segmentation
from app.services.forecast_service import get_sales_forecast
from app.services.anomaly_service import detect_anomalies

router = APIRouter(prefix="/analytics", tags=["数据分析"])


@router.get("/kpi")
async def get_kpi(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_ids: Optional[str] = Query(None, description="逗号分隔的门店ID"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    requested_stores = [int(s) for s in store_ids.split(",")] if store_ids else None
    if authorized_stores and requested_stores:
        requested_stores = [s for s in requested_stores if s in authorized_stores]
    elif authorized_stores:
        requested_stores = authorized_stores
    return await calculate_kpi(db, start_date, end_date, requested_stores)


@router.get("/ranking")
async def get_ranking(
    start_date: date = Query(...),
    end_date: date = Query(...),
    metric: str = Query("gmv", description="排名指标: gmv, orders, avg_ticket"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    return await get_store_ranking(db, start_date, end_date, metric, authorized_stores)


@router.get("/segmentation")
async def get_segmentation(
    store_ids: Optional[str] = Query(None),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    requested_stores = [int(s) for s in store_ids.split(",")] if store_ids else authorized_stores
    return await get_rfm_segmentation(db, requested_stores)


@router.get("/forecast")
async def get_forecast(
    store_id: int = Query(...),
    periods: int = Query(30, ge=7, le=90),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    if authorized_stores and store_id not in authorized_stores:
        return {"error": "无权访问该门店数据"}
    return await get_sales_forecast(db, store_id, periods)


@router.get("/anomalies")
async def get_anomalies(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_ids: Optional[str] = Query(None),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    requested_stores = [int(s) for s in store_ids.split(",")] if store_ids else authorized_stores
    return await detect_anomalies(db, start_date, end_date, requested_stores)


@router.get("/missing-periods")
async def get_missing_periods(
    store_id: int = Query(...),
    data_type: str = Query("sales"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    if authorized_stores and store_id not in authorized_stores:
        return {"error": "无权访问该门店数据"}
    return await detect_missing_periods(db, store_id, data_type)
