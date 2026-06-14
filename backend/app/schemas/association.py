from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class AnalysisJobCreate(BaseModel):
    store_id: int
    min_support: float = Field(default=0.01, ge=0.001, le=1.0)
    min_confidence: float = Field(default=0.3, ge=0.01, le=1.0)
    start_date: date
    end_date: date
    category_filter: Optional[str] = None
    min_transactions: int = Field(default=2, ge=2)
    adaptive_threshold: bool = Field(
        default=True,
        description="Use dynamic per-category support thresholds. When False, a single global threshold is used.",
    )


class AnalysisJobResponse(BaseModel):
    id: int
    store_id: int
    min_support: float
    min_confidence: float
    start_date: date
    end_date: date
    category_filter: Optional[str] = None
    min_transactions: int
    status: str
    rules_found: int
    error_message: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssociationRuleResponse(BaseModel):
    id: int
    store_id: int
    antecedent_items: List[str]
    consequent_items: List[str]
    antecedent_names: Optional[List[str]] = None
    consequent_names: Optional[List[str]] = None
    support: float
    confidence: float
    lift: float
    conviction: Optional[float] = None
    leverage: Optional[float] = None
    transaction_count: Optional[int] = None
    period_start: date
    period_end: date
    category_filter: Optional[str] = None
    computed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CooccurrenceMatrixResponse(BaseModel):
    labels: List[str]
    matrix: List[List[int]]


class NetworkGraphNode(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    value: int


class NetworkGraphEdge(BaseModel):
    source: str
    target: str
    value: float


class NetworkGraphResponse(BaseModel):
    nodes: List[NetworkGraphNode]
    edges: List[NetworkGraphEdge]


class BundleRecommendation(BaseModel):
    item_id: str
    item_name: str
    support: float
    confidence: float
    lift: float


class LayoutSuggestion(BaseModel):
    cluster_id: int
    items: List[dict]
    avg_lift: float
    suggestion: str
