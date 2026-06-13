from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
from app.database import get_db
from app.api.deps import get_auth_context, AuthContext
from app.core.permissions import enforce_store_access
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
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective_stores = auth.get_effective_stores(requested)
    return await calculate_kpi(db, start_date, end_date, effective_stores)


@router.get("/ranking")
async def get_ranking(
    start_date: date = Query(...),
    end_date: date = Query(...),
    metric: str = Query("gmv", description="排名指标: gmv, orders, avg_ticket"),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await get_store_ranking(db, start_date, end_date, metric, auth.authorized_stores)


@router.get("/segmentation")
async def get_segmentation(
    store_ids: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective_stores = auth.get_effective_stores(requested)
    return await get_rfm_segmentation(db, effective_stores)


@router.get("/forecast")
async def get_forecast(
    store_id: int = Query(...),
    periods: int = Query(30, ge=7, le=90),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await get_sales_forecast(db, store_id, periods)


@router.get("/anomalies")
async def get_anomalies(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_ids: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective_stores = auth.get_effective_stores(requested)
    return await detect_anomalies(db, start_date, end_date, effective_stores)


@router.get("/missing-periods")
async def get_missing_periods(
    store_id: int = Query(...),
    data_type: str = Query("sales"),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await detect_missing_periods(db, store_id, data_type)
