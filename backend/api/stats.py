"""
Stats API - Provides real-time statistics about Nifty Strategist
"""

from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/tools")
async def get_tools_count():
    """
    Count the number of trading tools available.
    """
    tools_dir = Path(__file__).parent.parent / "tools" / "trading"

    if not tools_dir.exists():
        return {"count": 0, "error": "trading tools directory not found"}

    # Count .py files, excluding __init__.py and test files
    py_files = list(tools_dir.glob("*.py"))
    tool_files = [
        f for f in py_files
        if f.name not in ("__init__.py",) and not f.name.startswith("test_")
    ]

    return {
        "count": len(tool_files),
        "tools": [f.stem for f in tool_files],
        "directory": str(tools_dir)
    }


@router.get("/landing")
async def get_landing_stats(db: AsyncSession = Depends(get_db)):
    """
    Get real-time statistics for the landing page.
    """
    try:
        # Get trading tools count
        tools_dir = Path(__file__).parent.parent / "tools" / "trading"
        py_files = list(tools_dir.glob("*.py")) if tools_dir.exists() else []
        tool_files = [
            f for f in py_files
            if f.name not in ("__init__.py",) and not f.name.startswith("test_")
        ]

        # Count supported stocks from instruments cache
        from services.instruments_cache import symbol_count
        supported_stocks = symbol_count()

        return {
            "toolsCount": len(tool_files),
            "supportedStocks": supported_stocks,
            "paperTrading": True,
            "marketStatus": "Paper Trading Mode"
        }
    except Exception as e:
        # Return safe defaults on error
        return {
            "toolsCount": 5,
            "supportedStocks": 50,
            "paperTrading": True,
            "error": str(e)
        }
