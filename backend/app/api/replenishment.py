from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.core.permissions import (
    get_user_authorized_stores, filter_by_authorized_stores,
    enforce_store_access, ROLE_ADMIN, ROLE_MANAGER,
)
from app.models.replenishment import ReplenishmentSuggestion, ReplenishmentConfig
from app.models.supply_chain import Supplier
from app.schemas.replenishment import (
    ReplenishmentSuggestionResponse, ReplenishmentConfigUpdate,
    ReplenishmentConfigResponse, GenerateSuggestionsRequest,
    ReplenishmentDashboard, ReplenishmentTimeline,
)
from app.services.replenishment_service import (
    generate_replenishment_suggestions,
    get_replenishment_dashboard,
    get_replenishment_timeline,
)

router = APIRouter(prefix="/replenishment", tags=["replenishment"])


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    return await get_replenishment_dashboard(db, authorized_stores)


@router.get("/suggestions", response_model=List[ReplenishmentSuggestionResponse])
async def list_suggestions(
    store_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    query = select(ReplenishmentSuggestion)
    query = filter_by_authorized_stores(query, ReplenishmentSuggestion.store_id, authorized_stores)
    if store_id:
        query = query.where(ReplenishmentSuggestion.store_id == store_id)
    if status_filter:
        query = query.where(ReplenishmentSuggestion.status == status_filter)
    query = query.order_by(ReplenishmentSuggestion.optimal_order_date.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    suggestions = result.scalars().all()

    response = []
    for s in suggestions:
        data = {c.name: getattr(s, c.name) for c in s.__table__.columns}
        if s.supplier_id:
            sup_result = await db.execute(select(Supplier).where(Supplier.id == s.supplier_id))
            supplier = sup_result.scalar_one_or_none()
            data["supplier_name"] = supplier.name if supplier else None
        else:
            data["supplier_name"] = None
        response.append(data)
    return response


@router.post("/suggestions/generate")
async def generate_suggestions(
    data: GenerateSuggestionsRequest,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    enforce_store_access(authorized_stores, data.store_id)

    suggestions = await generate_replenishment_suggestions(
        db, data.store_id, data.item_ids
    )
    return {"message": f"已生成 {len(suggestions)} 条补货建议", "count": len(suggestions)}


@router.put("/suggestions/{suggestion_id}/approve")
async def approve_suggestion(
    suggestion_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(
        select(ReplenishmentSuggestion).where(ReplenishmentSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="建议不存在")
    enforce_store_access(authorized_stores, suggestion.store_id)

    suggestion.status = "approved"
    suggestion.approved_by = user.id
    suggestion.approved_at = datetime.utcnow()
    await db.commit()
    return {"message": "已批准"}


@router.get("/timeline")
async def timeline(
    store_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    return await get_replenishment_timeline(db, store_id, limit)


@router.get("/config", response_model=List[ReplenishmentConfigResponse])
async def get_config(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    result = await db.execute(
        select(ReplenishmentConfig).where(ReplenishmentConfig.store_id == store_id)
    )
    return result.scalars().all()


@router.put("/config/{store_id}/{item_id}")
async def update_config(
    store_id: int,
    item_id: str,
    data: ReplenishmentConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    enforce_store_access(authorized_stores, store_id)

    result = await db.execute(
        select(ReplenishmentConfig).where(
            ReplenishmentConfig.store_id == store_id,
            ReplenishmentConfig.item_id == item_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        config = ReplenishmentConfig(store_id=store_id, item_id=item_id)
        db.add(config)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await db.commit()
    return {"message": "配置已更新"}


@router.get("/suppliers", response_model=List[dict])
async def list_suppliers(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    result = await db.execute(select(Supplier).where(Supplier.is_active == 1))
    suppliers = result.scalars().all()
    return [
        {"id": s.id, "name": s.name, "lead_time_days": s.lead_time_days,
         "min_order_qty": s.min_order_qty}
        for s in suppliers
    ]
