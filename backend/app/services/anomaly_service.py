import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from datetime import date


async def detect_anomalies(
    db: AsyncSession, start_date: date, end_date: date,
    store_ids: Optional[List[int]] = None,
) -> dict:
    store_filter = ""
    params = {"start": start_date, "end": end_date}
    if store_ids:
        store_filter = "AND s.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    SELECT s.store_id, st.name as store_name, s.sale_date, SUM(s.total_amount) as daily_sales
    FROM sales s
    JOIN stores st ON st.id = s.store_id
    WHERE s.sale_date BETWEEN :start AND :end {store_filter}
    GROUP BY s.store_id, st.name, s.sale_date
    ORDER BY s.store_id, s.sale_date
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    anomalies = []
    store_data = {}
    for row in rows:
        store_id = row[0]
        store_data.setdefault(store_id, {"name": row[1], "values": [], "dates": []})
        store_data[store_id]["values"].append(float(row[2]))
        store_data[store_id]["dates"].append(row[3])

    for store_id, data in store_data.items():
        values = np.array(data["values"])
        store_anomalies = _detect_iqr_anomalies(values, data["dates"], store_id, data["name"])
        anomalies.extend(store_anomalies)

        yoy_anomalies = await _detect_yoy_anomalies(db, store_id, data["name"], start_date, end_date)
        anomalies.extend(yoy_anomalies)

    inventory_anomalies = await _detect_inventory_anomalies(db, store_ids)
    anomalies.extend(inventory_anomalies)

    anomalies.sort(key=lambda x: x.get("severity_score", 0), reverse=True)

    return {
        "total_anomalies": len(anomalies),
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "anomalies": anomalies[:50],
    }


def _detect_iqr_anomalies(values: np.ndarray, dates: list, store_id: int, store_name: str) -> list:
    if len(values) < 7:
        return []

    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    anomalies = []
    for i, (val, dt) in enumerate(zip(values, dates)):
        if val < lower_bound or val > upper_bound:
            deviation = (val - np.median(values)) / max(iqr, 1)
            anomalies.append({
                "store_id": store_id,
                "store_name": store_name,
                "date": dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                "type": "sales_anomaly",
                "method": "IQR",
                "value": round(val, 2),
                "expected_range": [round(lower_bound, 2), round(upper_bound, 2)],
                "deviation": round(float(deviation), 2),
                "severity": "high" if abs(deviation) > 3 else "medium",
                "severity_score": round(abs(float(deviation)), 2),
                "direction": "above" if val > upper_bound else "below",
            })
    return anomalies


async def _detect_yoy_anomalies(
    db: AsyncSession, store_id: int, store_name: str,
    start_date: date, end_date: date,
) -> list:
    sql = """
    WITH current_period AS (
        SELECT sale_date, SUM(total_amount) as daily_sales
        FROM sales WHERE store_id = :sid AND sale_date BETWEEN :start AND :end
        GROUP BY sale_date
    ),
    last_year AS (
        SELECT sale_date + INTERVAL '1 year' as compare_date, SUM(total_amount) as daily_sales
        FROM sales WHERE store_id = :sid
            AND sale_date BETWEEN :start - INTERVAL '1 year' AND :end - INTERVAL '1 year'
        GROUP BY sale_date
    )
    SELECT cp.sale_date, cp.daily_sales, ly.daily_sales as ly_sales,
        CASE WHEN ly.daily_sales > 0
            THEN (cp.daily_sales - ly.daily_sales) / ly.daily_sales * 100
            ELSE NULL END as yoy_change
    FROM current_period cp
    LEFT JOIN last_year ly ON ly.compare_date = cp.sale_date
    WHERE ly.daily_sales IS NOT NULL
        AND ABS((cp.daily_sales - ly.daily_sales) / NULLIF(ly.daily_sales, 0)) > 0.5
    """
    result = await db.execute(text(sql), {"sid": store_id, "start": start_date, "end": end_date})
    rows = result.fetchall()

    anomalies = []
    for row in rows:
        yoy_change = float(row[3])
        anomalies.append({
            "store_id": store_id,
            "store_name": store_name,
            "date": row[0].isoformat(),
            "type": "yoy_deviation",
            "method": "YoY",
            "value": round(float(row[1]), 2),
            "last_year_value": round(float(row[2]), 2),
            "yoy_change_pct": round(yoy_change, 1),
            "severity": "high" if abs(yoy_change) > 100 else "medium",
            "severity_score": round(abs(yoy_change) / 50, 2),
            "direction": "above" if yoy_change > 0 else "below",
        })
    return anomalies


async def _detect_inventory_anomalies(
    db: AsyncSession, store_ids: Optional[List[int]] = None,
) -> list:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "AND i.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    SELECT i.store_id, st.name, i.item_id, i.item_name, i.quantity,
        i.min_stock, i.max_stock, i.snapshot_date
    FROM inventory i
    JOIN stores st ON st.id = i.store_id
    WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory)
        AND (i.quantity < i.min_stock OR (i.max_stock IS NOT NULL AND i.quantity > i.max_stock))
        {store_filter}
    LIMIT 30
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    anomalies = []
    for row in rows:
        qty = float(row[4])
        min_s = float(row[5]) if row[5] else 0
        max_s = float(row[6]) if row[6] else None

        if qty < min_s:
            severity_score = (min_s - qty) / max(min_s, 1)
            direction = "below_min"
        else:
            severity_score = (qty - max_s) / max(max_s, 1) if max_s else 0
            direction = "above_max"

        anomalies.append({
            "store_id": row[0],
            "store_name": row[1],
            "type": "inventory_anomaly",
            "method": "threshold",
            "item_id": row[2],
            "item_name": row[3],
            "quantity": round(qty, 2),
            "min_stock": round(min_s, 2),
            "max_stock": round(float(max_s), 2) if max_s else None,
            "date": row[7].isoformat() if row[7] else None,
            "severity": "high" if severity_score > 0.5 else "medium",
            "severity_score": round(float(severity_score), 2),
            "direction": direction,
        })
    return anomalies
