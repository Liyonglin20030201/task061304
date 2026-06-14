from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date, datetime

from app.database import get_db
from app.api.deps import get_current_user_with_stores
from app.core.permissions import enforce_store_access
from app.schemas.association import (
    AnalysisJobCreate,
    AnalysisJobResponse,
    AssociationRuleResponse,
    CooccurrenceMatrixResponse,
    NetworkGraphResponse,
    BundleRecommendation,
    LayoutSuggestion,
)
from app.services.association_service import (
    run_association_analysis,
    get_association_rules,
    get_cooccurrence_matrix,
    get_network_graph_data,
    get_bundle_recommendations,
    get_layout_suggestions,
)
from app.models.association import AssociationAnalysisJob
from sqlalchemy import text

router = APIRouter(prefix="/association", tags=["association"])


@router.post("/analyze")
async def trigger_analysis(
    body: AnalysisJobCreate,
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an association analysis job. Admin/Manager only."""
    user, authorized_stores, role_name = auth_info

    # Role check: admin/manager only
    if role_name not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员和经理可以执行关联分析",
        )

    # Store access check
    enforce_store_access(authorized_stores, body.store_id)

    # Create job record
    job = AssociationAnalysisJob(
        store_id=body.store_id,
        min_support=body.min_support,
        min_confidence=body.min_confidence,
        start_date=body.start_date,
        end_date=body.end_date,
        category_filter=body.category_filter,
        min_transactions=body.min_transactions,
        status="running",
        created_by=user.id,
    )
    db.add(job)
    await db.flush()

    # Run analysis
    try:
        result = await run_association_analysis(
            db=db,
            store_id=body.store_id,
            start_date=str(body.start_date),
            end_date=str(body.end_date),
            min_support=body.min_support,
            min_confidence=body.min_confidence,
            category_filter=body.category_filter,
            min_transactions=body.min_transactions,
        )
        job.status = "completed"
        job.rules_found = result.get("rules_found", 0)
        job.completed_at = datetime.utcnow()
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)[:500]
        job.completed_at = datetime.utcnow()
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分析执行失败: {str(e)[:200]}",
        )

    await db.flush()

    return {
        "job_id": job.id,
        "status": job.status,
        "rules_found": job.rules_found,
        "total_transactions": result.get("total_transactions", 0),
        "unique_items": result.get("unique_items", 0),
        "frequent_itemsets_count": result.get("frequent_itemsets_count", 0),
    }


@router.get("/jobs")
async def list_jobs(
    store_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """List analysis jobs for authorized stores."""
    user, authorized_stores, role_name = auth_info

    conditions = []
    params = {}

    if store_id is not None:
        enforce_store_access(authorized_stores, store_id)
        conditions.append("store_id = :store_id")
        params["store_id"] = store_id
    elif authorized_stores is not None:
        # Non-admin: filter by authorized stores
        if not authorized_stores:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        conditions.append("store_id = ANY(:store_ids)")
        params["store_ids"] = authorized_stores

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count total
    count_sql = text(f"SELECT COUNT(*) FROM association_analysis_jobs {where_clause}")
    count_result = await db.execute(count_sql, params)
    total = count_result.scalar()

    # Get paginated results
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = text(f"""
        SELECT id, store_id, min_support, min_confidence, start_date, end_date,
               category_filter, min_transactions, status, rules_found,
               error_message, created_by, created_at, completed_at
        FROM association_analysis_jobs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(data_sql, params)
    rows = result.fetchall()

    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "store_id": row[1],
            "min_support": row[2],
            "min_confidence": row[3],
            "start_date": row[4],
            "end_date": row[5],
            "category_filter": row[6],
            "min_transactions": row[7],
            "status": row[8],
            "rules_found": row[9],
            "error_message": row[10],
            "created_by": row[11],
            "created_at": row[12],
            "completed_at": row[13],
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/rules")
async def list_rules(
    store_id: int = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_lift: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get association rules with filters."""
    user, authorized_stores, role_name = auth_info
    enforce_store_access(authorized_stores, store_id)

    return await get_association_rules(
        db=db,
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
        category=category,
        min_lift=min_lift,
        page=page,
        page_size=page_size,
    )


@router.get("/cooccurrence-matrix")
async def cooccurrence_matrix(
    store_id: int = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    category: Optional[str] = Query(None),
    top_n: int = Query(20, ge=5, le=50),
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get co-occurrence matrix for top items."""
    user, authorized_stores, role_name = auth_info
    enforce_store_access(authorized_stores, store_id)

    return await get_cooccurrence_matrix(
        db=db,
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
        category=category,
        top_n=top_n,
    )


@router.get("/network-graph")
async def network_graph(
    store_id: int = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_lift: float = Query(1.5, ge=1.0),
    top_n: int = Query(30, ge=5, le=100),
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get network graph data for visualization."""
    user, authorized_stores, role_name = auth_info
    enforce_store_access(authorized_stores, store_id)

    return await get_network_graph_data(
        db=db,
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
        min_lift=min_lift,
        top_n=top_n,
    )


@router.get("/bundle-recommendations/{item_id}")
async def bundle_recommendations(
    item_id: str,
    store_id: int = Query(...),
    top_n: int = Query(10, ge=1, le=50),
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get bundle recommendations for a given item."""
    user, authorized_stores, role_name = auth_info
    enforce_store_access(authorized_stores, store_id)

    return await get_bundle_recommendations(
        db=db,
        store_id=store_id,
        item_id=item_id,
        top_n=top_n,
    )


@router.get("/layout-suggestions")
async def layout_suggestions(
    store_id: int = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_lift: float = Query(2.0, ge=1.0),
    auth_info: tuple = Depends(get_current_user_with_stores),
    db: AsyncSession = Depends(get_db),
):
    """Get shelf layout suggestions based on product associations."""
    user, authorized_stores, role_name = auth_info
    enforce_store_access(authorized_stores, store_id)

    return await get_layout_suggestions(
        db=db,
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
        min_lift=min_lift,
    )
