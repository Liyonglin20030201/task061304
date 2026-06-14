from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.services import store_energy_service
from app.schemas.store_energy import (
    EquipmentCreate, EquipmentUpdate, EquipmentResponse,
    ScheduleCreate, ScheduleResponse,
    AlertResponse, BudgetCreate, BudgetResponse,
)

router = APIRouter(prefix="/store-energy", tags=["store-energy"])


def _serialize_row(row) -> dict:
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _check_store_access(store_id: int, authorized_stores: Optional[List[int]]):
    if authorized_stores is not None and store_id not in authorized_stores:
        raise HTTPException(status_code=403, detail="No access to this store")


def _check_manager_role(role_name: str):
    if role_name not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


# ---------- Equipment ----------

@router.get("/equipment")
async def list_equipment(
    store_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    rows = await store_energy_service.get_equipment(db, store_id, authorized_stores)
    return {"items": [_serialize_row(r) for r in rows]}


@router.post("/equipment")
async def create_equipment(
    data: EquipmentCreate,
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_manager_role(role_name)
    _check_store_access(data.store_id, authorized_stores)
    row = await store_energy_service.create_equipment(db, data.model_dump(exclude_none=True))
    return _serialize_row(row)


@router.put("/equipment/{equipment_id}")
async def update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_manager_role(role_name)
    update_data = data.model_dump(exclude_none=True)
    row = await store_energy_service.update_equipment(db, equipment_id, update_data)
    if not row:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _serialize_row(row)


# ---------- Dashboard ----------

@router.get("/dashboard")
async def get_dashboard(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    result = await store_energy_service.get_energy_dashboard(db, authorized_stores, start_date, end_date)
    return result


# ---------- Trends ----------

@router.get("/trends")
async def get_trends(
    store_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = Query("daily"),
    equipment_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.get_energy_trends(db, store_id, start_date, end_date, granularity, equipment_type)
    return {"items": result}


# ---------- Peak Hours ----------

@router.get("/peak-hours")
async def get_peak_hours(
    store_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.get_peak_hour_analysis(db, store_id, start_date, end_date)
    return {"items": result}


# ---------- Correlations ----------

@router.get("/correlations/weather")
async def get_weather_correlation(
    store_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.get_weather_energy_correlation(db, store_id, start_date, end_date)
    return result


@router.get("/correlations/sales")
async def get_sales_correlation(
    store_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.get_sales_energy_correlation(db, store_id, start_date, end_date)
    return result


# ---------- Schedule Optimization ----------

@router.post("/optimize-schedule")
async def optimize_schedule(
    store_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_manager_role(role_name)
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.optimize_equipment_schedule(db, store_id)
    return {"items": result}


# ---------- Schedules ----------

@router.get("/schedules")
async def list_schedules(
    store_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    rows = await store_energy_service.get_schedules(db, store_id)
    return {"items": [_serialize_row(r) for r in rows]}


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_manager_role(role_name)
    update_data = data.model_dump(exclude_none=True)
    row = await store_energy_service.update_schedule(db, schedule_id, update_data)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _serialize_row(row)


# ---------- Anomalies ----------

@router.get("/anomalies")
async def detect_anomalies(
    store_id: int = Query(...),
    lookback_days: int = Query(30),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.detect_anomalies(db, store_id, lookback_days)
    return {"items": result}


# ---------- Alerts ----------

@router.get("/alerts")
async def list_alerts(
    store_id: int = Query(...),
    acknowledged: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    rows = await store_energy_service.get_alerts(db, store_id, acknowledged)
    return {"items": [_serialize_row(r) for r in rows]}


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    row = await store_energy_service.acknowledge_alert(db, alert_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize_row(row)


# ---------- Budget ----------

@router.get("/budget")
async def get_budget(
    store_id: int = Query(...),
    year_month: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    rows = await store_energy_service.get_budget(db, store_id, year_month)
    return {"items": [_serialize_row(r) for r in rows]}


@router.post("/budget")
async def set_budget(
    data: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_manager_role(role_name)
    _check_store_access(data.store_id, authorized_stores)
    budget_data = data.model_dump()
    row = await store_energy_service.set_budget(db, budget_data)
    return _serialize_row(row)


# ---------- Recommendations ----------

@router.get("/recommendations")
async def get_recommendations(
    store_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = auth
    _check_store_access(store_id, authorized_stores)
    result = await store_energy_service.get_cost_optimization_recommendations(db, store_id, start_date, end_date)
    return {"items": result}
