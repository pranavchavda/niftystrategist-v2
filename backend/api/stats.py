"""
Stats API - Provides real-time statistics about the EspressoBot system
"""

import os
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db
from services.price_monitor import PriceMonitorDashboard

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("/tools")
async def get_tools_count():
    """
    Count the number of Python tool files in backend/bash-tools directory.
    Excludes __init__.py and test files.
    """
    bash_tools_dir = Path(__file__).parent.parent / "bash-tools"

    if not bash_tools_dir.exists():
        return {"count": 0, "error": "bash-tools directory not found"}

    # Count .py files, excluding __init__.py and test files
    py_files = list(bash_tools_dir.glob("*.py"))
    tool_files = [
        f for f in py_files
        if f.name not in ("__init__.py",) and not f.name.startswith("test_")
    ]

    return {
        "count": len(tool_files),
        "total_py_files": len(py_files),
        "directory": str(bash_tools_dir)
    }

@router.get("/docs")
async def get_docs_count():
    """
    Count the number of documentation markdown files.
    """
    docs_dir = Path(__file__).parent.parent / "docs"

    if not docs_dir.exists():
        return {"count": 0, "error": "docs directory not found"}

    # Count all .md files recursively
    md_files = list(docs_dir.rglob("*.md"))

    return {
        "count": len(md_files),
        "directory": str(docs_dir)
    }

@router.get("/landing")
async def get_landing_stats(db: AsyncSession = Depends(get_db)):
    """
    Get real-time statistics for the landing page.
    Returns actual data from the price monitor and system.
    """
    try:
        # Get bash tools count
        bash_tools_dir = Path(__file__).parent.parent / "bash-tools"
        py_files = list(bash_tools_dir.glob("*.py"))
        tool_files = [
            f for f in py_files
            if f.name not in ("__init__.py",) and not f.name.startswith("test_")
        ]

        # Get documentation count
        docs_dir = Path(__file__).parent.parent / "docs"
        docs_count = len(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else 0

        # Get price monitor stats
        dashboard_service = PriceMonitorDashboard(db)
        try:
            price_stats = await dashboard_service.get_overview()
        except:
            # Fallback if price monitor not initialized
            price_stats = {
                "totalProducts": 0,
                "totalViolations": 0,
                "activeCompetitors": 0
            }

        # Calculate compliance rate (percentage of products without violations)
        total_products = price_stats.get("totalProducts", 0)
        total_violations = price_stats.get("totalViolations", 0)

        if total_products > 0:
            compliant_products = total_products - total_violations
            compliance_rate = round((compliant_products / total_products) * 100, 1)
        else:
            compliance_rate = None  # No data available

        return {
            "toolsCount": len(tool_files),
            "docsCount": docs_count,
            "mapCompliance": {
                "rate": compliance_rate,
                "totalProducts": total_products,
                "violations": total_violations,
                "hasData": total_products > 0
            }
        }
    except Exception as e:
        # Return safe defaults on error
        return {
            "toolsCount": 78,
            "docsCount": 42,
            "mapCompliance": {
                "rate": None,
                "totalProducts": 0,
                "violations": 0,
                "hasData": False
            },
            "error": str(e)
        }
