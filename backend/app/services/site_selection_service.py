import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import datetime
from typing import Optional, List

from app.models.site_selection import (
    CandidateLocation, LocationFactor, SiteEvaluation,
    SiteWeightProfile, CompetitorLocation,
)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_r, lat2_r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


async def evaluate_location(
    db: AsyncSession, location_id: int, weight_profile_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> dict:
    loc_result = await db.execute(
        select(CandidateLocation).where(CandidateLocation.id == location_id)
    )
    location = loc_result.scalar_one_or_none()
    if not location:
        return {"error": "候选地址不存在"}

    if weight_profile_id:
        wp_result = await db.execute(
            select(SiteWeightProfile).where(SiteWeightProfile.id == weight_profile_id)
        )
        profile = wp_result.scalar_one_or_none()
    else:
        wp_result = await db.execute(
            select(SiteWeightProfile).where(SiteWeightProfile.is_default == 1).limit(1)
        )
        profile = wp_result.scalar_one_or_none()

    if not profile:
        weights = {"traffic": 0.25, "competition": 0.20, "demographic": 0.20, "transport": 0.15, "commercial": 0.20}
    else:
        weights = {
            "traffic": profile.traffic_weight,
            "competition": profile.competition_weight,
            "demographic": profile.demographic_weight,
            "transport": profile.transport_weight,
            "commercial": profile.commercial_weight,
        }

    traffic_score = await _calculate_traffic_score(db, location)
    competition_score = await _calculate_competition_score(db, location)
    demographic_score = await _calculate_demographic_score(db, location)
    transport_score = await _calculate_transport_score(db, location)
    commercial_score = await _calculate_commercial_score(db, location)

    total_score = (
        traffic_score * weights["traffic"] +
        competition_score * weights["competition"] +
        demographic_score * weights["demographic"] +
        transport_score * weights["transport"] +
        commercial_score * weights["commercial"]
    )

    predicted_revenue = await _predict_revenue(db, total_score, location.area_sqm)
    payback_months = None
    if location.monthly_rent and predicted_revenue > 0:
        payback_months = round(location.monthly_rent * 12 / (predicted_revenue * 0.15), 1)

    confidence = min(100, max(30, total_score * 0.8 + 20))

    evaluation = SiteEvaluation(
        location_id=location_id,
        total_score=round(total_score, 1),
        traffic_score=round(traffic_score, 1),
        competition_score=round(competition_score, 1),
        demographic_score=round(demographic_score, 1),
        transport_score=round(transport_score, 1),
        commercial_score=round(commercial_score, 1),
        predicted_monthly_revenue=round(predicted_revenue, 0),
        predicted_payback_months=payback_months,
        confidence_level=round(confidence, 1),
        weight_profile_used=weight_profile_id,
        evaluated_by=user_id,
    )
    db.add(evaluation)

    _save_factors(db, location_id, traffic_score, competition_score,
                  demographic_score, transport_score, commercial_score)

    await db.commit()
    await db.refresh(evaluation)

    return {
        "id": evaluation.id,
        "location_id": location_id,
        "location_name": location.name,
        "total_score": evaluation.total_score,
        "traffic_score": evaluation.traffic_score,
        "competition_score": evaluation.competition_score,
        "demographic_score": evaluation.demographic_score,
        "transport_score": evaluation.transport_score,
        "commercial_score": evaluation.commercial_score,
        "predicted_monthly_revenue": evaluation.predicted_monthly_revenue,
        "predicted_payback_months": evaluation.predicted_payback_months,
        "confidence_level": evaluation.confidence_level,
        "evaluated_at": evaluation.evaluated_at,
    }


def _save_factors(db, location_id, traffic, competition, demographic, transport, commercial):
    factors = [
        ("traffic", "客流密度评分", traffic),
        ("competition", "竞争环境评分", competition),
        ("demographics", "人口结构评分", demographic),
        ("transport", "交通便利性评分", transport),
        ("commercial", "商业环境评分", commercial),
    ]
    for ftype, fname, score in factors:
        factor = LocationFactor(
            location_id=location_id,
            factor_type=ftype,
            factor_name=fname,
            raw_value=score,
            normalized_score=score,
            data_source="algorithm",
        )
        db.add(factor)


async def _calculate_traffic_score(db: AsyncSession, location: CandidateLocation) -> float:
    if not location.city:
        return 50.0

    sql = """
    SELECT AVG(daily_traffic) FROM (
        SELECT t.store_id, AVG(t.enter_count) as daily_traffic
        FROM traffic t
        JOIN stores s ON s.id = t.store_id
        WHERE s.city = :city
          AND t.traffic_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY t.store_id
    ) sub
    """
    result = await db.execute(text(sql), {"city": location.city})
    avg_traffic = result.scalar()

    if avg_traffic:
        score = min(100, float(avg_traffic) / 10)
    else:
        score = 50.0

    if location.district:
        district_sql = """
        SELECT COUNT(*) FROM stores
        WHERE district = :district AND is_active = 1
        """
        d_result = await db.execute(text(district_sql), {"district": location.district})
        nearby_stores = d_result.scalar() or 0
        if nearby_stores > 0:
            score = min(100, score * 1.2)

    return score


async def _calculate_competition_score(db: AsyncSession, location: CandidateLocation) -> float:
    if not location.latitude or not location.longitude:
        return 60.0

    comp_result = await db.execute(select(CompetitorLocation).where(
        CompetitorLocation.city == location.city
    ))
    competitors = comp_result.scalars().all()

    if not competitors:
        return 85.0

    nearby_500m = 0
    nearby_1km = 0
    nearby_2km = 0

    for comp in competitors:
        if not comp.latitude or not comp.longitude:
            continue
        dist = _haversine_km(location.latitude, location.longitude, comp.latitude, comp.longitude)
        if dist <= 0.5:
            nearby_500m += 1
        elif dist <= 1.0:
            nearby_1km += 1
        elif dist <= 2.0:
            nearby_2km += 1

    penalty = nearby_500m * 15 + nearby_1km * 8 + nearby_2km * 3
    score = max(10, 100 - penalty)
    return score


async def _calculate_demographic_score(db: AsyncSession, location: CandidateLocation) -> float:
    if not location.city:
        return 50.0

    sql = """
    SELECT COUNT(DISTINCT m.id)
    FROM members m
    JOIN stores s ON s.id = m.register_store_id
    WHERE s.city = :city AND m.is_active = 1
    """
    result = await db.execute(text(sql), {"city": location.city})
    member_count = result.scalar() or 0

    if member_count > 10000:
        score = 90
    elif member_count > 5000:
        score = 75
    elif member_count > 1000:
        score = 60
    else:
        score = 45

    return float(score)


async def _calculate_transport_score(db: AsyncSession, location: CandidateLocation) -> float:
    base_score = 50.0

    if location.district:
        sql = """
        SELECT COUNT(*) FROM stores WHERE district = :district AND is_active = 1
        """
        result = await db.execute(text(sql), {"district": location.district})
        store_count = result.scalar() or 0
        if store_count >= 3:
            base_score = 80.0
        elif store_count >= 1:
            base_score = 65.0

    return base_score


async def _calculate_commercial_score(db: AsyncSession, location: CandidateLocation) -> float:
    if not location.city:
        return 50.0

    sql = """
    SELECT AVG(total_amount) FROM (
        SELECT s.id, SUM(sa.total_amount) as total_amount
        FROM stores s
        JOIN sales sa ON sa.store_id = s.id
        WHERE s.city = :city AND sa.sale_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY s.id
    ) sub
    """
    result = await db.execute(text(sql), {"city": location.city})
    avg_revenue = result.scalar()

    if avg_revenue:
        if float(avg_revenue) > 500000:
            return 90.0
        elif float(avg_revenue) > 200000:
            return 75.0
        elif float(avg_revenue) > 100000:
            return 60.0
    return 50.0


async def _predict_revenue(
    db: AsyncSession, total_score: float, area_sqm: Optional[float]
) -> float:
    sql = """
    SELECT AVG(monthly_rev), STDDEV(monthly_rev) FROM (
        SELECT store_id, SUM(total_amount) as monthly_rev
        FROM sales
        WHERE sale_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY store_id
    ) sub
    """
    result = await db.execute(text(sql))
    row = result.fetchone()
    avg_rev = float(row[0]) if row[0] else 200000
    std_rev = float(row[1]) if row[1] else 50000

    score_factor = total_score / 70.0
    area_factor = 1.0
    if area_sqm:
        area_factor = min(2.0, area_sqm / 100.0)

    predicted = avg_rev * score_factor * area_factor
    return max(0, predicted)


async def get_store_benchmark(db: AsyncSession) -> dict:
    sql = """
    SELECT
        COUNT(DISTINCT s.id) as store_count,
        AVG(monthly_rev) as avg_monthly,
        MAX(monthly_rev) as max_monthly,
        AVG(monthly_rev / NULLIF(s.area_sqm, 0)) as avg_sqm_eff
    FROM stores s
    LEFT JOIN (
        SELECT store_id, SUM(total_amount) as monthly_rev
        FROM sales
        WHERE sale_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY store_id
    ) rev ON rev.store_id = s.id
    WHERE s.is_active = 1
    """
    result = await db.execute(text(sql))
    row = result.fetchone()

    traffic_sql = """
    SELECT AVG(daily_avg) FROM (
        SELECT store_id, AVG(enter_count) as daily_avg
        FROM traffic
        WHERE traffic_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY store_id
    ) sub
    """
    t_result = await db.execute(text(traffic_sql))
    avg_traffic = float(t_result.scalar() or 0)

    return {
        "store_count": row[0] or 0,
        "avg_monthly_revenue": round(float(row[1] or 0), 0),
        "top_store_revenue": round(float(row[2] or 0), 0),
        "avg_sqm_efficiency": round(float(row[3] or 0), 1),
        "avg_traffic": round(avg_traffic, 0),
    }
