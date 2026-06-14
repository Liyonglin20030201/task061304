from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# --- Equipment ---

class EquipmentCreate(BaseModel):
    store_id: int
    equipment_code: str
    equipment_type: str
    name: str
    rated_power_kw: float
    brand: Optional[str] = None
    model_no: Optional[str] = None
    installed_date: Optional[date] = None
    zone_id: Optional[int] = None


class EquipmentUpdate(BaseModel):
    equipment_code: Optional[str] = None
    equipment_type: Optional[str] = None
    name: Optional[str] = None
    rated_power_kw: Optional[float] = None
    brand: Optional[str] = None
    model_no: Optional[str] = None
    installed_date: Optional[date] = None
    zone_id: Optional[int] = None
    status: Optional[str] = None


class EquipmentResponse(BaseModel):
    id: int
    store_id: int
    equipment_code: str
    equipment_type: str
    name: str
    rated_power_kw: float
    brand: Optional[str] = None
    model_no: Optional[str] = None
    installed_date: Optional[date] = None
    zone_id: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Dashboard & Analytics ---

class EnergyDashboard(BaseModel):
    total_kwh: float
    total_cost: float
    cost_per_sqm: float
    revenue_per_kwh: float
    period_kwh_change_pct: float
    equipment_count: int
    by_type: List[dict]


class EnergyTrend(BaseModel):
    date: str
    total_kwh: float
    total_cost: float
    equipment_type: Optional[str] = None


class PeakHourData(BaseModel):
    hour: int
    avg_kwh: float
    avg_cost: float


class CorrelationResult(BaseModel):
    correlation_coefficient: float
    p_value: float
    data_points: List[dict]


class ScheduleRecommendation(BaseModel):
    equipment_id: int
    equipment_name: str
    day_of_week: int
    hour: int
    current_level: str
    recommended_level: str
    reason: str
    estimated_saving_kwh: float


# --- Schedules ---

class ScheduleCreate(BaseModel):
    equipment_id: int
    day_of_week: int
    start_hour: int
    end_hour: int
    power_level: str
    effective_date: Optional[date] = None


class ScheduleResponse(BaseModel):
    id: int
    store_id: int
    equipment_id: int
    day_of_week: int
    start_hour: int
    end_hour: int
    power_level: str
    effective_date: Optional[date] = None
    is_active: int

    class Config:
        from_attributes = True


# --- Alerts ---

class AlertResponse(BaseModel):
    id: int
    store_id: int
    equipment_id: Optional[int] = None
    alert_type: str
    alert_level: str
    message: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    alert_time: datetime
    is_acknowledged: int
    acknowledged_by: Optional[int] = None

    class Config:
        from_attributes = True


# --- Budget ---

class BudgetCreate(BaseModel):
    store_id: int
    year_month: str
    budget_kwh: float
    budget_yuan: float
    alert_threshold_pct: Optional[float] = 80


class BudgetResponse(BaseModel):
    id: int
    store_id: int
    year_month: str
    budget_kwh: float
    budget_yuan: float
    alert_threshold_pct: float

    class Config:
        from_attributes = True


# --- Cost Optimization ---

class CostRecommendation(BaseModel):
    category: str
    title: str
    description: str
    potential_saving_yuan: float
    priority: str
