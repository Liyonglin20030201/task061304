from datetime import date, datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np


DEFAULT_WEIGHTS = {
    "weight_sales": 0.40,
    "weight_service": 0.25,
    "weight_attendance": 0.20,
    "weight_training": 0.15,
}


async def _get_weight_config(db: AsyncSession, store_id: int, position: Optional[str] = None) -> dict:
    pos = position or "default"
    sql = text("""
        SELECT weight_sales, weight_service, weight_attendance, weight_training
        FROM performance_weight_configs
        WHERE store_id = :store_id AND position = :position
    """)
    result = await db.execute(sql, {"store_id": store_id, "position": pos})
    row = result.fetchone()
    if row:
        return {"weight_sales": row[0], "weight_service": row[1], "weight_attendance": row[2], "weight_training": row[3]}

    if pos != "default":
        sql2 = text("""
            SELECT weight_sales, weight_service, weight_attendance, weight_training
            FROM performance_weight_configs
            WHERE store_id = :store_id AND position = 'default'
        """)
        result2 = await db.execute(sql2, {"store_id": store_id})
        row2 = result2.fetchone()
        if row2:
            return {"weight_sales": row2[0], "weight_service": row2[1], "weight_attendance": row2[2], "weight_training": row2[3]}

    return DEFAULT_WEIGHTS


async def _calc_sales_score(db: AsyncSession, employee_id: int, store_id: int, start_date: date, end_date: date) -> float:
    sql = text("""
        SELECT COALESCE(SUM(revenue), 0), COALESCE(SUM(quantity_sold), 0), AVG(conversion_rate)
        FROM employee_sales_records
        WHERE employee_id = :emp_id AND record_date BETWEEN :start AND :end
    """)
    result = await db.execute(sql, {"emp_id": employee_id, "start": start_date, "end": end_date})
    row = result.fetchone()
    emp_revenue, emp_qty, emp_conv = row[0], row[1], row[2] or 0

    peers_sql = text("""
        SELECT employee_id, SUM(revenue) as total_rev
        FROM employee_sales_records
        WHERE store_id = :store_id AND record_date BETWEEN :start AND :end
        GROUP BY employee_id
    """)
    peers_result = await db.execute(peers_sql, {"store_id": store_id, "start": start_date, "end": end_date})
    peers = peers_result.fetchall()

    if not peers:
        return 50.0

    revenues = [p[1] for p in peers]
    if len(revenues) <= 1:
        return 75.0

    rank = sum(1 for r in revenues if r < emp_revenue)
    percentile = rank / len(revenues) * 100
    return min(100, max(0, percentile))


async def _calc_service_score(db: AsyncSession, employee_id: int, start_date: date, end_date: date) -> float:
    sql = text("""
        SELECT AVG(sr.customer_rating), COALESCE(SUM(sr.complaint_count), 0), COALESCE(SUM(sr.praise_count), 0),
               COUNT(sr.id)
        FROM employee_service_records sr
        JOIN employees e ON e.id = sr.employee_id AND e.store_id = sr.store_id
        WHERE sr.employee_id = :emp_id AND sr.record_date BETWEEN :start AND :end
    """)
    result = await db.execute(sql, {"emp_id": employee_id, "start": start_date, "end": end_date})
    row = result.fetchone()
    avg_rating = row[0] or 3.0
    complaints = row[1]
    praises = row[2]
    record_count = row[3]

    if record_count == 0:
        return 60.0

    base = (avg_rating / 5.0) * 80
    bonus = min(20, praises * 3)
    penalty = min(40, complaints * 5)
    return min(100, max(0, base + bonus - penalty))


async def _calc_attendance_score(db: AsyncSession, employee_id: int, start_date: date, end_date: date) -> float:
    sql = text("""
        SELECT COALESCE(SUM(ea.is_absent), 0), COALESCE(SUM(ea.is_late), 0),
               COALESCE(SUM(ea.scheduled_hours), 0), COALESCE(SUM(ea.actual_hours), 0),
               COUNT(ea.id)
        FROM employee_attendance ea
        JOIN employees e ON e.id = ea.employee_id AND e.store_id = ea.store_id
        WHERE ea.employee_id = :emp_id AND ea.attend_date BETWEEN :start AND :end
    """)
    result = await db.execute(sql, {"emp_id": employee_id, "start": start_date, "end": end_date})
    row = result.fetchone()
    absents, lates = row[0], row[1]
    scheduled, actual = row[2], row[3]
    record_count = row[4]

    if record_count == 0:
        return 70.0

    missed_hours = max(0, scheduled - actual)
    score = 100 - absents * 15 - lates * 5 - missed_hours * 2
    return min(100, max(0, score))


async def _calc_training_score(db: AsyncSession, employee_id: int, start_date: date, end_date: date) -> float:
    sql = text("""
        SELECT COUNT(*) as total,
               COALESCE(SUM(completed), 0) as completed_count,
               AVG(CASE WHEN completed = 1 THEN score END) as avg_score
        FROM employee_training
        WHERE employee_id = :emp_id AND scheduled_date BETWEEN :start AND :end
    """)
    result = await db.execute(sql, {"emp_id": employee_id, "start": start_date, "end": end_date})
    row = result.fetchone()
    total = row[0] or 0
    completed = row[1] or 0
    avg_score = row[2] or 0

    if total == 0:
        return 70.0

    completion_rate = completed / total
    return completion_rate * 70 + (avg_score / 100) * 30


async def calculate_performance_score(db: AsyncSession, employee_id: int, start_date: date, end_date: date) -> dict:
    emp_sql = text("SELECT id, name, position, store_id FROM employees WHERE id = :emp_id")
    emp_result = await db.execute(emp_sql, {"emp_id": employee_id})
    emp = emp_result.fetchone()
    if not emp:
        return None

    store_id = emp[3]
    position = emp[2]
    weights = await _get_weight_config(db, store_id, position)

    sales_score = await _calc_sales_score(db, employee_id, store_id, start_date, end_date)
    service_score = await _calc_service_score(db, employee_id, start_date, end_date)
    attendance_score = await _calc_attendance_score(db, employee_id, start_date, end_date)
    training_score = await _calc_training_score(db, employee_id, start_date, end_date)

    composite = (
        weights["weight_sales"] * sales_score +
        weights["weight_service"] * service_score +
        weights["weight_attendance"] * attendance_score +
        weights["weight_training"] * training_score
    )

    return {
        "employee_id": employee_id,
        "employee_name": emp[1],
        "position": position,
        "store_id": store_id,
        "composite_score": round(composite, 2),
        "sales_score": round(sales_score, 2),
        "service_score": round(service_score, 2),
        "attendance_score": round(attendance_score, 2),
        "training_score": round(training_score, 2),
    }


async def get_performance_ranking(
    db: AsyncSession, store_ids: Optional[List[int]],
    start_date: date, end_date: date, position: Optional[str] = None, top_n: int = 20,
) -> List[dict]:
    if store_ids is not None and len(store_ids) == 0:
        return []

    store_filter = ""
    params = {"start": start_date, "end": end_date}
    if store_ids is not None:
        store_filter = "AND store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    pos_filter = ""
    if position:
        pos_filter = "AND position = :position"
        params["position"] = position

    sql = text(f"""
        SELECT id, name, position, store_id
        FROM employees WHERE is_active = 1 {store_filter} {pos_filter}
    """)
    result = await db.execute(sql, params)
    employees = result.fetchall()

    scores = []
    for emp in employees:
        score_data = await calculate_performance_score(db, emp[0], start_date, end_date)
        if score_data:
            scores.append(score_data)

    scores.sort(key=lambda x: x["composite_score"], reverse=True)

    for i, s in enumerate(scores):
        s["rank_in_store"] = i + 1
        if i > 0 and scores[i - 1]["composite_score"] > s["composite_score"]:
            s["trend"] = "down"
        elif i == 0:
            s["trend"] = "up"
        else:
            s["trend"] = "stable"

    return scores[:top_n]


async def get_performance_trend(db: AsyncSession, employee_id: int, months: int = 6) -> List[dict]:
    today = date.today()
    trends = []

    for i in range(months - 1, -1, -1):
        end = today - timedelta(days=i * 30)
        start = end - timedelta(days=30)
        score_data = await calculate_performance_score(db, employee_id, start, end)
        if score_data:
            trends.append({
                "month": end.strftime("%Y-%m"),
                "composite_score": score_data["composite_score"],
                "sales_score": score_data["sales_score"],
                "service_score": score_data["service_score"],
                "attendance_score": score_data["attendance_score"],
                "training_score": score_data["training_score"],
            })

    return trends


async def get_peer_comparison(db: AsyncSession, employee_id: int, start_date: date, end_date: date, scope: str = "store") -> dict:
    emp_sql = text("SELECT id, name, position, store_id FROM employees WHERE id = :emp_id")
    emp_result = await db.execute(emp_sql, {"emp_id": employee_id})
    emp = emp_result.fetchone()
    if not emp:
        return None

    emp_score = await calculate_performance_score(db, employee_id, start_date, end_date)

    if scope == "store":
        peers_sql = text("SELECT id FROM employees WHERE store_id = :store_id AND is_active = 1 AND id != :emp_id")
        peers_result = await db.execute(peers_sql, {"store_id": emp[3], "emp_id": employee_id})
    else:
        peers_sql = text("SELECT id FROM employees WHERE is_active = 1 AND id != :emp_id")
        peers_result = await db.execute(peers_sql, {"emp_id": employee_id})

    peers = peers_result.fetchall()
    peer_scores = []
    for p in peers[:50]:
        ps = await calculate_performance_score(db, p[0], start_date, end_date)
        if ps:
            peer_scores.append(ps)

    if not peer_scores:
        peer_avg = {"sales_score": 50, "service_score": 50, "attendance_score": 50, "training_score": 50}
    else:
        peer_avg = {
            "sales_score": float(np.mean([p["sales_score"] for p in peer_scores])),
            "service_score": float(np.mean([p["service_score"] for p in peer_scores])),
            "attendance_score": float(np.mean([p["attendance_score"] for p in peer_scores])),
            "training_score": float(np.mean([p["training_score"] for p in peer_scores])),
        }

    dimensions = ["销售业绩", "服务质量", "出勤考核", "培训发展"]
    return {
        "employee_name": emp[1],
        "dimensions": dimensions,
        "employee_scores": [
            emp_score["sales_score"], emp_score["service_score"],
            emp_score["attendance_score"], emp_score["training_score"],
        ],
        "store_avg_scores": [
            round(peer_avg["sales_score"], 2), round(peer_avg["service_score"], 2),
            round(peer_avg["attendance_score"], 2), round(peer_avg["training_score"], 2),
        ],
        "chain_avg_scores": [
            round(peer_avg["sales_score"], 2), round(peer_avg["service_score"], 2),
            round(peer_avg["attendance_score"], 2), round(peer_avg["training_score"], 2),
        ],
    }


async def get_dashboard(db: AsyncSession, store_ids: Optional[List[int]], start_date: date, end_date: date) -> dict:
    if store_ids is not None and len(store_ids) == 0:
        return {
            "avg_score": 0, "top_performer": None, "top_score": 0,
            "improvement_rate": 0, "avg_attendance_rate": 0, "total_employees": 0,
        }

    store_filter = ""
    params = {}
    if store_ids is not None:
        store_filter = "AND store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    count_sql = text(f"SELECT COUNT(*) FROM employees WHERE is_active = 1 {store_filter}")
    count_result = await db.execute(count_sql, params)
    total = count_result.scalar() or 0

    if total == 0:
        return {
            "avg_score": 0, "top_performer": None, "top_score": 0,
            "improvement_rate": 0, "avg_attendance_rate": 0, "total_employees": 0,
        }

    emp_sql = text(f"SELECT id FROM employees WHERE is_active = 1 {store_filter} LIMIT 50")
    emp_result = await db.execute(emp_sql, params)
    employees = emp_result.fetchall()

    scores = []
    for e in employees:
        s = await calculate_performance_score(db, e[0], start_date, end_date)
        if s:
            scores.append(s)

    if not scores:
        return {
            "avg_score": 0, "top_performer": None, "top_score": 0,
            "improvement_rate": 0, "avg_attendance_rate": 0, "total_employees": total,
        }

    scores.sort(key=lambda x: x["composite_score"], reverse=True)
    avg_score = float(np.mean([s["composite_score"] for s in scores]))
    avg_attendance = float(np.mean([s["attendance_score"] for s in scores]))

    return {
        "avg_score": round(avg_score, 2),
        "top_performer": scores[0]["employee_name"],
        "top_score": scores[0]["composite_score"],
        "improvement_rate": 0.0,
        "avg_attendance_rate": round(avg_attendance, 2),
        "total_employees": total,
    }


async def get_weight_config(db: AsyncSession, store_id: int) -> dict:
    sql = text("SELECT * FROM performance_weight_configs WHERE store_id = :store_id ORDER BY position")
    result = await db.execute(sql, {"store_id": store_id})
    rows = result.fetchall()
    if not rows:
        return {"store_id": store_id, "position": "default", **DEFAULT_WEIGHTS}
    columns = result.keys()
    return [dict(zip(columns, r)) for r in rows]


async def update_weight_config(db: AsyncSession, config: dict) -> dict:
    now = datetime.now(timezone.utc)
    sql = text("""
        INSERT INTO performance_weight_configs (store_id, position, weight_sales, weight_service, weight_attendance, weight_training, updated_at, created_at)
        VALUES (:store_id, :position, :weight_sales, :weight_service, :weight_attendance, :weight_training, :now, :now)
        ON CONFLICT (store_id, position)
        DO UPDATE SET weight_sales = :weight_sales, weight_service = :weight_service,
                      weight_attendance = :weight_attendance, weight_training = :weight_training, updated_at = :now
    """)
    await db.execute(sql, {**config, "now": now})
    await db.commit()
    return {"message": "权重配置已更新"}
