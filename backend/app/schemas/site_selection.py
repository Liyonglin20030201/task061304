from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class CandidateCreate(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    area_sqm: Optional[float] = None
    monthly_rent: Optional[float] = None


class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    area_sqm: Optional[float] = None
    monthly_rent: Optional[float] = None
    status: Optional[str] = None


class CandidateResponse(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    area_sqm: Optional[float] = None
    monthly_rent: Optional[float] = None
    status: str
    submitted_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LocationFactorResponse(BaseModel):
    id: int
    location_id: int
    factor_type: str
    factor_name: str
    raw_value: Optional[float] = None
    normalized_score: Optional[float] = None
    data_source: Optional[str] = None

    class Config:
        from_attributes = True


class EvaluationResponse(BaseModel):
    id: int
    location_id: int
    location_name: Optional[str] = None
    total_score: float
    traffic_score: float
    competition_score: float
    demographic_score: float
    transport_score: float
    commercial_score: float
    predicted_monthly_revenue: Optional[float] = None
    predicted_payback_months: Optional[float] = None
    confidence_level: Optional[float] = None
    evaluated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WeightProfileCreate(BaseModel):
    name: str
    traffic_weight: float = 0.25
    competition_weight: float = 0.20
    demographic_weight: float = 0.20
    transport_weight: float = 0.15
    commercial_weight: float = 0.20
    is_default: int = 0


class WeightProfileResponse(BaseModel):
    id: int
    name: str
    version: int = 1
    traffic_weight: float
    competition_weight: float
    demographic_weight: float
    transport_weight: float
    commercial_weight: float
    is_default: int

    class Config:
        from_attributes = True


class CompetitorCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    estimated_revenue: Optional[float] = None
    data_source: Optional[str] = None


class CompetitorResponse(BaseModel):
    id: int
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    estimated_revenue: Optional[float] = None
    data_source: Optional[str] = None
    imported_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompareRequest(BaseModel):
    location_ids: List[int]


class BenchmarkResponse(BaseModel):
    avg_monthly_revenue: float
    avg_sqm_efficiency: float
    avg_traffic: float
    top_store_revenue: float
    store_count: int
