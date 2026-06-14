import asyncio
import random
import math
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.ws_manager import manager


EQUIPMENT_SEED = [
    {"code": "CRANE-01", "type": "crane", "name": "岸桥1号", "max_kw": 800, "x": 100, "y": 50, "z": 0},
    {"code": "CRANE-02", "type": "crane", "name": "岸桥2号", "max_kw": 800, "x": 200, "y": 50, "z": 0},
    {"code": "CRANE-03", "type": "crane", "name": "场桥1号", "max_kw": 400, "x": 150, "y": 150, "z": 0},
    {"code": "CRANE-04", "type": "crane", "name": "场桥2号", "max_kw": 400, "x": 250, "y": 150, "z": 0},
    {"code": "AGV-01", "type": "agv", "name": "自动导引车1号", "max_kw": 120, "x": 120, "y": 100, "z": 0},
    {"code": "AGV-02", "type": "agv", "name": "自动导引车2号", "max_kw": 120, "x": 180, "y": 100, "z": 0},
    {"code": "AGV-03", "type": "agv", "name": "自动导引车3号", "max_kw": 120, "x": 220, "y": 100, "z": 0},
    {"code": "AGV-04", "type": "agv", "name": "自动导引车4号", "max_kw": 120, "x": 280, "y": 100, "z": 0},
]

STATES = ["idle", "lifting", "traversing", "rotating"]
STATE_POWER_FACTOR = {"idle": 0.08, "lifting": 0.85, "traversing": 0.55, "rotating": 0.40}


def time_of_day_factor(hour: int) -> float:
    if 6 <= hour < 22:
        return 0.6 + 0.4 * math.sin((hour - 6) * math.pi / 16)
    return 0.2


def generate_reading(equip: dict, hour: int) -> dict:
    state = random.choices(
        STATES,
        weights=[30, 35, 25, 10] if 6 <= hour < 22 else [70, 15, 10, 5],
        k=1
    )[0]
    base_factor = STATE_POWER_FACTOR[state]
    tod = time_of_day_factor(hour)
    noise = random.gauss(0, 0.05)
    power_factor = max(0.02, min(1.0, base_factor * tod + noise))
    power_kw = equip["max_kw"] * power_factor
    voltage = 380 + random.gauss(0, 5)
    current_amps = (power_kw * 1000) / (voltage * 1.732) if voltage > 0 else 0
    energy_kwh = power_kw / 3600

    return {
        "equipment_id": equip.get("db_id", 0),
        "equipment_code": equip["code"],
        "power_kw": round(power_kw, 2),
        "energy_kwh": round(energy_kwh, 4),
        "voltage": round(voltage, 1),
        "current_amps": round(current_amps, 2),
        "operational_state": state,
        "timestamp": datetime.now().isoformat(),
    }


_equipment_cache = []
_batch_buffer = []
_db_session_factory = None


async def init_equipment(db: AsyncSession):
    global _equipment_cache
    result = await db.execute(text("SELECT id, equipment_code FROM port_equipment"))
    rows = result.fetchall()
    if not rows:
        for eq in EQUIPMENT_SEED:
            await db.execute(
                text("""INSERT INTO port_equipment (equipment_code, equipment_type, name, max_power_kw, location_x, location_y, location_z, status)
                        VALUES (:code, :type, :name, :max_kw, :x, :y, :z, 'idle')"""),
                eq
            )
        await db.commit()
        result = await db.execute(text("SELECT id, equipment_code FROM port_equipment"))
        rows = result.fetchall()

    code_to_id = {row[1]: row[0] for row in rows}
    _equipment_cache = []
    for eq in EQUIPMENT_SEED:
        eq_copy = eq.copy()
        eq_copy["db_id"] = code_to_id.get(eq["code"], 0)
        _equipment_cache.append(eq_copy)


async def start_energy_simulator(session_factory):
    global _db_session_factory
    _db_session_factory = session_factory

    async with session_factory() as db:
        await init_equipment(db)

    tick = 0
    while True:
        await asyncio.sleep(1)
        now = datetime.now()
        hour = now.hour
        readings = []
        for equip in _equipment_cache:
            reading = generate_reading(equip, hour)
            readings.append(reading)
            await manager.broadcast("energy", reading)

        tick += 1
        if tick >= 10:
            tick = 0
            await _batch_write_readings(readings)


async def _batch_write_readings(readings: list):
    if not _db_session_factory:
        return
    try:
        async with _db_session_factory() as db:
            for r in readings:
                await db.execute(
                    text("""INSERT INTO energy_readings (equipment_id, timestamp, power_kw, energy_kwh, voltage, current_amps, operational_state)
                            VALUES (:equipment_id, :timestamp, :power_kw, :energy_kwh, :voltage, :current_amps, :operational_state)"""),
                    {
                        "equipment_id": r["equipment_id"],
                        "timestamp": r["timestamp"],
                        "power_kw": r["power_kw"],
                        "energy_kwh": r["energy_kwh"],
                        "voltage": r["voltage"],
                        "current_amps": r["current_amps"],
                        "operational_state": r["operational_state"],
                    }
                )
            await db.commit()
    except Exception:
        pass


async def get_equipment_list(db: AsyncSession):
    result = await db.execute(text("SELECT * FROM port_equipment ORDER BY id"))
    return result.mappings().all()


async def get_energy_history(db: AsyncSession, equipment_id: int = None, start_time: str = None, end_time: str = None, limit: int = 500):
    query = "SELECT * FROM energy_readings WHERE 1=1"
    params = {}
    if equipment_id:
        query += " AND equipment_id = :equipment_id"
        params["equipment_id"] = equipment_id
    if start_time:
        query += " AND timestamp >= :start_time"
        params["start_time"] = start_time
    if end_time:
        query += " AND timestamp <= :end_time"
        params["end_time"] = end_time
    query += " ORDER BY timestamp DESC LIMIT :limit"
    params["limit"] = limit
    result = await db.execute(text(query), params)
    return result.mappings().all()


async def get_cost_summary(db: AsyncSession, start_time: str = None, end_time: str = None):
    time_filter = ""
    params = {}
    if start_time:
        time_filter += " AND er.timestamp >= :start_time"
        params["start_time"] = start_time
    if end_time:
        time_filter += " AND er.timestamp <= :end_time"
        params["end_time"] = end_time

    query = f"""
        SELECT pe.id as equipment_id, pe.equipment_code, pe.name as equipment_name,
               COALESCE(SUM(er.energy_kwh), 0) as total_energy_kwh,
               COALESCE(AVG(er.power_kw), 0) as avg_power_kw,
               COALESCE(MAX(er.power_kw), 0) as max_power_kw,
               COUNT(er.id) / 3600.0 as operating_hours
        FROM port_equipment pe
        LEFT JOIN energy_readings er ON pe.id = er.equipment_id {time_filter}
        GROUP BY pe.id, pe.equipment_code, pe.name
        ORDER BY total_energy_kwh DESC
    """
    result = await db.execute(text(query), params)
    rows = result.mappings().all()

    cost_configs = await db.execute(text("SELECT * FROM energy_cost_config WHERE is_active = true"))
    configs = cost_configs.mappings().all()
    default_rate = 0.85

    summaries = []
    for row in rows:
        cost = float(row["total_energy_kwh"]) * default_rate
        summaries.append({
            "equipment_id": row["equipment_id"],
            "equipment_code": row["equipment_code"],
            "equipment_name": row["equipment_name"],
            "total_energy_kwh": round(float(row["total_energy_kwh"]), 2),
            "avg_power_kw": round(float(row["avg_power_kw"]), 2),
            "max_power_kw": round(float(row["max_power_kw"]), 2),
            "operating_hours": round(float(row["operating_hours"]), 2),
            "cost": round(cost, 2),
        })
    return summaries


async def get_peak_analysis(db: AsyncSession, equipment_id: int = None, top_n: int = 20):
    query = """
        SELECT er.equipment_id, pe.equipment_code, er.power_kw as peak_power_kw,
               er.timestamp as peak_time, er.operational_state
        FROM energy_readings er
        JOIN port_equipment pe ON er.equipment_id = pe.id
    """
    params = {"top_n": top_n}
    if equipment_id:
        query += " WHERE er.equipment_id = :equipment_id"
        params["equipment_id"] = equipment_id
    query += " ORDER BY er.power_kw DESC LIMIT :top_n"
    result = await db.execute(text(query), params)
    return result.mappings().all()
