from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class QualityRuleCreate(BaseModel):
    rule_name: str
    target_table: str
    dimension: str
    check_type: str
    column_name: Optional[str] = None
    condition: Optional[dict] = None
    threshold_warn: float = Field(default=0.05, ge=0, le=1)
    threshold_error: float = Field(default=0.15, ge=0, le=1)


class QualityRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    condition: Optional[dict] = None
    threshold_warn: Optional[float] = None
    threshold_error: Optional[float] = None
    is_active: Optional[int] = None


class QualityRuleResponse(BaseModel):
    id: int
    rule_name: str
    target_table: str
    dimension: str
    check_type: str
    column_name: Optional[str]
    condition: Optional[dict]
    threshold_warn: float
    threshold_error: float
    is_active: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class QualityScoreResponse(BaseModel):
    target_table: str
    dimension: str
    score: float
    total_records: int
    failed_records: int
    score_date: date
    store_id: Optional[int] = None


class QualityAlertResponse(BaseModel):
    id: int
    store_id: Optional[int]
    rule_id: int
    target_table: str
    dimension: str
    severity: str
    title: str
    description: Optional[str]
    metric_value: Optional[float]
    threshold_value: Optional[float]
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    overall_score: float
    completeness_score: float
    accuracy_score: float
    timeliness_score: float
    alerts_open: int
    alerts_critical: int
    last_check_at: Optional[datetime] = None


class CheckRunResponse(BaseModel):
    id: int
    run_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_rules_run: int
    alerts_generated: int
    overall_score: Optional[float]
    status: str

    class Config:
        from_attributes = True
