from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Date, Time, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class PortPersonnel(Base):
    __tablename__ = "port_personnel"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    position = Column(String(50), nullable=False)
    skills = Column(JSON, default=list)
    max_continuous_hours = Column(Float, default=8.0)
    min_rest_hours = Column(Float, default=11.0)
    shift_preference = Column(String(20), default="flexible")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class ShiftDefinition(Base):
    __tablename__ = "shift_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_name = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    required_positions = Column(JSON, nullable=False)


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_date = Column(Date, nullable=False)
    shift_id = Column(Integer, nullable=False)
    personnel_id = Column(Integer, nullable=False)
    assignment_type = Column(String(20), default="auto")
    status = Column(String(20), default="planned")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("schedule_date", "shift_id", "personnel_id", name="uq_schedule_date_shift_person"),
        Index("ix_schedules_date", "schedule_date"),
    )


class ScheduleConstraintLog(Base):
    __tablename__ = "schedule_constraints_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_date = Column(Date)
    constraint_type = Column(String(50))
    personnel_id = Column(Integer)
    resolution = Column(String(200))
    created_at = Column(DateTime, server_default=func.now())
