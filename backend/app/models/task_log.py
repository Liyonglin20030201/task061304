from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from datetime import datetime, timezone
from app.database import Base


class ImportTask(Base):
    __tablename__ = "import_tasks"
    __table_args__ = (
        Index("ix_import_tasks_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(200), nullable=False)
    file_size = Column(Integer)
    data_type = Column(String(30), nullable=False)
    status = Column(String(20), default="pending")
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    error_details = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TaskLog(Base):
    __tablename__ = "task_logs"
    __table_args__ = (
        Index("ix_task_logs_task", "task_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("import_tasks.id"), nullable=False)
    level = Column(String(10), default="info")
    message = Column(Text, nullable=False)
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DataQualityLog(Base):
    __tablename__ = "data_quality_logs"
    __table_args__ = (
        Index("ix_dq_logs_store_type", "store_id", "issue_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    data_type = Column(String(30), nullable=False)
    issue_type = Column(String(30), nullable=False)
    description = Column(Text)
    affected_period_start = Column(DateTime(timezone=True))
    affected_period_end = Column(DateTime(timezone=True))
    affected_rows = Column(Integer, default=0)
    severity = Column(String(10), default="warning")
    resolved = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
