from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import UserStorePermission


ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_VIEWER = "viewer"


async def get_user_authorized_stores(db: AsyncSession, user_id: int, role_name: str) -> Optional[List[int]]:
    if role_name == ROLE_ADMIN:
        return None  # None means unrestricted (all stores)
    result = await db.execute(
        select(UserStorePermission.store_id).where(UserStorePermission.user_id == user_id)
    )
    store_ids = [row[0] for row in result.fetchall()]
    return store_ids  # may be empty — means user has access to NO stores


def filter_by_authorized_stores(query, store_column, authorized_stores: Optional[List[int]]):
    if authorized_stores is None:
        return query  # admin: no filter
    # Non-admin: always filter, even if list is empty (user sees nothing)
    return query.where(store_column.in_(authorized_stores))


def check_store_access(authorized_stores: Optional[List[int]], store_id: int) -> bool:
    if authorized_stores is None:
        return True  # admin
    return store_id in authorized_stores


def enforce_store_access(authorized_stores: Optional[List[int]], store_id: int):
    if authorized_stores is None:
        return  # admin
    if store_id not in authorized_stores:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无权访问门店 {store_id} 的数据",
        )
