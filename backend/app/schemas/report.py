from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class ReportRequest(BaseModel):
    report_type: str
    store_ids: Optional[List[int]] = None
    start_date: date
    end_date: date
    format: str = "excel"
    metrics: Optional[List[str]] = None


class ReportResponse(BaseModel):
    report_id: str
    file_name: str
    file_path: str
    status: str
    created_at: str
