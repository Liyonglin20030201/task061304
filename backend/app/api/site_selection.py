from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import pandas as pd
import io

from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.core.permissions import ROLE_ADMIN, ROLE_MANAGER
from app.models.site_selection import (
    CandidateLocation, SiteEvaluation, SiteWeightProfile, CompetitorLocation,
)
from app.schemas.site_selection import (
    CandidateCreate, CandidateUpdate, CandidateResponse,
    EvaluationResponse, WeightProfileCreate, WeightProfileResponse,
    CompetitorCreate, CompetitorResponse, BenchmarkResponse,
)
from app.services.site_selection_service import (
    evaluate_location, get_store_benchmark,
)

router = APIRouter(prefix="/site-selection", tags=["site-selection"])


@router.get("/candidates", response_model=List[CandidateResponse])
async def list_candidates(
    status: Optional[str] = None,
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    query = select(CandidateLocation)
    if status:
        query = query.where(CandidateLocation.status == status)
    if city:
        query = query.where(CandidateLocation.city == city)
    query = query.order_by(CandidateLocation.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/candidates", response_model=CandidateResponse)
async def create_candidate(
    data: CandidateCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    location = CandidateLocation(**data.model_dump(), submitted_by=user.id)
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


@router.put("/candidates/{location_id}", response_model=CandidateResponse)
async def update_candidate(
    location_id: int,
    data: CandidateUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(
        select(CandidateLocation).where(CandidateLocation.id == location_id)
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="候选地址不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    await db.commit()
    await db.refresh(location)
    return location


@router.delete("/candidates/{location_id}")
async def delete_candidate(
    location_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可删除")
    result = await db.execute(
        select(CandidateLocation).where(CandidateLocation.id == location_id)
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="候选地址不存在")
    await db.delete(location)
    await db.commit()
    return {"message": "已删除"}


@router.post("/candidates/{location_id}/evaluate")
async def run_evaluation(
    location_id: int,
    weight_profile_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await evaluate_location(db, location_id, weight_profile_id, user.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/candidates/{location_id}/evaluation")
async def get_evaluation(
    location_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    result = await db.execute(
        select(SiteEvaluation)
        .where(SiteEvaluation.location_id == location_id)
        .order_by(SiteEvaluation.evaluated_at.desc())
        .limit(1)
    )
    evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise HTTPException(status_code=404, detail="尚未评估")

    loc_result = await db.execute(
        select(CandidateLocation).where(CandidateLocation.id == location_id)
    )
    location = loc_result.scalar_one_or_none()

    return {
        "id": evaluation.id,
        "location_id": location_id,
        "location_name": location.name if location else None,
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


@router.get("/evaluations/compare")
async def compare_evaluations(
    location_ids: str,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    ids = [int(x) for x in location_ids.split(",") if x.strip()]
    results = []
    for loc_id in ids:
        eval_result = await db.execute(
            select(SiteEvaluation)
            .where(SiteEvaluation.location_id == loc_id)
            .order_by(SiteEvaluation.evaluated_at.desc())
            .limit(1)
        )
        evaluation = eval_result.scalar_one_or_none()
        loc_result = await db.execute(
            select(CandidateLocation).where(CandidateLocation.id == loc_id)
        )
        location = loc_result.scalar_one_or_none()

        if evaluation and location:
            results.append({
                "location_id": loc_id,
                "location_name": location.name,
                "total_score": evaluation.total_score,
                "traffic_score": evaluation.traffic_score,
                "competition_score": evaluation.competition_score,
                "demographic_score": evaluation.demographic_score,
                "transport_score": evaluation.transport_score,
                "commercial_score": evaluation.commercial_score,
                "predicted_monthly_revenue": evaluation.predicted_monthly_revenue,
                "predicted_payback_months": evaluation.predicted_payback_months,
            })

    return sorted(results, key=lambda x: x["total_score"], reverse=True)


@router.get("/weight-profiles", response_model=List[WeightProfileResponse])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    result = await db.execute(select(SiteWeightProfile))
    return result.scalars().all()


@router.post("/weight-profiles", response_model=WeightProfileResponse)
async def create_profile(
    data: WeightProfileCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    profile = SiteWeightProfile(**data.model_dump(), created_by=user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/competitors", response_model=List[CompetitorResponse])
async def list_competitors(
    city: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    query = select(CompetitorLocation)
    if city:
        query = query.where(CompetitorLocation.city == city)
    query = query.order_by(CompetitorLocation.imported_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/competitors/import")
async def import_competitors(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")

    content = await file.read()
    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_excel(io.BytesIO(content))

    required_cols = {"name"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(status_code=400, detail="文件必须包含 name 列")

    count = 0
    for _, row in df.iterrows():
        comp = CompetitorLocation(
            name=str(row.get("name", "")),
            brand=str(row.get("brand", "")) if pd.notna(row.get("brand")) else None,
            category=str(row.get("category", "")) if pd.notna(row.get("category")) else None,
            latitude=float(row["latitude"]) if pd.notna(row.get("latitude")) else None,
            longitude=float(row["longitude"]) if pd.notna(row.get("longitude")) else None,
            city=str(row.get("city", "")) if pd.notna(row.get("city")) else None,
            district=str(row.get("district", "")) if pd.notna(row.get("district")) else None,
            estimated_revenue=float(row["estimated_revenue"]) if pd.notna(row.get("estimated_revenue")) else None,
            data_source=file.filename,
        )
        db.add(comp)
        count += 1

    await db.commit()
    return {"message": f"成功导入 {count} 条竞品数据"}


@router.get("/benchmark")
async def benchmark(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    return await get_store_benchmark(db)
