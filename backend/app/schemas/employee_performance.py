from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class EmployeeCreate(BaseModel):
    store_id: int
    employee_no: str
    name: str
    position: Optional[str] = None
    hire_date: date


class EmployeeResponse(BaseModel):
    id: int
    store_id: int
    employee_no: str
    name: str
    position: Optional[str]
    hire_date: date
    is_active: int

    class Config:
        from_attributes = True


class PerformanceScoreResponse(BaseModel):
    employee_id: int
    employee_name: str
    position: Optional[str]
    store_id: int
    composite_score: float
    sales_score: float
    service_score: float
    attendance_score: float
    training_score: float
    rank_in_store: int
    trend: str


class PerformanceDashboardResponse(BaseModel):
    avg_score: float
    top_performer: Optional[str]
    top_score: float
    improvement_rate: float
    avg_attendance_rate: float
    total_employees: int


class PeerComparisonResponse(BaseModel):
    employee_name: str
    dimensions: List[str]
    employee_scores: List[float]
    store_avg_scores: List[float]
    chain_avg_scores: List[float]


class WeightConfigUpdate(BaseModel):
    store_id: int
    position: str = "default"
    weight_sales: float = Field(default=0.40, ge=0, le=1)
    weight_service: float = Field(default=0.25, ge=0, le=1)
    weight_attendance: float = Field(default=0.20, ge=0, le=1)
    weight_training: float = Field(default=0.15, ge=0, le=1)


class WeightConfigResponse(BaseModel):
    store_id: int
    position: str
    weight_sales: float
    weight_service: float
    weight_attendance: float
    weight_training: float

    class Config:
        from_attributes = True
