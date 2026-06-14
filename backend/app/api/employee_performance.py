from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_auth_context, AuthContext, require_role
from app.core.permissions import enforce_store_access
from app.services import employee_performance_service

router = APIRouter(prefix="/employee-performance", tags=["员工绩效分析"])


@router.get("/scores")
async def get_scores(
    store_ids: Optional[str] = Query(None, description="门店ID列表,逗号分隔"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    position: Optional[str] = Query(None),
    top_n: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    return await employee_performance_service.get_performance_ranking(db, effective, sd, ed, position, top_n)


@router.get("/scores/{employee_id}")
async def get_employee_score(
    employee_id: int,
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    result = await employee_performance_service.calculate_performance_score(db, employee_id, sd, ed)
    if result:
        enforce_store_access(auth.authorized_stores, result["store_id"])
    return result


@router.get("/ranking")
async def get_ranking(
    store_ids: Optional[str] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    position: Optional[str] = Query(None),
    top_n: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    return await employee_performance_service.get_performance_ranking(db, effective, sd, ed, position, top_n)


@router.get("/trend/{employee_id}")
async def get_trend(
    employee_id: int,
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await employee_performance_service.get_performance_trend(db, employee_id, months)


@router.get("/comparison/{employee_id}")
async def get_comparison(
    employee_id: int,
    start_date: str = Query(...),
    end_date: str = Query(...),
    scope: str = Query("store", description="比较范围: store/chain"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    return await employee_performance_service.get_peer_comparison(db, employee_id, sd, ed, scope)


@router.get("/weight-config")
async def get_weight_config(
    store_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await employee_performance_service.get_weight_config(db, store_id)


@router.put("/weight-config")
async def update_weight_config(
    config: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "manager"])),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, config.get("store_id", 0))
    return await employee_performance_service.update_weight_config(db, config)


@router.get("/dashboard")
async def get_dashboard(
    store_ids: Optional[str] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    return await employee_performance_service.get_dashboard(db, effective, sd, ed)
