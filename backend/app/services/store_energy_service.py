from datetime import datetime, date, timedelta
from typing import List, Optional
import numpy as np
from scipy import stats
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store_energy import (
    StoreEquipment, StoreEnergyDaily, StoreEnergyBudget,
    StoreEnergyAlert, EquipmentSchedule,
)


# ---------- Dashboard ----------

async def get_energy_dashboard(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
):
    store_filter = ""
    params: dict = {"start_date": str(start_date), "end_date": str(end_date)}
    if store_ids:
        store_filter = "AND d.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    # Total kWh and cost
    result = await db.execute(text(f"""
        SELECT COALESCE(SUM(d.total_kwh), 0) as total_kwh,
               COALESCE(SUM(d.cost_yuan), 0) as total_cost
        FROM store_energy_daily d
        WHERE d.energy_date BETWEEN :start_date AND :end_date {store_filter}
    """), params)
    row = result.mappings().first()
    total_kwh = float(row["total_kwh"])
    total_cost = float(row["total_cost"])

    # Cost per sqm
    result = await db.execute(text(f"""
        SELECT COALESCE(SUM(s.area_sqm), 0) as total_area
        FROM stores s
        WHERE s.id IN (
            SELECT DISTINCT d.store_id FROM store_energy_daily d
            WHERE d.energy_date BETWEEN :start_date AND :end_date {store_filter}
        )
    """), params)
    area_row = result.mappings().first()
    total_area = float(area_row["total_area"]) if area_row["total_area"] else 1.0
    cost_per_sqm = round(total_cost / total_area, 2) if total_area > 0 else 0.0

    # Revenue per kWh (from sales table GMV)
    result = await db.execute(text(f"""
        SELECT COALESCE(SUM(s.total_amount), 0) as total_revenue
        FROM sales s
        WHERE s.sale_date BETWEEN :start_date AND :end_date
        {"AND s.store_id = ANY(:store_ids)" if store_ids else ""}
    """), params)
    rev_row = result.mappings().first()
    total_revenue = float(rev_row["total_revenue"])
    revenue_per_kwh = round(total_revenue / total_kwh, 2) if total_kwh > 0 else 0.0

    # Period comparison
    period_length = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length - 1)
    params_prev = {"start_date": str(prev_start), "end_date": str(prev_end)}
    if store_ids:
        params_prev["store_ids"] = store_ids

    result = await db.execute(text(f"""
        SELECT COALESCE(SUM(d.total_kwh), 0) as prev_kwh
        FROM store_energy_daily d
        WHERE d.energy_date BETWEEN :start_date AND :end_date {store_filter}
    """), params_prev)
    prev_row = result.mappings().first()
    prev_kwh = float(prev_row["prev_kwh"])
    period_kwh_change_pct = round(((total_kwh - prev_kwh) / prev_kwh) * 100, 1) if prev_kwh > 0 else 0.0

    # Equipment count
    result = await db.execute(text(f"""
        SELECT COUNT(*) as cnt FROM store_equipment
        WHERE status = 'active'
        {"AND store_id = ANY(:store_ids)" if store_ids else ""}
    """), params if store_ids else {})
    eq_row = result.mappings().first()
    equipment_count = int(eq_row["cnt"])

    # Breakdown by type
    result = await db.execute(text(f"""
        SELECT e.equipment_type,
               COALESCE(SUM(d.total_kwh), 0) as type_kwh,
               COALESCE(SUM(d.cost_yuan), 0) as type_cost
        FROM store_energy_daily d
        JOIN store_equipment e ON d.equipment_id = e.id
        WHERE d.energy_date BETWEEN :start_date AND :end_date {store_filter}
        GROUP BY e.equipment_type
        ORDER BY type_kwh DESC
    """), params)
    by_type = []
    for r in result.mappings().all():
        by_type.append({
            "equipment_type": r["equipment_type"],
            "total_kwh": round(float(r["type_kwh"]), 2),
            "total_cost": round(float(r["type_cost"]), 2),
            "pct": round(float(r["type_kwh"]) / total_kwh * 100, 1) if total_kwh > 0 else 0.0,
        })

    return {
        "total_kwh": round(total_kwh, 2),
        "total_cost": round(total_cost, 2),
        "cost_per_sqm": cost_per_sqm,
        "revenue_per_kwh": revenue_per_kwh,
        "period_kwh_change_pct": period_kwh_change_pct,
        "equipment_count": equipment_count,
        "by_type": by_type,
    }


# ---------- Trends ----------

async def get_energy_trends(
    db: AsyncSession,
    store_id: int,
    start_date: date,
    end_date: date,
    granularity: str = "daily",
    equipment_type: Optional[str] = None,
):
    type_filter = ""
    params: dict = {"store_id": store_id, "start_date": str(start_date), "end_date": str(end_date)}
    if equipment_type:
        type_filter = "AND e.equipment_type = :equipment_type"
        params["equipment_type"] = equipment_type

    if granularity == "weekly":
        date_expr = "DATE_TRUNC('week', d.energy_date)::date"
    elif granularity == "monthly":
        date_expr = "DATE_TRUNC('month', d.energy_date)::date"
    else:
        date_expr = "d.energy_date"

    query = f"""
        SELECT {date_expr} as period_date,
               COALESCE(SUM(d.total_kwh), 0) as total_kwh,
               COALESCE(SUM(d.cost_yuan), 0) as total_cost
        FROM store_energy_daily d
        JOIN store_equipment e ON d.equipment_id = e.id
        WHERE d.store_id = :store_id
          AND d.energy_date BETWEEN :start_date AND :end_date
          {type_filter}
        GROUP BY period_date
        ORDER BY period_date
    """
    result = await db.execute(text(query), params)
    trends = []
    for r in result.mappings().all():
        trends.append({
            "date": str(r["period_date"]),
            "total_kwh": round(float(r["total_kwh"]), 2),
            "total_cost": round(float(r["total_cost"]), 2),
            "equipment_type": equipment_type,
        })
    return trends


# ---------- Peak Hour Analysis ----------

async def get_peak_hour_analysis(
    db: AsyncSession,
    store_id: int,
    start_date: date,
    end_date: date,
):
    params = {"store_id": store_id, "start_date": str(start_date), "end_date": str(end_date)}
    result = await db.execute(text("""
        SELECT EXTRACT(HOUR FROM reading_time)::int as hour,
               AVG(energy_kwh) as avg_kwh
        FROM store_energy_readings
        WHERE store_id = :store_id
          AND reading_time >= :start_date::timestamp
          AND reading_time < (:end_date::date + interval '1 day')
        GROUP BY hour
        ORDER BY hour
    """), params)

    cost_rate = 0.85  # default yuan/kWh
    hours_data = {i: {"avg_kwh": 0.0, "avg_cost": 0.0} for i in range(24)}
    for r in result.mappings().all():
        h = int(r["hour"])
        avg_kwh = float(r["avg_kwh"])
        hours_data[h] = {"avg_kwh": round(avg_kwh, 4), "avg_cost": round(avg_kwh * cost_rate, 4)}

    return [{"hour": h, "avg_kwh": v["avg_kwh"], "avg_cost": v["avg_cost"]} for h, v in sorted(hours_data.items())]


# ---------- Weather-Energy Correlation ----------

async def get_weather_energy_correlation(
    db: AsyncSession,
    store_id: int,
    start_date: date,
    end_date: date,
):
    params = {"store_id": store_id, "start_date": str(start_date), "end_date": str(end_date)}
    result = await db.execute(text("""
        SELECT d.energy_date,
               SUM(d.total_kwh) as daily_kwh,
               w.temp_high
        FROM store_energy_daily d
        JOIN stores s ON d.store_id = s.id
        JOIN weather w ON w.city = s.city AND w.weather_date = d.energy_date
        WHERE d.store_id = :store_id
          AND d.energy_date BETWEEN :start_date AND :end_date
          AND w.temp_high IS NOT NULL
        GROUP BY d.energy_date, w.temp_high
        ORDER BY d.energy_date
    """), params)

    rows = result.mappings().all()
    if len(rows) < 3:
        return {
            "correlation_coefficient": 0.0,
            "p_value": 1.0,
            "data_points": [],
        }

    temps = np.array([float(r["temp_high"]) for r in rows])
    kwhs = np.array([float(r["daily_kwh"]) for r in rows])

    corr, p_value = stats.pearsonr(temps, kwhs)

    data_points = [
        {"x": float(r["temp_high"]), "y": round(float(r["daily_kwh"]), 2)}
        for r in rows
    ]

    return {
        "correlation_coefficient": round(float(corr), 4),
        "p_value": round(float(p_value), 6),
        "data_points": data_points,
    }


# ---------- Sales-Energy Correlation ----------

async def get_sales_energy_correlation(
    db: AsyncSession,
    store_id: int,
    start_date: date,
    end_date: date,
):
    params = {"store_id": store_id, "start_date": str(start_date), "end_date": str(end_date)}
    result = await db.execute(text("""
        SELECT d.energy_date,
               SUM(d.total_kwh) as daily_kwh,
               COALESCE(sv.daily_revenue, 0) as daily_revenue
        FROM store_energy_daily d
        LEFT JOIN (
            SELECT sale_date, SUM(total_amount) as daily_revenue
            FROM sales
            WHERE store_id = :store_id AND sale_date BETWEEN :start_date AND :end_date
            GROUP BY sale_date
        ) sv ON sv.sale_date = d.energy_date
        WHERE d.store_id = :store_id
          AND d.energy_date BETWEEN :start_date AND :end_date
        GROUP BY d.energy_date, sv.daily_revenue
        ORDER BY d.energy_date
    """), params)

    rows = result.mappings().all()
    if len(rows) < 3:
        return {
            "correlation_coefficient": 0.0,
            "p_value": 1.0,
            "data_points": [],
        }

    revenues = np.array([float(r["daily_revenue"]) for r in rows])
    kwhs = np.array([float(r["daily_kwh"]) for r in rows])

    corr, p_value = stats.pearsonr(revenues, kwhs)

    data_points = [
        {"x": round(float(r["daily_revenue"]), 2), "y": round(float(r["daily_kwh"]), 2)}
        for r in rows
    ]

    return {
        "correlation_coefficient": round(float(corr), 4),
        "p_value": round(float(p_value), 6),
        "data_points": data_points,
    }


# ---------- Optimize Equipment Schedule ----------

async def optimize_equipment_schedule(db: AsyncSession, store_id: int):
    # 1. Get hourly traffic pattern
    result = await db.execute(text("""
        SELECT hour, AVG(enter_count) as avg_traffic
        FROM traffic
        WHERE store_id = :store_id
        GROUP BY hour
        ORDER BY hour
    """), {"store_id": store_id})
    traffic_rows = result.mappings().all()

    hourly_traffic = {int(r["hour"]): float(r["avg_traffic"]) for r in traffic_rows}
    peak_traffic = max(hourly_traffic.values()) if hourly_traffic else 1.0
    low_traffic_threshold = peak_traffic * 0.30

    # 2. Identify low-traffic hours
    low_traffic_hours = set()
    for h, count in hourly_traffic.items():
        if count < low_traffic_threshold:
            low_traffic_hours.add(h)

    # Identify peak hours for pre-cooling
    peak_hours = set()
    for h, count in hourly_traffic.items():
        if count >= peak_traffic * 0.8:
            peak_hours.add(h)

    # 3. Get equipment
    result = await db.execute(text("""
        SELECT id, name, equipment_type, rated_power_kw
        FROM store_equipment
        WHERE store_id = :store_id AND status = 'active'
    """), {"store_id": store_id})
    equipments = result.mappings().all()

    cost_rate = 0.85  # yuan per kWh
    recommendations = []

    for eq in equipments:
        eq_type = eq["equipment_type"]
        eq_id = eq["id"]
        eq_name = eq["name"]
        rated = float(eq["rated_power_kw"])

        for day in range(7):
            for h in range(24):
                current_level = "full"
                recommended_level = None
                reason = ""
                reduction_factor = 0.0

                if eq_type == "hvac":
                    if h in low_traffic_hours:
                        recommended_level = "reduced"
                        reason = "Low traffic period - reduce HVAC output"
                        reduction_factor = 0.4
                    elif (h + 1) in peak_hours and h not in peak_hours:
                        recommended_level = "full"
                        reason = "Pre-cool before predicted peak traffic"
                        reduction_factor = 0.0
                elif eq_type == "lighting":
                    if h in low_traffic_hours:
                        recommended_level = "reduced"
                        reason = "Low traffic - reduce lighting to 50%"
                        reduction_factor = 0.5
                elif eq_type == "refrigeration":
                    # Constant - no change
                    continue
                elif eq_type == "pos":
                    # Standby during store-closed hours (assume closed 22-7)
                    if h >= 22 or h < 7:
                        recommended_level = "standby"
                        reason = "Store closed - POS standby mode"
                        reduction_factor = 0.85

                if recommended_level and recommended_level != current_level:
                    saving = rated * reduction_factor * cost_rate / 7  # per day fraction
                    recommendations.append({
                        "equipment_id": eq_id,
                        "equipment_name": eq_name,
                        "day_of_week": day,
                        "hour": h,
                        "current_level": current_level,
                        "recommended_level": recommended_level,
                        "reason": reason,
                        "estimated_saving_kwh": round(rated * reduction_factor, 3),
                    })

    return recommendations


# ---------- Anomaly Detection ----------

async def detect_anomalies(db: AsyncSession, store_id: int, lookback_days: int = 30):
    result = await db.execute(text("""
        SELECT equipment_id, e.name as equipment_name, energy_date, total_kwh
        FROM store_energy_daily d
        JOIN store_equipment e ON d.equipment_id = e.id
        WHERE d.store_id = :store_id
          AND d.energy_date >= CURRENT_DATE - :lookback_days * interval '1 day'
        ORDER BY equipment_id, energy_date
    """), {"store_id": store_id, "lookback_days": lookback_days})
    rows = result.mappings().all()

    # Group by equipment
    equip_data: dict = {}
    for r in rows:
        eid = r["equipment_id"]
        if eid not in equip_data:
            equip_data[eid] = {"name": r["equipment_name"], "readings": []}
        equip_data[eid]["readings"].append({
            "date": r["energy_date"],
            "kwh": float(r["total_kwh"]),
        })

    anomalies = []
    now = datetime.now()

    for eid, data in equip_data.items():
        readings = data["readings"]
        if len(readings) < 7:
            continue

        kwh_values = np.array([r["kwh"] for r in readings])

        # Rolling window of 7 days
        window = 7
        for i in range(window, len(kwh_values)):
            window_data = kwh_values[max(0, i - window):i]
            mean = float(np.mean(window_data))
            std = float(np.std(window_data))

            if std > 0 and kwh_values[i] > mean + 2 * std:
                anomaly_date = readings[i]["date"]
                anomaly_kwh = kwh_values[i]

                # Create alert record
                await db.execute(text("""
                    INSERT INTO store_energy_alerts
                    (store_id, equipment_id, alert_type, alert_level, message, metric_value, threshold_value, alert_time)
                    VALUES (:store_id, :equipment_id, 'anomaly', 'warning',
                            :message, :metric_value, :threshold_value, :alert_time)
                """), {
                    "store_id": store_id,
                    "equipment_id": eid,
                    "message": f"Anomaly detected: {data['name']} consumed {anomaly_kwh:.1f} kWh on {anomaly_date}, exceeding 2-sigma threshold ({mean + 2*std:.1f} kWh)",
                    "metric_value": anomaly_kwh,
                    "threshold_value": round(mean + 2 * std, 2),
                    "alert_time": str(now),
                })

                anomalies.append({
                    "equipment_id": eid,
                    "equipment_name": data["name"],
                    "date": str(anomaly_date),
                    "actual_kwh": round(anomaly_kwh, 2),
                    "expected_kwh": round(mean, 2),
                    "threshold_kwh": round(mean + 2 * std, 2),
                })

    await db.commit()
    return anomalies


# ---------- Budget Alerts ----------

async def check_budget_alerts(db: AsyncSession, store_id: int, year_month: str):
    # Get budget
    result = await db.execute(text("""
        SELECT * FROM store_energy_budget
        WHERE store_id = :store_id AND year_month = :year_month
    """), {"store_id": store_id, "year_month": year_month})
    budget = result.mappings().first()
    if not budget:
        return []

    budget_kwh = float(budget["budget_kwh"])
    threshold_pct = float(budget["alert_threshold_pct"])

    # Get actual consumption for the month
    month_start = f"{year_month}-01"
    result = await db.execute(text("""
        SELECT COALESCE(SUM(total_kwh), 0) as actual_kwh
        FROM store_energy_daily
        WHERE store_id = :store_id
          AND energy_date >= :month_start
          AND TO_CHAR(energy_date, 'YYYY-MM') = :year_month
    """), {"store_id": store_id, "month_start": month_start, "year_month": year_month})
    row = result.mappings().first()
    actual_kwh = float(row["actual_kwh"])

    alerts = []
    now = datetime.now()
    usage_pct = (actual_kwh / budget_kwh * 100) if budget_kwh > 0 else 0

    if usage_pct >= 100:
        alerts.append({
            "alert_type": "budget_exceeded",
            "alert_level": "critical",
            "message": f"Energy budget exceeded: {actual_kwh:.1f} kWh used vs {budget_kwh:.1f} kWh budget ({usage_pct:.1f}%)",
            "metric_value": actual_kwh,
            "threshold_value": budget_kwh,
        })
        await db.execute(text("""
            INSERT INTO store_energy_alerts
            (store_id, alert_type, alert_level, message, metric_value, threshold_value, alert_time)
            VALUES (:store_id, 'budget_exceeded', 'critical', :message, :metric_value, :threshold_value, :alert_time)
        """), {
            "store_id": store_id,
            "message": f"Energy budget exceeded: {actual_kwh:.1f}/{budget_kwh:.1f} kWh ({usage_pct:.1f}%)",
            "metric_value": actual_kwh,
            "threshold_value": budget_kwh,
            "alert_time": str(now),
        })
    elif usage_pct >= threshold_pct:
        alerts.append({
            "alert_type": "budget_exceeded",
            "alert_level": "warning",
            "message": f"Energy budget threshold reached: {actual_kwh:.1f} kWh used ({usage_pct:.1f}% of {budget_kwh:.1f} kWh budget)",
            "metric_value": actual_kwh,
            "threshold_value": budget_kwh * threshold_pct / 100,
        })
        await db.execute(text("""
            INSERT INTO store_energy_alerts
            (store_id, alert_type, alert_level, message, metric_value, threshold_value, alert_time)
            VALUES (:store_id, 'budget_exceeded', 'warning', :message, :metric_value, :threshold_value, :alert_time)
        """), {
            "store_id": store_id,
            "message": f"Energy budget at {usage_pct:.1f}%: {actual_kwh:.1f}/{budget_kwh:.1f} kWh",
            "metric_value": actual_kwh,
            "threshold_value": budget_kwh * threshold_pct / 100,
            "alert_time": str(now),
        })

    await db.commit()
    return alerts


# ---------- Cost Optimization Recommendations ----------

async def get_cost_optimization_recommendations(
    db: AsyncSession,
    store_id: int,
    start_date: date,
    end_date: date,
):
    params = {"store_id": store_id, "start_date": str(start_date), "end_date": str(end_date)}
    recommendations = []

    # 1. Peak/off-peak ratio analysis
    result = await db.execute(text("""
        SELECT EXTRACT(HOUR FROM reading_time)::int as hour,
               SUM(energy_kwh) as hour_kwh
        FROM store_energy_readings
        WHERE store_id = :store_id
          AND reading_time >= :start_date::timestamp
          AND reading_time < (:end_date::date + interval '1 day')
        GROUP BY hour
    """), params)
    hourly = result.mappings().all()

    if hourly:
        peak_hours_kwh = sum(float(r["hour_kwh"]) for r in hourly if 8 <= int(r["hour"]) <= 22)
        total_kwh = sum(float(r["hour_kwh"]) for r in hourly)
        peak_ratio = peak_hours_kwh / total_kwh if total_kwh > 0 else 0

        if peak_ratio > 0.6:
            potential_saving = total_kwh * 0.05 * 0.85  # 5% shift * cost rate
            recommendations.append({
                "category": "load_shifting",
                "title": "Peak Hour Load Shifting",
                "description": f"Peak hours account for {peak_ratio*100:.0f}% of total consumption. Shifting non-critical loads to off-peak hours can reduce costs.",
                "potential_saving_yuan": round(potential_saving, 2),
                "priority": "high",
            })

    # 2. Equipment efficiency analysis
    result = await db.execute(text("""
        SELECT e.id, e.name, e.equipment_type, e.rated_power_kw,
               AVG(d.avg_kw) as actual_avg_kw,
               SUM(d.total_kwh) as period_kwh
        FROM store_equipment e
        JOIN store_energy_daily d ON e.id = d.equipment_id
        WHERE e.store_id = :store_id
          AND d.energy_date BETWEEN :start_date AND :end_date
          AND e.status = 'active'
        GROUP BY e.id, e.name, e.equipment_type, e.rated_power_kw
    """), params)
    equip_rows = result.mappings().all()

    for eq in equip_rows:
        rated = float(eq["rated_power_kw"])
        actual_avg = float(eq["actual_avg_kw"]) if eq["actual_avg_kw"] else 0
        if rated > 0 and actual_avg > rated * 0.9:
            period_kwh = float(eq["period_kwh"])
            saving = period_kwh * 0.1 * 0.85
            recommendations.append({
                "category": "equipment_efficiency",
                "title": f"High Load on {eq['name']}",
                "description": f"{eq['name']} running at {actual_avg/rated*100:.0f}% of rated capacity. Consider maintenance or upgrade.",
                "potential_saving_yuan": round(saving, 2),
                "priority": "medium",
            })

    # 3. Type breakdown - HVAC dominance
    result = await db.execute(text("""
        SELECT e.equipment_type,
               SUM(d.total_kwh) as type_kwh
        FROM store_energy_daily d
        JOIN store_equipment e ON d.equipment_id = e.id
        WHERE d.store_id = :store_id
          AND d.energy_date BETWEEN :start_date AND :end_date
        GROUP BY e.equipment_type
    """), params)
    type_rows = result.mappings().all()
    type_kwh_map = {r["equipment_type"]: float(r["type_kwh"]) for r in type_rows}
    total_type_kwh = sum(type_kwh_map.values())

    hvac_kwh = type_kwh_map.get("hvac", 0)
    if total_type_kwh > 0 and hvac_kwh / total_type_kwh > 0.5:
        saving = hvac_kwh * 0.15 * 0.85
        recommendations.append({
            "category": "hvac_optimization",
            "title": "HVAC Energy Dominance",
            "description": f"HVAC accounts for {hvac_kwh/total_type_kwh*100:.0f}% of total energy. Consider inverter upgrades, improved insulation, or smart thermostat controls.",
            "potential_saving_yuan": round(saving, 2),
            "priority": "high",
        })

    # 4. Weekend vs weekday pattern
    result = await db.execute(text("""
        SELECT EXTRACT(DOW FROM d.energy_date)::int as dow,
               AVG(d.total_kwh) as avg_daily_kwh
        FROM store_energy_daily d
        WHERE d.store_id = :store_id
          AND d.energy_date BETWEEN :start_date AND :end_date
        GROUP BY dow
    """), params)
    dow_rows = result.mappings().all()
    dow_map = {int(r["dow"]): float(r["avg_daily_kwh"]) for r in dow_rows}

    weekday_avg = np.mean([v for k, v in dow_map.items() if k in (1, 2, 3, 4, 5)]) if any(k in dow_map for k in (1, 2, 3, 4, 5)) else 0
    weekend_avg = np.mean([v for k, v in dow_map.items() if k in (0, 6)]) if any(k in dow_map for k in (0, 6)) else 0

    if weekday_avg > 0 and weekend_avg / weekday_avg > 0.85:
        # Check weekend sales vs weekday
        result = await db.execute(text("""
            SELECT EXTRACT(DOW FROM sale_date)::int as dow,
                   AVG(total_amount) as avg_revenue
            FROM sales
            WHERE store_id = :store_id
              AND sale_date BETWEEN :start_date AND :end_date
            GROUP BY dow
        """), params)
        sales_dow = result.mappings().all()
        sales_map = {int(r["dow"]): float(r["avg_revenue"]) for r in sales_dow}

        wd_sales = np.mean([v for k, v in sales_map.items() if k in (1, 2, 3, 4, 5)]) if sales_map else 0
        we_sales = np.mean([v for k, v in sales_map.items() if k in (0, 6)]) if sales_map else 0

        if wd_sales > 0 and we_sales / wd_sales < 0.7:
            saving = (weekend_avg - weekday_avg * 0.7) * 2 * 4 * 0.85  # 2 weekend days * 4 weeks
            recommendations.append({
                "category": "weekend_optimization",
                "title": "Weekend Energy Reduction",
                "description": "Weekend energy consumption is similar to weekdays but sales are significantly lower. Reduce operational intensity on weekends.",
                "potential_saving_yuan": round(max(saving, 0), 2),
                "priority": "medium",
            })

    return recommendations


# ---------- Equipment CRUD ----------

async def get_equipment(db: AsyncSession, store_id: int, authorized_stores: Optional[List[int]]):
    params: dict = {"store_id": store_id}
    if authorized_stores is not None and store_id not in authorized_stores:
        return []
    result = await db.execute(text("""
        SELECT * FROM store_equipment WHERE store_id = :store_id ORDER BY equipment_type, name
    """), params)
    return result.mappings().all()


async def create_equipment(db: AsyncSession, data: dict):
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f":{k}" for k in data.keys())
    result = await db.execute(
        text(f"INSERT INTO store_equipment ({columns}) VALUES ({placeholders}) RETURNING id"),
        data,
    )
    await db.commit()
    row = result.mappings().first()
    eq_id = row["id"]
    result = await db.execute(text("SELECT * FROM store_equipment WHERE id = :id"), {"id": eq_id})
    return result.mappings().first()


async def update_equipment(db: AsyncSession, equipment_id: int, data: dict):
    if not data:
        result = await db.execute(text("SELECT * FROM store_equipment WHERE id = :id"), {"id": equipment_id})
        return result.mappings().first()
    set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
    data["id"] = equipment_id
    await db.execute(text(f"UPDATE store_equipment SET {set_clause} WHERE id = :id"), data)
    await db.commit()
    result = await db.execute(text("SELECT * FROM store_equipment WHERE id = :id"), {"id": equipment_id})
    return result.mappings().first()


# ---------- Schedules ----------

async def get_schedules(db: AsyncSession, store_id: int):
    result = await db.execute(text("""
        SELECT * FROM equipment_schedules
        WHERE store_id = :store_id AND is_active = 1
        ORDER BY equipment_id, day_of_week, start_hour
    """), {"store_id": store_id})
    return result.mappings().all()


async def create_schedule(db: AsyncSession, data: dict):
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f":{k}" for k in data.keys())
    result = await db.execute(
        text(f"INSERT INTO equipment_schedules ({columns}) VALUES ({placeholders}) RETURNING id"),
        data,
    )
    await db.commit()
    row = result.mappings().first()
    sch_id = row["id"]
    result = await db.execute(text("SELECT * FROM equipment_schedules WHERE id = :id"), {"id": sch_id})
    return result.mappings().first()


async def update_schedule(db: AsyncSession, schedule_id: int, data: dict):
    if not data:
        result = await db.execute(text("SELECT * FROM equipment_schedules WHERE id = :id"), {"id": schedule_id})
        return result.mappings().first()
    set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
    data["id"] = schedule_id
    await db.execute(text(f"UPDATE equipment_schedules SET {set_clause} WHERE id = :id"), data)
    await db.commit()
    result = await db.execute(text("SELECT * FROM equipment_schedules WHERE id = :id"), {"id": schedule_id})
    return result.mappings().first()


# ---------- Alerts ----------

async def get_alerts(db: AsyncSession, store_id: int, acknowledged: Optional[bool] = None):
    params: dict = {"store_id": store_id}
    ack_filter = ""
    if acknowledged is not None:
        ack_filter = "AND is_acknowledged = :ack"
        params["ack"] = 1 if acknowledged else 0
    result = await db.execute(text(f"""
        SELECT * FROM store_energy_alerts
        WHERE store_id = :store_id {ack_filter}
        ORDER BY alert_time DESC
        LIMIT 100
    """), params)
    return result.mappings().all()


async def acknowledge_alert(db: AsyncSession, alert_id: int, user_id: int):
    await db.execute(text("""
        UPDATE store_energy_alerts
        SET is_acknowledged = 1, acknowledged_by = :user_id
        WHERE id = :alert_id
    """), {"alert_id": alert_id, "user_id": user_id})
    await db.commit()
    result = await db.execute(text("SELECT * FROM store_energy_alerts WHERE id = :id"), {"id": alert_id})
    return result.mappings().first()


# ---------- Budget ----------

async def get_budget(db: AsyncSession, store_id: int, year_month: Optional[str] = None):
    params: dict = {"store_id": store_id}
    month_filter = ""
    if year_month:
        month_filter = "AND year_month = :year_month"
        params["year_month"] = year_month
    result = await db.execute(text(f"""
        SELECT * FROM store_energy_budget
        WHERE store_id = :store_id {month_filter}
        ORDER BY year_month DESC
    """), params)
    return result.mappings().all()


async def set_budget(db: AsyncSession, data: dict):
    # Upsert: insert or update on conflict
    result = await db.execute(text("""
        INSERT INTO store_energy_budget (store_id, year_month, budget_kwh, budget_yuan, alert_threshold_pct)
        VALUES (:store_id, :year_month, :budget_kwh, :budget_yuan, :alert_threshold_pct)
        ON CONFLICT ON CONSTRAINT uq_store_energy_budget
        DO UPDATE SET budget_kwh = EXCLUDED.budget_kwh,
                      budget_yuan = EXCLUDED.budget_yuan,
                      alert_threshold_pct = EXCLUDED.alert_threshold_pct
        RETURNING id
    """), data)
    await db.commit()
    row = result.mappings().first()
    budget_id = row["id"]
    result = await db.execute(text("SELECT * FROM store_energy_budget WHERE id = :id"), {"id": budget_id})
    return result.mappings().first()
