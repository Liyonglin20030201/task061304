from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import asyncio
import os
from app.database import get_db
from app.models.task_log import ImportTask, TaskLog
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user
from app.models.user import User
from app.config import get_settings
from app.services.import_service import process_import_file

settings = get_settings()
router = APIRouter(prefix="/imports", tags=["数据导入"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    data_type: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{user.id}_{file.filename}")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    task = ImportTask(
        user_id=user.id,
        file_name=file.filename,
        file_size=len(content),
        data_type=data_type,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    asyncio.create_task(process_import_file(task.id, file_path, data_type))

    return {"task_id": task.id, "status": "pending", "message": "文件已上传，正在处理"}


@router.get("/{task_id}/status")
async def get_import_status(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ImportTask).where(ImportTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if task.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看")
    return {
        "task_id": task.id,
        "status": task.status,
        "total_rows": task.total_rows,
        "processed_rows": task.processed_rows,
        "success_rows": task.success_rows,
        "error_rows": task.error_rows,
        "duplicate_rows": task.duplicate_rows,
        "progress": round(task.processed_rows / max(task.total_rows, 1) * 100, 1),
    }


@router.get("/history")
async def import_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ImportTask).where(ImportTask.user_id == user.id)
        .order_by(ImportTask.created_at.desc()).limit(50)
    )
    tasks = result.scalars().all()
    return [
        {
            "task_id": t.id, "file_name": t.file_name, "data_type": t.data_type,
            "status": t.status, "total_rows": t.total_rows,
            "success_rows": t.success_rows, "error_rows": t.error_rows,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]
