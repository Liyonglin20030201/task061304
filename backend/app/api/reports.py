from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Optional
import os
from app.database import get_db
from app.api.deps import get_auth_context, AuthContext
from app.schemas.report import ReportRequest, ReportResponse
from app.services.report_service import generate_report
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/reports", tags=["报表导出"])


@router.post("/export", response_model=ReportResponse)
async def export_report(
    request: ReportRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    request.store_ids = auth.get_effective_stores(request.store_ids)
    return await generate_report(db, request, auth.user.id)


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    file_path = os.path.join(settings.REPORT_DIR, report_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="报表文件不存在")
    return FileResponse(file_path, filename=os.path.basename(file_path))
