import pytest
import os
import tempfile
import pandas as pd


@pytest.mark.asyncio
async def test_upload_csv_creates_task(client, db_session, setup_roles):
    from app.models.user import User
    from app.core.security import get_password_hash, create_access_token

    user = User(
        id=200, username="importer", email="importer@test.com",
        hashed_password=get_password_hash("Test123"), role_id=1,
    )
    db_session.add(user)
    await db_session.commit()

    df = pd.DataFrame({
        "store_id": [1, 1],
        "sale_date": ["2024-01-01", "2024-01-02"],
        "receipt_no": ["R001", "R002"],
        "item_id": ["A001", "A002"],
        "quantity": [2, 3],
        "unit_price": [10.0, 20.0],
        "total_amount": [20.0, 60.0],
    })

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as f:
        df.to_csv(f, index=False)
        tmp_path = f.name

    try:
        token = create_access_token({"sub": "200", "role": "admin"})
        with open(tmp_path, "rb") as f:
            response = await client.post(
                "/api/imports/upload",
                files={"file": ("test_sales.csv", f, "text/csv")},
                data={"data_type": "sales"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
    finally:
        os.unlink(tmp_path)
