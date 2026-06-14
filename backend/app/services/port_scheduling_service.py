import asyncio
import json
from datetime import date, timedelta, datetime, time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import pulp
    HAS_PULP = True
except ImportError:
    HAS_PULP = False


async def get_personnel(db: AsyncSession, position: str = None, active_only: bool = True):
    query = "SELECT * FROM port_personnel WHERE 1=1"
    params = {}
    if active_only:
        query += " AND is_active = true"
    if position:
        query += " AND position = :position"
        params["position"] = position
    query += " ORDER BY id"
    result = await db.execute(text(query), params)
    return [dict(r) for r in result.mappings().all()]


async def create_personnel(db: AsyncSession, data: dict):
    skills_json = json.dumps(data.get("skills", []))
    await db.execute(
        text("""INSERT INTO port_personnel (employee_code, name, position, skills, max_continuous_hours, min_rest_hours, shift_preference)
                VALUES (:employee_code, :name, :position, :skills, :max_continuous_hours, :min_rest_hours, :shift_preference)"""),
        {**data, "skills": skills_json}
    )
    await db.commit()
    result = await db.execute(text("SELECT * FROM port_personnel ORDER BY id DESC LIMIT 1"))
    return dict(result.mappings().first())


async def update_personnel(db: AsyncSession, personnel_id: int, data: dict):
    sets = []
    params = {"id": personnel_id}
    for key in ["name", "position", "shift_preference", "max_continuous_hours", "min_rest_hours", "is_active"]:
        if key in data and data[key] is not None:
            sets.append(f"{key} = :{key}")
            params[key] = data[key]
    if sets:
        await db.execute(text(f"UPDATE port_personnel SET {', '.join(sets)} WHERE id = :id"), params)
        await db.commit()
    result = await db.execute(text("SELECT * FROM port_personnel WHERE id = :id"), {"id": personnel_id})
    return dict(result.mappings().first())


async def get_shifts(db: AsyncSession):
    result = await db.execute(text("SELECT * FROM shift_definitions ORDER BY id"))
    return [dict(r) for r in result.mappings().all()]


async def create_shift(db: AsyncSession, data: dict):
    req_json = json.dumps(data["required_positions"])
    await db.execute(
        text("""INSERT INTO shift_definitions (shift_name, start_time, end_time, required_positions)
                VALUES (:shift_name, :start_time, :end_time, :required_positions)"""),
        {**data, "required_positions": req_json}
    )
    await db.commit()
    result = await db.execute(text("SELECT * FROM shift_definitions ORDER BY id DESC LIMIT 1"))
    return dict(result.mappings().first())


def _parse_required(required) -> dict:
    if isinstance(required, dict):
        return required
    if isinstance(required, str):
        try:
            return json.loads(required.replace("'", '"'))
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


async def generate_schedule(db: AsyncSession, start_date: date, end_date: date) -> dict:
    personnel = await get_personnel(db, active_only=True)
    shifts = await get_shifts(db)

    if not personnel or not shifts:
        return {"error": "No personnel or shifts defined", "schedules": [], "violations": []}

    await db.execute(
        text("""DELETE FROM schedules
                WHERE schedule_date >= :sd AND schedule_date <= :ed
                AND assignment_type = 'auto' AND status = 'planned'"""),
        {"sd": start_date.isoformat(), "ed": end_date.isoformat()}
    )

    realtime_load = await _get_realtime_load(db)
    existing = await _get_existing_load(db, personnel)
    for pid, extra in realtime_load.items():
        existing[pid] = existing.get(pid, 0) + extra

    result = await asyncio.to_thread(_solve_schedule, personnel, shifts, start_date, end_date, existing)

    for assignment in result["schedules"]:
        await db.execute(
            text("""INSERT INTO schedules (schedule_date, shift_id, personnel_id, assignment_type, status)
                    VALUES (:schedule_date, :shift_id, :personnel_id, 'auto', 'planned')
                    ON CONFLICT (schedule_date, shift_id, personnel_id) DO NOTHING"""),
            assignment
        )

    for violation in result["violations"]:
        await db.execute(
            text("""INSERT INTO schedule_constraints_log (schedule_date, constraint_type, personnel_id, resolution)
                    VALUES (:schedule_date, :constraint_type, :personnel_id, :resolution)"""),
            violation
        )

    await db.commit()
    return result


async def _get_existing_load(db: AsyncSession, personnel: list) -> dict:
    result = await db.execute(text("""
        SELECT personnel_id, COUNT(*) as shift_count
        FROM schedules
        WHERE schedule_date >= CURRENT_DATE - INTERVAL '7 days'
        AND status NOT IN ('cancelled', 'planned')
        GROUP BY personnel_id
    """))
    return {row["personnel_id"]: row["shift_count"] for row in result.mappings().all()}


async def _get_realtime_load(db: AsyncSession) -> dict:
    result = await db.execute(text("""
        SELECT personnel_id, COUNT(*) as active_tasks
        FROM schedules
        WHERE schedule_date = CURRENT_DATE AND status = 'active'
        GROUP BY personnel_id
    """))
    return {row["personnel_id"]: row["active_tasks"] for row in result.mappings().all()}


def _solve_schedule(personnel: list, shifts: list, start_date: date, end_date: date, existing_load: dict) -> dict:
    schedules = []
    violations = []
    days = (end_date - start_date).days + 1

    if not HAS_PULP:
        return _greedy_schedule(personnel, shifts, start_date, days, existing_load)

    day_assignments = {}

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        day_key = current_date.isoformat()
        day_assignments[day_key] = set()

        all_shift_vars = {}

        problem = pulp.LpProblem(f"DaySchedule_{current_date}", pulp.LpMinimize)

        for shift in shifts:
            required = _parse_required(shift.get("required_positions", {}))
            for p in personnel:
                var_name = f"x_{p['id']}_{shift['id']}"
                all_shift_vars[(p["id"], shift["id"])] = pulp.LpVariable(var_name, cat="Binary")

        # Constraint 1: Each person assigned to AT MOST ONE shift per day
        for p in personnel:
            person_vars = [all_shift_vars[(p["id"], s["id"])] for s in shifts if (p["id"], s["id"]) in all_shift_vars]
            if person_vars:
                problem += pulp.lpSum(person_vars) <= 1

        # Constraint 2: Meet required positions per shift
        for shift in shifts:
            required = _parse_required(shift.get("required_positions", {}))
            for position, count in required.items():
                eligible = [p for p in personnel if p["position"] == position]
                if eligible:
                    problem += pulp.lpSum([all_shift_vars[(p["id"], shift["id"])] for p in eligible]) >= count
                else:
                    violations.append({
                        "schedule_date": day_key,
                        "constraint_type": "no_eligible",
                        "personnel_id": 0,
                        "resolution": f"No personnel with position '{position}' for shift {shift['shift_name']}",
                    })

        # Constraint 3: Rest from previous day - block person if assigned yesterday
        prev_day = (current_date - timedelta(days=1)).isoformat()
        if prev_day in day_assignments:
            for p_id in day_assignments[prev_day]:
                for shift in shifts:
                    if shift.get("shift_name", "").startswith("day") or "早" in shift.get("shift_name", ""):
                        if (p_id, shift["id"]) in all_shift_vars:
                            p_obj = next((p for p in personnel if p["id"] == p_id), None)
                            if p_obj and p_obj.get("min_rest_hours", 11) >= 10:
                                problem += all_shift_vars[(p_id, shift["id"])] == 0

        # Objective: minimize preference cost + load imbalance
        obj_terms = []
        for p in personnel:
            pref = p.get("shift_preference", "flexible")
            load_weight = existing_load.get(p["id"], 0) * 2

            for shift in shifts:
                if (p["id"], shift["id"]) not in all_shift_vars:
                    continue
                var = all_shift_vars[(p["id"], shift["id"])]
                shift_name = shift.get("shift_name", "")
                pref_penalty = 0
                if pref == "day" and ("night" in shift_name or "夜" in shift_name):
                    pref_penalty = 10
                elif pref == "night" and ("day" in shift_name or "白" in shift_name or "早" in shift_name):
                    pref_penalty = 10
                obj_terms.append((pref_penalty + load_weight) * var)

        if obj_terms:
            problem += pulp.lpSum(obj_terms)

        try:
            problem.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=10))
        except Exception:
            violations.append({
                "schedule_date": day_key,
                "constraint_type": "solver_error",
                "personnel_id": 0,
                "resolution": "Solver failed to execute",
            })
            continue

        if problem.status == 1:
            for shift in shifts:
                for p in personnel:
                    key = (p["id"], shift["id"])
                    if key in all_shift_vars and all_shift_vars[key].varValue and all_shift_vars[key].varValue > 0.5:
                        schedules.append({
                            "schedule_date": day_key,
                            "shift_id": shift["id"],
                            "personnel_id": p["id"],
                        })
                        day_assignments[day_key].add(p["id"])
                        existing_load[p["id"]] = existing_load.get(p["id"], 0) + 1
        else:
            violations.append({
                "schedule_date": day_key,
                "constraint_type": "infeasible",
                "personnel_id": 0,
                "resolution": f"No feasible solution for {current_date} (status={problem.status})",
            })

    return {"schedules": schedules, "violations": violations}


def _greedy_schedule(personnel: list, shifts: list, start_date: date, days: int, existing_load: dict) -> dict:
    schedules = []
    violations = []
    day_assigned = {}

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        day_key = current_date.isoformat()
        day_assigned[day_key] = set()

        for shift in shifts:
            required = _parse_required(shift.get("required_positions", {}))

            for position, count in required.items():
                eligible = [p for p in personnel if p["position"] == position and p["id"] not in day_assigned[day_key]]
                if not eligible:
                    violations.append({
                        "schedule_date": day_key,
                        "constraint_type": "no_eligible",
                        "personnel_id": 0,
                        "resolution": f"No available personnel with position '{position}' (all already assigned today)",
                    })
                    continue

                eligible_sorted = sorted(eligible, key=lambda p: existing_load.get(p["id"], 0))

                assigned = 0
                for p in eligible_sorted:
                    if assigned >= count:
                        break
                    schedules.append({
                        "schedule_date": day_key,
                        "shift_id": shift["id"],
                        "personnel_id": p["id"],
                    })
                    day_assigned[day_key].add(p["id"])
                    existing_load[p["id"]] = existing_load.get(p["id"], 0) + 1
                    assigned += 1

                if assigned < count:
                    violations.append({
                        "schedule_date": day_key,
                        "constraint_type": "understaffed",
                        "personnel_id": 0,
                        "resolution": f"Need {count} {position} but only {assigned} available for shift {shift['shift_name']}",
                    })

    return {"schedules": schedules, "violations": violations}


async def get_schedules(db: AsyncSession, start_date: str = None, end_date: str = None):
    query = """
        SELECT s.id, s.schedule_date, s.shift_id, s.personnel_id, s.assignment_type, s.status,
               sd.shift_name, pp.name as personnel_name, pp.position
        FROM schedules s
        JOIN shift_definitions sd ON s.shift_id = sd.id
        JOIN port_personnel pp ON s.personnel_id = pp.id
        WHERE 1=1
    """
    params = {}
    if start_date:
        query += " AND s.schedule_date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND s.schedule_date <= :end_date"
        params["end_date"] = end_date
    query += " ORDER BY s.schedule_date, s.shift_id, pp.position"
    result = await db.execute(text(query), params)
    rows = result.mappings().all()
    return [_format_schedule(dict(r)) for r in rows]


async def override_schedule(db: AsyncSession, schedule_id: int, personnel_id: int):
    existing = await db.execute(
        text("SELECT schedule_date, shift_id FROM schedules WHERE id = :id"),
        {"id": schedule_id}
    )
    row = existing.mappings().first()
    if not row:
        return {"error": "Schedule not found"}

    conflict = await db.execute(
        text("""SELECT id FROM schedules
                WHERE schedule_date = :d AND personnel_id = :p AND id != :sid"""),
        {"d": row["schedule_date"], "p": personnel_id, "sid": schedule_id}
    )
    if conflict.first():
        return {"error": "Personnel already assigned to another shift on this date"}

    await db.execute(
        text("UPDATE schedules SET personnel_id = :personnel_id, assignment_type = 'manual_override' WHERE id = :id"),
        {"id": schedule_id, "personnel_id": personnel_id}
    )
    await db.commit()
    return {"message": "Schedule overridden"}


async def get_violations(db: AsyncSession, start_date: str = None, end_date: str = None):
    query = """SELECT scl.*, pp.name as personnel_name
               FROM schedule_constraints_log scl
               LEFT JOIN port_personnel pp ON scl.personnel_id = pp.id
               WHERE 1=1"""
    params = {}
    if start_date:
        query += " AND scl.schedule_date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND scl.schedule_date <= :end_date"
        params["end_date"] = end_date
    query += " ORDER BY scl.created_at DESC LIMIT 100"
    result = await db.execute(text(query), params)
    return [dict(r) for r in result.mappings().all()]


def _format_schedule(row: dict) -> dict:
    if row.get("schedule_date") and isinstance(row["schedule_date"], date):
        row["schedule_date"] = row["schedule_date"].isoformat()
    return row
