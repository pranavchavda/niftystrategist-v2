"""API routes for Inventory Prediction system"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging
import json
import uuid

from database.session import get_db
from database.models import User
from auth import get_current_user, requires_permission
from services.inventory_forecasting import (
    get_inventory_forecasting_service,
    ForecastSummary,
    ForecastResult
)
from services.skuvault_forecasting import get_skuvault_forecasting_service, SkuVaultSalesCacheService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/inventory",
    tags=["inventory-prediction"],
    dependencies=[Depends(requires_permission("inventory.access"))]
)


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateForecastRequest(BaseModel):
    """Request to create a forecast for a SKU"""
    sku: str = Field(..., description="SkuVault SKU to forecast")
    horizon_days: int = Field(default=30, ge=7, le=90, description="Days to forecast")
    warehouse_id: Optional[str] = Field(None, description="Warehouse filter (None=aggregate)")
    method: str = Field(default="prophet", description="Forecasting method")


class BatchForecastRequest(BaseModel):
    """Request to create forecasts for multiple SKUs"""
    skus: List[str] = Field(..., min_length=1, max_length=100)
    horizon_days: int = Field(default=30, ge=7, le=90)
    warehouse_id: Optional[str] = None


class ForecastResponse(BaseModel):
    """Individual forecast day response"""
    forecast_date: datetime
    predicted_units: int
    confidence_low: int
    confidence_high: int
    trend_component: float
    seasonal_component: float
    holiday_component: float


class ForecastSummaryResponse(BaseModel):
    """Complete forecast response"""
    model_id: str
    sku: str
    warehouse_id: Optional[str]
    forecast_horizon_days: int
    method: str
    mape: Optional[float]
    current_inventory: int
    days_until_stockout: Optional[int]
    reorder_recommendation: Optional[str]
    created_at: datetime
    forecasts: List[ForecastResponse]


class StockoutRiskResponse(BaseModel):
    """SKU at risk of stockout"""
    sku: str
    warehouse_id: Optional[str]
    current_inventory: int
    days_until_stockout: int
    reorder_recommendation: str
    severity: str  # critical, high, medium


class InventorySnapshotResponse(BaseModel):
    """Current inventory state"""
    sku: str
    warehouse_id: str
    warehouse_name: str
    quantity_on_hand: int
    quantity_available: int
    quantity_committed: int


class SalesHistoryResponse(BaseModel):
    """Historical sales data point"""
    date: datetime
    units_sold: int
    revenue: float


# ============================================================================
# Forecast Endpoints
# ============================================================================

@router.post("/forecasts", response_model=ForecastSummaryResponse)
async def create_forecast(
    request: CreateForecastRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a demand forecast for a specific SKU.

    Uses Prophet with SkuVault historical sales data.
    Uses cached sales data when available.
    """
    try:
        service = get_inventory_forecasting_service(db)

        summary = await service.create_forecast(
            sku=request.sku,
            horizon_days=request.horizon_days,
            warehouse_id=request.warehouse_id,
            method=request.method
        )

        return _summary_to_response(summary)

    except Exception as e:
        logger.error(f"Error creating forecast for {request.sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecasts/batch")
async def batch_forecast(
    request: BatchForecastRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create forecasts for multiple SKUs.

    For large batches, consider using the async endpoint instead.
    """
    try:
        service = get_inventory_forecasting_service(db)

        results = await service.batch_forecast(
            skus=request.skus,
            horizon_days=request.horizon_days,
            warehouse_id=request.warehouse_id
        )

        return {
            "success": True,
            "count": len(results),
            "forecasts": [_summary_to_response(s) for s in results]
        }

    except Exception as e:
        logger.error(f"Error in batch forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecasts/{sku}")
async def get_forecast(
    sku: str,
    horizon_days: int = 30,
    warehouse_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get or create a forecast for a specific SKU.

    This is a convenience endpoint that creates a fresh forecast.
    Uses cached sales data when available.
    """
    try:
        service = get_inventory_forecasting_service(db)

        summary = await service.create_forecast(
            sku=sku,
            horizon_days=horizon_days,
            warehouse_id=warehouse_id
        )

        return _summary_to_response(summary)

    except Exception as e:
        logger.error(f"Error getting forecast for {sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Alert Endpoints
# ============================================================================

@router.get("/alerts")
async def get_alerts(
    unacknowledged_only: bool = False,
    alert_type: Optional[str] = None,
    sku: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get inventory alerts.

    Supports filtering by acknowledged status, type, and SKU.
    """
    from sqlalchemy import select, desc
    from database.models import InventoryAlert

    try:
        query = select(InventoryAlert).order_by(desc(InventoryAlert.created_at))

        if unacknowledged_only:
            query = query.where(InventoryAlert.is_acknowledged == False)

        if alert_type:
            query = query.where(InventoryAlert.alert_type == alert_type)

        if sku:
            query = query.where(InventoryAlert.sku == sku)

        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        alerts = result.scalars().all()

        return {
            "success": True,
            "count": len(alerts),
            "alerts": [
                {
                    "id": str(a.id),
                    "sku": a.sku,
                    "warehouse_id": a.warehouse_id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "recommended_action": a.recommended_action,
                    "days_until_stockout": a.days_until_stockout,
                    "current_quantity": a.current_quantity,
                    "is_acknowledged": a.is_acknowledged,
                    "created_at": a.created_at.isoformat() if a.created_at else None
                }
                for a in alerts
            ]
        }

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Acknowledge an inventory alert.
    """
    from sqlalchemy import select
    from database.models import InventoryAlert

    try:
        result = await db.execute(
            select(InventoryAlert).where(InventoryAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.is_acknowledged = True
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = str(user.id)

        await db.commit()

        return {
            "success": True,
            "message": "Alert acknowledged"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/stockout-risks")
async def get_stockout_risks(
    threshold_days: int = 14,
    warehouse_id: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get SKUs at risk of stockout within the threshold period.

    Returns items sorted by urgency (days until stockout ascending).
    """
    try:
        service = get_inventory_forecasting_service(db)

        # Get at-risk items
        at_risk = await service.get_stockout_risks(
            threshold_days=threshold_days,
            warehouse_id=warehouse_id
        )

        # Convert to response format
        risks = []
        for summary in at_risk[:limit]:
            severity = "critical" if summary.days_until_stockout <= 7 else \
                       "high" if summary.days_until_stockout <= 14 else "medium"

            risks.append(StockoutRiskResponse(
                sku=summary.sku,
                warehouse_id=summary.warehouse_id,
                current_inventory=summary.current_inventory,
                days_until_stockout=summary.days_until_stockout,
                reorder_recommendation=summary.reorder_recommendation or "",
                severity=severity
            ))

        return {
            "success": True,
            "count": len(risks),
            "threshold_days": threshold_days,
            "risks": risks
        }

    except Exception as e:
        logger.error(f"Error getting stockout risks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Inventory Endpoints
# ============================================================================

@router.get("/inventory/{sku}")
async def get_inventory(
    sku: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current inventory levels for a SKU across all warehouses.

    Uses cache with API fallback. Results are cached for future lookups.
    """
    try:
        # Use cache service (with API fallback and auto-caching)
        cache_service = SkuVaultSalesCacheService(db)
        snapshots = await cache_service.get_inventory_snapshots(sku)

        return {
            "success": True,
            "sku": sku,
            "warehouses": [
                InventorySnapshotResponse(
                    sku=s.sku,
                    warehouse_id=s.warehouse_id,
                    warehouse_name=s.warehouse_name,
                    quantity_on_hand=s.quantity_on_hand,
                    quantity_available=s.quantity_available,
                    quantity_committed=s.quantity_committed
                ) for s in snapshots
            ],
            "total_available": sum(s.quantity_available for s in snapshots),
            "total_on_hand": sum(s.quantity_on_hand for s in snapshots),
            "total_committed": sum(s.quantity_committed for s in snapshots)
        }

    except Exception as e:
        logger.error(f"Error getting inventory for {sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{sku}")
async def get_sales_history(
    sku: str,
    days: int = 365,
    warehouse_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical sales data for a SKU.

    This data is used for Prophet training and visualization.
    Uses cached data when available.
    """
    try:
        # Use cache service if db available
        cache_service = SkuVaultSalesCacheService(db)
        df = await cache_service.get_sales_for_prophet(
            sku=sku,
            days=days,
            warehouse_id=warehouse_id
        )

        if df.empty:
            return {
                "success": True,
                "sku": sku,
                "days": days,
                "data": [],
                "summary": {
                    "total_units": 0,
                    "total_revenue": 0,
                    "avg_daily_units": 0
                }
            }

        # Build data array with format expected by frontend
        data = [
            {
                "date": row["ds"].isoformat() if hasattr(row["ds"], 'isoformat') else str(row["ds"]),
                "units": int(row["y"]),
                "revenue": float(row.get("revenue", 0)),
                "warehouse_id": row.get("warehouse_id")
            }
            for _, row in df.iterrows()
        ]

        total_units = int(df["y"].sum())
        total_revenue = float(df["revenue"].sum()) if "revenue" in df.columns else 0
        avg_daily = round(total_units / len(df), 2) if len(df) > 0 else 0

        return {
            "success": True,
            "sku": sku,
            "days": days,
            "warehouse_id": warehouse_id,
            "data": data,
            "summary": {
                "total_units": total_units,
                "total_revenue": total_revenue,
                "avg_daily_units": avg_daily
            }
        }

    except Exception as e:
        logger.error(f"Error getting sales history for {sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Catalog Endpoints
# ============================================================================

@router.get("/skus")
async def list_active_skus(
    limit: int = 10000,  # Effectively unlimited
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all SKUs with sales data from cache.

    Returns all SKUs that have historical sales data.
    """
    try:
        cache_service = SkuVaultSalesCacheService(db)

        # Get all SKUs from cache
        skus = await cache_service.get_cached_skus(limit=limit, offset=offset)
        total = await cache_service.get_cached_sku_count()

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "skus": skus
        }

    except Exception as e:
        logger.error(f"Error listing SKUs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{sku}")
async def get_product_details(
    sku: str,
    user: User = Depends(get_current_user)
):
    """
    Get detailed product information for a SKU.
    """
    try:
        service = get_skuvault_forecasting_service()

        products = service.get_product_details([sku])

        if not products:
            raise HTTPException(status_code=404, detail=f"SKU not found: {sku}")

        return {
            "success": True,
            "product": products[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product details for {sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get summary statistics for the inventory prediction dashboard.
    Returns cache stats quickly without running forecasts.
    """
    try:
        cache_service = SkuVaultSalesCacheService(db)

        # Get SKU count from cache (fast query)
        total_skus = await cache_service.get_cached_sku_count()

        # Get cache coverage stats
        cache_coverage = await cache_service.get_cache_coverage()

        # Get sync status
        cache_status = await cache_service.get_sync_status()

        # Get inventory sync status
        inventory_status = await cache_service.get_inventory_sync_status()

        return {
            "success": True,
            "total_active_skus": total_skus,
            "cache_coverage": cache_coverage,
            "sales_sync": cache_status,
            "inventory_sync": inventory_status,
            "last_updated": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Cache Sync Endpoints
# ============================================================================

@router.get("/cache/status")
async def get_cache_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current status of the SkuVault sales cache.
    """
    from services.skuvault_forecasting import get_skuvault_cache_service

    try:
        cache = await get_skuvault_cache_service(db)
        status = await cache.get_sync_status()
        coverage = await cache.get_cache_coverage()

        return {
            "success": True,
            "sync_status": status,
            "coverage": coverage
        }

    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/sync")
async def trigger_cache_sync(
    background_tasks: BackgroundTasks,
    force_full: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger a sync of SkuVault sales data to cache.

    Args:
        force_full: If True, re-sync all 365 days. Otherwise, only sync new data.
    """
    from services.skuvault_forecasting import get_skuvault_cache_service

    try:
        cache = await get_skuvault_cache_service(db)

        # Check if already running
        status = await cache.get_sync_status()
        if status.get("status") == "running":
            return {
                "success": False,
                "message": "Sync already in progress",
                "status": status
            }

        # Run sync (this can take a while for initial sync)
        result = await cache.sync_sales_data(force_full=force_full)

        return {
            "success": True,
            "message": "Sync completed",
            "result": result
        }

    except Exception as e:
        logger.error(f"Error triggering cache sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/coverage/{sku}")
async def get_sku_cache_coverage(
    sku: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cache coverage for a specific SKU.
    """
    from services.skuvault_forecasting import get_skuvault_cache_service

    try:
        cache = await get_skuvault_cache_service(db)
        coverage = await cache.get_cache_coverage(sku)

        return {
            "success": True,
            "sku": sku,
            "coverage": coverage
        }

    except Exception as e:
        logger.error(f"Error getting SKU cache coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Helper Functions
# ============================================================================

def _summary_to_response(summary: ForecastSummary) -> ForecastSummaryResponse:
    """Convert internal ForecastSummary to API response"""
    return ForecastSummaryResponse(
        model_id=summary.model_id,
        sku=summary.sku,
        warehouse_id=summary.warehouse_id,
        forecast_horizon_days=summary.forecast_horizon_days,
        method=summary.method,
        mape=summary.mape,
        current_inventory=summary.current_inventory,
        days_until_stockout=summary.days_until_stockout,
        reorder_recommendation=summary.reorder_recommendation,
        created_at=summary.created_at,
        forecasts=[
            ForecastResponse(
                forecast_date=f.forecast_date,
                predicted_units=f.predicted_units,
                confidence_low=f.confidence_low,
                confidence_high=f.confidence_high,
                trend_component=f.trend_component,
                seasonal_component=f.seasonal_component,
                holiday_component=f.holiday_component
            ) for f in summary.forecasts
        ]
    )
