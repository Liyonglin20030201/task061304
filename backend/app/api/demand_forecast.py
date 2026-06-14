from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_auth_context, AuthContext, require_role
from app.core.permissions import enforce_store_access
from app.schemas.demand_forecast import ExternalSignalCreate
from app.services import demand_forecast_service

router = APIRouter(prefix="/demand-forecast", tags=["智能需求预测"])


@router.get("/enhanced")
async def get_enhanced_forecast(
    store_id: int = Query(...),
    periods: int = Query(30, ge=7, le=90),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await demand_forecast_service.get_enhanced_forecast(db, store_id, periods, category)


@router.get("/comparison")
async def get_forecast_comparison(
    store_id: int = Query(...),
    periods: int = Query(30, ge=7, le=90),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await demand_forecast_service.get_forecast_comparison(db, store_id, periods, category)


@router.get("/accuracy")
async def get_accuracy(
    store_ids: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await demand_forecast_service.get_accuracy_history(db, effective, model_name, days)


@router.get("/signals")
async def get_signals(
    region: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await demand_forecast_service.get_signals(db, region, signal_type, start_date, end_date)


@router.post("/signals")
async def create_signal(
    signal_data: ExternalSignalCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
):
    return await demand_forecast_service.create_signal(db, signal_data.model_dump())


@router.get("/ab-experiments")
async def get_ab_experiments(
    store_ids: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    requested = [int(s) for s in store_ids.split(",")] if store_ids else None
    effective = auth.get_effective_stores(requested)
    return await demand_forecast_service.get_ab_experiments(db, effective, status)


@router.post("/ab-experiments")
async def create_ab_experiment(
    experiment_data: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "manager"])),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, experiment_data.get("store_id", 0))
    return await demand_forecast_service.create_ab_experiment(db, experiment_data)


@router.get("/ab-experiments/{experiment_id}")
async def get_ab_experiment_detail(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await demand_forecast_service.get_ab_experiment_detail(db, experiment_id)


@router.post("/tune")
async def auto_tune(
    store_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin"])),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await demand_forecast_service.auto_tune_model(db, store_id)


@router.get("/model-config")
async def get_model_config(
    store_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, store_id)
    return await demand_forecast_service.get_model_config(db, store_id)


@router.put("/model-config")
async def update_model_config(
    config: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "manager"])),
    auth: AuthContext = Depends(get_auth_context),
):
    enforce_store_access(auth.authorized_stores, config.get("store_id", 0))
    return await demand_forecast_service.update_model_config(db, config)
