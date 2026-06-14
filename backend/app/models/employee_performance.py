from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, UniqueConstraint, Index,
)
from app.database import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("store_id", "employee_no", name="uq_emp_store_no"),
        Index("ix_emp_store", "store_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    employee_no = Column(String(30), nullable=False)
    name = Column(String(50), nullable=False)
    position = Column(String(30))
    hire_date = Column(Date, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EmployeeSalesRecord(Base):
    __tablename__ = "employee_sales_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "record_date", name="uq_emp_sales_day"),
        Index("ix_empsales_emp_date", "employee_id", "record_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    record_date = Column(Date, nullable=False)
    revenue = Column(Float, default=0)
    quantity_sold = Column(Integer, default=0)
    transaction_count = Column(Integer, default=0)
    avg_ticket = Column(Float, default=0)
    conversion_rate = Column(Float)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EmployeeServiceRecord(Base):
    __tablename__ = "employee_service_records"
    __table_args__ = (
        Index("ix_empservice_emp_date", "employee_id", "record_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    record_date = Column(Date, nullable=False)
    customer_rating = Column(Float)
    rating_count = Column(Integer, default=0)
    complaint_count = Column(Integer, default=0)
    praise_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EmployeeAttendance(Base):
    __tablename__ = "employee_attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "attend_date", name="uq_emp_attend_day"),
        Index("ix_empattend_emp_date", "employee_id", "attend_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    attend_date = Column(Date, nullable=False)
    scheduled_hours = Column(Float, default=8.0)
    actual_hours = Column(Float, default=0)
    is_late = Column(Integer, default=0)
    is_absent = Column(Integer, default=0)
    overtime_hours = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EmployeeTraining(Base):
    __tablename__ = "employee_training"
    __table_args__ = (
        Index("ix_emptrain_emp", "employee_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    course_name = Column(String(100), nullable=False)
    course_category = Column(String(30))
    scheduled_date = Column(Date, nullable=False)
    completed = Column(Integer, default=0)
    score = Column(Float)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PerformanceWeightConfig(Base):
    __tablename__ = "performance_weight_configs"
    __table_args__ = (
        UniqueConstraint("store_id", "position", name="uq_perf_weight_store_pos"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    position = Column(String(30), default="default")
    weight_sales = Column(Float, default=0.40)
    weight_service = Column(Float, default=0.25)
    weight_attendance = Column(Float, default=0.20)
    weight_training = Column(Float, default=0.15)
    updated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
