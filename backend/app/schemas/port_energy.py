from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EquipmentResponse(BaseModel):
    id: int
    equipment_code: str
    equipment_type: str
    name: str
    max_power_kw: float
    location_x: float
    location_y: float
    location_z: float
    status: str
    created_at: Optional[datetime] = None


class EnergyReadingResponse(BaseModel):
    id: int
    equipment_id: int
    timestamp: datetime
    power_kw: float
    energy_kwh: float
    voltage: Optional[float] = None
    current_amps: Optional[float] = None
    operational_state: Optional[str] = None


class EnergySummary(BaseModel):
    equipment_id: int
    equipment_code: str
    equipment_name: str
    total_energy_kwh: float
    avg_power_kw: float
    max_power_kw: float
    operating_hours: float
    cost: float


class CostAnalysis(BaseModel):
    period_name: str
    total_kwh: float
    rate_per_kwh: float
    total_cost: float
    percentage: float


class PeakRecord(BaseModel):
    equipment_id: int
    equipment_code: str
    peak_power_kw: float
    peak_time: datetime
    operational_state: Optional[str] = None


class RealTimeReading(BaseModel):
    equipment_id: int
    equipment_code: str
    power_kw: float
    energy_kwh: float
    voltage: float
    current_amps: float
    operational_state: str
    timestamp: str
