from datetime import date, datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np


STAGE_INTRODUCTION = "introduction"
STAGE_GROWTH = "growth"
STAGE_MATURITY = "maturity"
STAGE_DECLINE = "decline"


def _detect_stage(growth_rates: List[float], weeks_since_launch: int, adoption_rate: float, velocity: float, category_median_velocity: float) -> str:
    if len(growth_rates) < 4:
        return STAGE_INTRODUCTION

    if weeks_since_launch <= 8 and adoption_rate < 0.5:
        return STAGE_INTRODUCTION

    recent = growth_rates[-4:]
    positive_weeks = sum(1 for g in recent if g > 0.05)
    negative_weeks = sum(1 for g in recent if g < -0.05)
    stable_weeks = sum(1 for g in recent if abs(g) <= 0.05)

    if negative_weeks >= 3 or (velocity < category_median_velocity * 0.3 and weeks_since_launch > 26):
        return STAGE_DECLINE

    if positive_weeks >= 3 and adoption_rate >= 0.5:
        return STAGE_GROWTH

    if stable_weeks >= 3 and velocity > category_median_velocity * 0.7:
        return STAGE_MATURITY

    if positive_weeks >= 2:
        return STAGE_GROWTH

    return STAGE_MATURITY


async def get_lifecycle_overview(db: AsyncSession, store_ids: Optional[List[int]], category: Optional[str] = None) -> dict:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "AND pls.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    cat_filter = ""
    if category:
        cat_filter = "AND p.category = :category"
        params["category"] = category

    sql = text(f"""
        SELECT pls.stage, COUNT(DISTINCT pls.product_id) as cnt
        FROM product_lifecycle_snapshots pls
        JOIN products p ON p.id = pls.product_id
        WHERE pls.snapshot_week = (
            SELECT MAX(snapshot_week) FROM product_lifecycle_snapshots
        ) {store_filter} {cat_filter}
        GROUP BY pls.stage
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    counts = {STAGE_INTRODUCTION: 0, STAGE_GROWTH: 0, STAGE_MATURITY: 0, STAGE_DECLINE: 0}
    for stage, cnt in rows:
        if stage in counts:
            counts[stage] = cnt

    total = sum(counts.values())
    return {
        "introduction_count": counts[STAGE_INTRODUCTION],
        "growth_count": counts[STAGE_GROWTH],
        "maturity_count": counts[STAGE_MATURITY],
        "decline_count": counts[STAGE_DECLINE],
        "total_products": total,
    }


async def get_products_with_stage(
    db: AsyncSession, store_ids: Optional[List[int]],
    stage: Optional[str] = None, category: Optional[str] = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    conditions = ["1=1"]
    params = {}
    if store_ids:
        conditions.append("pls.store_id = ANY(:store_ids)")
        params["store_ids"] = store_ids
    if stage:
        conditions.append("pls.stage = :stage")
        params["stage"] = stage
    if category:
        conditions.append("p.category = :category")
        params["category"] = category

    where = " AND ".join(conditions)

    count_sql = text(f"""
        SELECT COUNT(DISTINCT p.id) FROM products p
        JOIN product_lifecycle_snapshots pls ON pls.product_id = p.id
        WHERE pls.snapshot_week = (SELECT MAX(snapshot_week) FROM product_lifecycle_snapshots)
        AND {where}
    """)
    count_result = await db.execute(count_sql, params)
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    sql = text(f"""
        SELECT p.id, p.item_id, p.item_name, p.category, pls.stage,
               pls.weekly_revenue, pls.growth_rate, pls.snapshot_week, p.launch_date
        FROM products p
        JOIN product_lifecycle_snapshots pls ON pls.product_id = p.id
        WHERE pls.snapshot_week = (SELECT MAX(snapshot_week) FROM product_lifecycle_snapshots)
        AND {where}
        ORDER BY pls.weekly_revenue DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    items = []
    for r in rows:
        weeks_in_stage = 0
        if r[7] and r[8]:
            weeks_in_stage = max(1, (r[7] - r[8]).days // 7) if isinstance(r[8], date) else 1
        items.append({
            "id": r[0], "item_id": r[1], "item_name": r[2], "category": r[3],
            "current_stage": r[4], "weekly_revenue": r[5] or 0,
            "growth_rate": r[6], "weeks_in_stage": weeks_in_stage,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}


async def get_lifecycle_curve(db: AsyncSession, product_id: int, store_ids: Optional[List[int]] = None) -> dict:
    store_filter = ""
    params = {"product_id": product_id}
    if store_ids:
        store_filter = "AND store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    name_sql = text("SELECT item_name FROM products WHERE id = :product_id")
    name_result = await db.execute(name_sql, {"product_id": product_id})
    name_row = name_result.fetchone()
    item_name = name_row[0] if name_row else "未知商品"

    sql = text(f"""
        SELECT snapshot_week, weekly_revenue, weekly_quantity, stage
        FROM product_lifecycle_snapshots
        WHERE product_id = :product_id {store_filter}
        ORDER BY snapshot_week
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    return {
        "product_id": product_id,
        "item_name": item_name,
        "weeks": [str(r[0]) for r in rows],
        "revenues": [r[1] or 0 for r in rows],
        "quantities": [r[2] or 0 for r in rows],
        "stages": [r[3] for r in rows],
    }


async def get_stage_transitions(db: AsyncSession, store_ids: Optional[List[int]], days: int = 30) -> List[dict]:
    store_filter = ""
    params = {"days": days}
    if store_ids:
        store_filter = "AND pls.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = text(f"""
        WITH ranked AS (
            SELECT pls.product_id, p.item_name, pls.stage, pls.snapshot_week,
                   LAG(pls.stage) OVER (PARTITION BY pls.product_id ORDER BY pls.snapshot_week) as prev_stage
            FROM product_lifecycle_snapshots pls
            JOIN products p ON p.id = pls.product_id
            WHERE pls.snapshot_week >= CURRENT_DATE - :days {store_filter}
        )
        SELECT product_id, item_name, prev_stage, stage, snapshot_week
        FROM ranked
        WHERE prev_stage IS NOT NULL AND prev_stage != stage
        ORDER BY snapshot_week DESC
        LIMIT 50
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {"product_id": r[0], "item_name": r[1], "from_stage": r[2], "to_stage": r[3], "transition_date": str(r[4])}
        for r in rows
    ]


async def get_stage_kpis(db: AsyncSession, store_ids: Optional[List[int]], stage: str) -> dict:
    store_filter = ""
    params = {"stage": stage}
    if store_ids:
        store_filter = "AND store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = text(f"""
        SELECT COUNT(DISTINCT product_id) as product_count,
               AVG(weekly_revenue) as avg_revenue,
               AVG(growth_rate) as avg_growth,
               AVG(adoption_rate) as avg_adoption,
               AVG(market_share) as avg_market_share,
               AVG(margin_rate) as avg_margin,
               AVG(velocity) as avg_velocity
        FROM product_lifecycle_snapshots
        WHERE stage = :stage
        AND snapshot_week = (SELECT MAX(snapshot_week) FROM product_lifecycle_snapshots)
        {store_filter}
    """)
    result = await db.execute(sql, params)
    row = result.fetchone()

    kpis = {
        "stage": stage,
        "product_count": row[0] or 0,
        "avg_weekly_revenue": round(row[1] or 0, 2),
        "avg_growth_rate": round(row[2] or 0, 4),
    }

    if stage == STAGE_INTRODUCTION:
        kpis["avg_adoption_rate"] = round(row[3] or 0, 4)
    elif stage == STAGE_GROWTH:
        kpis["avg_growth_rate"] = round(row[2] or 0, 4)
        kpis["avg_velocity"] = round(row[6] or 0, 2)
    elif stage == STAGE_MATURITY:
        kpis["avg_market_share"] = round(row[4] or 0, 4)
        kpis["avg_velocity"] = round(row[6] or 0, 2)
    elif stage == STAGE_DECLINE:
        kpis["avg_margin_rate"] = round(row[5] or 0, 4)
        kpis["avg_velocity"] = round(row[6] or 0, 2)

    return kpis


async def get_retirement_recommendations(db: AsyncSession, store_ids: Optional[List[int]], category: Optional[str] = None) -> List[dict]:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "AND prr.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    cat_filter = ""
    if category:
        cat_filter = "AND p.category = :category"
        params["category"] = category

    sql = text(f"""
        SELECT prr.id, prr.product_id, p.item_name, prr.recommendation, prr.confidence,
               prr.reason, prr.impact_revenue_loss, prr.remaining_inventory, prr.suggested_action_date
        FROM product_retirement_recommendations prr
        JOIN products p ON p.id = prr.product_id
        WHERE 1=1 {store_filter} {cat_filter}
        ORDER BY prr.confidence DESC, prr.impact_revenue_loss ASC
        LIMIT 50
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": r[0], "product_id": r[1], "item_name": r[2],
            "recommendation": r[3], "confidence": r[4], "reason": r[5],
            "impact_revenue_loss": r[6], "remaining_inventory": r[7],
            "suggested_action_date": str(r[8]) if r[8] else None,
        }
        for r in rows
    ]


async def recalculate_lifecycle(db: AsyncSession, store_ids: Optional[List[int]]) -> dict:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "AND s.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    today = date.today()
    monday = today - timedelta(days=today.weekday())

    products_sql = text("SELECT id, item_id, item_name, category, launch_date, unit_cost FROM products WHERE is_active = 1")
    products_result = await db.execute(products_sql)
    products = products_result.fetchall()

    total_stores_sql = text("SELECT COUNT(*) FROM stores WHERE status = 'active'")
    total_stores_result = await db.execute(total_stores_sql)
    total_stores = total_stores_result.scalar() or 1

    processed = 0
    recommendations_created = 0

    for prod in products:
        prod_id, item_id, item_name, category, launch_date, unit_cost = prod

        weekly_sql = text(f"""
            SELECT DATE_TRUNC('week', s.sale_date)::date as week_start,
                   SUM(s.total_amount) as revenue,
                   SUM(s.quantity) as qty,
                   COUNT(DISTINCT s.store_id) as store_count
            FROM sales s
            WHERE s.item_id = :item_id
            AND s.sale_date >= CURRENT_DATE - 84
            {store_filter}
            GROUP BY DATE_TRUNC('week', s.sale_date)::date
            ORDER BY week_start
        """)
        weekly_result = await db.execute(weekly_sql, {**params, "item_id": item_id})
        weeks = weekly_result.fetchall()

        if not weeks:
            continue

        revenues = [w[1] or 0 for w in weeks]
        growth_rates = []
        for i in range(1, len(revenues)):
            prev = revenues[i - 1]
            curr = revenues[i]
            rate = (curr - prev) / max(prev, 1)
            growth_rates.append(rate)

        weeks_since_launch = ((today - launch_date).days // 7) if launch_date else 52
        adoption_rate = (weeks[-1][3] / total_stores) if weeks else 0

        cat_vel_sql = text(f"""
            SELECT AVG(s.quantity) / 7.0
            FROM sales s
            JOIN products p2 ON p2.item_id = s.item_id
            WHERE p2.category = :cat AND s.sale_date >= CURRENT_DATE - 28 {store_filter}
        """)
        cat_vel_result = await db.execute(cat_vel_sql, {**params, "cat": category or ""})
        category_median_velocity = cat_vel_result.scalar() or 1.0

        velocity = (revenues[-1] / 7.0) if revenues else 0
        stage = _detect_stage(growth_rates, weeks_since_launch, adoption_rate, velocity, category_median_velocity)

        latest_growth = growth_rates[-1] if growth_rates else 0
        market_share = 0
        margin_rate = ((revenues[-1] - (unit_cost or 0) * (weeks[-1][2] or 0)) / max(revenues[-1], 1)) if revenues and revenues[-1] > 0 else 0

        snap_sql = text("""
            INSERT INTO product_lifecycle_snapshots (product_id, store_id, snapshot_week, stage, weekly_revenue, weekly_quantity, growth_rate, adoption_rate, market_share, margin_rate, velocity, created_at)
            VALUES (:prod_id, :store_id, :week, :stage, :rev, :qty, :growth, :adopt, :mshare, :margin, :vel, :now)
            ON CONFLICT (product_id, snapshot_week, store_id) DO UPDATE
            SET stage = :stage, weekly_revenue = :rev, growth_rate = :growth, velocity = :vel
        """)
        await db.execute(snap_sql, {
            "prod_id": prod_id, "store_id": store_ids[0] if store_ids else None,
            "week": monday, "stage": stage, "rev": revenues[-1] if revenues else 0,
            "qty": weeks[-1][2] if weeks else 0, "growth": latest_growth,
            "adopt": adoption_rate, "mshare": market_share, "margin": margin_rate,
            "vel": velocity, "now": datetime.now(timezone.utc),
        })

        if stage == STAGE_DECLINE and len(growth_rates) >= 4 and sum(1 for g in growth_rates[-4:] if g < -0.05) >= 3:
            if margin_rate < 0:
                rec, conf, reason = "phase_out", 0.9, "利润率为负，建议淘汰"
            elif velocity < 0.5:
                rec, conf, reason = "markdown", 0.75, "销售速度极低，建议打折清仓"
            else:
                rec, conf, reason = "keep", 0.5, "仍有一定销量，建议观察"

            rec_sql = text("""
                INSERT INTO product_retirement_recommendations (product_id, store_id, recommendation, confidence, reason, impact_revenue_loss, remaining_inventory, suggested_action_date, created_at)
                VALUES (:prod_id, :store_id, :rec, :conf, :reason, :rev_loss, :inv, :action_date, :now)
            """)
            await db.execute(rec_sql, {
                "prod_id": prod_id, "store_id": store_ids[0] if store_ids else None,
                "rec": rec, "conf": conf, "reason": reason,
                "rev_loss": revenues[-1] if revenues else 0, "inv": 0,
                "action_date": today + timedelta(days=14), "now": datetime.now(timezone.utc),
            })
            recommendations_created += 1

        processed += 1

    await db.commit()
    return {"processed": processed, "recommendations_created": recommendations_created}
