from datetime import datetime, date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import port_scheduling_service
from app.schemas.port_scheduling import PersonnelCreate, ShiftCreate, ScheduleRequest

router = APIRouter(prefix="/port/scheduling", tags=["port-scheduling"])


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


@router.get("/personnel")
async def list_personnel(
    position: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_scheduling_service.get_personnel(db, position)
    return {"items": [_serialize_row(i) for i in items]}


@router.post("/personnel")
async def create_personnel(data: PersonnelCreate, db: AsyncSession = Depends(get_db)):
    result = await port_scheduling_service.create_personnel(db, data.model_dump())
    return _serialize_row(result)


@router.put("/personnel/{personnel_id}")
async def update_personnel(personnel_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    result = await port_scheduling_service.update_personnel(db, personnel_id, data)
    return _serialize_row(result)


@router.get("/shifts")
async def list_shifts(db: AsyncSession = Depends(get_db)):
    items = await port_scheduling_service.get_shifts(db)
    return {"items": [_serialize_row(i) for i in items]}


@router.post("/shifts")
async def create_shift(data: ShiftCreate, db: AsyncSession = Depends(get_db)):
    result = await port_scheduling_service.create_shift(db, data.model_dump())
    return _serialize_row(result)


@router.post("/generate")
async def generate_schedule(data: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    result = await port_scheduling_service.generate_schedule(db, data.start_date, data.end_date)
    return result


@router.get("/schedules")
async def list_schedules(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_scheduling_service.get_schedules(db, start_date, end_date)
    return {"items": items}


@router.put("/schedules/{schedule_id}")
async def override_schedule(schedule_id: int, personnel_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    result = await port_scheduling_service.override_schedule(db, schedule_id, personnel_id)
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.get("/violations")
async def get_violations(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_scheduling_service.get_violations(db, start_date, end_date)
    return {"items": [_serialize_row(i) for i in items]}
