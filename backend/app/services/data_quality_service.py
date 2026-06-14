from datetime import datetime, date, timezone, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np


TABLE_CONFIG = {
    "sales": {"date_column": "sale_date", "store_column": "store_id"},
    "inventory": {"date_column": "snapshot_date", "store_column": "store_id"},
    "traffic": {"date_column": "traffic_date", "store_column": "store_id"},
    "members": {"date_column": "created_at", "store_column": "store_id"},
}


async def _check_completeness(db: AsyncSession, target_table: str, store_ids: Optional[List[int]], check_date: date) -> dict:
    store_filter = ""
    params = {"check_date": str(check_date)}
    if store_ids is not None:
        store_filter = f"AND {TABLE_CONFIG.get(target_table, {}).get('store_column', 'store_id')} = ANY(:store_ids)"
        params["store_ids"] = store_ids

    date_col = TABLE_CONFIG.get(target_table, {}).get("date_column", "created_at")

    total_sql = text(f"""
        SELECT COUNT(*) as total FROM {target_table}
        WHERE CAST({date_col} AS DATE) <= :check_date {store_filter}
    """)
    result = await db.execute(total_sql, params)
    total = result.scalar() or 0

    if total == 0:
        return {"score": 100.0, "total_records": 0, "failed_records": 0, "details": {"message": "无数据"}}

    columns_sql = text(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :table_name AND is_nullable = 'YES'
    """)
    col_result = await db.execute(columns_sql, {"table_name": target_table})
    nullable_cols = [r[0] for r in col_result.fetchall()]

    total_nulls = 0
    total_checks = 0
    col_details = {}
    for col in nullable_cols[:20]:
        null_sql = text(f"""
            SELECT COUNT(*) FROM {target_table}
            WHERE {col} IS NULL AND CAST({date_col} AS DATE) <= :check_date {store_filter}
        """)
        null_result = await db.execute(null_sql, params)
        null_count = null_result.scalar() or 0
        total_nulls += null_count
        total_checks += total
        if null_count > 0:
            col_details[col] = {"null_count": null_count, "null_rate": round(null_count / total, 4)}

    if total_checks == 0:
        score = 100.0
    else:
        score = round((1 - total_nulls / total_checks) * 100, 2)

    return {
        "score": max(0, score),
        "total_records": total,
        "failed_records": total_nulls,
        "details": col_details,
    }


async def _check_accuracy(db: AsyncSession, target_table: str, store_ids: Optional[List[int]], check_date: date) -> dict:
    store_filter = ""
    params = {"check_date": str(check_date)}
    if store_ids is not None:
        store_filter = f"AND {TABLE_CONFIG.get(target_table, {}).get('store_column', 'store_id')} = ANY(:store_ids)"
        params["store_ids"] = store_ids

    date_col = TABLE_CONFIG.get(target_table, {}).get("date_column", "created_at")

    total_sql = text(f"""
        SELECT COUNT(*) FROM {target_table}
        WHERE CAST({date_col} AS DATE) <= :check_date {store_filter}
    """)
    result = await db.execute(total_sql, params)
    total = result.scalar() or 0

    if total == 0:
        return {"score": 100.0, "total_records": 0, "failed_records": 0, "details": {}}

    violations = 0
    details = {}

    if target_table == "sales":
        checks = [
            ("negative_amount", "SELECT COUNT(*) FROM sales WHERE total_amount < 0 AND CAST(sale_date AS DATE) <= :check_date"),
            ("negative_quantity", "SELECT COUNT(*) FROM sales WHERE quantity <= 0 AND CAST(sale_date AS DATE) <= :check_date"),
            ("price_outlier", """
                SELECT COUNT(*) FROM sales
                WHERE unit_price > 100000 AND CAST(sale_date AS DATE) <= :check_date
            """),
        ]
    elif target_table == "inventory":
        checks = [
            ("negative_stock", "SELECT COUNT(*) FROM inventory WHERE current_stock < 0 AND CAST(snapshot_date AS DATE) <= :check_date"),
            ("min_exceeds_max", "SELECT COUNT(*) FROM inventory WHERE min_stock > max_stock AND CAST(snapshot_date AS DATE) <= :check_date"),
        ]
    elif target_table == "traffic":
        checks = [
            ("negative_count", "SELECT COUNT(*) FROM traffic WHERE customer_count < 0 AND CAST(traffic_date AS DATE) <= :check_date"),
            ("extreme_count", "SELECT COUNT(*) FROM traffic WHERE customer_count > 100000 AND CAST(traffic_date AS DATE) <= :check_date"),
        ]
    else:
        checks = []

    for check_name, sql in checks:
        check_sql = text(sql + (f" {store_filter}" if store_filter else ""))
        r = await db.execute(check_sql, params)
        count = r.scalar() or 0
        violations += count
        if count > 0:
            details[check_name] = {"count": count, "rate": round(count / total, 4)}

    score = round((1 - violations / max(total, 1)) * 100, 2)
    return {
        "score": max(0, min(100, score)),
        "total_records": total,
        "failed_records": violations,
        "details": details,
    }


async def _check_timeliness(db: AsyncSession, target_table: str, store_ids: Optional[List[int]], check_date: date) -> dict:
    store_filter = ""
    params = {}
    if store_ids is not None:
        store_filter = f"WHERE {TABLE_CONFIG.get(target_table, {}).get('store_column', 'store_id')} = ANY(:store_ids)"
        params["store_ids"] = store_ids

    date_col = TABLE_CONFIG.get(target_table, {}).get("date_column", "created_at")

    sql = text(f"SELECT MAX({date_col}) FROM {target_table} {store_filter}")
    result = await db.execute(sql, params)
    latest = result.scalar()

    if latest is None:
        return {"score": 0.0, "total_records": 0, "failed_records": 0, "details": {"message": "无数据"}}

    if isinstance(latest, datetime):
        latest_date = latest.date()
    else:
        latest_date = latest

    days_stale = (check_date - latest_date).days
    max_acceptable_days = 2

    if days_stale <= max_acceptable_days:
        score = 100.0
    else:
        score = max(0, 100 - (days_stale - max_acceptable_days) * 15)

    return {
        "score": round(score, 2),
        "total_records": 1,
        "failed_records": 1 if days_stale > max_acceptable_days else 0,
        "details": {"latest_date": str(latest_date), "days_stale": days_stale},
    }


async def calculate_overall_health(db: AsyncSession, store_ids: Optional[List[int]]) -> dict:
    today = date.today()
    tables = list(TABLE_CONFIG.keys())

    completeness_scores = []
    accuracy_scores = []
    timeliness_scores = []

    for tbl in tables:
        c = await _check_completeness(db, tbl, store_ids, today)
        a = await _check_accuracy(db, tbl, store_ids, today)
        t = await _check_timeliness(db, tbl, store_ids, today)
        completeness_scores.append(c["score"])
        accuracy_scores.append(a["score"])
        timeliness_scores.append(t["score"])

    comp_avg = float(np.mean(completeness_scores)) if completeness_scores else 100.0
    acc_avg = float(np.mean(accuracy_scores)) if accuracy_scores else 100.0
    time_avg = float(np.mean(timeliness_scores)) if timeliness_scores else 100.0

    overall = comp_avg * 0.35 + acc_avg * 0.40 + time_avg * 0.25

    alert_sql = text("SELECT COUNT(*) FROM data_quality_alerts WHERE status = 'open'")
    alert_result = await db.execute(alert_sql)
    alerts_open = alert_result.scalar() or 0

    critical_sql = text("SELECT COUNT(*) FROM data_quality_alerts WHERE status = 'open' AND severity IN ('error', 'critical')")
    critical_result = await db.execute(critical_sql)
    alerts_critical = critical_result.scalar() or 0

    run_sql = text("SELECT MAX(completed_at) FROM data_quality_check_runs WHERE status = 'completed'")
    run_result = await db.execute(run_sql)
    last_check = run_result.scalar()

    return {
        "overall_score": round(overall, 2),
        "completeness_score": round(comp_avg, 2),
        "accuracy_score": round(acc_avg, 2),
        "timeliness_score": round(time_avg, 2),
        "alerts_open": alerts_open,
        "alerts_critical": alerts_critical,
        "last_check_at": last_check,
    }


async def get_quality_scores(
    db: AsyncSession, store_ids: Optional[List[int]],
    target_table: Optional[str] = None, dimension: Optional[str] = None,
    start_date: Optional[date] = None, end_date: Optional[date] = None,
) -> List[dict]:
    today = date.today()
    tables = [target_table] if target_table else list(TABLE_CONFIG.keys())
    dimensions = [dimension] if dimension else ["completeness", "accuracy", "timeliness"]

    results = []
    for tbl in tables:
        for dim in dimensions:
            if dim == "completeness":
                r = await _check_completeness(db, tbl, store_ids, today)
            elif dim == "accuracy":
                r = await _check_accuracy(db, tbl, store_ids, today)
            else:
                r = await _check_timeliness(db, tbl, store_ids, today)
            results.append({
                "target_table": tbl,
                "dimension": dim,
                "score": r["score"],
                "total_records": r["total_records"],
                "failed_records": r["failed_records"],
                "score_date": str(today),
            })
    return results


async def get_score_trend(db: AsyncSession, store_ids: Optional[List[int]], target_table: Optional[str] = None, days: int = 30) -> List[dict]:
    store_filter = ""
    params = {"days": days}
    if store_ids is not None:
        store_filter = "AND store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    table_filter = ""
    if target_table:
        table_filter = "AND target_table = :target_table"
        params["target_table"] = target_table

    sql = text(f"""
        SELECT score_date, dimension, AVG(score) as avg_score
        FROM data_quality_scores
        WHERE score_date >= CURRENT_DATE - :days {store_filter} {table_filter}
        GROUP BY score_date, dimension
        ORDER BY score_date
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [{"score_date": str(r[0]), "dimension": r[1], "avg_score": round(r[2], 2)} for r in rows]


async def get_alerts(
    db: AsyncSession, store_ids: Optional[List[int]],
    severity: Optional[str] = None, status: Optional[str] = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    conditions = ["1=1"]
    params = {}
    if store_ids is not None:
        conditions.append("store_id = ANY(:store_ids)")
        params["store_ids"] = store_ids
    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions)

    count_sql = text(f"SELECT COUNT(*) FROM data_quality_alerts WHERE {where}")
    count_result = await db.execute(count_sql, params)
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    sql = text(f"""
        SELECT id, store_id, rule_id, target_table, dimension, severity, title,
               description, metric_value, threshold_value, status, created_at
        FROM data_quality_alerts
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r[0], "store_id": r[1], "rule_id": r[2],
            "target_table": r[3], "dimension": r[4], "severity": r[5],
            "title": r[6], "description": r[7], "metric_value": r[8],
            "threshold_value": r[9], "status": r[10], "created_at": r[11],
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}


async def acknowledge_alert(db: AsyncSession, alert_id: int, user_id: int) -> dict:
    sql = text("""
        UPDATE data_quality_alerts
        SET status = 'acknowledged', acknowledged_by = :user_id
        WHERE id = :alert_id AND status = 'open'
    """)
    await db.execute(sql, {"alert_id": alert_id, "user_id": user_id})
    await db.commit()
    return {"message": "已确认"}


async def resolve_alert(db: AsyncSession, alert_id: int) -> dict:
    now = datetime.now(timezone.utc)
    sql = text("""
        UPDATE data_quality_alerts
        SET status = 'resolved', resolved_at = :now
        WHERE id = :alert_id AND status IN ('open', 'acknowledged')
    """)
    await db.execute(sql, {"alert_id": alert_id, "now": now})
    await db.commit()
    return {"message": "已解决"}


async def run_quality_check(db: AsyncSession, store_ids: Optional[List[int]]) -> dict:
    now = datetime.now(timezone.utc)
    run_sql = text("""
        INSERT INTO data_quality_check_runs (run_type, started_at, status, created_at)
        VALUES ('manual', :now, 'running', :now)
        RETURNING id
    """)
    run_result = await db.execute(run_sql, {"now": now})
    run_id = run_result.scalar()
    await db.commit()

    today = date.today()
    tables = list(TABLE_CONFIG.keys())
    alerts_count = 0
    scores = []

    for tbl in tables:
        for dim, check_fn in [("completeness", _check_completeness), ("accuracy", _check_accuracy), ("timeliness", _check_timeliness)]:
            result = await check_fn(db, tbl, store_ids, today)
            scores.append(result["score"])

            fail_rate = result["failed_records"] / max(result["total_records"], 1)
            if fail_rate > 0.15:
                severity = "critical" if fail_rate > 0.3 else "error"
                alert_sql = text("""
                    INSERT INTO data_quality_alerts (store_id, rule_id, target_table, dimension, severity, title, description, metric_value, threshold_value, status, created_at)
                    SELECT :store_id, COALESCE((SELECT id FROM data_quality_rules WHERE target_table = :tbl AND dimension = :dim LIMIT 1), 0),
                           :tbl, :dim, :severity, :title, :desc, :metric, 0.15, 'open', :now
                    WHERE NOT EXISTS (
                        SELECT 1 FROM data_quality_alerts
                        WHERE target_table = :tbl AND dimension = :dim AND status = 'open'
                        AND created_at > :dedup_time
                    )
                """)
                await db.execute(alert_sql, {
                    "store_id": store_ids[0] if store_ids else None,
                    "tbl": tbl, "dim": dim, "severity": severity,
                    "title": f"{tbl}表{dim}质量异常",
                    "desc": f"失败率: {fail_rate:.2%}, 失败记录: {result['failed_records']}",
                    "metric": round(fail_rate, 4), "now": now,
                    "dedup_time": now - timedelta(hours=24),
                })
                alerts_count += 1

            score_sql = text("""
                INSERT INTO data_quality_scores (store_id, target_table, dimension, score_date, score, total_records, passed_records, failed_records, details, created_at)
                VALUES (:store_id, :tbl, :dim, :score_date, :score, :total, :passed, :failed, :details, :now)
                ON CONFLICT (store_id, target_table, dimension, score_date) DO UPDATE SET score = :score, total_records = :total, failed_records = :failed
            """)
            await db.execute(score_sql, {
                "store_id": store_ids[0] if store_ids else None,
                "tbl": tbl, "dim": dim, "score_date": today,
                "score": result["score"], "total": result["total_records"],
                "passed": result["total_records"] - result["failed_records"],
                "failed": result["failed_records"],
                "details": str(result.get("details", {})), "now": now,
            })

    overall = float(np.mean(scores)) if scores else 100.0

    update_sql = text("""
        UPDATE data_quality_check_runs
        SET completed_at = :now, total_rules_run = :rules, alerts_generated = :alerts, overall_score = :score, status = 'completed'
        WHERE id = :run_id
    """)
    await db.execute(update_sql, {"now": datetime.now(timezone.utc), "rules": len(tables) * 3, "alerts": alerts_count, "score": round(overall, 2), "run_id": run_id})
    await db.commit()

    return {"run_id": run_id, "overall_score": round(overall, 2), "alerts_generated": alerts_count, "rules_checked": len(tables) * 3}


async def get_rules(db: AsyncSession, target_table: Optional[str] = None, dimension: Optional[str] = None) -> List[dict]:
    conditions = ["1=1"]
    params = {}
    if target_table:
        conditions.append("target_table = :target_table")
        params["target_table"] = target_table
    if dimension:
        conditions.append("dimension = :dimension")
        params["dimension"] = dimension

    where = " AND ".join(conditions)
    sql = text(f"SELECT * FROM data_quality_rules WHERE {where} ORDER BY target_table, dimension")
    result = await db.execute(sql, params)
    rows = result.fetchall()
    columns = result.keys()
    return [dict(zip(columns, r)) for r in rows]


async def create_rule(db: AsyncSession, rule_data: dict) -> dict:
    now = datetime.now(timezone.utc)
    sql = text("""
        INSERT INTO data_quality_rules (rule_name, target_table, dimension, check_type, column_name, condition, threshold_warn, threshold_error, is_active, created_at)
        VALUES (:rule_name, :target_table, :dimension, :check_type, :column_name, :condition, :threshold_warn, :threshold_error, 1, :now)
        RETURNING id
    """)
    result = await db.execute(sql, {**rule_data, "now": now})
    rule_id = result.scalar()
    await db.commit()
    return {"id": rule_id, "message": "规则创建成功"}


async def update_rule(db: AsyncSession, rule_id: int, update_data: dict) -> dict:
    sets = []
    params = {"rule_id": rule_id}
    for key, value in update_data.items():
        if value is not None:
            sets.append(f"{key} = :{key}")
            params[key] = value
    if not sets:
        return {"message": "无更新"}
    sql = text(f"UPDATE data_quality_rules SET {', '.join(sets)} WHERE id = :rule_id")
    await db.execute(sql, params)
    await db.commit()
    return {"message": "规则更新成功"}


async def delete_rule(db: AsyncSession, rule_id: int) -> dict:
    sql = text("UPDATE data_quality_rules SET is_active = 0 WHERE id = :rule_id")
    await db.execute(sql, {"rule_id": rule_id})
    await db.commit()
    return {"message": "规则已停用"}


async def get_check_runs(db: AsyncSession, days: int = 7) -> List[dict]:
    sql = text("""
        SELECT id, run_type, started_at, completed_at, total_rules_run, alerts_generated, overall_score, status
        FROM data_quality_check_runs
        WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL ':days days'
        ORDER BY started_at DESC
    """.replace(":days", str(int(days))))
    result = await db.execute(sql)
    rows = result.fetchall()
    columns = result.keys()
    return [dict(zip(columns, r)) for r in rows]
