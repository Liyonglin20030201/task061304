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


@router.get("/task-load")
async def get_task_load(db: AsyncSession = Depends(get_db)):
    """Real-time task load per personnel for allocation weight calculation."""
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT pp.id as personnel_id, pp.employee_code, pp.name, pp.position,
               COUNT(s.id) FILTER (WHERE s.status = 'active') as active_tasks,
               COUNT(s.id) FILTER (WHERE s.schedule_date = CURRENT_DATE) as today_shifts,
               COUNT(s.id) FILTER (WHERE s.schedule_date >= CURRENT_DATE - INTERVAL '7 days') as week_shifts
        FROM port_personnel pp
        LEFT JOIN schedules s ON pp.id = s.personnel_id
        WHERE pp.is_active = true
        GROUP BY pp.id, pp.employee_code, pp.name, pp.position
        ORDER BY week_shifts DESC
    """))
    items = [_serialize_row(dict(r)) for r in result.mappings().all()]
    return {"items": items, "ts": int(__import__('time').time() * 1000)}


@router.get("/violations")
async def get_violations(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_scheduling_service.get_violations(db, start_date, end_date)
    return {"items": [_serialize_row(i) for i in items]}
