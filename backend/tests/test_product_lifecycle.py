import pytest
from datetime import date, timedelta
from app.core.security import create_access_token
from app.services.product_lifecycle_service import _detect_stage


def test_detect_stage_introduction_short_history():
    result = _detect_stage(growth_rates=[0.1, 0.2], weeks_since_launch=4, adoption_rate=0.3, velocity=1.0, category_median_velocity=5.0)
    assert result == "introduction"


def test_detect_stage_introduction_low_adoption():
    result = _detect_stage(growth_rates=[0.1, 0.15, 0.12, 0.08], weeks_since_launch=6, adoption_rate=0.3, velocity=2.0, category_median_velocity=5.0)
    assert result == "introduction"


def test_detect_stage_growth():
    result = _detect_stage(growth_rates=[0.1, 0.08, 0.12, 0.15], weeks_since_launch=12, adoption_rate=0.7, velocity=5.0, category_median_velocity=5.0)
    assert result == "growth"


def test_detect_stage_maturity():
    result = _detect_stage(growth_rates=[0.02, -0.01, 0.03, -0.02], weeks_since_launch=30, adoption_rate=0.9, velocity=4.5, category_median_velocity=5.0)
    assert result == "maturity"


def test_detect_stage_decline_negative_growth():
    result = _detect_stage(growth_rates=[-0.1, -0.08, -0.12, -0.15], weeks_since_launch=40, adoption_rate=0.8, velocity=1.0, category_median_velocity=5.0)
    assert result == "decline"


def test_detect_stage_decline_low_velocity():
    # Low velocity combined with extended age triggers decline via volatility-based floor
    result = _detect_stage(growth_rates=[0.01, -0.02, 0.01, -0.03, -0.04, -0.02, -0.06, -0.08], weeks_since_launch=30, adoption_rate=0.5, velocity=0.5, category_median_velocity=5.0)
    assert result == "decline"


@pytest.mark.asyncio
async def test_product_lifecycle_overview(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.product_lifecycle import Product, ProductLifecycleSnapshot

    store = Store(id=1, name="生命周期测试店", code="PL01", address="地址", status="active")
    db_session.add(store)

    user = User(id=500, username="pl_admin", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    prod1 = Product(id=1, item_id="P001", item_name="测试商品A", category="食品", launch_date=date(2024, 1, 1))
    prod2 = Product(id=2, item_id="P002", item_name="测试商品B", category="饮料", launch_date=date(2023, 6, 1))
    db_session.add_all([prod1, prod2])

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    db_session.add(ProductLifecycleSnapshot(product_id=1, store_id=1, snapshot_week=monday, stage="growth", weekly_revenue=5000, weekly_quantity=100, growth_rate=0.12))
    db_session.add(ProductLifecycleSnapshot(product_id=2, store_id=1, snapshot_week=monday, stage="decline", weekly_revenue=1000, weekly_quantity=20, growth_rate=-0.1))
    await db_session.commit()

    token = create_access_token({"sub": "500", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/product-lifecycle/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["growth_count"] >= 1
    assert data["decline_count"] >= 1
    assert data["total_products"] >= 2


@pytest.mark.asyncio
async def test_product_lifecycle_curve(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.product_lifecycle import Product, ProductLifecycleSnapshot

    store = Store(id=2, name="曲线测试店", code="PL02", address="地址2", status="active")
    db_session.add(store)

    user = User(id=501, username="pl_viewer", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    prod = Product(id=10, item_id="P010", item_name="曲线商品", category="日用品", launch_date=date(2024, 1, 1))
    db_session.add(prod)

    today = date.today()
    for i in range(8):
        week = today - timedelta(weeks=i)
        db_session.add(ProductLifecycleSnapshot(
            product_id=10, store_id=2, snapshot_week=week,
            stage="growth" if i > 4 else "maturity",
            weekly_revenue=3000 + i * 200, weekly_quantity=50 + i * 5, growth_rate=0.05,
        ))
    await db_session.commit()

    token = create_access_token({"sub": "501", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/product-lifecycle/curve/10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 10
    assert data["item_name"] == "曲线商品"
    assert len(data["weeks"]) == 8
    assert len(data["revenues"]) == 8


@pytest.mark.asyncio
async def test_product_lifecycle_retirement_recommendations(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.product_lifecycle import Product, ProductRetirementRecommendation

    store = Store(id=3, name="淘汰测试店", code="PL03", address="地址3", status="active")
    db_session.add(store)

    user = User(id=502, username="pl_rec", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    prod = Product(id=20, item_id="P020", item_name="衰退商品", category="食品", launch_date=date(2022, 1, 1))
    db_session.add(prod)

    db_session.add(ProductRetirementRecommendation(
        product_id=20, store_id=3, recommendation="phase_out",
        confidence=0.9, reason="利润率为负", impact_revenue_loss=500,
        remaining_inventory=200, suggested_action_date=date.today() + timedelta(days=14),
    ))
    await db_session.commit()

    token = create_access_token({"sub": "502", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/product-lifecycle/retirement-recommendations", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["recommendation"] == "phase_out"
    assert data[0]["confidence"] == 0.9
