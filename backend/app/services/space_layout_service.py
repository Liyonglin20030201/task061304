from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional, List

from app.models.space_layout import StoreZone, ZoneSalesDaily, ZoneItemMapping


async def get_zones(db: AsyncSession, store_id: int, authorized_stores: Optional[List[int]]):
    """Query store_zones with permission check, return list of dicts."""
    query = select(StoreZone).where(StoreZone.is_active == 1)

    if store_id:
        query = query.where(StoreZone.store_id == store_id)

    if authorized_stores is not None:
        query = query.where(StoreZone.store_id.in_(authorized_stores))

    result = await db.execute(query.order_by(StoreZone.id))
    zones = result.scalars().all()
    return [
        {c.name: getattr(z, c.name) for c in z.__table__.columns}
        for z in zones
    ]


async def create_zone(db: AsyncSession, data: dict):
    """Insert new zone, commit, return the created zone."""
    zone = StoreZone(**data)
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    return {c.name: getattr(zone, c.name) for c in zone.__table__.columns}


async def update_zone(db: AsyncSession, zone_id: int, data: dict):
    """Update zone fields."""
    result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(zone, key, value)
    await db.flush()
    await db.refresh(zone)
    return {c.name: getattr(zone, c.name) for c in zone.__table__.columns}


async def delete_zone(db: AsyncSession, zone_id: int):
    """Soft delete (set is_active=0)."""
    result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        return False
    zone.is_active = 0
    await db.flush()
    return True


async def get_zone_kpis(db: AsyncSession, store_id: int, start_date: str, end_date: str):
    """Join store_zones with zone_sales_daily aggregated over date range."""
    sql = """
    SELECT
        sz.id as zone_id,
        sz.zone_name,
        sz.zone_type,
        sz.area_sqm,
        COALESCE(SUM(zsd.revenue), 0) as revenue,
        COALESCE(SUM(zsd.transaction_count), 0) as transaction_count,
        COALESCE(SUM(zsd.items_sold), 0) as items_sold,
        COALESCE(SUM(zsd.traffic_count), 0) as traffic_count
    FROM store_zones sz
    LEFT JOIN zone_sales_daily zsd
        ON zsd.zone_id = sz.id
        AND zsd.sale_date BETWEEN :start_date AND :end_date
    WHERE sz.store_id = :store_id AND sz.is_active = 1
    GROUP BY sz.id, sz.zone_name, sz.zone_type, sz.area_sqm
    ORDER BY revenue DESC
    """
    result = await db.execute(text(sql), {
        "store_id": store_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    rows = result.fetchall()

    kpis = []
    for row in rows:
        zone_id, zone_name, zone_type, area_sqm, revenue, txn_count, items_sold, traffic_count = row
        area = max(float(area_sqm), 0.01)
        revenue_f = float(revenue)
        items_f = float(items_sold)
        txn_i = int(txn_count)
        traffic_i = int(traffic_count)

        kpis.append({
            "zone_id": zone_id,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "area_sqm": float(area_sqm),
            "revenue": round(revenue_f, 2),
            "transaction_count": txn_i,
            "items_sold": round(items_f, 2),
            "traffic_count": traffic_i,
            "revenue_per_sqm": round(revenue_f / area, 2),
            "items_per_sqm": round(items_f / area, 2),
            "traffic_conversion": round(txn_i / traffic_i, 4) if traffic_i > 0 else 0.0,
        })
    return kpis


async def get_sales_heatmap(db: AsyncSession, store_id: int, start_date: str, end_date: str):
    """Get zone positions + total revenue, normalize intensities."""
    sql = """
    SELECT
        sz.id as zone_id,
        sz.zone_name,
        sz.position_x,
        sz.position_y,
        sz.width,
        sz.height,
        COALESCE(SUM(zsd.revenue), 0) as revenue
    FROM store_zones sz
    LEFT JOIN zone_sales_daily zsd
        ON zsd.zone_id = sz.id
        AND zsd.sale_date BETWEEN :start_date AND :end_date
    WHERE sz.store_id = :store_id AND sz.is_active = 1
    GROUP BY sz.id, sz.zone_name, sz.position_x, sz.position_y, sz.width, sz.height
    """
    result = await db.execute(text(sql), {
        "store_id": store_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    rows = result.fetchall()

    if not rows:
        return []

    max_revenue = max(float(r[6]) for r in rows)
    if max_revenue == 0:
        max_revenue = 1.0

    cells = []
    for row in rows:
        zone_id, zone_name, pos_x, pos_y, width, height, revenue = row
        revenue_f = float(revenue)
        cells.append({
            "zone_id": zone_id,
            "zone_name": zone_name,
            "position_x": pos_x,
            "position_y": pos_y,
            "width": width,
            "height": height,
            "intensity": round(revenue_f / max_revenue, 4),
            "revenue": round(revenue_f, 2),
        })
    return cells


async def get_zone_ranking(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: str,
    end_date: str,
    metric: str = "revenue_per_sqm",
):
    """Rank zones across authorized stores by chosen metric."""
    store_filter = ""
    params: dict = {"start_date": start_date, "end_date": end_date}
    if store_ids is not None:
        store_filter = "AND sz.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    metric_col = {
        "revenue_per_sqm": "COALESCE(SUM(zsd.revenue), 0) / GREATEST(sz.area_sqm, 0.01)",
        "revenue": "COALESCE(SUM(zsd.revenue), 0)",
        "transaction_count": "COALESCE(SUM(zsd.transaction_count), 0)",
    }.get(metric, "COALESCE(SUM(zsd.revenue), 0) / GREATEST(sz.area_sqm, 0.01)")

    sql = f"""
    SELECT
        sz.id as zone_id,
        sz.zone_name,
        st.name as store_name,
        sz.zone_type,
        {metric_col} as metric_value
    FROM store_zones sz
    JOIN stores st ON st.id = sz.store_id
    LEFT JOIN zone_sales_daily zsd
        ON zsd.zone_id = sz.id
        AND zsd.sale_date BETWEEN :start_date AND :end_date
    WHERE sz.is_active = 1 {store_filter}
    GROUP BY sz.id, sz.zone_name, st.name, sz.zone_type, sz.area_sqm
    ORDER BY metric_value DESC
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    rankings = []
    for idx, row in enumerate(rows, start=1):
        zone_id, zone_name, store_name, zone_type, metric_value = row
        rankings.append({
            "zone_id": zone_id,
            "zone_name": zone_name,
            "store_name": store_name,
            "zone_type": zone_type,
            "metric_value": round(float(metric_value), 2),
            "rank": idx,
        })
    return rankings


async def get_zone_trends(
    db: AsyncSession,
    zone_id: int,
    start_date: str,
    end_date: str,
    granularity: str = "daily",
):
    """Time series for a specific zone with daily/weekly/monthly aggregation."""
    if granularity == "weekly":
        date_expr = "DATE_TRUNC('week', zsd.sale_date)::date"
    elif granularity == "monthly":
        date_expr = "DATE_TRUNC('month', zsd.sale_date)::date"
    else:
        date_expr = "zsd.sale_date"

    # Get zone area for per-sqm calc
    zone_result = await db.execute(select(StoreZone).where(StoreZone.id == zone_id))
    zone = zone_result.scalar_one_or_none()
    area_sqm = float(zone.area_sqm) if zone else 1.0
    area_sqm = max(area_sqm, 0.01)

    sql = f"""
    SELECT
        {date_expr} as period_date,
        COALESCE(SUM(zsd.revenue), 0) as revenue,
        COALESCE(SUM(zsd.transaction_count), 0) as transaction_count,
        COALESCE(SUM(zsd.items_sold), 0) as items_sold
    FROM zone_sales_daily zsd
    WHERE zsd.zone_id = :zone_id
        AND zsd.sale_date BETWEEN :start_date AND :end_date
    GROUP BY period_date
    ORDER BY period_date
    """
    result = await db.execute(text(sql), {
        "zone_id": zone_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    rows = result.fetchall()

    trends = []
    for row in rows:
        period_date, revenue, txn_count, items_sold = row
        revenue_f = float(revenue)
        trends.append({
            "date": str(period_date),
            "revenue": round(revenue_f, 2),
            "transaction_count": int(txn_count),
            "items_sold": round(float(items_sold), 2),
            "revenue_per_sqm": round(revenue_f / area_sqm, 2),
        })
    return trends


async def generate_layout_recommendations(
    db: AsyncSession, store_id: int, start_date: str, end_date: str
):
    """Generate layout optimization recommendations based on zone performance."""
    sql = """
    SELECT
        sz.id as zone_id,
        sz.zone_name,
        sz.zone_type,
        sz.area_sqm,
        COALESCE(SUM(zsd.revenue), 0) as revenue,
        COALESCE(SUM(zsd.transaction_count), 0) as transaction_count,
        COALESCE(SUM(zsd.traffic_count), 0) as traffic_count
    FROM store_zones sz
    LEFT JOIN zone_sales_daily zsd
        ON zsd.zone_id = sz.id
        AND zsd.sale_date BETWEEN :start_date AND :end_date
    WHERE sz.store_id = :store_id AND sz.is_active = 1
    GROUP BY sz.id, sz.zone_name, sz.zone_type, sz.area_sqm
    """
    result = await db.execute(text(sql), {
        "store_id": store_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    rows = result.fetchall()

    if not rows:
        return []

    # Calculate revenue_per_sqm for each zone
    zone_data = []
    for row in rows:
        zone_id, zone_name, zone_type, area_sqm, revenue, txn_count, traffic_count = row
        area = max(float(area_sqm), 0.01)
        rev_per_sqm = float(revenue) / area
        zone_data.append({
            "zone_id": zone_id,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "area_sqm": float(area_sqm),
            "revenue": float(revenue),
            "revenue_per_sqm": rev_per_sqm,
            "transaction_count": int(txn_count),
            "traffic_count": int(traffic_count),
        })

    # Calculate store average revenue_per_sqm
    total_rev_per_sqm = sum(z["revenue_per_sqm"] for z in zone_data)
    avg_rev_per_sqm = total_rev_per_sqm / len(zone_data) if zone_data else 0

    recommendations = []

    for z in zone_data:
        # Rule 1: Underperforming zones (below 70% of average)
        if avg_rev_per_sqm > 0 and z["revenue_per_sqm"] < avg_rev_per_sqm * 0.7:
            pct = round(z["revenue_per_sqm"] / avg_rev_per_sqm * 100, 1) if avg_rev_per_sqm > 0 else 0
            recommendations.append({
                "zone_id": z["zone_id"],
                "zone_name": z["zone_name"],
                "current_performance": f"坪效 {round(z['revenue_per_sqm'], 2)} 元/㎡ (店均 {round(avg_rev_per_sqm, 2)} 的 {pct}%)",
                "issue": "区域坪效显著低于门店平均水平",
                "suggestion": "建议调整品类布局，替换为高坪效品类或缩减该区域面积",
                "estimated_impact": f"若提升至店均水平，预计增收 {round((avg_rev_per_sqm - z['revenue_per_sqm']) * z['area_sqm'], 0)} 元",
                "priority": "high",
            })

        # Rule 2: High traffic but low conversion
        if z["traffic_count"] > 0:
            conversion = z["transaction_count"] / z["traffic_count"]
            avg_conversion = (
                sum(zz["transaction_count"] for zz in zone_data) /
                max(sum(zz["traffic_count"] for zz in zone_data), 1)
            )
            if conversion < avg_conversion * 0.6 and z["traffic_count"] > 0:
                recommendations.append({
                    "zone_id": z["zone_id"],
                    "zone_name": z["zone_name"],
                    "current_performance": f"客流 {z['traffic_count']}，转化率 {round(conversion * 100, 1)}%",
                    "issue": "高客流但低转化，顾客未有效购买",
                    "suggestion": "建议摆放高毛利冲动消费商品，优化陈列吸引力",
                    "estimated_impact": f"转化率每提升1%，预计增加 {round(z['traffic_count'] * 0.01 * (z['revenue'] / max(z['transaction_count'], 1)), 0)} 元收入",
                    "priority": "medium",
                })

        # Rule 3: Entrance zones with low traffic
        if z["zone_type"] == "entrance" and z["traffic_count"] > 0:
            max_traffic = max(zz["traffic_count"] for zz in zone_data)
            if z["traffic_count"] < max_traffic * 0.5 and max_traffic > 0:
                recommendations.append({
                    "zone_id": z["zone_id"],
                    "zone_name": z["zone_name"],
                    "current_performance": f"入口区客流 {z['traffic_count']}，低于最高区域 {max_traffic}",
                    "issue": "入口区域客流吸引力不足",
                    "suggestion": "建议将高引流品类（生鲜、促销商品）调整至此入口区域",
                    "estimated_impact": "预计可提升入口引流效果30-50%",
                    "priority": "high",
                })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: priority_order.get(x["priority"], 2))
    return recommendations


async def aggregate_zone_sales(db: AsyncSession, store_id: int, target_date: str):
    """Join sales.category with zone_item_mapping to assign sales to zones, upsert into zone_sales_daily."""
    sql = """
    SELECT
        zim.zone_id,
        COALESCE(SUM(s.total_amount), 0) as revenue,
        COUNT(DISTINCT s.receipt_no) as transaction_count,
        COALESCE(SUM(s.quantity), 0) as items_sold
    FROM sales s
    JOIN zone_item_mapping zim
        ON (zim.category = s.category AND (zim.item_id IS NULL OR zim.item_id = s.item_id))
    JOIN store_zones sz ON sz.id = zim.zone_id AND sz.store_id = s.store_id
    WHERE s.store_id = :store_id AND s.sale_date = :target_date
    GROUP BY zim.zone_id
    """
    result = await db.execute(text(sql), {
        "store_id": store_id,
        "target_date": target_date,
    })
    rows = result.fetchall()

    # Get traffic data for the date
    traffic_sql = """
    SELECT COALESCE(SUM(t.count), 0) as total_traffic
    FROM traffic t
    WHERE t.store_id = :store_id AND t.traffic_date = :target_date
    """
    traffic_result = await db.execute(text(traffic_sql), {
        "store_id": store_id,
        "target_date": target_date,
    })
    traffic_row = traffic_result.fetchone()
    total_traffic = int(traffic_row[0]) if traffic_row else 0

    # Get zone count for traffic distribution
    zone_count_result = await db.execute(
        select(StoreZone).where(
            StoreZone.store_id == store_id,
            StoreZone.is_active == 1,
        )
    )
    zone_count = len(zone_count_result.scalars().all())
    traffic_per_zone = total_traffic // max(zone_count, 1)

    count = 0
    for row in rows:
        zone_id, revenue, transaction_count, items_sold = row

        upsert_sql = """
        INSERT INTO zone_sales_daily (store_id, zone_id, sale_date, revenue, transaction_count, items_sold, traffic_count)
        VALUES (:store_id, :zone_id, :sale_date, :revenue, :transaction_count, :items_sold, :traffic_count)
        ON CONFLICT (zone_id, sale_date)
        DO UPDATE SET
            revenue = EXCLUDED.revenue,
            transaction_count = EXCLUDED.transaction_count,
            items_sold = EXCLUDED.items_sold,
            traffic_count = EXCLUDED.traffic_count
        """
        await db.execute(text(upsert_sql), {
            "store_id": store_id,
            "zone_id": zone_id,
            "sale_date": target_date,
            "revenue": float(revenue),
            "transaction_count": int(transaction_count),
            "items_sold": float(items_sold),
            "traffic_count": traffic_per_zone,
        })
        count += 1

    await db.flush()
    return count


async def compare_stores_layout(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: str,
    end_date: str,
):
    """Compare same zone_type performance across stores, grouped by zone_type."""
    store_filter = ""
    params: dict = {"start_date": start_date, "end_date": end_date}
    if store_ids is not None:
        store_filter = "AND sz.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    SELECT
        sz.zone_type,
        st.id as store_id,
        st.name as store_name,
        COALESCE(SUM(zsd.revenue), 0) as revenue,
        COALESCE(SUM(zsd.transaction_count), 0) as transaction_count,
        COALESCE(SUM(zsd.items_sold), 0) as items_sold,
        SUM(sz.area_sqm) as total_area,
        COUNT(DISTINCT sz.id) as zone_count
    FROM store_zones sz
    JOIN stores st ON st.id = sz.store_id
    LEFT JOIN zone_sales_daily zsd
        ON zsd.zone_id = sz.id
        AND zsd.sale_date BETWEEN :start_date AND :end_date
    WHERE sz.is_active = 1 AND sz.zone_type IS NOT NULL {store_filter}
    GROUP BY sz.zone_type, st.id, st.name
    ORDER BY sz.zone_type, revenue DESC
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    # Group by zone_type
    grouped = {}
    for row in rows:
        zone_type, store_id, store_name, revenue, txn_count, items_sold, total_area, zone_count = row
        area = max(float(total_area), 0.01)
        if zone_type not in grouped:
            grouped[zone_type] = []
        grouped[zone_type].append({
            "store_id": store_id,
            "store_name": store_name,
            "revenue": round(float(revenue), 2),
            "transaction_count": int(txn_count),
            "items_sold": round(float(items_sold), 2),
            "total_area_sqm": round(float(total_area), 2),
            "revenue_per_sqm": round(float(revenue) / area, 2),
            "zone_count": int(zone_count),
        })

    return grouped
