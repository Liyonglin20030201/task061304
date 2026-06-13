import pytest
from httpx import AsyncClient
from app.models.user import User, UserStorePermission, Role
from app.models.store import Store
from app.core.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_admin_can_access_all_stores(client: AsyncClient, db_session, setup_roles):
    store1 = Store(id=1, code="S001", name="门店一", city="上海")
    store2 = Store(id=2, code="S002", name="门店二", city="北京")
    db_session.add_all([store1, store2])
    await db_session.flush()

    admin = User(
        id=100, username="admin_perm", email="admin_perm@test.com",
        hashed_password=get_password_hash("Test123"), role_id=1,
    )
    db_session.add(admin)
    await db_session.commit()

    token = create_access_token({"sub": "100", "role": "admin"})
    response = await client.get("/api/stores", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    stores = response.json()
    assert len(stores) == 2


@pytest.mark.asyncio
async def test_viewer_can_only_see_authorized_stores(client: AsyncClient, db_session, setup_roles):
    store1 = Store(id=3, code="S003", name="门店三", city="广州")
    store2 = Store(id=4, code="S004", name="门店四", city="深圳")
    db_session.add_all([store1, store2])
    await db_session.flush()

    viewer = User(
        id=101, username="viewer_perm", email="viewer_perm@test.com",
        hashed_password=get_password_hash("Test123"), role_id=3,
    )
    db_session.add(viewer)
    await db_session.flush()

    perm = UserStorePermission(user_id=101, store_id=3)
    db_session.add(perm)
    await db_session.commit()

    token = create_access_token({"sub": "101", "role": "viewer"})
    response = await client.get("/api/stores", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    stores = response.json()
    assert len(stores) == 1
    assert stores[0]["code"] == "S003"


@pytest.mark.asyncio
async def test_viewer_cannot_access_unauthorized_store(client: AsyncClient, db_session, setup_roles):
    store = Store(id=5, code="S005", name="门店五", city="杭州")
    db_session.add(store)
    await db_session.flush()

    viewer = User(
        id=102, username="viewer_blocked", email="viewer_blocked@test.com",
        hashed_password=get_password_hash("Test123"), role_id=3,
    )
    db_session.add(viewer)
    await db_session.commit()

    token = create_access_token({"sub": "102", "role": "viewer"})
    response = await client.get("/api/stores/5", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_with_no_permissions_sees_nothing(client: AsyncClient, db_session, setup_roles):
    """A non-admin user with no store assignments should see zero stores, not all."""
    store = Store(id=6, code="S006", name="门店六", city="成都")
    db_session.add(store)
    await db_session.flush()

    viewer = User(
        id=103, username="viewer_empty", email="viewer_empty@test.com",
        hashed_password=get_password_hash("Test123"), role_id=3,
    )
    db_session.add(viewer)
    await db_session.commit()
    # No UserStorePermission rows for this user

    token = create_access_token({"sub": "103", "role": "viewer"})
    response = await client.get("/api/stores", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    stores = response.json()
    assert len(stores) == 0  # must see nothing, not everything


@pytest.mark.asyncio
async def test_viewer_cannot_access_forecast_for_unauthorized_store(client: AsyncClient, db_session, setup_roles):
    """Analytics forecast endpoint must return 403, not a data leak."""
    store = Store(id=7, code="S007", name="门店七", city="武汉")
    db_session.add(store)
    await db_session.flush()

    viewer = User(
        id=104, username="viewer_forecast", email="viewer_forecast@test.com",
        hashed_password=get_password_hash("Test123"), role_id=3,
    )
    db_session.add(viewer)
    await db_session.commit()

    token = create_access_token({"sub": "104", "role": "viewer"})
    response = await client.get(
        "/api/analytics/forecast?store_id=7&periods=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
