from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import port_cargo_service
from app.schemas.port_cargo import ContainerCreate, ContainerEventCreate

router = APIRouter(prefix="/port/cargo", tags=["port-cargo"])


@router.get("/containers")
async def search_containers(
    keyword: str = Query(None),
    vessel: str = Query(None),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await port_cargo_service.search_containers(
        db, keyword, vessel, status, start_date, end_date, page, page_size
    )


@router.post("/containers")
async def create_container(data: ContainerCreate, db: AsyncSession = Depends(get_db)):
    return await port_cargo_service.create_container(db, data.model_dump())


@router.get("/containers/{container_id}")
async def get_container(container_id: int, db: AsyncSession = Depends(get_db)):
    container = await port_cargo_service.get_container(db, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return container


@router.get("/containers/{container_id}/trace")
async def get_trace(container_id: int, db: AsyncSession = Depends(get_db)):
    events = await port_cargo_service.get_container_trace(db, container_id)
    return {"items": events}


@router.post("/containers/{container_id}/events")
async def add_event(container_id: int, data: ContainerEventCreate, db: AsyncSession = Depends(get_db)):
    container = await port_cargo_service.get_container(db, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return await port_cargo_service.add_event(db, container_id, data.model_dump())


@router.get("/statistics")
async def get_statistics(db: AsyncSession = Depends(get_db)):
    return await port_cargo_service.get_statistics(db)
