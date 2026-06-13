from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.database import get_db
from app.models.member import Member
from app.schemas.member import MemberResponse
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user_with_stores

router = APIRouter(prefix="/members", tags=["会员管理"])


@router.get("", response_model=PaginatedResponse)
async def list_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    level: Optional[str] = None,
    rfm_segment: Optional[str] = None,
    keyword: Optional[str] = None,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    query = select(Member)
    if authorized_stores is not None:
        query = query.where(Member.register_store_id.in_(authorized_stores))
    if level:
        query = query.where(Member.level == level)
    if rfm_segment:
        query = query.where(Member.rfm_segment == rfm_segment)
    if keyword:
        query = query.where(
            (Member.name.ilike(f"%{keyword}%")) | (Member.phone.ilike(f"%{keyword}%"))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    items = (await db.execute(
        query.order_by(Member.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedResponse(
        items=[MemberResponse.model_validate(item) for item in items],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
