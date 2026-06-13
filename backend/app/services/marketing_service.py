import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from datetime import date, datetime, timedelta
from typing import Optional, List

from app.models.marketing import (
    MarketingCampaign, CampaignExecution, MarketingRule, CampaignAnalytics,
)
from app.models.member import Member


LIFECYCLE_STAGES = {
    "new": (0, 30),
    "active": (0, 30),
    "declining": (31, 90),
    "at_risk": (91, 180),
    "churned": (181, 9999),
}


async def classify_member_lifecycle(db: AsyncSession) -> List[dict]:
    sql = """
    SELECT
        m.id, m.member_no, m.name, m.birthday, m.level, m.total_points,
        m.register_date, m.rfm_segment,
        CURRENT_DATE - MAX(mt.transaction_date)::date as days_since_last
    FROM members m
    LEFT JOIN member_transactions mt ON mt.member_id = m.id
    WHERE m.is_active = 1
    GROUP BY m.id, m.member_no, m.name, m.birthday, m.level,
             m.total_points, m.register_date, m.rfm_segment
    """
    result = await db.execute(text(sql))
    rows = result.fetchall()

    members = []
    for row in rows:
        days_since = row[8] if row[8] is not None else 9999
        days_registered = (date.today() - row[6]).days if row[6] else 9999

        if days_registered <= 30:
            stage = "new"
        elif days_since <= 30:
            stage = "active"
        elif days_since <= 90:
            stage = "declining"
        elif days_since <= 180:
            stage = "at_risk"
        else:
            stage = "churned"

        members.append({
            "member_id": row[0],
            "member_no": row[1],
            "name": row[2],
            "birthday": row[3],
            "level": row[4],
            "total_points": row[5],
            "rfm_segment": row[7],
            "days_since_last": days_since,
            "lifecycle_stage": stage,
        })

    return members


async def get_lifecycle_distribution(db: AsyncSession) -> List[dict]:
    members = await classify_member_lifecycle(db)
    total = len(members) or 1

    stage_counts = {}
    for m in members:
        stage = m["lifecycle_stage"]
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    return [
        {"stage": stage, "count": count, "percentage": round(count / total * 100, 1)}
        for stage, count in stage_counts.items()
    ]


async def evaluate_triggers(db: AsyncSession) -> List[dict]:
    results = []

    campaigns_result = await db.execute(
        select(MarketingCampaign).where(MarketingCampaign.status == "active")
    )
    active_campaigns = campaigns_result.scalars().all()

    for campaign in active_campaigns:
        triggered = await _evaluate_campaign_triggers(db, campaign)
        if triggered:
            results.append({
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "triggered_members": len(triggered),
                "trigger_type": campaign.campaign_type,
            })

    return results


async def _evaluate_campaign_triggers(
    db: AsyncSession, campaign: MarketingCampaign
) -> List[int]:
    triggered_member_ids = []

    if campaign.campaign_type == "birthday":
        triggered_member_ids = await _find_birthday_members(db)
    elif campaign.campaign_type == "churn_warning":
        triggered_member_ids = await _find_churn_risk_members(db)
    elif campaign.campaign_type == "repurchase":
        triggered_member_ids = await _find_repurchase_candidates(db)
    elif campaign.campaign_type == "upgrade":
        triggered_member_ids = await _find_upgrade_candidates(db)

    if not triggered_member_ids:
        return []

    valid_members = await _apply_cooldown_filter(
        db, campaign.id, triggered_member_ids
    )

    for member_id in valid_members:
        message = _render_template(campaign.message_template, member_id)
        execution = CampaignExecution(
            campaign_id=campaign.id,
            member_id=member_id,
            channel=campaign.channel,
            message_content=message,
            status="sent",
            sent_at=datetime.utcnow(),
        )
        db.add(execution)

    await db.commit()
    return valid_members


async def _find_birthday_members(db: AsyncSession) -> List[int]:
    sql = """
    SELECT id FROM members
    WHERE is_active = 1
      AND EXTRACT(MONTH FROM birthday) = EXTRACT(MONTH FROM CURRENT_DATE)
      AND EXTRACT(DAY FROM birthday) BETWEEN
          EXTRACT(DAY FROM CURRENT_DATE) AND EXTRACT(DAY FROM CURRENT_DATE + INTERVAL '7 days')
    """
    result = await db.execute(text(sql))
    return [row[0] for row in result.fetchall()]


async def _find_churn_risk_members(db: AsyncSession) -> List[int]:
    sql = """
    SELECT m.id
    FROM members m
    LEFT JOIN member_transactions mt ON mt.member_id = m.id
    WHERE m.is_active = 1
    GROUP BY m.id
    HAVING CURRENT_DATE - MAX(mt.transaction_date)::date BETWEEN 90 AND 180
    """
    result = await db.execute(text(sql))
    return [row[0] for row in result.fetchall()]


async def _find_repurchase_candidates(db: AsyncSession) -> List[int]:
    sql = """
    WITH member_intervals AS (
        SELECT member_id,
            AVG(interval_days) as avg_interval,
            MAX(transaction_date) as last_purchase
        FROM (
            SELECT member_id, transaction_date,
                transaction_date - LAG(transaction_date) OVER (PARTITION BY member_id ORDER BY transaction_date) as interval_days
            FROM member_transactions
        ) sub
        WHERE interval_days IS NOT NULL
        GROUP BY member_id
    )
    SELECT member_id FROM member_intervals
    WHERE CURRENT_DATE - last_purchase::date > avg_interval * 1.5
      AND avg_interval IS NOT NULL
    """
    result = await db.execute(text(sql))
    return [row[0] for row in result.fetchall()]


async def _find_upgrade_candidates(db: AsyncSession) -> List[int]:
    sql = """
    SELECT m.id
    FROM members m
    JOIN member_transactions mt ON mt.member_id = m.id
    WHERE m.is_active = 1
      AND mt.transaction_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY m.id, m.level, m.total_points
    HAVING SUM(mt.amount) > m.total_points * 0.8
       AND m.level IN ('silver', 'bronze', '普通')
    """
    result = await db.execute(text(sql))
    return [row[0] for row in result.fetchall()]


async def _apply_cooldown_filter(
    db: AsyncSession, campaign_id: int, member_ids: List[int]
) -> List[int]:
    if not member_ids:
        return []

    rule_result = await db.execute(
        select(MarketingRule).where(
            MarketingRule.campaign_id == campaign_id,
            MarketingRule.is_active == 1,
        )
    )
    rule = rule_result.scalar_one_or_none()
    cooldown_days = rule.cooldown_days if rule else 7
    max_triggers = rule.max_triggers_per_member if rule else 3

    sql = """
    SELECT member_id, COUNT(*) as trigger_count, MAX(triggered_at) as last_trigger
    FROM campaign_executions
    WHERE campaign_id = :campaign_id AND member_id = ANY(:member_ids)
    GROUP BY member_id
    """
    result = await db.execute(text(sql), {
        "campaign_id": campaign_id,
        "member_ids": member_ids,
    })
    history = {row[0]: (row[1], row[2]) for row in result.fetchall()}

    valid = []
    cutoff = datetime.utcnow() - timedelta(days=cooldown_days)
    for mid in member_ids:
        if mid in history:
            count, last = history[mid]
            if count >= max_triggers:
                continue
            if last and last > cutoff:
                continue
        valid.append(mid)

    return valid


def _render_template(template: Optional[str], member_id: int) -> str:
    if not template:
        return f"尊敬的会员，我们为您准备了专属优惠！"
    return template.replace("{member_id}", str(member_id))


async def get_campaign_analytics(db: AsyncSession, campaign_id: int) -> List[dict]:
    result = await db.execute(
        select(CampaignAnalytics)
        .where(CampaignAnalytics.campaign_id == campaign_id)
        .order_by(CampaignAnalytics.period_date.desc())
        .limit(30)
    )
    records = result.scalars().all()

    return [
        {
            "campaign_id": r.campaign_id,
            "period_date": str(r.period_date),
            "total_targeted": r.total_targeted,
            "total_sent": r.total_sent,
            "total_delivered": r.total_delivered,
            "total_opened": r.total_opened,
            "total_converted": r.total_converted,
            "total_revenue": r.total_revenue,
            "total_cost": r.total_cost,
            "roi": r.roi,
            "conversion_rate": round(r.total_converted / r.total_sent * 100, 1) if r.total_sent > 0 else 0,
            "open_rate": round(r.total_opened / r.total_delivered * 100, 1) if r.total_delivered > 0 else 0,
        }
        for r in reversed(records)
    ]


async def get_marketing_dashboard(db: AsyncSession) -> dict:
    active_count = await db.execute(
        select(func.count()).select_from(MarketingCampaign)
        .where(MarketingCampaign.status == "active")
    )
    active_campaigns = active_count.scalar() or 0

    month_start = date.today().replace(day=1)
    reached_sql = """
    SELECT COUNT(DISTINCT member_id)
    FROM campaign_executions
    WHERE sent_at >= :month_start AND status IN ('sent', 'delivered', 'opened', 'converted')
    """
    reached_result = await db.execute(text(reached_sql), {"month_start": month_start})
    members_reached = reached_result.scalar() or 0

    conv_sql = """
    SELECT
        COALESCE(AVG(CASE WHEN total_sent > 0 THEN total_converted::float / total_sent * 100 ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN total_cost > 0 THEN (total_revenue - total_cost) / total_cost ELSE 0 END), 0)
    FROM campaign_analytics
    WHERE period_date >= CURRENT_DATE - INTERVAL '30 days'
    """
    conv_result = await db.execute(text(conv_sql))
    conv_row = conv_result.fetchone()
    avg_conversion = float(conv_row[0]) if conv_row[0] else 0
    total_roi = float(conv_row[1]) if conv_row[1] else 0

    lifecycle = await get_lifecycle_distribution(db)

    return {
        "active_campaigns": active_campaigns,
        "members_reached_month": members_reached,
        "avg_conversion_rate": round(avg_conversion, 1),
        "total_roi": round(total_roi, 2),
        "lifecycle_distribution": lifecycle,
    }
