from datetime import datetime, date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import port_energy_service

router = APIRouter(prefix="/port/energy", tags=["port-energy"])


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


@router.get("/equipment")
async def list_equipment(db: AsyncSession = Depends(get_db)):
    rows = await port_energy_service.get_equipment_list(db)
    return {"items": [_serialize_row(dict(r)) for r in rows]}


@router.get("/equipment/{equipment_id}")
async def get_equipment(equipment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM port_equipment WHERE id = :id"),
        {"id": equipment_id}
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _serialize_row(dict(row))


@router.get("/history")
async def get_history(
    equipment_id: int = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    rows = await port_energy_service.get_energy_history(db, equipment_id, start_time, end_time, limit)
    return {"items": [_serialize_row(dict(r)) for r in rows]}


@router.get("/cost-summary")
async def get_cost_summary(
    start_time: str = Query(None),
    end_time: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    summaries = await port_energy_service.get_cost_summary(db, start_time, end_time)
    return {"items": summaries}


@router.get("/peak-analysis")
async def get_peak_analysis(
    equipment_id: int = Query(None),
    top_n: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    peaks = await port_energy_service.get_peak_analysis(db, equipment_id, top_n)
    return {"items": [_serialize_row(dict(r)) for r in peaks]}
