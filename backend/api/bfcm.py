"""
BFCM Tracker API Endpoints
Provides endpoints for the BFCM dashboard with multi-year comparison.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db
from services.bfcm_service import get_bfcm_service
from auth import get_current_user, User as AuthUser
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bfcm", tags=["bfcm"])


@router.get("/dashboard")
async def get_bfcm_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get complete BFCM dashboard data.

    Returns all years comparison (2022-2025), milestones, and YoY growth.
    Use this for initial page load.
    """
    try:
        logger.info(f"[BFCM API] Dashboard request from user {current_user.id}")

        service = get_bfcm_service()
        data = await service.get_dashboard_data(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BFCM API] Error fetching dashboard: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live")
async def get_live_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get lightweight live metrics for 5-minute polling.

    Returns current year data only with milestones.
    More efficient than /dashboard for frequent updates.
    """
    try:
        logger.info(f"[BFCM API] Live metrics request from user {current_user.id}")

        service = get_bfcm_service()
        data = await service.get_live_metrics(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        logger.error(f"[BFCM API] Error fetching live metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/year/{year}")
async def get_year_data(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get BFCM data for a specific year.

    Includes daily breakdown, top products, and category data.
    """
    try:
        if year < 2022 or year > 2025:
            raise HTTPException(status_code=400, detail="Year must be between 2022 and 2025")

        logger.info(f"[BFCM API] Year {year} request from user {current_user.id}")

        service = get_bfcm_service()

        # Try cache first for historical years
        if year < 2025:
            cached = await service.get_cached_data(db, year)
            if cached:
                return {"success": True, "data": cached}

        # Fetch fresh data
        data = await service.fetch_year_data(year)
        top_products = await service.fetch_top_products(year)
        categories = await service.fetch_category_breakdown(year)

        data["top_products"] = top_products
        data["category_breakdown"] = categories

        return {
            "success": True,
            "data": data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BFCM API] Error fetching year {year}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/milestones")
async def get_milestones(
    year: int = Query(2025, description="Year to get milestones for"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get milestone status for a year.

    Returns list of milestones with achieved status.
    """
    try:
        service = get_bfcm_service()
        milestones = await service.get_milestones(db, year)

        return {
            "success": True,
            "data": {
                "year": year,
                "milestones": milestones
            }
        }

    except Exception as e:
        logger.error(f"[BFCM API] Error fetching milestones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/milestones/{threshold}/notified")
async def mark_milestone_notified(
    threshold: float,
    year: int = Query(2025, description="Year of the milestone"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Mark a milestone as notified (toast has been shown).

    Prevents duplicate toast notifications across page refreshes.
    """
    try:
        service = get_bfcm_service()
        await service.mark_milestone_notified(db, threshold, year)

        return {
            "success": True,
            "message": f"Milestone ${threshold:,.0f} marked as notified"
        }

    except Exception as e:
        logger.error(f"[BFCM API] Error marking milestone notified: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill/{year}")
async def backfill_historical_data(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Backfill historical BFCM data for a year.

    Admin-only endpoint. Use for populating cache with historical data.
    """
    try:
        # Check if user is admin
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        if year >= 2025:
            raise HTTPException(status_code=400, detail="Cannot backfill current or future years")

        if year < 2022:
            raise HTTPException(status_code=400, detail="Data only available from 2022")

        logger.info(f"[BFCM API] Backfill request for {year} from admin {current_user.id}")

        service = get_bfcm_service()
        result = await service.backfill_historical_year(db, year)

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BFCM API] Error backfilling {year}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_bfcm_status(
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get BFCM period status.

    Returns whether BFCM is currently active and date ranges.
    """
    service = get_bfcm_service()

    return {
        "success": True,
        "data": {
            "is_active": service.is_bfcm_active(2025),
            "current_year": 2025,
            "date_ranges": {
                year: {
                    "start": dates[0],
                    "end": dates[1]
                }
                for year, dates in service.date_ranges.items()
            },
            "milestones": service.milestones
        }
    }


@router.get("/comparison/today")
async def get_today_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get today's sales up to current hour vs same day/hour in previous years.

    Compares e.g. Black Friday 2025 at 5PM vs Black Friday 2024 at 5PM.
    Returns current revenue and YoY comparisons.
    """
    try:
        logger.info(f"[BFCM API] Today comparison request from user {current_user.id}")

        service = get_bfcm_service()
        data = await service.get_today_comparison(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BFCM API] Error fetching today comparison: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/days")
async def get_day_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get day-by-day comparison across all BFCM years.

    Returns revenue for each day (Thu-Wed) across 2022-2025.
    Useful for comparing Black Friday vs Black Friday, Cyber Monday vs Cyber Monday, etc.
    """
    try:
        logger.info(f"[BFCM API] Day comparison request from user {current_user.id}")

        service = get_bfcm_service()
        data = await service.get_day_comparison(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BFCM API] Error fetching day comparison: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/pace")
async def get_pace_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get hourly pace comparison across all BFCM years.

    Returns cumulative revenue at each hour mark, showing how 2025
    compares to previous years at the same point in time.
    """
    try:
        logger.info(f"[BFCM API] Pace comparison request from user {current_user.id}")

        service = get_bfcm_service()
        data = await service.get_hourly_comparison(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BFCM API] Error fetching pace comparison: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/pace/summary")
async def get_pace_summary(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get a summary of current pace vs previous years.

    Returns how 2025 compares to 2024, 2023, 2022 at the same hour mark.
    Includes percentage difference and whether we're ahead or behind.
    """
    try:
        logger.info(f"[BFCM API] Pace summary request from user {current_user.id}")

        service = get_bfcm_service()
        data = await service.get_pace_summary(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BFCM API] Error fetching pace summary: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
