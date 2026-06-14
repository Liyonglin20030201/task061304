import asyncio
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
    await db.execute(
        text("""INSERT INTO port_personnel (employee_code, name, position, skills, max_continuous_hours, min_rest_hours, shift_preference)
                VALUES (:employee_code, :name, :position, :skills, :max_continuous_hours, :min_rest_hours, :shift_preference)"""),
        {**data, "skills": str(data.get("skills", []))}
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
    await db.execute(
        text("""INSERT INTO shift_definitions (shift_name, start_time, end_time, required_positions)
                VALUES (:shift_name, :start_time, :end_time, :required_positions)"""),
        {**data, "required_positions": str(data["required_positions"])}
    )
    await db.commit()
    result = await db.execute(text("SELECT * FROM shift_definitions ORDER BY id DESC LIMIT 1"))
    return dict(result.mappings().first())


async def generate_schedule(db: AsyncSession, start_date: date, end_date: date) -> dict:
    personnel = await get_personnel(db, active_only=True)
    shifts = await get_shifts(db)

    if not personnel or not shifts:
        return {"error": "No personnel or shifts defined", "schedules": [], "violations": []}

    result = await asyncio.to_thread(_solve_schedule, personnel, shifts, start_date, end_date)

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


def _solve_schedule(personnel: list, shifts: list, start_date: date, end_date: date) -> dict:
    schedules = []
    violations = []
    days = (end_date - start_date).days + 1

    if not HAS_PULP:
        return _greedy_schedule(personnel, shifts, start_date, days)

    prev_assignments = {}

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)

        for shift in shifts:
            required = shift.get("required_positions", {})
            if isinstance(required, str):
                import json
                try:
                    required = json.loads(required.replace("'", '"'))
                except:
                    required = {}

            problem = pulp.LpProblem(f"Schedule_{current_date}_{shift['id']}", pulp.LpMinimize)

            x = {}
            for p in personnel:
                x[p["id"]] = pulp.LpVariable(f"x_{p['id']}_{shift['id']}_{current_date}", cat="Binary")

            # Objective: minimize preference penalty + fairness
            preference_cost = []
            for p in personnel:
                pref = p.get("shift_preference", "flexible")
                shift_name = shift.get("shift_name", "")
                penalty = 0
                if pref == "day" and "night" in shift_name:
                    penalty = 10
                elif pref == "night" and "day" in shift_name:
                    penalty = 10
                preference_cost.append(penalty * x[p["id"]])

            problem += pulp.lpSum(preference_cost)

            # Constraint: meet required positions
            for position, count in required.items():
                eligible = [p for p in personnel if p["position"] == position]
                if eligible:
                    problem += pulp.lpSum([x[p["id"]] for p in eligible]) >= count

            # Constraint: rest hours - skip if assigned to prev shift same day
            for p_id in prev_assignments:
                if prev_assignments[p_id] == current_date:
                    if p_id in x:
                        problem += x[p_id] == 0

            try:
                problem.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=5))
            except:
                continue

            if problem.status == 1:
                for p in personnel:
                    if x[p["id"]].varValue and x[p["id"]].varValue > 0.5:
                        schedules.append({
                            "schedule_date": current_date.isoformat(),
                            "shift_id": shift["id"],
                            "personnel_id": p["id"],
                        })
                        prev_assignments[p["id"]] = current_date
            else:
                violations.append({
                    "schedule_date": current_date.isoformat(),
                    "constraint_type": "infeasible",
                    "personnel_id": 0,
                    "resolution": f"No feasible solution for shift {shift['shift_name']} on {current_date}",
                })

    return {"schedules": schedules, "violations": violations}


def _greedy_schedule(personnel: list, shifts: list, start_date: date, days: int) -> dict:
    schedules = []
    violations = []
    rotation_index = {}

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        for shift in shifts:
            required = shift.get("required_positions", {})
            if isinstance(required, str):
                import json
                try:
                    required = json.loads(required.replace("'", '"'))
                except:
                    required = {}

            for position, count in required.items():
                eligible = [p for p in personnel if p["position"] == position]
                if not eligible:
                    violations.append({
                        "schedule_date": current_date.isoformat(),
                        "constraint_type": "no_eligible",
                        "personnel_id": 0,
                        "resolution": f"No personnel with position {position}",
                    })
                    continue

                key = f"{position}_{shift['id']}"
                start_idx = rotation_index.get(key, 0)
                assigned = 0
                for i in range(len(eligible)):
                    idx = (start_idx + i) % len(eligible)
                    if assigned >= count:
                        break
                    schedules.append({
                        "schedule_date": current_date.isoformat(),
                        "shift_id": shift["id"],
                        "personnel_id": eligible[idx]["id"],
                    })
                    assigned += 1
                rotation_index[key] = (start_idx + count) % max(len(eligible), 1)

    return {"schedules": schedules, "violations": violations}


async def get_schedules(db: AsyncSession, start_date: str = None, end_date: str = None):
    query = """
        SELECT s.*, sd.shift_name, pp.name as personnel_name, pp.position
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
    query += " ORDER BY s.schedule_date, s.shift_id"
    result = await db.execute(text(query), params)
    return [dict(r) for r in result.mappings().all()]


async def override_schedule(db: AsyncSession, schedule_id: int, personnel_id: int):
    await db.execute(
        text("UPDATE schedules SET personnel_id = :personnel_id, assignment_type = 'manual_override' WHERE id = :id"),
        {"id": schedule_id, "personnel_id": personnel_id}
    )
    await db.commit()
    return {"message": "Schedule overridden"}


async def get_violations(db: AsyncSession, start_date: str = None, end_date: str = None):
    query = "SELECT scl.*, pp.name as personnel_name FROM schedule_constraints_log scl LEFT JOIN port_personnel pp ON scl.personnel_id = pp.id WHERE 1=1"
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
