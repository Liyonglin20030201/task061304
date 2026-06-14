from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import date

from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.core.permissions import (
    filter_by_authorized_stores,
    enforce_store_access,
    ROLE_ADMIN,
    ROLE_MANAGER,
)
from app.models.space_layout import StoreZone
from app.schemas.space_layout import (
    ZoneCreate,
    ZoneUpdate,
    ZoneResponse,
    ZoneKPI,
    HeatmapCell,
    HeatmapResponse,
    FloorPlanCreate,
    FloorPlanResponse,
    ZoneRanking,
    ZoneTrend,
    LayoutRecommendation,
    ZoneItemMappingCreate,
)
from app.schemas.common import PaginatedResponse
from app.services.space_layout_service import (
    get_zones,
    create_zone,
    update_zone,
    delete_zone,
    get_zone_kpis,
    get_sales_heatmap,
    get_zone_ranking,
    get_zone_trends,
    generate_layout_recommendations,
    aggregate_zone_sales,
    compare_stores_layout,
    get_floor_plan,
    upsert_floor_plan,
)

router = APIRouter(prefix="/space-layout", tags=["space-layout"])


@router.get("/zones", response_model=PaginatedResponse)
async def list_zones(
    store_id: int = Query(..., description="门店ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """List zones for a store with pagination."""
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)

    # Count total
    count_query = select(func.count()).select_from(StoreZone).where(
        StoreZone.store_id == store_id,
        StoreZone.is_active == 1,
    )
    if authorized_stores is not None:
        count_query = count_query.where(StoreZone.store_id.in_(authorized_stores))
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated zones
    zones = await get_zones(db, store_id, authorized_stores)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = zones[start:end]

    return PaginatedResponse(
        items=[ZoneResponse(**z) for z in paginated],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("/zones", response_model=ZoneResponse)
async def create_zone_endpoint(
    data: ZoneCreate,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Create a new zone (admin/manager only)."""
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    enforce_store_access(authorized_stores, data.store_id)

    zone_dict = data.model_dump()
    result = await create_zone(db, zone_dict)
    return ZoneResponse(**result)


@router.put("/zones/{zone_id}", response_model=ZoneResponse)
async def update_zone_endpoint(
    zone_id: int,
    data: ZoneUpdate,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Update a zone (admin/manager only)."""
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    # Check zone exists and user has access
    zone_result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = zone_result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="区域不存在")
    enforce_store_access(authorized_stores, zone.store_id)

    update_data = data.model_dump(exclude_unset=True)
    result = await update_zone(db, zone_id, update_data)
    if result is None:
        raise HTTPException(status_code=404, detail="区域不存在")
    return ZoneResponse(**result)


@router.delete("/zones/{zone_id}")
async def delete_zone_endpoint(
    zone_id: int,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a zone (admin/manager only)."""
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    # Check zone exists and user has access
    zone_result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = zone_result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="区域不存在")
    enforce_store_access(authorized_stores, zone.store_id)

    success = await delete_zone(db, zone_id)
    if not success:
        raise HTTPException(status_code=404, detail="区域不存在")
    return {"message": "区域已删除"}


@router.get("/kpis", response_model=List[ZoneKPI])
async def zone_kpis(
    store_id: int = Query(..., description="门店ID"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get zone KPIs for a store."""
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    return await get_zone_kpis(db, store_id, start_date, end_date)


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(
    store_id: int = Query(..., description="门店ID"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get sales heatmap data for store layout."""
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    return await get_sales_heatmap(db, store_id, start_date, end_date)


@router.get("/floor-plan", response_model=Optional[FloorPlanResponse])
async def get_floor_plan_endpoint(
    store_id: int = Query(..., description="门店ID"),
    floor: int = Query(1, description="楼层"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get floor plan configuration for a store."""
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    result = await get_floor_plan(db, store_id, floor)
    if not result:
        return None
    return FloorPlanResponse(**result)


@router.post("/floor-plan", response_model=FloorPlanResponse)
async def set_floor_plan_endpoint(
    data: FloorPlanCreate,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Set floor plan dimensions (admin/manager only)."""
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    enforce_store_access(authorized_stores, data.store_id)
    result = await upsert_floor_plan(db, data.model_dump())
    return FloorPlanResponse(**result)


@router.get("/ranking", response_model=List[ZoneRanking])
async def ranking(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    metric: str = Query("revenue_per_sqm", description="排名指标"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get zone ranking across authorized stores."""
    user, authorized_stores, role_name = user_stores
    results = await get_zone_ranking(db, authorized_stores, start_date, end_date, metric)
    start = (page - 1) * page_size
    end_idx = start + page_size
    return results[start:end_idx]


@router.get("/trends/{zone_id}", response_model=List[ZoneTrend])
async def trends(
    zone_id: int,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    granularity: str = Query("daily", description="聚合粒度: daily/weekly/monthly"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get time series trends for a specific zone."""
    user, authorized_stores, role_name = user_stores

    # Verify zone access
    zone_result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = zone_result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="区域不存在")
    enforce_store_access(authorized_stores, zone.store_id)

    return await get_zone_trends(db, zone_id, start_date, end_date, granularity)


@router.get("/recommendations", response_model=List[LayoutRecommendation])
async def recommendations(
    store_id: int = Query(..., description="门店ID"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get layout optimization recommendations for a store."""
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    return await generate_layout_recommendations(db, store_id, start_date, end_date)


@router.post("/aggregate")
async def trigger_aggregation(
    store_id: int = Query(..., description="门店ID"),
    target_date: str = Query(..., description="目标日期 YYYY-MM-DD"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Trigger sales aggregation by zone (admin only)."""
    user, authorized_stores, role_name = user_stores
    if role_name != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可执行聚合操作")
    enforce_store_access(authorized_stores, store_id)

    count = await aggregate_zone_sales(db, store_id, target_date)
    return {"message": f"聚合完成，处理 {count} 条区域销售记录", "count": count}


@router.get("/compare")
async def compare(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Cross-store layout performance comparison."""
    user, authorized_stores, role_name = user_stores
    return await compare_stores_layout(db, authorized_stores, start_date, end_date)
