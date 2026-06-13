from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import date

from app.database import get_db
from app.api.deps import get_current_user, get_current_user_with_stores
from app.core.permissions import (
    get_user_authorized_stores, filter_by_authorized_stores,
    enforce_store_access, ROLE_ADMIN, ROLE_MANAGER,
)
from app.models.supply_chain import (
    Supplier, SupplierItem, PurchaseOrder, PurchaseOrderItem,
    SupplierPerformance, InventoryAdjustment,
)
from app.schemas.supply_chain import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    SupplierItemCreate, SupplierItemResponse,
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse,
    PurchaseOrderItemResponse, ReceiveDelivery,
    InventoryAdjustmentCreate, InventoryAdjustmentResponse,
    SupplierPerformanceResponse, HealthDashboardResponse,
    AdjustmentRecommendation,
)
from app.services.supply_chain_service import (
    get_supplier_performance_metrics,
    calculate_all_supplier_performance,
    get_health_dashboard,
    get_stockout_analysis,
    get_adjustment_recommendations,
    get_performance_trend,
)

router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])


@router.get("/suppliers", response_model=List[SupplierResponse])
async def list_suppliers(
    is_active: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    query = select(Supplier)
    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
    query = query.order_by(Supplier.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/suppliers", response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}/items", response_model=List[SupplierItemResponse])
async def list_supplier_items(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    result = await db.execute(
        select(SupplierItem).where(SupplierItem.supplier_id == supplier_id)
    )
    return result.scalars().all()


@router.post("/suppliers/{supplier_id}/items", response_model=SupplierItemResponse)
async def add_supplier_item(
    supplier_id: int,
    data: SupplierItemCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    item = SupplierItem(supplier_id=supplier_id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/orders", response_model=List[PurchaseOrderResponse])
async def list_orders(
    store_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    query = select(PurchaseOrder)
    query = filter_by_authorized_stores(query, PurchaseOrder.store_id, authorized_stores)
    if store_id:
        query = query.where(PurchaseOrder.store_id == store_id)
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    query = query.order_by(PurchaseOrder.order_date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    orders = result.scalars().all()

    response = []
    for order in orders:
        items_result = await db.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()
        order_dict = {
            "id": order.id, "supplier_id": order.supplier_id,
            "store_id": order.store_id, "order_no": order.order_no,
            "order_date": order.order_date,
            "expected_delivery_date": order.expected_delivery_date,
            "actual_delivery_date": order.actual_delivery_date,
            "status": order.status, "total_amount": order.total_amount,
            "total_items": order.total_items, "notes": order.notes,
            "created_by": order.created_by, "created_at": order.created_at,
            "items": items,
        }
        response.append(order_dict)
    return response


@router.post("/orders", response_model=PurchaseOrderResponse)
async def create_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    enforce_store_access(authorized_stores, data.store_id)

    total_amount = sum(item.quantity * item.unit_cost for item in data.items)
    order = PurchaseOrder(
        supplier_id=data.supplier_id,
        store_id=data.store_id,
        order_no=data.order_no,
        order_date=data.order_date,
        expected_delivery_date=data.expected_delivery_date,
        notes=data.notes,
        total_amount=total_amount,
        total_items=len(data.items),
        created_by=user.id,
    )
    db.add(order)
    await db.flush()

    order_items = []
    for item_data in data.items:
        oi = PurchaseOrderItem(
            order_id=order.id,
            item_id=item_data.item_id,
            item_name=item_data.item_name,
            quantity=item_data.quantity,
            unit_cost=item_data.unit_cost,
            total_cost=item_data.quantity * item_data.unit_cost,
        )
        db.add(oi)
        order_items.append(oi)

    await db.commit()
    await db.refresh(order)
    return {
        **{c.name: getattr(order, c.name) for c in order.__table__.columns},
        "items": order_items,
    }


@router.put("/orders/{order_id}", response_model=dict)
async def update_order(
    order_id: int,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
    await db.commit()
    return {"message": "更新成功"}


@router.put("/orders/{order_id}/receive")
async def receive_delivery(
    order_id: int,
    data: ReceiveDelivery,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order.actual_delivery_date = data.actual_delivery_date
    order.status = "delivered"

    for item_detail in data.items:
        item_result = await db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.order_id == order_id,
                PurchaseOrderItem.item_id == item_detail.item_id,
            )
        )
        oi = item_result.scalar_one_or_none()
        if oi:
            oi.received_quantity = item_detail.received_quantity
            if item_detail.quality_score is not None:
                oi.quality_score = item_detail.quality_score

    await db.commit()
    return {"message": "收货确认成功"}


@router.get("/performance", response_model=List[dict])
async def list_performance(
    period_days: int = 90,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    return await calculate_all_supplier_performance(db, period_days, authorized_stores)


@router.post("/performance/calculate")
async def recalculate_performance(
    period_days: int = 90,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    performances = await calculate_all_supplier_performance(db, period_days, authorized_stores)

    for perf in performances:
        record = SupplierPerformance(
            supplier_id=perf["supplier_id"],
            period_start=perf["period_start"],
            period_end=perf["period_end"],
            total_orders=perf["total_orders"],
            on_time_deliveries=perf["on_time_deliveries"],
            late_deliveries=perf["late_deliveries"],
            total_items_ordered=perf["total_items_ordered"],
            total_items_received=perf["total_items_received"],
            defect_items=perf["defect_items"],
            avg_lead_time_actual=perf["avg_lead_time_actual"],
            cost_variance_pct=perf["cost_variance_pct"],
            overall_score=perf["overall_score"],
        )
        db.add(record)

    await db.commit()
    return {"message": f"已计算 {len(performances)} 个供应商的绩效指标"}


@router.get("/performance/{supplier_id}")
async def get_supplier_detail(
    supplier_id: int,
    period_days: int = 90,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    return await get_supplier_performance_metrics(db, supplier_id, period_days, authorized_stores)


@router.get("/performance/{supplier_id}/trend")
async def get_supplier_trend(
    supplier_id: int,
    periods: int = 6,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    return await get_performance_trend(db, supplier_id, periods)


@router.get("/stockout-analysis")
async def stockout_analysis(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    return await get_stockout_analysis(db, authorized_stores, days)


@router.get("/health-dashboard")
async def health_dashboard(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    return await get_health_dashboard(db, authorized_stores)


@router.post("/adjustments", response_model=InventoryAdjustmentResponse)
async def create_adjustment(
    data: InventoryAdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    if role_name not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=403, detail="权限不足")
    enforce_store_access(authorized_stores, data.store_id)

    adjustment = InventoryAdjustment(
        **data.model_dump(),
        approved_by=user.id,
    )
    db.add(adjustment)
    await db.commit()
    await db.refresh(adjustment)
    return adjustment


@router.get("/adjustments", response_model=List[InventoryAdjustmentResponse])
async def list_adjustments(
    store_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    query = select(InventoryAdjustment)
    query = filter_by_authorized_stores(query, InventoryAdjustment.store_id, authorized_stores)
    if store_id:
        query = query.where(InventoryAdjustment.store_id == store_id)
    query = query.order_by(InventoryAdjustment.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/recommendations", response_model=List[AdjustmentRecommendation])
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
    user_stores: tuple = Depends(get_current_user_with_stores),
):
    user, authorized_stores, role_name = user_stores
    return await get_adjustment_recommendations(db, authorized_stores)
