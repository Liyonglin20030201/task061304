import pytest
from datetime import date, timedelta
from app.core.security import create_access_token
from app.services.demand_forecast_service import _compute_external_factor


def test_external_factor_no_signals():
    factor = _compute_external_factor([], date.today())
    assert factor == 1.0


def test_external_factor_competitor_price_high():
    today = date.today()
    signals = [{"signal_type": "competitor_price", "signal_date": today, "value": 1.2, "confidence": 1.0}]
    factor = _compute_external_factor(signals, today)
    assert factor > 1.0
    assert factor <= 1.1


def test_external_factor_competitor_price_low():
    today = date.today()
    signals = [{"signal_type": "competitor_price", "signal_date": today, "value": 0.8, "confidence": 1.0}]
    factor = _compute_external_factor(signals, today)
    assert factor < 1.0
    assert factor >= 0.9


def test_external_factor_sentiment_positive():
    today = date.today()
    signals = [{"signal_type": "sentiment", "signal_date": today, "value": 0.8, "confidence": 1.0}]
    factor = _compute_external_factor(signals, today)
    assert factor > 1.0
    assert factor < 1.1


def test_external_factor_sentiment_negative():
    today = date.today()
    signals = [{"signal_type": "sentiment", "signal_date": today, "value": -0.5, "confidence": 1.0}]
    factor = _compute_external_factor(signals, today)
    assert factor < 1.0


def test_external_factor_market_trend():
    today = date.today()
    signals = [{"signal_type": "market_trend", "signal_date": today, "value": 1.2, "confidence": 1.0}]
    factor = _compute_external_factor(signals, today)
    assert factor > 1.0


def test_external_factor_low_confidence():
    today = date.today()
    signals = [{"signal_type": "competitor_price", "signal_date": today, "value": 1.5, "confidence": 0.0}]
    factor = _compute_external_factor(signals, today)
    assert factor == 1.0


def test_external_factor_combined_signals():
    today = date.today()
    signals = [
        {"signal_type": "competitor_price", "signal_date": today, "value": 1.15, "confidence": 1.0},
        {"signal_type": "sentiment", "signal_date": today, "value": 0.5, "confidence": 0.8},
        {"signal_type": "market_trend", "signal_date": today, "value": 1.1, "confidence": 1.0},
    ]
    factor = _compute_external_factor(signals, today)
    assert factor > 1.0
    assert factor <= 1.5


@pytest.mark.asyncio
async def test_demand_forecast_enhanced(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.sales import Sale

    store = Store(id=1, name="预测测试店", code="DF01", address="地址", status="active")
    db_session.add(store)

    user = User(id=600, username="df_admin", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    today = date.today()
    for i in range(60):
        d = today - timedelta(days=i)
        db_session.add(Sale(
            store_id=1, sale_date=d, item_id=f"I{i%5}",
            item_name=f"商品{i%5}", category="食品",
            quantity=10 + i % 3, unit_price=50.0,
            total_amount=500.0 + (i % 3) * 50,
            receipt_no=f"R{i:04d}",
        ))
    await db_session.commit()

    token = create_access_token({"sub": "600", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/demand-forecast/enhanced?store_id=1&periods=14", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "forecast" in data
    assert len(data["forecast"]) == 14
    for fc in data["forecast"]:
        assert "date" in fc
        assert "forecast" in fc
        assert fc["forecast"] >= 0
        assert fc["lower"] <= fc["forecast"] <= fc["upper"]


@pytest.mark.asyncio
async def test_demand_forecast_comparison(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.sales import Sale

    store = Store(id=2, name="对比测试店", code="DF02", address="地址2", status="active")
    db_session.add(store)

    user = User(id=601, username="df_comp", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    today = date.today()
    for i in range(30):
        d = today - timedelta(days=i)
        db_session.add(Sale(store_id=2, sale_date=d, item_id="I1", item_name="商品1", category="饮料", quantity=5, unit_price=20.0, total_amount=100.0, receipt_no=f"C{i:04d}"))
    await db_session.commit()

    token = create_access_token({"sub": "601", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/demand-forecast/comparison?store_id=2&periods=7", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "baseline" in data
    assert "enhanced" in data
    assert len(data["baseline"]) == 7
    assert len(data["enhanced"]) == 7


@pytest.mark.asyncio
async def test_demand_forecast_signals_crud(client, db_session, setup_roles):
    from app.models.user import User

    user = User(id=602, username="df_signal", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": "602", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    signal = {
        "signal_type": "competitor_price",
        "signal_date": str(date.today()),
        "region": "华东",
        "category": "食品",
        "value": 1.15,
        "source": "test",
        "confidence": 0.9,
    }
    response = await client.post("/api/demand-forecast/signals", json=signal, headers=headers)
    assert response.status_code == 200
    assert "id" in response.json()

    response = await client.get("/api/demand-forecast/signals?signal_type=competitor_price", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_demand_forecast_permission_isolation(client, db_session, setup_roles):
    from app.models.user import User, UserStorePermission
    from app.models.store import Store

    store1 = Store(id=10, name="授权店", code="DFA", address="A", status="active")
    store2 = Store(id=11, name="未授权店", code="DFB", address="B", status="active")
    db_session.add_all([store1, store2])

    user = User(id=603, username="df_limited", hashed_password="x", role_id=2, is_active=True)
    db_session.add(user)
    await db_session.flush()

    perm = UserStorePermission(user_id=603, store_id=10, can_read=True, can_write=False)
    db_session.add(perm)
    await db_session.commit()

    token = create_access_token({"sub": "603", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/demand-forecast/enhanced?store_id=10&periods=7", headers=headers)
    assert response.status_code == 200

    response = await client.get("/api/demand-forecast/enhanced?store_id=11&periods=7", headers=headers)
    assert response.status_code == 403
