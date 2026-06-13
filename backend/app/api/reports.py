from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Optional
import os
from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.schemas.report import ReportRequest, ReportResponse
from app.services.report_service import generate_report
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/reports", tags=["报表导出"])


@router.post("/export", response_model=ReportResponse)
async def export_report(
    request: ReportRequest,
    user_stores: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    user, authorized_stores, role_name = user_stores
    if authorized_stores is not None and request.store_ids:
        request.store_ids = [s for s in request.store_ids if s in authorized_stores]
    elif authorized_stores is not None:
        request.store_ids = authorized_stores
    return await generate_report(db, request, user.id)


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    file_path = os.path.join(settings.REPORT_DIR, report_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="报表文件不存在")
    return FileResponse(file_path, filename=os.path.basename(file_path))
