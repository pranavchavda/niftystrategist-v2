"""
Boxing Week Tracker API Endpoints
Provides endpoints for the Boxing Week dashboard with multi-year comparison.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db
from services.boxing_week_service import get_boxing_week_service
from auth import get_current_user, User as AuthUser
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boxing-week", tags=["boxing-week"])


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get complete Boxing Week dashboard data.

    Returns all years comparison (2022-2025), milestones, and YoY growth.
    Use this for initial page load.
    """
    try:
        logger.info(f"[BoxingWeek API] Dashboard request from user {current_user.id}")

        service = get_boxing_week_service()
        data = await service.get_dashboard_data(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BoxingWeek API] Error fetching dashboard: {e}\n{traceback.format_exc()}")
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
        logger.info(f"[BoxingWeek API] Live metrics request from user {current_user.id}")

        service = get_boxing_week_service()
        data = await service.get_live_metrics(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        logger.error(f"[BoxingWeek API] Error fetching live metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/year/{year}")
async def get_year_data(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get Boxing Week data for a specific year.
    """
    try:
        if year < 2022 or year > 2025:
            raise HTTPException(status_code=400, detail="Year must be between 2022 and 2025")

        logger.info(f"[BoxingWeek API] Year {year} request from user {current_user.id}")

        service = get_boxing_week_service()

        # Try cache first for historical years
        if year < 2025:
            cached = await service.get_cached_data(db, year)
            if cached:
                return {"success": True, "data": cached}

        # Fetch fresh data in parallel
        data, top_products, categories = await asyncio.gather(
            service.fetch_year_data(year),
            service.fetch_top_products(year),
            service.fetch_category_breakdown(year)
        )

        data["top_products"] = top_products
        data["category_breakdown"] = categories

        return {
            "success": True,
            "data": data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BoxingWeek API] Error fetching year {year}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/milestones")
async def get_milestones(
    year: int = Query(2025, description="Year to get milestones for"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get milestone status for a year.
    """
    try:
        service = get_boxing_week_service()
        milestones = await service.get_milestones(db, year)

        return {
            "success": True,
            "data": {
                "year": year,
                "milestones": milestones
            }
        }

    except Exception as e:
        logger.error(f"[BoxingWeek API] Error fetching milestones: {e}")
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
    """
    try:
        service = get_boxing_week_service()
        await service.mark_milestone_notified(db, threshold, year)

        return {
            "success": True,
            "message": f"Milestone ${threshold:,.0f} marked as notified"
        }

    except Exception as e:
        logger.error(f"[BoxingWeek API] Error marking milestone notified: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status(
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get Boxing Week period status.
    """
    service = get_boxing_week_service()

    return {
        "success": True,
        "data": {
            "is_active": service.is_boxing_week_active(2025),
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
    """
    try:
        logger.info(f"[BoxingWeek API] Today comparison request from user {current_user.id}")

        service = get_boxing_week_service()
        data = await service.get_today_comparison(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BoxingWeek API] Error fetching today comparison: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/days")
async def get_day_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get day-by-day comparison across all years.
    """
    try:
        logger.info(f"[BoxingWeek API] Day comparison request from user {current_user.id}")

        service = get_boxing_week_service()
        data = await service.get_day_comparison(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BoxingWeek API] Error fetching day comparison: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/pace")
async def get_pace_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get hourly pace comparison across all years.
    """
    try:
        logger.info(f"[BoxingWeek API] Pace comparison request from user {current_user.id}")

        service = get_boxing_week_service()
        data = await service.get_hourly_comparison(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BoxingWeek API] Error fetching pace comparison: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/pace/summary")
async def get_pace_summary(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get a summary of current pace vs previous years.
    """
    try:
        logger.info(f"[BoxingWeek API] Pace summary request from user {current_user.id}")

        service = get_boxing_week_service()
        data = await service.get_pace_summary(db)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        import traceback
        logger.error(f"[BoxingWeek API] Error fetching pace summary: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
