from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryResponse
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user_with_stores
from app.core.permissions import filter_by_authorized_stores, enforce_store_access

router = APIRouter(prefix="/inventory", tags=["库存数据"])


@router.get("", response_model=PaginatedResponse)
async def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: Optional[int] = None,
    category: Optional[str] = None,
    snapshot_date: Optional[date] = None,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    if store_id is not None:
        enforce_store_access(authorized_stores, store_id)
    query = select(Inventory)
    query = filter_by_authorized_stores(query, Inventory.store_id, authorized_stores)
    if store_id:
        query = query.where(Inventory.store_id == store_id)
    if category:
        query = query.where(Inventory.category == category)
    if snapshot_date:
        query = query.where(Inventory.snapshot_date == snapshot_date)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    items = (await db.execute(
        query.order_by(Inventory.snapshot_date.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedResponse(
        items=[InventoryResponse.model_validate(item) for item in items],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
