from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from datetime import date


async def calculate_kpi(
    db: AsyncSession, start_date: date, end_date: date, store_ids: Optional[List[int]] = None
) -> dict:
    store_filter = ""
    params = {"start": start_date, "end": end_date}
    if store_ids:
        store_filter = "AND s.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    SELECT
        COALESCE(SUM(s.total_amount), 0) as gmv,
        COUNT(DISTINCT s.receipt_no) as total_orders,
        CASE WHEN COUNT(DISTINCT s.receipt_no) > 0
            THEN SUM(s.total_amount) / COUNT(DISTINCT s.receipt_no)
            ELSE 0 END as avg_ticket,
        COUNT(DISTINCT s.store_id) as active_stores,
        COUNT(DISTINCT s.member_id) FILTER (WHERE s.member_id IS NOT NULL) as active_members,
        COALESCE(SUM(s.discount_amount), 0) as total_discount
    FROM sales s
    WHERE s.sale_date BETWEEN :start AND :end {store_filter}
    """
    result = await db.execute(text(sql), params)
    row = result.fetchone()

    area_sql = f"""
    SELECT COALESCE(SUM(st.area_sqm), 1) as total_area
    FROM stores st
    WHERE st.is_active = true
    {"AND st.id = ANY(:store_ids)" if store_ids else ""}
    """
    area_result = await db.execute(text(area_sql), {"store_ids": store_ids} if store_ids else {})
    area_row = area_result.fetchone()
    total_area = area_row[0] if area_row else 1

    gmv = float(row[0])
    days = (end_date - start_date).days + 1

    return {
        "gmv": round(gmv, 2),
        "total_orders": row[1],
        "avg_ticket": round(float(row[2]), 2),
        "active_stores": row[3],
        "active_members": row[4],
        "total_discount": round(float(row[5]), 2),
        "daily_avg_gmv": round(gmv / max(days, 1), 2),
        "sqm_efficiency": round(gmv / max(total_area, 1), 2),
        "period_days": days,
    }


async def get_store_ranking(
    db: AsyncSession, start_date: date, end_date: date,
    metric: str = "gmv", authorized_stores: Optional[List[int]] = None,
) -> list:
    store_filter = ""
    params = {"start": start_date, "end": end_date}
    if authorized_stores:
        store_filter = "AND s.store_id = ANY(:store_ids)"
        params["store_ids"] = authorized_stores

    metric_col = {
        "gmv": "SUM(s.total_amount)",
        "orders": "COUNT(DISTINCT s.receipt_no)",
        "avg_ticket": "CASE WHEN COUNT(DISTINCT s.receipt_no) > 0 THEN SUM(s.total_amount)/COUNT(DISTINCT s.receipt_no) ELSE 0 END",
    }.get(metric, "SUM(s.total_amount)")

    sql = f"""
    SELECT st.id, st.code, st.name, st.city,
        {metric_col} as metric_value,
        SUM(s.total_amount) as gmv,
        COUNT(DISTINCT s.receipt_no) as orders
    FROM sales s
    JOIN stores st ON st.id = s.store_id
    WHERE s.sale_date BETWEEN :start AND :end {store_filter}
    GROUP BY st.id, st.code, st.name, st.city
    ORDER BY metric_value DESC
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        {
            "rank": idx + 1,
            "store_id": row[0], "store_code": row[1], "store_name": row[2],
            "city": row[3], "metric_value": round(float(row[4]), 2),
            "gmv": round(float(row[5]), 2), "orders": row[6],
        }
        for idx, row in enumerate(rows)
    ]


async def detect_missing_periods(
    db: AsyncSession, store_id: int, data_type: str = "sales"
) -> list:
    table_map = {"sales": ("sales", "sale_date"), "traffic": ("traffic", "traffic_date")}
    if data_type not in table_map:
        return []

    table, date_col = table_map[data_type]
    sql = f"""
    WITH date_series AS (
        SELECT generate_series(
            (SELECT MIN({date_col}) FROM {table} WHERE store_id = :sid),
            (SELECT MAX({date_col}) FROM {table} WHERE store_id = :sid),
            '1 day'::interval
        )::date as expected_date
    ),
    actual_dates AS (
        SELECT DISTINCT {date_col} as actual_date FROM {table} WHERE store_id = :sid
    )
    SELECT ds.expected_date
    FROM date_series ds
    LEFT JOIN actual_dates ad ON ds.expected_date = ad.actual_date
    WHERE ad.actual_date IS NULL
    ORDER BY ds.expected_date
    """
    result = await db.execute(text(sql), {"sid": store_id})
    missing_dates = [row[0].isoformat() for row in result.fetchall()]

    gaps = []
    if missing_dates:
        gap_start = missing_dates[0]
        prev = missing_dates[0]
        for d in missing_dates[1:]:
            from datetime import timedelta
            prev_date = date.fromisoformat(prev)
            curr_date = date.fromisoformat(d)
            if (curr_date - prev_date).days > 1:
                gaps.append({"start": gap_start, "end": prev, "days": (date.fromisoformat(prev) - date.fromisoformat(gap_start)).days + 1})
                gap_start = d
            prev = d
        gaps.append({"start": gap_start, "end": prev, "days": (date.fromisoformat(prev) - date.fromisoformat(gap_start)).days + 1})

    return {"store_id": store_id, "data_type": data_type, "total_missing_days": len(missing_dates), "gaps": gaps}
