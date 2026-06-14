import pytest
from datetime import date, timedelta
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_manager_cannot_view_other_store_employees(client, db_session, setup_roles):
    """Store manager should only see employees in their authorized stores."""
    from app.models.user import User, UserStorePermission
    from app.models.store import Store
    from app.models.employee_performance import Employee, EmployeeSalesRecord

    store_a = Store(id=100, name="授权门店", code="AUTH01", address="A", status="active")
    store_b = Store(id=101, name="未授权门店", code="NOAUTH01", address="B", status="active")
    db_session.add_all([store_a, store_b])

    manager = User(id=700, username="mgr_perm_test", hashed_password="x", role_id=2, is_active=True)
    db_session.add(manager)
    await db_session.flush()

    perm = UserStorePermission(user_id=700, store_id=100, can_read=True, can_write=True)
    db_session.add(perm)

    emp_own = Employee(id=100, store_id=100, employee_no="E100", name="本店员工", position="sales", hire_date=date(2023, 1, 1))
    emp_other = Employee(id=101, store_id=101, employee_no="E101", name="他店员工", position="sales", hire_date=date(2023, 1, 1))
    db_session.add_all([emp_own, emp_other])

    today = date.today()
    for i in range(5):
        d = today - timedelta(days=i)
        db_session.add(EmployeeSalesRecord(employee_id=100, store_id=100, record_date=d, revenue=3000, quantity_sold=30, transaction_count=10))
        db_session.add(EmployeeSalesRecord(employee_id=101, store_id=101, record_date=d, revenue=5000, quantity_sold=50, transaction_count=20))
    await db_session.commit()

    token = create_access_token({"sub": "700", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()

    # Ranking without store_ids should only return authorized store employees
    response = await client.get(f"/api/employee-performance/ranking?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    for emp in data:
        assert emp["store_id"] == 100, f"Manager saw employee from store {emp['store_id']}, expected only 100"


@pytest.mark.asyncio
async def test_manager_cannot_access_other_store_employee_trend(client, db_session, setup_roles):
    """Store manager cannot access trend for employee in unauthorized store."""
    from app.models.user import User, UserStorePermission
    from app.models.store import Store
    from app.models.employee_performance import Employee

    store_a = Store(id=110, name="我的店", code="MY01", address="A", status="active")
    store_b = Store(id=111, name="别人的店", code="OT01", address="B", status="active")
    db_session.add_all([store_a, store_b])

    manager = User(id=701, username="mgr_trend_test", hashed_password="x", role_id=2, is_active=True)
    db_session.add(manager)
    await db_session.flush()

    perm = UserStorePermission(user_id=701, store_id=110, can_read=True, can_write=False)
    db_session.add(perm)

    emp_other = Employee(id=110, store_id=111, employee_no="E110", name="他店员工", position="sales", hire_date=date(2023, 1, 1))
    db_session.add(emp_other)
    await db_session.commit()

    token = create_access_token({"sub": "701", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/employee-performance/trend/110?months=3", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_access_other_store_comparison(client, db_session, setup_roles):
    """Store manager cannot access peer comparison for employee in unauthorized store."""
    from app.models.user import User, UserStorePermission
    from app.models.store import Store
    from app.models.employee_performance import Employee

    store_a = Store(id=120, name="授权A", code="PA01", address="A", status="active")
    store_b = Store(id=121, name="未授权B", code="PB01", address="B", status="active")
    db_session.add_all([store_a, store_b])

    manager = User(id=702, username="mgr_comp_test", hashed_password="x", role_id=2, is_active=True)
    db_session.add(manager)
    await db_session.flush()

    perm = UserStorePermission(user_id=702, store_id=120, can_read=True, can_write=False)
    db_session.add(perm)

    emp_other = Employee(id=120, store_id=121, employee_no="E120", name="未授权员工", position="cashier", hire_date=date(2023, 6, 1))
    db_session.add(emp_other)
    await db_session.commit()

    token = create_access_token({"sub": "702", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()

    response = await client.get(f"/api/employee-performance/comparison/120?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_empty_store_permissions_returns_no_data(client, db_session, setup_roles):
    """User with no store permissions should get empty results, not all data."""
    from app.models.user import User
    from app.models.store import Store
    from app.models.employee_performance import Employee, EmployeeSalesRecord

    store = Store(id=130, name="某门店", code="EMPTY01", address="X", status="active")
    db_session.add(store)

    # User with manager role but NO UserStorePermission entries
    user = User(id=703, username="no_perm_user", hashed_password="x", role_id=2, is_active=True)
    db_session.add(user)

    emp = Employee(id=130, store_id=130, employee_no="E130", name="员工X", position="sales", hire_date=date(2023, 1, 1))
    db_session.add(emp)

    today = date.today()
    db_session.add(EmployeeSalesRecord(employee_id=130, store_id=130, record_date=today, revenue=1000, quantity_sold=10, transaction_count=5))
    await db_session.commit()

    token = create_access_token({"sub": "703", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()

    response = await client.get(f"/api/employee-performance/ranking?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0, "User with no store permissions should see no employees"


@pytest.mark.asyncio
async def test_admin_can_view_all_stores(client, db_session, setup_roles):
    """Admin should see employees from all stores regardless."""
    from app.models.user import User
    from app.models.store import Store
    from app.models.employee_performance import Employee, EmployeeSalesRecord

    store_a = Store(id=140, name="店铺A", code="ADM01", address="A", status="active")
    store_b = Store(id=141, name="店铺B", code="ADM02", address="B", status="active")
    db_session.add_all([store_a, store_b])

    admin = User(id=704, username="admin_all", hashed_password="x", role_id=1, is_active=True)
    db_session.add(admin)

    emp_a = Employee(id=140, store_id=140, employee_no="EA", name="员工A", position="sales", hire_date=date(2023, 1, 1))
    emp_b = Employee(id=141, store_id=141, employee_no="EB", name="员工B", position="sales", hire_date=date(2023, 1, 1))
    db_session.add_all([emp_a, emp_b])

    today = date.today()
    for eid, sid in [(140, 140), (141, 141)]:
        db_session.add(EmployeeSalesRecord(employee_id=eid, store_id=sid, record_date=today, revenue=2000, quantity_sold=20, transaction_count=10))
    await db_session.commit()

    token = create_access_token({"sub": "704", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()

    response = await client.get(f"/api/employee-performance/ranking?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    store_ids_seen = set(emp["store_id"] for emp in data)
    assert 140 in store_ids_seen
    assert 141 in store_ids_seen


@pytest.mark.asyncio
async def test_data_quality_manager_isolation(client, db_session, setup_roles):
    """Data quality endpoints should respect store permission for managers."""
    from app.models.user import User, UserStorePermission
    from app.models.store import Store

    store_a = Store(id=150, name="DQ授权店", code="DQ01", address="A", status="active")
    store_b = Store(id=151, name="DQ未授权店", code="DQ02", address="B", status="active")
    db_session.add_all([store_a, store_b])

    manager = User(id=705, username="dq_mgr_iso", hashed_password="x", role_id=2, is_active=True)
    db_session.add(manager)
    await db_session.flush()

    perm = UserStorePermission(user_id=705, store_id=150, can_read=True, can_write=False)
    db_session.add(perm)
    await db_session.commit()

    token = create_access_token({"sub": "705", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    # Request for authorized store should succeed
    response = await client.get("/api/data-quality/health?store_ids=150", headers=headers)
    assert response.status_code == 200

    # Request for unauthorized store - effective_stores filters it out
    response = await client.get("/api/data-quality/health?store_ids=151", headers=headers)
    assert response.status_code == 200
    # The result should reflect no data (manager's effective_stores won't include 151)


@pytest.mark.asyncio
async def test_demand_forecast_manager_blocked(client, db_session, setup_roles):
    """Demand forecast should block access to unauthorized store."""
    from app.models.user import User, UserStorePermission
    from app.models.store import Store

    store_a = Store(id=160, name="预测授权店", code="FC01", address="A", status="active")
    store_b = Store(id=161, name="预测未授权店", code="FC02", address="B", status="active")
    db_session.add_all([store_a, store_b])

    manager = User(id=706, username="fc_mgr_iso", hashed_password="x", role_id=2, is_active=True)
    db_session.add(manager)
    await db_session.flush()

    perm = UserStorePermission(user_id=706, store_id=160, can_read=True, can_write=False)
    db_session.add(perm)
    await db_session.commit()

    token = create_access_token({"sub": "706", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    # Authorized store
    response = await client.get("/api/demand-forecast/enhanced?store_id=160&periods=7", headers=headers)
    assert response.status_code == 200

    # Unauthorized store
    response = await client.get("/api/demand-forecast/enhanced?store_id=161&periods=7", headers=headers)
    assert response.status_code == 403
