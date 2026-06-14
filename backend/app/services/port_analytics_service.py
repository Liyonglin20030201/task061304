from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_dashboard_metrics(db: AsyncSession) -> dict:
    containers_result = await db.execute(text("""
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE status = 'stacked') as stacked
        FROM containers
    """))
    c_row = containers_result.mappings().first()

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    throughput_result = await db.execute(
        text("""SELECT COUNT(*) as count FROM container_events
                WHERE event_type IN ('discharge', 'load', 'gate_in', 'gate_out')
                AND event_time >= :today"""),
        {"today": today}
    )
    t_row = throughput_result.mappings().first()

    energy_result = await db.execute(
        text("SELECT COALESCE(SUM(energy_kwh), 0) as total FROM energy_readings WHERE timestamp >= :today"),
        {"today": today}
    )
    e_row = energy_result.mappings().first()

    equip_result = await db.execute(text("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status != 'idle') as active FROM port_equipment"))
    eq_row = equip_result.mappings().first()

    energy_kwh = float(e_row["total"])
    return {
        "current_containers": c_row["stacked"] or 0,
        "today_throughput": t_row["count"] or 0,
        "avg_crane_util": 65.0,
        "avg_agv_util": 72.0,
        "today_energy_kwh": round(energy_kwh, 1),
        "energy_cost": round(energy_kwh * 0.85, 2),
        "personnel_on_duty": 24,
        "equipment_active": eq_row["active"] or 0,
    }


async def get_utilization(db: AsyncSession, start_time: str = None, end_time: str = None) -> list:
    time_filter = ""
    params = {}
    if start_time:
        time_filter += " AND er.timestamp >= :start_time"
        params["start_time"] = start_time
    if end_time:
        time_filter += " AND er.timestamp <= :end_time"
        params["end_time"] = end_time

    result = await db.execute(text(f"""
        SELECT pe.equipment_code, pe.name as equipment_name,
               COUNT(*) FILTER (WHERE er.operational_state != 'idle') * 100.0 / NULLIF(COUNT(*), 0) as utilization_percent,
               COUNT(*) FILTER (WHERE er.operational_state != 'idle') / 3600.0 as operating_hours,
               COUNT(*) FILTER (WHERE er.operational_state = 'idle') / 3600.0 as idle_hours
        FROM port_equipment pe
        LEFT JOIN energy_readings er ON pe.id = er.equipment_id {time_filter}
        GROUP BY pe.equipment_code, pe.name
        ORDER BY utilization_percent DESC
    """), params)
    return [dict(r) for r in result.mappings().all()]


async def get_throughput_trend(db: AsyncSession, days: int = 7) -> list:
    start = datetime.now() - timedelta(days=days)
    result = await db.execute(
        text("""
            SELECT DATE(event_time) as time_bucket,
                   COUNT(*) as container_count,
                   COUNT(*) as teu_count
            FROM container_events
            WHERE event_type IN ('discharge', 'load')
            AND event_time >= :start
            GROUP BY DATE(event_time)
            ORDER BY time_bucket
        """),
        {"start": start}
    )
    return [dict(r) for r in result.mappings().all()]


async def get_hourly_metrics(db: AsyncSession, hours: int = 24) -> list:
    result = await db.execute(text("""
        SELECT * FROM yard_metrics_hourly
        ORDER BY metric_time DESC
        LIMIT :hours
    """), {"hours": hours})
    return [dict(r) for r in result.mappings().all()]
