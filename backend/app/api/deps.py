from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.security import decode_token
from app.core.permissions import get_user_authorized_stores
from app.models.user import User, Role

security = HTTPBearer()


class AuthContext:
    """Encapsulates authenticated user with their authorization scope."""
    def __init__(self, user: User, authorized_stores: Optional[List[int]], role_name: str):
        self.user = user
        self.authorized_stores = authorized_stores
        self.role_name = role_name

    @property
    def is_admin(self) -> bool:
        return self.authorized_stores is None

    def get_effective_stores(self, requested_stores: Optional[List[int]] = None) -> Optional[List[int]]:
        if self.is_admin:
            return requested_stores  # admin can request any stores, or None for all
        if requested_stores:
            return [s for s in requested_stores if s in self.authorized_stores]
        return self.authorized_stores


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的Token")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


async def get_current_user_with_stores(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple:
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()
    role_name = role.name if role else "viewer"
    authorized_stores = await get_user_authorized_stores(db, user.id, role_name)
    return user, authorized_stores, role_name


async def get_auth_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()
    role_name = role.name if role else "viewer"
    authorized_stores = await get_user_authorized_stores(db, user.id, role_name)
    return AuthContext(user=user, authorized_stores=authorized_stores, role_name=role_name)


def require_role(allowed_roles: List[str]):
    async def role_checker(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = result.scalar_one_or_none()
        if role is None or role.name not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user
    return role_checker
