from pydantic import BaseModel
from datetime import date, time, datetime
from typing import Optional


class PersonnelCreate(BaseModel):
    employee_code: str
    name: str
    position: str
    skills: list = []
    max_continuous_hours: float = 8.0
    min_rest_hours: float = 11.0
    shift_preference: str = "flexible"


class PersonnelResponse(BaseModel):
    id: int
    employee_code: str
    name: str
    position: str
    skills: list = []
    max_continuous_hours: float
    min_rest_hours: float
    shift_preference: str
    is_active: bool
    created_at: Optional[datetime] = None


class ShiftCreate(BaseModel):
    shift_name: str
    start_time: time
    end_time: time
    required_positions: dict


class ShiftResponse(BaseModel):
    id: int
    shift_name: str
    start_time: time
    end_time: time
    required_positions: dict


class ScheduleRequest(BaseModel):
    start_date: date
    end_date: date


class ScheduleResponse(BaseModel):
    id: int
    schedule_date: date
    shift_id: int
    personnel_id: int
    assignment_type: str
    status: str
    shift_name: Optional[str] = None
    personnel_name: Optional[str] = None
    position: Optional[str] = None


class ConstraintViolation(BaseModel):
    schedule_date: date
    constraint_type: str
    personnel_id: int
    personnel_name: Optional[str] = None
    resolution: Optional[str] = None
