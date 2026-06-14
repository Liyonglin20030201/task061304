from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.services.omnichannel_service import (
    get_channel_kpi_comparison,
    get_channel_trends,
    get_channel_attribution,
    get_channel_funnel,
    get_member_cross_channel_behavior,
    get_channel_member_overlap,
    get_inventory_by_channel,
    get_unified_member_stats,
)

router = APIRouter(prefix="/omnichannel", tags=["omnichannel"])


def _parse_store_ids(store_ids_str: Optional[str], authorized_stores):
    """Parse comma-separated store IDs and apply authorization filtering."""
    if authorized_stores is None:
        # Admin: use requested stores or None (all)
        if store_ids_str:
            return [int(s) for s in store_ids_str.split(",")]
        return None
    # Non-admin: intersect with authorized stores
    if store_ids_str:
        requested = [int(s) for s in store_ids_str.split(",")]
        return [s for s in requested if s in authorized_stores]
    return authorized_stores


@router.get("/kpis")
async def get_kpis(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_ids: Optional[str] = Query(None, description="Comma-separated store IDs"),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    effective_stores = _parse_store_ids(store_ids, authorized_stores)
    return await get_channel_kpi_comparison(db, effective_stores, start_date, end_date)


@router.get("/trends")
async def get_trends(
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = Query("daily", description="daily/weekly/monthly"),
    store_ids: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    effective_stores = _parse_store_ids(store_ids, authorized_stores)
    return await get_channel_trends(db, effective_stores, start_date, end_date, granularity)


@router.get("/attribution")
async def get_attribution(
    start_date: date = Query(...),
    end_date: date = Query(...),
    model: str = Query("last_touch", description="last_touch/first_touch/linear/time_decay"),
    store_ids: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    effective_stores = _parse_store_ids(store_ids, authorized_stores)
    return await get_channel_attribution(db, effective_stores, start_date, end_date, model)


@router.get("/funnel")
async def get_funnel(
    start_date: date = Query(...),
    end_date: date = Query(...),
    channel: Optional[str] = Query(None, description="Filter to specific channel"),
    store_ids: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    effective_stores = _parse_store_ids(store_ids, authorized_stores)
    return await get_channel_funnel(db, effective_stores, start_date, end_date, channel)


@router.get("/member-behavior/{member_id}")
async def get_member_behavior(
    member_id: int,
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    return await get_member_cross_channel_behavior(db, member_id, authorized_stores)


@router.get("/member-overlap")
async def get_member_overlap(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_ids: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    effective_stores = _parse_store_ids(store_ids, authorized_stores)
    return await get_channel_member_overlap(db, effective_stores, start_date, end_date)


@router.get("/inventory")
async def get_inventory(
    store_id: int = Query(...),
    snapshot_date: Optional[date] = Query(None),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    # Validate store access
    if authorized_stores is not None and store_id not in authorized_stores:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this store")
    return await get_inventory_by_channel(db, store_id, snapshot_date)


@router.get("/member-stats")
async def get_member_stats(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_ids: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = auth
    effective_stores = _parse_store_ids(store_ids, authorized_stores)
    return await get_unified_member_stats(db, effective_stores, start_date, end_date)
