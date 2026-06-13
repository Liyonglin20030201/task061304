import os
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from app.schemas.report import ReportRequest, ReportResponse
from app.config import get_settings

settings = get_settings()


async def generate_report(
    db: AsyncSession, request: ReportRequest, user_id: int,
) -> ReportResponse:
    os.makedirs(settings.REPORT_DIR, exist_ok=True)
    report_id = f"{uuid.uuid4().hex[:12]}"

    if request.format == "excel":
        file_name = f"report_{report_id}.xlsx"
    else:
        file_name = f"report_{report_id}.csv"

    file_path = os.path.join(settings.REPORT_DIR, file_name)

    store_filter = ""
    params = {"start": request.start_date, "end": request.end_date}
    if request.store_ids:
        store_filter = "AND s.store_id = ANY(:store_ids)"
        params["store_ids"] = request.store_ids

    if request.report_type == "sales_summary":
        sql = f"""
        SELECT st.code, st.name, s.sale_date,
            COUNT(DISTINCT s.receipt_no) as orders,
            SUM(s.total_amount) as gmv,
            SUM(s.total_amount)/NULLIF(COUNT(DISTINCT s.receipt_no),0) as avg_ticket
        FROM sales s
        JOIN stores st ON st.id = s.store_id
        WHERE s.sale_date BETWEEN :start AND :end {store_filter}
        GROUP BY st.code, st.name, s.sale_date
        ORDER BY s.sale_date, st.code
        """
    elif request.report_type == "inventory_status":
        sql = f"""
        SELECT st.code, st.name, i.item_id, i.item_name, i.category,
            i.quantity, i.unit_cost, i.total_value, i.status
        FROM inventory i
        JOIN stores st ON st.id = i.store_id
        WHERE i.snapshot_date BETWEEN :start AND :end
            {"AND i.store_id = ANY(:store_ids)" if request.store_ids else ""}
        ORDER BY st.code, i.item_id
        """
    else:
        sql = f"""
        SELECT st.code, st.name, s.sale_date, SUM(s.total_amount) as gmv
        FROM sales s
        JOIN stores st ON st.id = s.store_id
        WHERE s.sale_date BETWEEN :start AND :end {store_filter}
        GROUP BY st.code, st.name, s.sale_date
        ORDER BY s.sale_date
        """

    result = await db.execute(text(sql), params)
    rows = result.fetchall()
    columns = result.keys()

    import pandas as pd
    df = pd.DataFrame(rows, columns=columns)

    if request.format == "excel":
        df.to_excel(file_path, index=False, engine="openpyxl")
    else:
        df.to_csv(file_path, index=False, encoding="utf-8-sig")

    return ReportResponse(
        report_id=file_name,
        file_name=file_name,
        file_path=file_path,
        status="completed",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
