from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models.store import Store
from app.schemas.store import StoreCreate, StoreResponse
from app.api.deps import get_current_user_with_stores, require_role
from app.core.permissions import filter_by_authorized_stores, enforce_store_access

router = APIRouter(prefix="/stores", tags=["门店管理"])


@router.get("", response_model=List[StoreResponse])
async def list_stores(
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    query = select(Store).where(Store.is_active == True)
    query = filter_by_authorized_stores(query, Store.id, authorized_stores)
    result = await db.execute(query.order_by(Store.code))
    return result.scalars().all()


@router.post("", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def create_store(
    form: StoreCreate,
    _=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    store = Store(**form.model_dump())
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return store


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: int,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    enforce_store_access(authorized_stores, store_id)
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="门店不存在")
    return store
