from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class SupplierCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    lead_time_days: int = 7
    min_order_qty: int = 1
    bulk_discount_threshold: Optional[int] = None
    bulk_discount_rate: Optional[float] = None
    payment_terms: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    lead_time_days: Optional[int] = None
    min_order_qty: Optional[int] = None
    bulk_discount_threshold: Optional[int] = None
    bulk_discount_rate: Optional[float] = None
    payment_terms: Optional[str] = None
    is_active: Optional[int] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    lead_time_days: int
    min_order_qty: int
    bulk_discount_threshold: Optional[int] = None
    bulk_discount_rate: Optional[float] = None
    payment_terms: Optional[str] = None
    is_active: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SupplierItemCreate(BaseModel):
    item_id: str
    item_name: str
    category: Optional[str] = None
    unit_cost: float
    moq: int = 1
    bulk_price: Optional[float] = None
    supply_capacity_daily: Optional[int] = None
    is_primary: int = 0


class SupplierItemResponse(BaseModel):
    id: int
    supplier_id: int
    item_id: str
    item_name: str
    category: Optional[str] = None
    unit_cost: float
    moq: int
    bulk_price: Optional[float] = None
    supply_capacity_daily: Optional[int] = None
    is_primary: int

    class Config:
        from_attributes = True


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    store_id: int
    order_no: str
    order_date: date
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    items: List["PurchaseOrderItemCreate"]


class PurchaseOrderItemCreate(BaseModel):
    item_id: str
    item_name: str
    quantity: int
    unit_cost: float


class PurchaseOrderUpdate(BaseModel):
    expected_delivery_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ReceiveDelivery(BaseModel):
    actual_delivery_date: date
    items: List["ReceiveItemDetail"]


class ReceiveItemDetail(BaseModel):
    item_id: str
    received_quantity: int
    quality_score: Optional[float] = None


class PurchaseOrderItemResponse(BaseModel):
    id: int
    item_id: str
    item_name: str
    quantity: int
    unit_cost: float
    total_cost: float
    received_quantity: int
    quality_score: Optional[float] = None

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: int
    supplier_id: int
    store_id: int
    order_no: str
    order_date: date
    expected_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    status: str
    total_amount: float
    total_items: int
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    items: List[PurchaseOrderItemResponse] = []

    class Config:
        from_attributes = True


class SupplierPerformanceResponse(BaseModel):
    id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    period_start: date
    period_end: date
    total_orders: int
    on_time_deliveries: int
    late_deliveries: int
    on_time_rate: float = 0
    fulfillment_rate: float = 0
    quality_score: float = 0
    cost_variance_pct: Optional[float] = None
    overall_score: float = 0
    health_level: str = "green"

    class Config:
        from_attributes = True


class InventoryAdjustmentCreate(BaseModel):
    store_id: int
    item_id: str
    item_name: str
    adjustment_type: str
    quantity: int
    reason: Optional[str] = None
    source_store_id: Optional[int] = None


class InventoryAdjustmentResponse(BaseModel):
    id: int
    store_id: int
    item_id: str
    item_name: str
    adjustment_type: str
    quantity: int
    reason: Optional[str] = None
    source_store_id: Optional[int] = None
    approved_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HealthDashboardResponse(BaseModel):
    suppliers: List[SupplierPerformanceResponse]
    summary: dict


class AdjustmentRecommendation(BaseModel):
    store_id: int
    item_id: str
    item_name: str
    current_stock: int
    recommended_action: str
    recommended_qty: int
    reason: str
    priority: str
