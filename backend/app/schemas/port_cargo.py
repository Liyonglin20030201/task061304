from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ContainerCreate(BaseModel):
    container_code: str
    container_type: str = "20GP"
    weight_tons: Optional[float] = None
    owner: Optional[str] = None
    vessel_name: Optional[str] = None
    voyage_no: Optional[str] = None
    bill_of_lading: Optional[str] = None
    yard_block: Optional[str] = None
    yard_bay: Optional[int] = None
    yard_row: Optional[int] = None
    yard_tier: Optional[int] = None


class ContainerResponse(BaseModel):
    id: int
    container_code: str
    container_type: str
    weight_tons: Optional[float] = None
    owner: Optional[str] = None
    vessel_name: Optional[str] = None
    voyage_no: Optional[str] = None
    bill_of_lading: Optional[str] = None
    status: str
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    yard_block: Optional[str] = None
    yard_bay: Optional[int] = None
    yard_row: Optional[int] = None
    yard_tier: Optional[int] = None
    created_at: Optional[datetime] = None


class ContainerEventCreate(BaseModel):
    event_type: str
    event_time: Optional[datetime] = None
    location: Optional[str] = None
    equipment_id: Optional[int] = None
    operator_id: Optional[int] = None
    details: Optional[dict] = None


class ContainerEventResponse(BaseModel):
    id: int
    container_id: int
    event_type: str
    event_time: datetime
    location: Optional[str] = None
    equipment_id: Optional[int] = None
    operator_id: Optional[int] = None
    details: Optional[dict] = None
    created_at: Optional[datetime] = None


class CargoStatistics(BaseModel):
    total_containers: int
    en_route: int
    stacked: int
    departed: int
    avg_dwell_hours: float
