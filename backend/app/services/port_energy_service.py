import asyncio
import random
import math
import time as time_module
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

_equipment_cache = []
_db_session_factory = None
_sequence = 0
_equipment_states = {}
_cumulative_kwh = {}
_next_tick_target = 0.0


def time_of_day_factor(hour: int) -> float:
    if 6 <= hour < 22:
        return 0.6 + 0.4 * math.sin((hour - 6) * math.pi / 16)
    return 0.2


def _transition_state(equip_code: str, hour: int) -> str:
    current = _equipment_states.get(equip_code, "idle")
    if random.random() < 0.15:
        weights = [30, 35, 25, 10] if 6 <= hour < 22 else [70, 15, 10, 5]
        current = random.choices(STATES, weights=weights, k=1)[0]
    _equipment_states[equip_code] = current
    return current


def generate_reading(equip: dict, hour: int, tick_ts_ms: int) -> dict:
    state = _transition_state(equip["code"], hour)
    base_factor = STATE_POWER_FACTOR[state]
    tod = time_of_day_factor(hour)
    noise = random.gauss(0, 0.03)
    power_factor = max(0.02, min(1.0, base_factor * tod + noise))

    power_kw = round(equip["max_kw"] * power_factor, 2)
    voltage = round(380 + random.gauss(0, 3), 1)
    current_a = round((power_kw * 1000) / (voltage * 1.732), 2) if voltage > 0 else 0.0
    delta_kwh = round(power_kw / 3600, 6)

    eq_id = equip.get("db_id", 0)
    _cumulative_kwh[eq_id] = _cumulative_kwh.get(eq_id, 0.0) + delta_kwh

    return {
        "equipment_id": eq_id,
        "equipment_code": equip["code"],
        "equipment_type": equip["type"],
        "power_kw": power_kw,
        "delta_kwh": delta_kwh,
        "cumulative_kwh": round(_cumulative_kwh[eq_id], 4),
        "voltage_v": voltage,
        "current_a": current_a,
        "state": state,
        "ts": tick_ts_ms,
    }


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
    global _db_session_factory, _sequence, _next_tick_target
    _db_session_factory = session_factory

    async with session_factory() as db:
        await init_equipment(db)

    _next_tick_target = time_module.monotonic() + 1.0
    batch_buffer = []
    tick = 0

    while True:
        now_mono = time_module.monotonic()
        sleep_needed = _next_tick_target - now_mono
        if sleep_needed > 0:
            await asyncio.sleep(sleep_needed)

        _next_tick_target += 1.0
        _sequence += 1

        wall_now = datetime.now()
        tick_ts_ms = int(wall_now.timestamp() * 1000)
        hour = wall_now.hour

        readings = []
        for equip in _equipment_cache:
            readings.append(generate_reading(equip, hour, tick_ts_ms))

        await manager.broadcast("energy", {
            "type": "tick",
            "seq": _sequence,
            "ts": tick_ts_ms,
            "readings": readings,
        })

        batch_buffer.extend(readings)
        tick += 1

        if tick >= 10:
            tick = 0
            asyncio.create_task(_batch_write_readings(list(batch_buffer)))
            batch_buffer = []


async def _batch_write_readings(readings: list):
    if not _db_session_factory:
        return
    try:
        async with _db_session_factory() as db:
            for r in readings:
                await db.execute(
                    text("""INSERT INTO energy_readings
                            (equipment_id, timestamp, power_kw, energy_kwh, voltage, current_amps, operational_state)
                            VALUES (:eid, to_timestamp(:ts_sec), :power, :delta, :volt, :amp, :state)"""),
                    {
                        "eid": r["equipment_id"],
                        "ts_sec": r["ts"] / 1000.0,
                        "power": r["power_kw"],
                        "delta": r["delta_kwh"],
                        "volt": r["voltage_v"],
                        "amp": r["current_a"],
                        "state": r["state"],
                    }
                )
            await db.commit()
    except Exception:
        pass


async def get_equipment_list(db: AsyncSession):
    result = await db.execute(text("SELECT * FROM port_equipment ORDER BY id"))
    return result.mappings().all()


async def get_energy_history(db: AsyncSession, equipment_id: int = None, start_time: str = None, end_time: str = None, limit: int = 500):
    query = """SELECT er.id, er.equipment_id, pe.equipment_code, pe.equipment_type,
                      EXTRACT(EPOCH FROM er.timestamp)::bigint * 1000 as ts,
                      er.power_kw, er.energy_kwh as delta_kwh,
                      er.voltage as voltage_v, er.current_amps as current_a,
                      er.operational_state as state
               FROM energy_readings er
               JOIN port_equipment pe ON er.equipment_id = pe.id WHERE 1=1"""
    params = {}
    if equipment_id:
        query += " AND er.equipment_id = :equipment_id"
        params["equipment_id"] = equipment_id
    if start_time:
        query += " AND er.timestamp >= :start_time"
        params["start_time"] = start_time
    if end_time:
        query += " AND er.timestamp <= :end_time"
        params["end_time"] = end_time
    query += " ORDER BY er.timestamp DESC LIMIT :limit"
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
        SELECT pe.id as equipment_id, pe.equipment_code, pe.equipment_type, pe.name as equipment_name,
               COALESCE(SUM(er.energy_kwh), 0) as total_kwh,
               COALESCE(AVG(er.power_kw), 0) as avg_power_kw,
               COALESCE(MAX(er.power_kw), 0) as peak_power_kw,
               COUNT(er.id) as sample_count
        FROM port_equipment pe
        LEFT JOIN energy_readings er ON pe.id = er.equipment_id {time_filter}
        GROUP BY pe.id, pe.equipment_code, pe.equipment_type, pe.name
        ORDER BY total_kwh DESC
    """
    result = await db.execute(text(query), params)
    rows = result.mappings().all()
    default_rate = 0.85

    summaries = []
    for row in rows:
        total_kwh = round(float(row["total_kwh"]), 4)
        summaries.append({
            "equipment_id": row["equipment_id"],
            "equipment_code": row["equipment_code"],
            "equipment_type": row["equipment_type"],
            "equipment_name": row["equipment_name"],
            "total_kwh": total_kwh,
            "avg_power_kw": round(float(row["avg_power_kw"]), 2),
            "peak_power_kw": round(float(row["peak_power_kw"]), 2),
            "sample_count": row["sample_count"],
            "cost_yuan": round(total_kwh * default_rate, 2),
        })
    return summaries


async def get_peak_analysis(db: AsyncSession, equipment_id: int = None, top_n: int = 20):
    query = """
        SELECT er.equipment_id, pe.equipment_code, pe.equipment_type,
               er.power_kw as peak_power_kw,
               EXTRACT(EPOCH FROM er.timestamp)::bigint * 1000 as ts,
               er.operational_state as state
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
