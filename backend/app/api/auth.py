from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, Role, UserStorePermission
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.core.security import verify_password, get_password_hash, create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=Token)
async def login(form: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()
    token = create_access_token(data={"sub": str(user.id), "role": role.name if role else "viewer"})
    return Token(access_token=token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(form: UserCreate, db: AsyncSession = Depends(get_db)):
    exists = await db.execute(select(User).where((User.username == form.username) | (User.email == form.email)))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或邮箱已存在")
    user = User(
        username=form.username,
        email=form.email,
        hashed_password=get_password_hash(form.password),
        full_name=form.full_name,
        role_id=form.role_id,
    )
    db.add(user)
    await db.flush()
    if form.store_ids:
        for store_id in form.store_ids:
            perm = UserStorePermission(user_id=user.id, store_id=store_id)
            db.add(perm)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, is_active=user.is_active,
        role_id=user.role_id, authorized_store_ids=form.store_ids or [],
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()
    perm_result = await db.execute(
        select(UserStorePermission.store_id).where(UserStorePermission.user_id == user.id)
    )
    store_ids = [row[0] for row in perm_result.fetchall()]
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, is_active=user.is_active,
        role_id=user.role_id, role_name=role.name if role else None,
        authorized_store_ids=store_ids, created_at=user.created_at,
    )
