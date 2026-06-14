from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class ExternalSignalCreate(BaseModel):
    signal_type: str
    signal_date: date
    region: Optional[str] = None
    category: Optional[str] = None
    value: float
    raw_value: Optional[str] = None
    source: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1)


class ExternalSignalResponse(BaseModel):
    id: int
    signal_type: str
    signal_date: date
    region: Optional[str]
    category: Optional[str]
    value: float
    source: Optional[str]
    confidence: float

    class Config:
        from_attributes = True


class ForecastComparisonResponse(BaseModel):
    store_id: int
    baseline: List[dict]
    enhanced: List[dict]
    improvement_mape: Optional[float]
    external_signals_used: List[str]


class AccuracyLogResponse(BaseModel):
    model_name: str
    evaluation_date: date
    mape: Optional[float]
    rmse: Optional[float]
    mae: Optional[float]
    bias: Optional[float]

    class Config:
        from_attributes = True


class ABExperimentCreate(BaseModel):
    store_id: int
    experiment_name: str
    model_a: str = "baseline"
    model_b: str = "enhanced"
    start_date: date
    end_date: Optional[date] = None


class ABExperimentResponse(BaseModel):
    id: int
    store_id: int
    experiment_name: str
    model_a: str
    model_b: str
    start_date: date
    end_date: Optional[date]
    status: str
    winner: Optional[str]
    mape_a: Optional[float]
    mape_b: Optional[float]
    conclusion: Optional[str]

    class Config:
        from_attributes = True


class ModelConfigUpdate(BaseModel):
    store_id: int
    model_name: str = "ensemble"
    weight_internal: float = Field(default=0.7, ge=0, le=1)
    weight_external: float = Field(default=0.3, ge=0, le=1)
    hyperparams: Optional[dict] = None
