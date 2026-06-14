import time as time_module
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

_stats_cache = None
_stats_cache_ts = 0
_STATS_TTL = 5

_count_cache = {}
_count_cache_ts = 0
_COUNT_TTL = 10


def _ts_iso(dt) -> str:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat(timespec="milliseconds")
    return str(dt)


def _format_container(row: dict) -> dict:
    out = dict(row)
    out["arrival_time"] = _ts_iso(out.get("arrival_time"))
    out["departure_time"] = _ts_iso(out.get("departure_time"))
    out["created_at"] = _ts_iso(out.get("created_at"))
    return out


def _format_event(row: dict) -> dict:
    out = dict(row)
    out["event_time"] = _ts_iso(out.get("event_time"))
    out["created_at"] = _ts_iso(out.get("created_at"))
    return out


async def create_container(db: AsyncSession, data: dict) -> dict:
    result = await db.execute(
        text("""INSERT INTO containers (container_code, container_type, weight_tons, owner, vessel_name, voyage_no, bill_of_lading, status, yard_block, yard_bay, yard_row, yard_tier)
                VALUES (:container_code, :container_type, :weight_tons, :owner, :vessel_name, :voyage_no, :bill_of_lading, 'en_route', :yard_block, :yard_bay, :yard_row, :yard_tier)
                RETURNING id"""),
        data
    )
    container_id = result.scalar()
    await db.commit()
    _invalidate_caches()
    return await get_container(db, container_id)


async def get_container(db: AsyncSession, container_id: int) -> dict:
    result = await db.execute(
        text("SELECT * FROM containers WHERE id = :id"),
        {"id": container_id}
    )
    row = result.mappings().first()
    return _format_container(row) if row else None


async def search_containers(db: AsyncSession, keyword: str = None, vessel: str = None,
                            status: str = None, start_date: str = None, end_date: str = None,
                            page: int = 1, page_size: int = 20):
    where_clauses = []
    params = {}
    use_exact = False

    if keyword:
        clean = keyword.strip().upper()
        if len(clean) >= 4 and clean[:4].isalpha():
            where_clauses.append("container_code = :code")
            params["code"] = clean
            use_exact = True
        else:
            where_clauses.append("(container_code LIKE :kw OR bill_of_lading LIKE :kw)")
            params["kw"] = f"{keyword}%"
    if vessel:
        where_clauses.append("vessel_name LIKE :vessel")
        params["vessel"] = f"%{vessel}%"
    if status:
        where_clauses.append("status = :status")
        params["status"] = status
    if start_date:
        where_clauses.append("arrival_time >= :sd")
        params["sd"] = start_date
    if end_date:
        where_clauses.append("arrival_time <= :ed")
        params["ed"] = end_date

    where = " AND ".join(where_clauses) if where_clauses else "TRUE"

    if use_exact:
        total = 1
    elif not where_clauses:
        total = await _get_estimated_count(db)
    else:
        count_result = await db.execute(text(f"SELECT COUNT(*) FROM containers WHERE {where}"), params)
        total = count_result.scalar()

    params["lim"] = page_size
    params["off"] = (page - 1) * page_size
    result = await db.execute(
        text(f"SELECT * FROM containers WHERE {where} ORDER BY created_at DESC LIMIT :lim OFFSET :off"),
        params
    )
    items = [_format_container(dict(r)) for r in result.mappings().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def _get_estimated_count(db: AsyncSession) -> int:
    global _count_cache, _count_cache_ts
    now = time_module.time()
    if _count_cache.get("total") and (now - _count_cache_ts) < _COUNT_TTL:
        return _count_cache["total"]

    result = await db.execute(text(
        "SELECT reltuples::bigint FROM pg_class WHERE relname = 'containers'"
    ))
    row = result.first()
    est = row[0] if row and row[0] > 0 else 0
    if est == 0:
        result2 = await db.execute(text("SELECT COUNT(*) FROM containers"))
        est = result2.scalar()
    _count_cache["total"] = est
    _count_cache_ts = now
    return est


async def add_event(db: AsyncSession, container_id: int, data: dict) -> dict:
    event_time = data.get("event_time") or datetime.now().isoformat(timespec="milliseconds")
    await db.execute(
        text("""INSERT INTO container_events (container_id, event_type, event_time, location, equipment_id, operator_id, details)
                VALUES (:cid, :etype, :etime, :loc, :eid, :oid, :det)"""),
        {
            "cid": container_id,
            "etype": data["event_type"],
            "etime": event_time,
            "loc": data.get("location"),
            "eid": data.get("equipment_id"),
            "oid": data.get("operator_id"),
            "det": None,
        }
    )

    new_status = STATUS_TRANSITIONS.get(data["event_type"])
    if new_status:
        update_fields = "status = :status"
        update_params = {"status": new_status, "id": container_id}
        if new_status == "arrived" and data["event_type"] == "vessel_arrival":
            update_fields += ", arrival_time = :at"
            update_params["at"] = event_time
        elif new_status == "departed":
            update_fields += ", departure_time = :dt"
            update_params["dt"] = event_time
        await db.execute(text(f"UPDATE containers SET {update_fields} WHERE id = :id"), update_params)

    await db.commit()
    _invalidate_caches()
    return {"message": "Event recorded", "new_status": new_status}


async def get_container_trace(db: AsyncSession, container_id: int) -> list:
    result = await db.execute(
        text("""SELECT ce.*, pe.equipment_code, pe.name as equipment_name
                FROM container_events ce
                LEFT JOIN port_equipment pe ON ce.equipment_id = pe.id
                WHERE ce.container_id = :id
                ORDER BY ce.event_time ASC"""),
        {"id": container_id}
    )
    return [_format_event(dict(r)) for r in result.mappings().all()]


async def get_statistics(db: AsyncSession) -> dict:
    global _stats_cache, _stats_cache_ts
    now = time_module.time()
    if _stats_cache and (now - _stats_cache_ts) < _STATS_TTL:
        return _stats_cache

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
    stats = {
        "total_containers": row["total_containers"] or 0,
        "en_route": row["en_route"] or 0,
        "stacked": row["stacked"] or 0,
        "departed": row["departed"] or 0,
        "avg_dwell_hours": round(float(row["avg_dwell_hours"] or 0), 1),
    }
    _stats_cache = stats
    _stats_cache_ts = now
    return stats


def _invalidate_caches():
    global _stats_cache, _stats_cache_ts, _count_cache, _count_cache_ts
    _stats_cache = None
    _stats_cache_ts = 0
    _count_cache = {}
    _count_cache_ts = 0
