import numpy as np
from scipy.stats import norm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import date, timedelta
from typing import Optional, List

from app.models.supply_chain import Supplier, SupplierItem
from app.models.replenishment import ReplenishmentSuggestion, ReplenishmentConfig


async def generate_replenishment_suggestions(
    db: AsyncSession, store_id: int, item_ids: Optional[List[str]] = None
) -> List[dict]:
    item_filter = ""
    params = {"store_id": store_id}
    if item_ids:
        item_filter = "AND i.item_id = ANY(:item_ids)"
        params["item_ids"] = item_ids

    inventory_sql = f"""
    SELECT DISTINCT ON (i.item_id)
        i.item_id, i.item_name, i.quantity, i.category, i.min_stock
    FROM inventory i
    WHERE i.store_id = :store_id {item_filter}
    ORDER BY i.item_id, i.snapshot_date DESC
    """
    inv_result = await db.execute(text(inventory_sql), params)
    inventory_items = inv_result.fetchall()

    if not inventory_items:
        return []

    suggestions = []
    for item_row in inventory_items:
        item_id = item_row[0]
        item_name = item_row[1]
        current_stock = item_row[2] or 0
        category = item_row[3]
        min_stock = item_row[4] or 0

        velocity = await _calculate_demand_velocity(db, store_id, item_id)
        std_demand = await _calculate_demand_std(db, store_id, item_id)

        config = await _get_item_config(db, store_id, item_id)
        service_level = config["service_level"]
        review_period = config["review_period_days"]

        supplier_info = await _get_primary_supplier(db, item_id)
        lead_time = supplier_info["lead_time"] if supplier_info else 7

        promo_factor = await _get_promo_boost(db, store_id, item_id, config["promo_boost_factor"])
        weather_factor = await _get_weather_factor(db, store_id, config["weather_sensitivity"])

        adjusted_velocity = velocity * promo_factor * weather_factor

        z_score = norm.ppf(service_level)
        safety_stock = int(np.ceil(
            z_score * std_demand * np.sqrt(lead_time + review_period)
        ))
        safety_stock = max(safety_stock, min_stock)

        reorder_point = int(np.ceil(adjusted_velocity * lead_time + safety_stock))

        if current_stock <= reorder_point:
            annual_demand = adjusted_velocity * 365
            ordering_cost = 50
            holding_cost_rate = 0.25
            unit_cost = supplier_info["unit_cost"] if supplier_info else 10

            holding_cost = unit_cost * holding_cost_rate
            if holding_cost > 0 and annual_demand > 0:
                eoq = int(np.ceil(np.sqrt(2 * annual_demand * ordering_cost / holding_cost)))
            else:
                eoq = int(adjusted_velocity * config["max_stock_days"])

            moq = supplier_info["moq"] if supplier_info else 1
            suggested_qty = max(eoq, moq)

            if supplier_info and supplier_info.get("bulk_threshold"):
                if suggested_qty >= supplier_info["bulk_threshold"] * 0.8:
                    suggested_qty = max(suggested_qty, supplier_info["bulk_threshold"])
                    bulk_discount_applied = 1
                else:
                    bulk_discount_applied = 0
            else:
                bulk_discount_applied = 0

            max_stock = int(adjusted_velocity * config["max_stock_days"])
            suggested_qty = min(suggested_qty, max(max_stock - current_stock, moq))
            suggested_qty = max(suggested_qty, moq)

            days_until_stockout = int((current_stock - safety_stock) / adjusted_velocity) if adjusted_velocity > 0 else 999
            optimal_order_date = date.today() + timedelta(days=max(0, days_until_stockout - lead_time))

            estimated_cost = suggested_qty * unit_cost
            if bulk_discount_applied and supplier_info.get("bulk_price"):
                estimated_cost = suggested_qty * supplier_info["bulk_price"]

            suggestion_data = {
                "store_id": store_id,
                "item_id": item_id,
                "item_name": item_name,
                "supplier_id": supplier_info["supplier_id"] if supplier_info else None,
                "current_stock": current_stock,
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "suggested_qty": suggested_qty,
                "optimal_order_date": optimal_order_date,
                "estimated_cost": round(estimated_cost, 2),
                "bulk_discount_applied": bulk_discount_applied,
                "demand_velocity": round(adjusted_velocity, 2),
                "status": "pending",
            }

            db_suggestion = ReplenishmentSuggestion(**suggestion_data)
            db.add(db_suggestion)
            suggestions.append(suggestion_data)

    await db.commit()
    return suggestions


async def _calculate_demand_velocity(db: AsyncSession, store_id: int, item_id: str) -> float:
    sql = """
    SELECT COALESCE(AVG(daily_qty), 0)
    FROM (
        SELECT sale_date, SUM(quantity) as daily_qty
        FROM sales
        WHERE store_id = :store_id AND item_id = :item_id
          AND sale_date >= CURRENT_DATE - INTERVAL '60 days'
        GROUP BY sale_date
    ) sub
    """
    result = await db.execute(text(sql), {"store_id": store_id, "item_id": item_id})
    return float(result.scalar() or 0)


async def _calculate_demand_std(db: AsyncSession, store_id: int, item_id: str) -> float:
    sql = """
    SELECT COALESCE(STDDEV(daily_qty), 1)
    FROM (
        SELECT sale_date, SUM(quantity) as daily_qty
        FROM sales
        WHERE store_id = :store_id AND item_id = :item_id
          AND sale_date >= CURRENT_DATE - INTERVAL '60 days'
        GROUP BY sale_date
    ) sub
    """
    result = await db.execute(text(sql), {"store_id": store_id, "item_id": item_id})
    val = result.scalar()
    return float(val) if val and float(val) > 0 else 1.0


async def _get_item_config(db: AsyncSession, store_id: int, item_id: str) -> dict:
    result = await db.execute(
        select(ReplenishmentConfig).where(
            ReplenishmentConfig.store_id == store_id,
            ReplenishmentConfig.item_id == item_id,
        )
    )
    config = result.scalar_one_or_none()
    if config:
        return {
            "service_level": config.service_level,
            "review_period_days": config.review_period_days,
            "max_stock_days": config.max_stock_days,
            "weather_sensitivity": config.weather_sensitivity,
            "promo_boost_factor": config.promo_boost_factor,
        }
    return {
        "service_level": 0.95,
        "review_period_days": 7,
        "max_stock_days": 30,
        "weather_sensitivity": 0.1,
        "promo_boost_factor": 1.3,
    }


async def _get_primary_supplier(db: AsyncSession, item_id: str) -> Optional[dict]:
    result = await db.execute(
        select(SupplierItem, Supplier)
        .join(Supplier, Supplier.id == SupplierItem.supplier_id)
        .where(SupplierItem.item_id == item_id, Supplier.is_active == 1)
        .order_by(SupplierItem.is_primary.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None
    si, supplier = row
    return {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "lead_time": supplier.lead_time_days,
        "unit_cost": si.unit_cost,
        "moq": si.moq,
        "bulk_price": si.bulk_price,
        "bulk_threshold": supplier.bulk_discount_threshold,
    }


async def _get_promo_boost(
    db: AsyncSession, store_id: int, item_id: str, boost_factor: float
) -> float:
    sql = """
    SELECT COUNT(*) FROM promotions
    WHERE store_id = :store_id
      AND status = 'active'
      AND start_date <= CURRENT_DATE + INTERVAL '14 days'
      AND end_date >= CURRENT_DATE
      AND (target_items IS NULL OR target_items LIKE :item_pattern)
    """
    result = await db.execute(text(sql), {
        "store_id": store_id,
        "item_id": item_id,
        "item_pattern": f"%{item_id}%",
    })
    count = result.scalar() or 0
    return boost_factor if count > 0 else 1.0


async def _get_weather_factor(db: AsyncSession, store_id: int, sensitivity: float) -> float:
    sql = """
    SELECT AVG(precipitation)
    FROM weather w
    JOIN stores s ON s.city = w.city
    WHERE s.id = :store_id
      AND w.weather_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
    """
    result = await db.execute(text(sql), {"store_id": store_id})
    avg_precip = result.scalar()
    if avg_precip and float(avg_precip) > 10:
        return 1.0 - sensitivity
    return 1.0


async def get_replenishment_dashboard(
    db: AsyncSession, store_ids: Optional[List[int]] = None
) -> dict:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "WHERE store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    pending_sql = f"""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
        COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
        COALESCE(SUM(CASE WHEN status = 'pending' THEN estimated_cost ELSE 0 END), 0) as pending_value,
        COUNT(CASE WHEN current_stock <= 0 THEN 1 END) as urgent_items
    FROM replenishment_suggestions
    {store_filter}
    """
    result = await db.execute(text(pending_sql), params)
    row = result.fetchone()

    coverage_sql = f"""
    SELECT
        COUNT(*) as total_items,
        COUNT(CASE WHEN quantity > min_stock THEN 1 END) as covered_items
    FROM (
        SELECT DISTINCT ON (store_id, item_id) store_id, item_id, quantity, min_stock
        FROM inventory
        {"WHERE store_id = ANY(:store_ids)" if store_ids else ""}
        ORDER BY store_id, item_id, snapshot_date DESC
    ) latest
    """
    cov_result = await db.execute(text(coverage_sql), params)
    cov_row = cov_result.fetchone()
    total_items = cov_row[0] or 1
    covered = cov_row[1] or 0
    coverage_rate = round(covered / total_items * 100, 1)

    return {
        "items_below_rop": row[4] or 0,
        "coverage_rate": coverage_rate,
        "pending_orders_value": float(row[3] or 0),
        "pending_count": row[1] or 0,
        "approved_count": row[2] or 0,
        "urgent_items": [],
    }


async def get_replenishment_timeline(
    db: AsyncSession, store_id: int, limit: int = 20
) -> List[dict]:
    sql = """
    SELECT
        rs.item_id, rs.item_name, rs.current_stock,
        rs.demand_velocity, rs.optimal_order_date,
        rs.suggested_qty, s.lead_time_days
    FROM replenishment_suggestions rs
    LEFT JOIN suppliers s ON s.id = rs.supplier_id
    WHERE rs.store_id = :store_id AND rs.status = 'pending'
    ORDER BY rs.optimal_order_date ASC
    LIMIT :limit
    """
    result = await db.execute(text(sql), {"store_id": store_id, "limit": limit})
    rows = result.fetchall()

    timeline = []
    for row in rows:
        velocity = float(row[3]) if row[3] else 0
        days_until = int(row[2] / velocity) if velocity > 0 else 999
        lead_time = row[6] or 7
        delivery_date = row[4] + timedelta(days=lead_time) if row[4] else None

        timeline.append({
            "item_id": row[0],
            "item_name": row[1],
            "current_stock": row[2],
            "daily_consumption": velocity,
            "days_until_stockout": days_until,
            "reorder_date": str(row[4]) if row[4] else None,
            "delivery_date": str(delivery_date) if delivery_date else None,
        })

    return timeline
