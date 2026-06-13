import numpy as np
from scipy.stats import norm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import date, timedelta
from typing import Optional, List

from app.models.supply_chain import Supplier, SupplierItem, SupplierDiscountTier
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
            packaging_unit = supplier_info.get("packaging_unit", 1) if supplier_info else 1
            suggested_qty = max(eoq, moq)

            # Round up to nearest packaging unit
            if packaging_unit > 1:
                suggested_qty = int(np.ceil(suggested_qty / packaging_unit) * packaging_unit)

            # Apply tiered discount: find the best tier for this quantity
            discount_tiers = supplier_info.get("discount_tiers", []) if supplier_info else []
            bulk_discount_applied = 0
            effective_unit_cost = unit_cost

            if discount_tiers:
                # Tiers sorted ascending by min_qty
                applicable_tier = None
                next_tier = None
                for i, tier in enumerate(discount_tiers):
                    if suggested_qty >= tier["min_qty"]:
                        applicable_tier = tier
                    elif next_tier is None:
                        next_tier = tier

                # Check if bumping up to next tier saves money overall
                if next_tier and applicable_tier:
                    cost_at_current = suggested_qty * (applicable_tier.get("tier_price") or unit_cost * (1 - applicable_tier["discount_rate"]))
                    next_qty = int(np.ceil(next_tier["min_qty"] / packaging_unit) * packaging_unit)
                    cost_at_next = next_qty * (next_tier.get("tier_price") or unit_cost * (1 - next_tier["discount_rate"]))
                    if cost_at_next <= cost_at_current * 1.05:
                        applicable_tier = next_tier
                        suggested_qty = next_qty
                elif next_tier and not applicable_tier:
                    # Below first tier; check if hitting it is worthwhile
                    next_qty = int(np.ceil(next_tier["min_qty"] / packaging_unit) * packaging_unit)
                    cost_no_discount = suggested_qty * unit_cost
                    cost_at_tier = next_qty * (next_tier.get("tier_price") or unit_cost * (1 - next_tier["discount_rate"]))
                    if cost_at_tier <= cost_no_discount * 1.1:
                        applicable_tier = next_tier
                        suggested_qty = next_qty

                if applicable_tier:
                    effective_unit_cost = applicable_tier.get("tier_price") or unit_cost * (1 - applicable_tier["discount_rate"])
                    bulk_discount_applied = 1

            max_stock = int(adjusted_velocity * config["max_stock_days"])
            suggested_qty = min(suggested_qty, max(max_stock - current_stock, moq))
            suggested_qty = max(suggested_qty, moq)
            # Re-align to packaging unit after capping
            if packaging_unit > 1:
                suggested_qty = int(np.ceil(suggested_qty / packaging_unit) * packaging_unit)

            days_until_stockout = int((current_stock - safety_stock) / adjusted_velocity) if adjusted_velocity > 0 else 999
            optimal_order_date = date.today() + timedelta(days=max(0, days_until_stockout - lead_time))

            estimated_cost = round(suggested_qty * effective_unit_cost, 2)

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

    # Secondary MOQ validation: aggregate per-supplier totals and round up if below MOQ
    supplier_totals: dict = {}
    for s in suggestions:
        sid = s.get("supplier_id")
        if sid is not None:
            supplier_totals.setdefault(sid, []).append(s)

    for sid, items in supplier_totals.items():
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.id == sid)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier or not supplier.min_order_qty:
            continue
        total_qty = sum(s["suggested_qty"] for s in items)
        if total_qty < supplier.min_order_qty:
            deficit = supplier.min_order_qty - total_qty
            last = items[-1]
            si_result = await db.execute(
                select(SupplierItem).where(
                    SupplierItem.supplier_id == sid,
                    SupplierItem.item_id == last["item_id"],
                )
            )
            si = si_result.scalar_one_or_none()
            pkg = (si.packaging_unit or 1) if si else 1
            added = int(np.ceil(deficit / pkg) * pkg)
            last["suggested_qty"] += added
            last["estimated_cost"] = round(
                last["suggested_qty"] * (last["estimated_cost"] / (last["suggested_qty"] - added)),
                2,
            )

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

    # Fetch tiered discount schedule
    tiers_result = await db.execute(
        select(SupplierDiscountTier)
        .where(
            SupplierDiscountTier.supplier_id == supplier.id,
            SupplierDiscountTier.item_id == item_id,
        )
        .order_by(SupplierDiscountTier.min_qty.asc())
    )
    tiers = [
        {"min_qty": t.min_qty, "discount_rate": t.discount_rate, "tier_price": t.tier_price}
        for t in tiers_result.scalars().all()
    ]

    return {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "lead_time": supplier.lead_time_days,
        "unit_cost": si.unit_cost,
        "moq": si.moq,
        "packaging_unit": si.packaging_unit or 1,
        "bulk_price": si.bulk_price,
        "bulk_threshold": supplier.bulk_discount_threshold,
        "discount_tiers": tiers,
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
