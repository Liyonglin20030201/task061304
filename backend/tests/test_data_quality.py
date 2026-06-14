import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import text
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_data_quality_health(client: AsyncClient, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store

    store = Store(id=1, name="测试门店", code="T001", address="测试地址", status="active")
    db_session.add(store)

    user = User(id=300, username="dq_admin", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "300", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/data-quality/health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert "completeness_score" in data
    assert "accuracy_score" in data
    assert "timeliness_score" in data
    assert "alerts_open" in data
    assert data["overall_score"] >= 0
    assert data["overall_score"] <= 100


@pytest.mark.asyncio
async def test_data_quality_scores(client: AsyncClient, db_session, setup_roles):
    from app.models.user import User

    user = User(id=301, username="dq_viewer", hashed_password="x", role_id=3, is_active=True)
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "301", "role": "viewer"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/data-quality/scores?target_table=sales", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert "target_table" in item
        assert "dimension" in item
        assert "score" in item
        assert item["score"] >= 0
        assert item["score"] <= 100


@pytest.mark.asyncio
async def test_data_quality_alerts_empty(client: AsyncClient, db_session, setup_roles):
    from app.models.user import User

    user = User(id=302, username="dq_mgr", hashed_password="x", role_id=2, is_active=True)
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "302", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/data-quality/alerts?page=1&page_size=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_data_quality_rules_crud(client: AsyncClient, db_session, setup_roles):
    from app.models.user import User

    user = User(id=303, username="dq_rule_admin", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "303", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    rule_data = {
        "rule_name": "销售金额非负检查",
        "target_table": "sales",
        "dimension": "accuracy",
        "check_type": "range_check",
        "column_name": "total_amount",
        "condition": {"min": 0},
        "threshold_warn": 0.05,
        "threshold_error": 0.15,
    }
    response = await client.post("/api/data-quality/rules", json=rule_data, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data

    response = await client.get("/api/data-quality/rules", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_data_quality_permission_isolation(client: AsyncClient, db_session, setup_roles):
    from app.models.user import User, UserStorePermission
    from app.models.store import Store

    store1 = Store(id=10, name="门店A", code="A001", address="地址A", status="active")
    store2 = Store(id=11, name="门店B", code="B001", address="地址B", status="active")
    db_session.add_all([store1, store2])

    user = User(id=304, username="dq_limited", hashed_password="x", role_id=2, is_active=True)
    db_session.add(user)
    await db_session.flush()

    perm = UserStorePermission(user_id=304, store_id=10, can_read=True, can_write=False)
    db_session.add(perm)
    await db_session.commit()

    token = create_access_token({"sub": "304", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/data-quality/health?store_ids=10", headers=headers)
    assert response.status_code == 200

    response = await client.get("/api/data-quality/health?store_ids=11", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_data_quality_check_run_unauthorized(client: AsyncClient, db_session, setup_roles):
    from app.models.user import User

    user = User(id=305, username="dq_viewer2", hashed_password="x", role_id=3, is_active=True)
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "305", "role": "viewer"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/data-quality/run-check", headers=headers)
    assert response.status_code == 403
