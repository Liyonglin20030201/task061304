from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import UserStorePermission


ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_VIEWER = "viewer"


async def get_user_authorized_stores(db: AsyncSession, user_id: int, role_name: str) -> List[int]:
    if role_name == ROLE_ADMIN:
        return []  # empty means all stores
    result = await db.execute(
        select(UserStorePermission.store_id).where(UserStorePermission.user_id == user_id)
    )
    return [row[0] for row in result.fetchall()]


def filter_by_authorized_stores(query, store_column, authorized_stores: List[int]):
    if not authorized_stores:
        return query
    return query.where(store_column.in_(authorized_stores))


def check_store_access(authorized_stores: List[int], store_id: int) -> bool:
    if not authorized_stores:
        return True
    return store_id in authorized_stores
