from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_auth_context, AuthContext, require_role
from app.services import data_quality_service

router = APIRouter(prefix="/data-quality", tags=["数据质量监控"])


@router.get("/health")
async def get_health(
    store_ids: Optional[str] = Query(None, description="门店ID列表,逗号分隔"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await data_quality_service.calculate_overall_health(db, effective)


@router.get("/scores")
async def get_scores(
    target_table: Optional[str] = Query(None, description="目标表名"),
    dimension: Optional[str] = Query(None, description="质量维度"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await data_quality_service.get_quality_scores(db, effective, target_table, dimension)


@router.get("/scores/trend")
async def get_score_trend(
    target_table: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await data_quality_service.get_score_trend(db, effective, target_table, days)


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    store_ids: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await data_quality_service.get_alerts(db, effective, severity, status, page, page_size)


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await data_quality_service.acknowledge_alert(db, alert_id, auth.user.id)


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await data_quality_service.resolve_alert(db, alert_id)


@router.get("/rules")
async def get_rules(
    target_table: Optional[str] = Query(None),
    dimension: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await data_quality_service.get_rules(db, target_table, dimension)


@router.post("/rules")
async def create_rule(
    rule_data: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "manager"])),
):
    return await data_quality_service.create_rule(db, rule_data)


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    update_data: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "manager"])),
):
    return await data_quality_service.update_rule(db, rule_id, update_data)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "manager"])),
):
    return await data_quality_service.delete_rule(db, rule_id)


@router.post("/run-check")
async def run_check(
    store_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await data_quality_service.run_quality_check(db, effective)


@router.get("/check-runs")
async def get_check_runs(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await data_quality_service.get_check_runs(db, days)
