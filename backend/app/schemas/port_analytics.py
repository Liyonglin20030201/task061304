from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MetricSummary(BaseModel):
    metric_time: datetime
    total_containers: int
    throughput_teu: int
    avg_crane_utilization: float
    avg_agv_utilization: float
    total_energy_kwh: float
    personnel_on_duty: int


class DashboardMetrics(BaseModel):
    current_containers: int
    today_throughput: int
    avg_crane_util: float
    avg_agv_util: float
    today_energy_kwh: float
    energy_cost: float
    personnel_on_duty: int
    equipment_active: int


class UtilizationData(BaseModel):
    equipment_code: str
    equipment_name: str
    utilization_percent: float
    operating_hours: float
    idle_hours: float


class ThroughputTrend(BaseModel):
    time_bucket: str
    teu_count: int
    container_count: int
