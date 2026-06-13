from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import asyncio
import json
import os
from app.database import get_db
from app.models.task_log import ImportTask, TaskLog
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user
from app.models.user import User
from app.config import get_settings
from app.services.import_service import process_import_file, import_progress

settings = get_settings()
router = APIRouter(prefix="/imports", tags=["数据导入"])

STREAM_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming to disk


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    data_type: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{user.id}_{file.filename}")

    file_size = 0
    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > settings.MAX_UPLOAD_SIZE:
                f.close()
                os.unlink(file_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件超过最大限制 {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB",
                )
            f.write(chunk)

    task = ImportTask(
        user_id=user.id,
        file_name=file.filename,
        file_size=file_size,
        data_type=data_type,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    asyncio.create_task(process_import_file(task.id, file_path, data_type))

    return {"task_id": task.id, "status": "pending", "message": "文件已上传，正在后台分批处理"}


@router.get("/{task_id}/progress")
async def stream_import_progress(
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

    async def event_generator():
        while True:
            progress = import_progress.get(task_id)
            if progress:
                yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                if progress.get("status") in ("completed", "failed"):
                    import_progress.pop(task_id, None)
                    break
            else:
                fresh = await db.execute(select(ImportTask).where(ImportTask.id == task_id))
                t = fresh.scalar_one_or_none()
                if t and t.status in ("completed", "failed"):
                    yield f"data: {json.dumps({'status': t.status, 'progress': 100.0}, ensure_ascii=False)}\n\n"
                    break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
