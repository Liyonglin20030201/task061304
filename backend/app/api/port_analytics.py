from datetime import datetime, date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import port_analytics_service

router = APIRouter(prefix="/port/analytics", tags=["port-analytics"])


def _serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return await port_analytics_service.get_dashboard_metrics(db)


@router.get("/utilization")
async def get_utilization(
    start_time: str = Query(None),
    end_time: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_analytics_service.get_utilization(db, start_time, end_time)
    return {"items": [_serialize_row(dict(r)) for r in items]}


@router.get("/throughput")
async def get_throughput(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    items = await port_analytics_service.get_throughput_trend(db, days)
    return {"items": [_serialize_row(dict(r)) for r in items]}


@router.get("/hourly-metrics")
async def get_hourly_metrics(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    items = await port_analytics_service.get_hourly_metrics(db, hours)
    return {"items": [_serialize_row(dict(r)) for r in items]}
