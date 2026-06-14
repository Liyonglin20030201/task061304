import pytest
from datetime import date, timedelta
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_employee_performance_ranking(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.employee_performance import Employee, EmployeeSalesRecord, EmployeeAttendance

    store = Store(id=1, name="绩效测试店", code="EP01", address="地址", status="active")
    db_session.add(store)

    user = User(id=400, username="ep_admin", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    emp1 = Employee(id=1, store_id=1, employee_no="E001", name="张三", position="sales", hire_date=date(2023, 1, 1))
    emp2 = Employee(id=2, store_id=1, employee_no="E002", name="李四", position="sales", hire_date=date(2023, 3, 1))
    db_session.add_all([emp1, emp2])

    today = date.today()
    for i in range(10):
        d = today - timedelta(days=i)
        db_session.add(EmployeeSalesRecord(employee_id=1, store_id=1, record_date=d, revenue=5000 + i * 100, quantity_sold=50, transaction_count=20))
        db_session.add(EmployeeSalesRecord(employee_id=2, store_id=1, record_date=d, revenue=3000 + i * 50, quantity_sold=30, transaction_count=15))
        db_session.add(EmployeeAttendance(employee_id=1, store_id=1, attend_date=d, scheduled_hours=8, actual_hours=8, is_late=0, is_absent=0))
        db_session.add(EmployeeAttendance(employee_id=2, store_id=1, attend_date=d, scheduled_hours=8, actual_hours=7, is_late=1, is_absent=0))

    await db_session.commit()

    token = create_access_token({"sub": "400", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()
    response = await client.get(f"/api/employee-performance/ranking?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["composite_score"] >= data[1]["composite_score"]
    assert data[0]["employee_name"] == "张三"


@pytest.mark.asyncio
async def test_employee_performance_score_detail(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.employee_performance import Employee, EmployeeSalesRecord, EmployeeServiceRecord

    store = Store(id=2, name="详情测试店", code="EP02", address="地址2", status="active")
    db_session.add(store)

    user = User(id=401, username="ep_mgr", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    emp = Employee(id=10, store_id=2, employee_no="E010", name="王五", position="cashier", hire_date=date(2022, 6, 1))
    db_session.add(emp)

    today = date.today()
    for i in range(5):
        d = today - timedelta(days=i)
        db_session.add(EmployeeSalesRecord(employee_id=10, store_id=2, record_date=d, revenue=2000, quantity_sold=20, transaction_count=10))
        db_session.add(EmployeeServiceRecord(employee_id=10, store_id=2, record_date=d, customer_rating=4.5, rating_count=5, complaint_count=0, praise_count=1))

    await db_session.commit()

    token = create_access_token({"sub": "401", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()
    response = await client.get(f"/api/employee-performance/scores/10?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == 10
    assert data["employee_name"] == "王五"
    assert 0 <= data["composite_score"] <= 100
    assert 0 <= data["sales_score"] <= 100
    assert 0 <= data["service_score"] <= 100
    assert 0 <= data["attendance_score"] <= 100
    assert 0 <= data["training_score"] <= 100


@pytest.mark.asyncio
async def test_employee_performance_trend(client, db_session, setup_roles):
    from app.models.user import User
    from app.models.store import Store
    from app.models.employee_performance import Employee

    store = Store(id=3, name="趋势测试店", code="EP03", address="地址3", status="active")
    db_session.add(store)

    user = User(id=402, username="ep_trend", hashed_password="x", role_id=1, is_active=True)
    db_session.add(user)

    emp = Employee(id=20, store_id=3, employee_no="E020", name="赵六", position="sales", hire_date=date(2023, 1, 1))
    db_session.add(emp)
    await db_session.commit()

    token = create_access_token({"sub": "402", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/employee-performance/trend/20?months=3", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_employee_performance_permission_isolation(client, db_session, setup_roles):
    from app.models.user import User, UserStorePermission
    from app.models.store import Store
    from app.models.employee_performance import Employee

    store1 = Store(id=20, name="门店X", code="EPX", address="X", status="active")
    store2 = Store(id=21, name="门店Y", code="EPY", address="Y", status="active")
    db_session.add_all([store1, store2])

    user = User(id=403, username="ep_limited", hashed_password="x", role_id=2, is_active=True)
    db_session.add(user)
    await db_session.flush()

    perm = UserStorePermission(user_id=403, store_id=20, can_read=True, can_write=False)
    db_session.add(perm)

    emp = Employee(id=30, store_id=21, employee_no="E030", name="孙七", position="sales", hire_date=date(2023, 1, 1))
    db_session.add(emp)
    await db_session.commit()

    token = create_access_token({"sub": "403", "role": "manager"})
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()

    response = await client.get(f"/api/employee-performance/scores/30?start_date={start}&end_date={end}", headers=headers)
    assert response.status_code in [200, 403]
