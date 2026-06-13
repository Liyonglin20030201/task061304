from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.core.permissions import ROLE_ADMIN, ROLE_MANAGER
from app.models.marketing import MarketingCampaign, MarketingRule, CampaignExecution
from app.schemas.marketing import (
    CampaignCreate, CampaignUpdate, CampaignStatusUpdate, CampaignResponse,
    RuleCreate, RuleUpdate, RuleResponse,
    MarketingDashboard, TriggerEvaluationResult,
)
from app.services.marketing_service import (
    get_marketing_dashboard,
    get_lifecycle_distribution,
    evaluate_triggers,
    get_campaign_analytics,
)

router = APIRouter(prefix="/marketing", tags=["marketing"])


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    return await get_marketing_dashboard(db)


@router.get("/campaigns", response_model=List[CampaignResponse])
async def list_campaigns(
    status_filter: Optional[str] = None,
    campaign_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    query = select(MarketingCampaign)
    if status_filter:
        query = query.where(MarketingCampaign.status == status_filter)
    if campaign_type:
        query = query.where(MarketingCampaign.campaign_type == campaign_type)
    query = query.order_by(MarketingCampaign.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    campaigns = result.scalars().all()

    response = []
    for c in campaigns:
        data = {col.name: getattr(c, col.name) for col in c.__table__.columns}
        exec_result = await db.execute(
            select(
                CampaignExecution.status,
                CampaignExecution.id,
            ).where(CampaignExecution.campaign_id == c.id)
        )
        execs = exec_result.fetchall()
        total_sent = len(execs)
        converted = sum(1 for e in execs if e[0] == "converted")
        data["stats"] = {
            "total_sent": total_sent,
            "converted": converted,
            "conversion_rate": round(converted / total_sent * 100, 1) if total_sent > 0 else 0,
        }
        response.append(data)
    return response


@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    campaign = MarketingCampaign(**data.model_dump(), created_by=user.id)
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return {**{col.name: getattr(campaign, col.name) for col in campaign.__table__.columns}, "stats": None}


@router.put("/campaigns/{campaign_id}", response_model=dict)
async def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(
        select(MarketingCampaign).where(MarketingCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    await db.commit()
    return {"message": "更新成功"}


@router.put("/campaigns/{campaign_id}/status")
async def update_campaign_status(
    campaign_id: int,
    data: CampaignStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(
        select(MarketingCampaign).where(MarketingCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    campaign.status = data.status
    await db.commit()
    return {"message": f"状态已更新为 {data.status}"}


@router.post("/campaigns/{campaign_id}/execute")
async def execute_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(
        select(MarketingCampaign).where(MarketingCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")

    from app.services.marketing_service import _evaluate_campaign_triggers
    triggered = await _evaluate_campaign_triggers(db, campaign)
    return {"message": f"已触发 {len(triggered)} 位会员", "triggered_count": len(triggered)}


@router.get("/campaigns/{campaign_id}/analytics")
async def campaign_analytics(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    return await get_campaign_analytics(db, campaign_id)


@router.get("/rules", response_model=List[RuleResponse])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    result = await db.execute(
        select(MarketingRule).order_by(MarketingRule.priority.desc())
    )
    return result.scalars().all()


@router.post("/rules", response_model=RuleResponse)
async def create_rule(
    data: RuleCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    rule = MarketingRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    data: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(select(MarketingRule).where(MarketingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    return {"message": "规则已更新"}


@router.get("/members/lifecycle")
async def lifecycle_distribution(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    return await get_lifecycle_distribution(db)


@router.post("/evaluate-triggers")
async def run_trigger_evaluation(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    results = await evaluate_triggers(db)
    total_triggered = sum(r["triggered_members"] for r in results)
    return {
        "message": f"已评估 {len(results)} 个活动，触发 {total_triggered} 位会员",
        "details": results,
    }
