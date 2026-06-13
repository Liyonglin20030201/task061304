from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.task_log import ImportTask, TaskLog
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/tasks", tags=["任务日志"])


@router.get("")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ImportTask).where(ImportTask.user_id == user.id)
        .order_by(ImportTask.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id, "file_name": t.file_name, "data_type": t.data_type,
            "status": t.status, "total_rows": t.total_rows,
            "processed_rows": t.processed_rows, "success_rows": t.success_rows,
            "error_rows": t.error_rows, "duplicate_rows": t.duplicate_rows,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task_result = await db.execute(select(ImportTask).where(ImportTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.user_id != user.id:
        return {"error": "任务不存在或无权访问"}

    result = await db.execute(
        select(TaskLog).where(TaskLog.task_id == task_id).order_by(TaskLog.created_at)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id, "level": log.level, "message": log.message,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
