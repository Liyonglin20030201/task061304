from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import port_scheduling_service
from app.schemas.port_scheduling import PersonnelCreate, ShiftCreate, ScheduleRequest

router = APIRouter(prefix="/port/scheduling", tags=["port-scheduling"])


@router.get("/personnel")
async def list_personnel(
    position: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_scheduling_service.get_personnel(db, position)
    return {"items": items}


@router.post("/personnel")
async def create_personnel(data: PersonnelCreate, db: AsyncSession = Depends(get_db)):
    return await port_scheduling_service.create_personnel(db, data.model_dump())


@router.put("/personnel/{personnel_id}")
async def update_personnel(personnel_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await port_scheduling_service.update_personnel(db, personnel_id, data)


@router.get("/shifts")
async def list_shifts(db: AsyncSession = Depends(get_db)):
    items = await port_scheduling_service.get_shifts(db)
    return {"items": items}


@router.post("/shifts")
async def create_shift(data: ShiftCreate, db: AsyncSession = Depends(get_db)):
    return await port_scheduling_service.create_shift(db, data.model_dump())


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
    return await port_scheduling_service.override_schedule(db, schedule_id, personnel_id)


@router.get("/violations")
async def get_violations(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items = await port_scheduling_service.get_violations(db, start_date, end_date)
    return {"items": items}
