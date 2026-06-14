from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


STATUS_TRANSITIONS = {
    "vessel_arrival": "arrived",
    "discharge": "arrived",
    "gate_in": "arrived",
    "stack": "stacked",
    "restack": "stacked",
    "retrieve": "retrieving",
    "load": "departed",
    "gate_out": "departed",
    "inspection": None,
}


async def create_container(db: AsyncSession, data: dict) -> dict:
    result = await db.execute(
        text("""INSERT INTO containers (container_code, container_type, weight_tons, owner, vessel_name, voyage_no, bill_of_lading, status, yard_block, yard_bay, yard_row, yard_tier)
                VALUES (:container_code, :container_type, :weight_tons, :owner, :vessel_name, :voyage_no, :bill_of_lading, 'en_route', :yard_block, :yard_bay, :yard_row, :yard_tier)
                RETURNING id"""),
        data
    )
    container_id = result.scalar()
    await db.commit()
    return await get_container(db, container_id)


async def get_container(db: AsyncSession, container_id: int) -> dict:
    result = await db.execute(
        text("SELECT * FROM containers WHERE id = :id"),
        {"id": container_id}
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def search_containers(db: AsyncSession, keyword: str = None, vessel: str = None,
                            status: str = None, start_date: str = None, end_date: str = None,
                            page: int = 1, page_size: int = 20):
    where_clauses = ["1=1"]
    params = {}

    if keyword:
        where_clauses.append("(container_code ILIKE :keyword OR bill_of_lading ILIKE :keyword)")
        params["keyword"] = f"%{keyword}%"
    if vessel:
        where_clauses.append("vessel_name ILIKE :vessel")
        params["vessel"] = f"%{vessel}%"
    if status:
        where_clauses.append("status = :status")
        params["status"] = status
    if start_date:
        where_clauses.append("arrival_time >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where_clauses.append("arrival_time <= :end_date")
        params["end_date"] = end_date

    where = " AND ".join(where_clauses)

    count_result = await db.execute(text(f"SELECT COUNT(*) FROM containers WHERE {where}"), params)
    total = count_result.scalar()

    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    result = await db.execute(
        text(f"SELECT * FROM containers WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
        params
    )
    items = [dict(r) for r in result.mappings().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def add_event(db: AsyncSession, container_id: int, data: dict) -> dict:
    event_time = data.get("event_time") or datetime.now().isoformat()
    await db.execute(
        text("""INSERT INTO container_events (container_id, event_type, event_time, location, equipment_id, operator_id, details)
                VALUES (:container_id, :event_type, :event_time, :location, :equipment_id, :operator_id, :details)"""),
        {
            "container_id": container_id,
            "event_type": data["event_type"],
            "event_time": event_time,
            "location": data.get("location"),
            "equipment_id": data.get("equipment_id"),
            "operator_id": data.get("operator_id"),
            "details": None,
        }
    )

    new_status = STATUS_TRANSITIONS.get(data["event_type"])
    if new_status:
        update_fields = "status = :status"
        update_params = {"status": new_status, "id": container_id}
        if new_status == "arrived" and data["event_type"] == "vessel_arrival":
            update_fields += ", arrival_time = :arrival_time"
            update_params["arrival_time"] = event_time
        elif new_status == "departed":
            update_fields += ", departure_time = :departure_time"
            update_params["departure_time"] = event_time
        await db.execute(text(f"UPDATE containers SET {update_fields} WHERE id = :id"), update_params)

    await db.commit()
    return {"message": "Event recorded", "new_status": new_status}


async def get_container_trace(db: AsyncSession, container_id: int) -> list:
    result = await db.execute(
        text("SELECT * FROM container_events WHERE container_id = :id ORDER BY event_time ASC"),
        {"id": container_id}
    )
    return [dict(r) for r in result.mappings().all()]


async def get_statistics(db: AsyncSession) -> dict:
    result = await db.execute(text("""
        SELECT
            COUNT(*) as total_containers,
            COUNT(*) FILTER (WHERE status = 'en_route') as en_route,
            COUNT(*) FILTER (WHERE status = 'stacked') as stacked,
            COUNT(*) FILTER (WHERE status = 'departed') as departed,
            COALESCE(AVG(EXTRACT(EPOCH FROM (COALESCE(departure_time, NOW()) - arrival_time)) / 3600)
                FILTER (WHERE arrival_time IS NOT NULL), 0) as avg_dwell_hours
        FROM containers
    """))
    row = result.mappings().first()
    return dict(row)
