import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, and_
from datetime import date, timedelta
from typing import Optional, List

from app.models.supply_chain import (
    Supplier, PurchaseOrder, PurchaseOrderItem,
    SupplierPerformance, InventoryAdjustment,
)


async def get_supplier_performance_metrics(
    db: AsyncSession, supplier_id: int, period_days: int = 90,
    authorized_stores: Optional[List[int]] = None,
) -> dict:
    period_start = date.today() - timedelta(days=period_days)

    store_filter = ""
    params = {"sid": supplier_id, "period_start": period_start}
    if authorized_stores is not None:
        store_filter = "AND store_id = ANY(:store_ids)"
        params["store_ids"] = authorized_stores

    sql = f"""
    SELECT
        COUNT(*) as total_orders,
        SUM(CASE WHEN actual_delivery_date <= expected_delivery_date THEN 1 ELSE 0 END) as on_time,
        SUM(CASE WHEN actual_delivery_date > expected_delivery_date THEN 1 ELSE 0 END) as late,
        AVG(actual_delivery_date - order_date) as avg_lead_time
    FROM purchase_orders
    WHERE supplier_id = :sid
      AND order_date >= :period_start
      AND status = 'delivered'
      {store_filter}
    """
    result = await db.execute(text(sql), params)
    row = result.fetchone()

    total_orders = row[0] or 0
    on_time = row[1] or 0
    late = row[2] or 0
    avg_lead_time = float(row[3]) if row[3] else 0

    item_sql = f"""
    SELECT
        COALESCE(SUM(poi.quantity), 0) as total_ordered,
        COALESCE(SUM(poi.received_quantity), 0) as total_received,
        COALESCE(SUM(CASE WHEN poi.quality_score IS NOT NULL AND poi.quality_score < 60 THEN poi.received_quantity ELSE 0 END), 0) as defect_items
    FROM purchase_order_items poi
    JOIN purchase_orders po ON po.id = poi.order_id
    WHERE po.supplier_id = :sid
      AND po.order_date >= :period_start
      AND po.status = 'delivered'
      {store_filter}
    """
    item_result = await db.execute(text(item_sql), params)
    item_row = item_result.fetchone()

    total_ordered = item_row[0] or 0
    total_received = item_row[1] or 0
    defect_items = item_row[2] or 0

    on_time_rate = (on_time / total_orders * 100) if total_orders > 0 else 0
    fulfillment_rate = (total_received / total_ordered * 100) if total_ordered > 0 else 0
    quality_score = ((total_received - defect_items) / total_received * 100) if total_received > 0 else 100

    cost_sql = f"""
    SELECT
        COALESCE(AVG(
            CASE WHEN si.unit_cost > 0
            THEN (si.unit_cost - poi.unit_cost) / si.unit_cost * 100
            ELSE 0 END
        ), 0)
    FROM purchase_order_items poi
    JOIN purchase_orders po ON po.id = poi.order_id
    LEFT JOIN supplier_items si ON si.supplier_id = po.supplier_id AND si.item_id = poi.item_id
    WHERE po.supplier_id = :sid AND po.order_date >= :period_start AND po.status = 'delivered'
      {store_filter}
    """
    cost_result = await db.execute(text(cost_sql), params)
    cost_variance = float(cost_result.scalar() or 0)

    cost_score = max(0, 100 - abs(cost_variance) * 5)

    overall_score = (
        on_time_rate * 0.30 +
        fulfillment_rate * 0.25 +
        quality_score * 0.25 +
        cost_score * 0.20
    )

    if overall_score >= 80:
        health_level = "green"
    elif overall_score >= 60:
        health_level = "yellow"
    else:
        health_level = "red"

    return {
        "supplier_id": supplier_id,
        "period_start": period_start,
        "period_end": date.today(),
        "total_orders": total_orders,
        "on_time_deliveries": on_time,
        "late_deliveries": late,
        "total_items_ordered": total_ordered,
        "total_items_received": total_received,
        "defect_items": defect_items,
        "avg_lead_time_actual": avg_lead_time,
        "on_time_rate": round(on_time_rate, 1),
        "fulfillment_rate": round(fulfillment_rate, 1),
        "quality_score": round(quality_score, 1),
        "cost_variance_pct": round(cost_variance, 2),
        "overall_score": round(overall_score, 1),
        "health_level": health_level,
    }


async def calculate_all_supplier_performance(
    db: AsyncSession, period_days: int = 90,
    authorized_stores: Optional[List[int]] = None,
) -> List[dict]:
    period_start = date.today() - timedelta(days=period_days)
    params: dict = {"period_start": period_start}

    store_filter = ""
    if authorized_stores is not None:
        store_filter = "AND po.store_id = ANY(:store_ids)"
        params["store_ids"] = authorized_stores

    batch_sql = f"""
    WITH authorized_orders AS (
        SELECT * FROM purchase_orders po
        WHERE po.order_date >= :period_start AND po.status = 'delivered'
        {store_filter}
    ),
    order_metrics AS (
        SELECT
            ao.supplier_id,
            COUNT(*) as total_orders,
            SUM(CASE WHEN ao.actual_delivery_date <= ao.expected_delivery_date THEN 1 ELSE 0 END) as on_time,
            SUM(CASE WHEN ao.actual_delivery_date > ao.expected_delivery_date THEN 1 ELSE 0 END) as late,
            AVG(ao.actual_delivery_date - ao.order_date) as avg_lead_time
        FROM authorized_orders ao
        GROUP BY ao.supplier_id
    ),
    item_metrics AS (
        SELECT
            ao.supplier_id,
            COALESCE(SUM(poi.quantity), 0) as total_ordered,
            COALESCE(SUM(poi.received_quantity), 0) as total_received,
            COALESCE(SUM(CASE WHEN poi.quality_score IS NOT NULL AND poi.quality_score < 60
                THEN poi.received_quantity ELSE 0 END), 0) as defect_items
        FROM purchase_order_items poi
        JOIN authorized_orders ao ON ao.id = poi.order_id
        GROUP BY ao.supplier_id
    ),
    cost_metrics AS (
        SELECT
            ao.supplier_id,
            COALESCE(AVG(
                CASE WHEN si.unit_cost > 0
                THEN (si.unit_cost - poi.unit_cost) / si.unit_cost * 100
                ELSE 0 END
            ), 0) as cost_variance
        FROM purchase_order_items poi
        JOIN authorized_orders ao ON ao.id = poi.order_id
        LEFT JOIN supplier_items si ON si.supplier_id = ao.supplier_id AND si.item_id = poi.item_id
        GROUP BY ao.supplier_id
    )
    SELECT
        s.id, s.name,
        COALESCE(om.total_orders, 0), COALESCE(om.on_time, 0), COALESCE(om.late, 0),
        COALESCE(om.avg_lead_time, 0),
        COALESCE(im.total_ordered, 0), COALESCE(im.total_received, 0), COALESCE(im.defect_items, 0),
        COALESCE(cm.cost_variance, 0)
    FROM suppliers s
    LEFT JOIN order_metrics om ON om.supplier_id = s.id
    LEFT JOIN item_metrics im ON im.supplier_id = s.id
    LEFT JOIN cost_metrics cm ON cm.supplier_id = s.id
    WHERE s.is_active = 1
    ORDER BY s.name
    """
    result = await db.execute(text(batch_sql), params)
    rows = result.fetchall()

    performances = []
    for row in rows:
        supplier_id, supplier_name = row[0], row[1]
        total_orders, on_time, late = int(row[2]), int(row[3]), int(row[4])
        avg_lead_time = float(row[5]) if row[5] else 0
        total_ordered, total_received, defect_items = int(row[6]), int(row[7]), int(row[8])
        cost_variance = float(row[9])

        on_time_rate = (on_time / total_orders * 100) if total_orders > 0 else 0
        fulfillment_rate = (total_received / total_ordered * 100) if total_ordered > 0 else 0
        quality_score = ((total_received - defect_items) / total_received * 100) if total_received > 0 else 100
        cost_score = max(0, 100 - abs(cost_variance) * 5)

        overall_score = (
            on_time_rate * 0.30 +
            fulfillment_rate * 0.25 +
            quality_score * 0.25 +
            cost_score * 0.20
        )

        if overall_score >= 80:
            health_level = "green"
        elif overall_score >= 60:
            health_level = "yellow"
        else:
            health_level = "red"

        performances.append({
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "period_start": period_start,
            "period_end": date.today(),
            "total_orders": total_orders,
            "on_time_deliveries": on_time,
            "late_deliveries": late,
            "total_items_ordered": total_ordered,
            "total_items_received": total_received,
            "defect_items": defect_items,
            "avg_lead_time_actual": avg_lead_time,
            "on_time_rate": round(on_time_rate, 1),
            "fulfillment_rate": round(fulfillment_rate, 1),
            "quality_score": round(quality_score, 1),
            "cost_variance_pct": round(cost_variance, 2),
            "overall_score": round(overall_score, 1),
            "health_level": health_level,
        })

    return performances


async def get_health_dashboard(
    db: AsyncSession, authorized_stores: Optional[List[int]] = None
) -> dict:
    performances = await calculate_all_supplier_performance(db, authorized_stores=authorized_stores)

    green_count = sum(1 for p in performances if p["health_level"] == "green")
    yellow_count = sum(1 for p in performances if p["health_level"] == "yellow")
    red_count = sum(1 for p in performances if p["health_level"] == "red")

    avg_on_time = np.mean([p["on_time_rate"] for p in performances]) if performances else 0
    avg_quality = np.mean([p["quality_score"] for p in performances]) if performances else 0

    return {
        "suppliers": performances,
        "summary": {
            "total_suppliers": len(performances),
            "green": green_count,
            "yellow": yellow_count,
            "red": red_count,
            "avg_on_time_rate": round(float(avg_on_time), 1),
            "avg_quality_score": round(float(avg_quality), 1),
        }
    }


async def get_stockout_analysis(
    db: AsyncSession, store_ids: Optional[List[int]] = None, days: int = 30
) -> List[dict]:
    store_filter = ""
    params = {"days": days}
    if store_ids:
        store_filter = "AND i.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    SELECT
        i.store_id, i.item_id, i.item_name,
        COUNT(CASE WHEN i.quantity <= 0 THEN 1 END) as stockout_days,
        COUNT(*) as total_days,
        ROUND(COUNT(CASE WHEN i.quantity <= 0 THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as stockout_rate
    FROM inventory i
    WHERE i.snapshot_date >= CURRENT_DATE - :days * INTERVAL '1 day'
    {store_filter}
    GROUP BY i.store_id, i.item_id, i.item_name
    HAVING COUNT(CASE WHEN i.quantity <= 0 THEN 1 END) > 0
    ORDER BY stockout_rate DESC
    LIMIT 100
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        {
            "store_id": row[0],
            "item_id": row[1],
            "item_name": row[2],
            "stockout_days": row[3],
            "total_days": row[4],
            "stockout_rate": float(row[5]) if row[5] else 0,
        }
        for row in rows
    ]


async def get_adjustment_recommendations(
    db: AsyncSession, store_ids: Optional[List[int]] = None
) -> List[dict]:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "AND i.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    WITH current_stock AS (
        SELECT DISTINCT ON (store_id, item_id)
            store_id, item_id, item_name, quantity, min_stock, max_stock
        FROM inventory
        WHERE snapshot_date >= CURRENT_DATE - INTERVAL '7 days'
        {store_filter}
        ORDER BY store_id, item_id, snapshot_date DESC
    ),
    item_velocity AS (
        SELECT store_id, item_id,
            AVG(quantity) as avg_daily_sales
        FROM sales
        WHERE sale_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY store_id, item_id
    )
    SELECT
        cs.store_id, cs.item_id, cs.item_name,
        cs.quantity as current_stock,
        cs.min_stock,
        COALESCE(iv.avg_daily_sales, 0) as velocity
    FROM current_stock cs
    LEFT JOIN item_velocity iv ON iv.store_id = cs.store_id AND iv.item_id = cs.item_id
    WHERE cs.quantity <= cs.min_stock * 1.2
    ORDER BY (cs.quantity::float / NULLIF(cs.min_stock, 0)) ASC
    LIMIT 50
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    recommendations = []
    for row in rows:
        current = row[3]
        min_stock = row[4] or 0
        velocity = float(row[5])

        if current <= 0:
            priority = "critical"
            action = "urgent_replenish"
            qty = max(min_stock * 2, int(velocity * 14))
        elif current <= min_stock * 0.5:
            priority = "high"
            action = "replenish"
            qty = max(min_stock, int(velocity * 10))
        else:
            priority = "medium"
            action = "monitor"
            qty = max(min_stock - current, int(velocity * 7))

        recommendations.append({
            "store_id": row[0],
            "item_id": row[1],
            "item_name": row[2],
            "current_stock": current,
            "recommended_action": action,
            "recommended_qty": max(1, qty),
            "reason": f"库存{'已耗尽' if current <= 0 else '低于安全水平'}，日均消耗{velocity:.1f}",
            "priority": priority,
        })

    return recommendations


async def get_performance_trend(
    db: AsyncSession, supplier_id: int, periods: int = 6
) -> List[dict]:
    result = await db.execute(
        select(SupplierPerformance)
        .where(SupplierPerformance.supplier_id == supplier_id)
        .order_by(SupplierPerformance.period_start.desc())
        .limit(periods)
    )
    records = result.scalars().all()

    return [
        {
            "period_start": str(r.period_start),
            "period_end": str(r.period_end),
            "on_time_rate": round((r.on_time_deliveries / r.total_orders * 100) if r.total_orders > 0 else 0, 1),
            "fulfillment_rate": round((r.total_items_received / r.total_items_ordered * 100) if r.total_items_ordered > 0 else 0, 1),
            "quality_score": round(((r.total_items_received - r.defect_items) / r.total_items_received * 100) if r.total_items_received > 0 else 100, 1),
            "overall_score": r.overall_score or 0,
        }
        for r in reversed(records)
    ]
