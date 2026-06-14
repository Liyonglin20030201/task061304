from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_auth_context, AuthContext, require_role
from app.services import product_lifecycle_service

router = APIRouter(prefix="/product-lifecycle", tags=["商品生命周期"])


@router.get("/overview")
async def get_overview(
    store_ids: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_lifecycle_overview(db, effective, category)


@router.get("/products")
async def get_products(
    store_ids: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_products_with_stage(db, effective, stage, category, page, page_size)


@router.get("/products/{product_id}")
async def get_product_detail(
    product_id: int,
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_lifecycle_curve(db, product_id, effective)


@router.get("/curve/{product_id}")
async def get_curve(
    product_id: int,
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_lifecycle_curve(db, product_id, effective)


@router.get("/transitions")
async def get_transitions(
    store_ids: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_stage_transitions(db, effective, days)


@router.get("/stage-kpis")
async def get_stage_kpis(
    stage: str = Query(..., description="生命周期阶段: introduction/growth/maturity/decline"),
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_stage_kpis(db, effective, stage)


@router.get("/retirement-recommendations")
async def get_retirement_recommendations(
    store_ids: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.get_retirement_recommendations(db, effective, category)


@router.post("/recalculate")
async def recalculate(
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await product_lifecycle_service.recalculate_lifecycle(db, effective)
