"""
BFCM (Black Friday/Cyber Monday) Analytics Service
Provides multi-year comparison data for the BFCM tracker dashboard.
"""

import os
import sys
import json
import logging
import asyncio
import subprocess
from datetime import datetime, date, timedelta, timezone
from utils.datetime_utils import utc_now_naive
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BFCMAnalyticsCache, BFCMMilestone

# Import the MCP tools for GraphQL order queries
from mcp_tools.analytics.order_analytics import OrderAnalyticsTool

logger = logging.getLogger(__name__)

# BFCM date ranges per year (Thursday Thanksgiving through Wednesday)
BFCM_DATE_RANGES = {
    2022: ("2022-11-24", "2022-11-30"),  # Thu-Wed
    2023: ("2023-11-23", "2023-11-29"),  # Thu-Wed
    2024: ("2024-11-28", "2024-12-04"),  # Thu-Wed
    2025: ("2025-11-27", "2025-12-03"),  # Thu-Wed
}

# Revenue milestones for alerts (up to $1.5M)
REVENUE_MILESTONES = [100000, 250000, 500000, 750000, 1000000, 1250000, 1500000]

# Path to analytics.py bash tool
ANALYTICS_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "bash-tools", "analytics", "analytics.py"
)


class BFCMService:
    """Service for BFCM analytics with multi-year comparison support"""

    def __init__(self):
        self.date_ranges = BFCM_DATE_RANGES
        self.milestones = REVENUE_MILESTONES

    def get_bfcm_dates(self, year: int) -> Tuple[str, str]:
        """Get BFCM start and end dates for a given year"""
        if year in self.date_ranges:
            return self.date_ranges[year]
        # Estimate for future years (4th Thursday of November + 5 days)
        # This is a simplification - real dates would need calculation
        return (f"{year}-11-27", f"{year}-12-02")

    def is_bfcm_active(self, year: int = 2025) -> bool:
        """Check if we're currently in the BFCM period"""
        start_str, end_str = self.get_bfcm_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        today = date.today()
        return start <= today <= end

    async def execute_shopifyql(self, query: str) -> Dict[str, Any]:
        """Execute a ShopifyQL query via the analytics.py script"""
        try:
            logger.info(f"[BFCM] Executing ShopifyQL: {query[:100]}...")

            # Run analytics.py with the query
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, ANALYTICS_SCRIPT, query, "--output", "raw"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"[BFCM] ShopifyQL error: {result.stderr}")
                return {"error": result.stderr, "tableData": {"rows": []}}

            # Parse JSON output
            data = json.loads(result.stdout)
            return data

        except subprocess.TimeoutExpired:
            logger.error("[BFCM] ShopifyQL query timed out")
            return {"error": "Query timed out", "tableData": {"rows": []}}
        except json.JSONDecodeError as e:
            logger.error(f"[BFCM] Failed to parse ShopifyQL response: {e}")
            return {"error": str(e), "tableData": {"rows": []}}
        except Exception as e:
            logger.error(f"[BFCM] Error executing ShopifyQL: {e}")
            return {"error": str(e), "tableData": {"rows": []}}

    async def fetch_year_sales(self, year: int) -> Dict[str, Any]:
        """Fetch BFCM sales data for a specific year (ShopifyQL only - no GraphQL)"""
        start_date, end_date = self.get_bfcm_dates(year)

        # Query for daily sales via ShopifyQL
        sales_query = f"""
        FROM sales
        SHOW total_sales, gross_sales, net_sales
        GROUP BY day
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY day
        """

        sales_result = await self.execute_shopifyql(sales_query)

        if "error" in sales_result:
            logger.error(f"[BFCM] Error fetching {year} sales data: {sales_result['error']}")
            return {
                "year": year,
                "total_revenue": 0,
                "daily": [],
                "error": sales_result["error"]
            }

        # Parse the sales results
        table_data = sales_result.get("tableData", {})
        rows = table_data.get("rows", [])

        daily_data = []
        total_revenue = 0

        for row in rows:
            day_revenue = float(row.get("total_sales", 0) or 0)
            total_revenue += day_revenue
            daily_data.append({
                "date": row.get("day"),
                "revenue": day_revenue,
                "gross_sales": float(row.get("gross_sales", 0) or 0),
                "net_sales": float(row.get("net_sales", 0) or 0)
            })

        return {
            "year": year,
            "start_date": start_date,
            "end_date": end_date,
            "total_revenue": total_revenue,
            "daily": daily_data,
            "order_count": 0,  # Will be filled by parallel GraphQL call
            "aov": 0
        }

    async def fetch_year_data(self, year: int) -> Dict[str, Any]:
        """Fetch BFCM sales data for a specific year (ShopifyQL + GraphQL in parallel)"""
        # Run ShopifyQL and GraphQL in parallel
        sales_data, order_metrics = await asyncio.gather(
            self.fetch_year_sales(year),
            self.fetch_order_metrics(year)
        )

        # Merge the results
        sales_data["order_count"] = order_metrics["order_count"]
        sales_data["aov"] = order_metrics["aov"]

        # Calculate AOV as fallback if GraphQL failed but we have revenue
        if sales_data["aov"] == 0 and sales_data["order_count"] > 0:
            sales_data["aov"] = sales_data["total_revenue"] / sales_data["order_count"]

        return sales_data

    async def fetch_top_products(self, year: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch top products for BFCM period"""
        start_date, end_date = self.get_bfcm_dates(year)

        query = f"""
        FROM sales
        SHOW total_sales, quantity_ordered
        GROUP BY product_title
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY total_sales DESC
        LIMIT {limit}
        """

        result = await self.execute_shopifyql(query)

        if "error" in result:
            return []

        rows = result.get("tableData", {}).get("rows", [])
        products = []

        for row in rows:
            products.append({
                "title": row.get("product_title", "Unknown"),
                "revenue": float(row.get("total_sales", 0) or 0),
                "quantity": int(row.get("quantity_ordered", 0) or 0)
            })

        return products

    async def fetch_category_breakdown(self, year: int) -> List[Dict[str, Any]]:
        """Fetch revenue by product type/category"""
        start_date, end_date = self.get_bfcm_dates(year)

        query = f"""
        FROM sales
        SHOW total_sales
        GROUP BY product_type
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY total_sales DESC
        """

        result = await self.execute_shopifyql(query)

        if "error" in result:
            return []

        rows = result.get("tableData", {}).get("rows", [])
        categories = []

        for row in rows:
            categories.append({
                "category": row.get("product_type", "Other") or "Other",
                "revenue": float(row.get("total_sales", 0) or 0)
            })

        return categories

    def _parse_hour_value(self, hour_value) -> int:
        """Parse hour value from ShopifyQL - can be int or datetime string like '2022-11-24T05:00:00Z'"""
        if hour_value is None:
            return 0
        if isinstance(hour_value, int):
            return hour_value
        if isinstance(hour_value, str):
            # Handle datetime string format: '2022-11-24T05:00:00Z'
            if 'T' in hour_value:
                try:
                    dt = datetime.fromisoformat(hour_value.replace('Z', '+00:00'))
                    return dt.hour
                except (ValueError, AttributeError):
                    pass
            # Try parsing as plain integer string
            try:
                return int(hour_value)
            except ValueError:
                pass
        return 0

    async def fetch_hourly_data(self, year: int) -> List[Dict[str, Any]]:
        """Fetch hourly sales data for a BFCM period"""
        start_date, end_date = self.get_bfcm_dates(year)

        query = f"""
        FROM sales
        SHOW total_sales
        GROUP BY day, hour
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY day, hour
        """

        result = await self.execute_shopifyql(query)

        if "error" in result:
            logger.error(f"[BFCM] Error fetching hourly data for {year}: {result['error']}")
            return []

        rows = result.get("tableData", {}).get("rows", [])
        hourly_data = []

        for row in rows:
            hourly_data.append({
                "date": row.get("day"),
                "hour": self._parse_hour_value(row.get("hour")),
                "revenue": float(row.get("total_sales", 0) or 0)
            })

        return hourly_data

    def get_day_index(self, date_str: str, year: int) -> int:
        """Get the day index (0-5) within BFCM period (Thu=0, Fri=1, etc.)"""
        start_str, _ = self.get_bfcm_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        current = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (current - start).days

    def get_day_label(self, day_index: int) -> str:
        """Get day label from index"""
        labels = ["Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed"]
        return labels[day_index] if 0 <= day_index < len(labels) else f"Day {day_index + 1}"

    def get_day_name(self, day_index: int) -> str:
        """Get full day name from index"""
        names = [
            "Thanksgiving",
            "Black Friday",
            "Saturday",
            "Sunday",
            "Cyber Monday",
            "Tuesday",
            "Wednesday"
        ]
        return names[day_index] if 0 <= day_index < len(names) else f"Day {day_index + 1}"

    def get_equivalent_date(self, day_index: int, year: int) -> str:
        """Get the date for a given day index in a specific year"""
        start_str, _ = self.get_bfcm_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d")
        target = start + timedelta(days=day_index)
        return target.strftime("%Y-%m-%d")

    async def fetch_today_up_to_hour(self, year: int, day_index: int, hour: int) -> Dict[str, Any]:
        """Fetch sales for a specific day up to a specific hour"""
        target_date = self.get_equivalent_date(day_index, year)

        # ShopifyQL with datetime for hour precision
        # Format: UNTIL 2024-11-28T17:00:00
        query = f"""
        FROM sales
        SHOW total_sales
        SINCE {target_date}
        UNTIL {target_date}T{hour:02d}:59:59
        """

        result = await self.execute_shopifyql(query)

        if "error" in result:
            logger.error(f"[BFCM] Error fetching {year} day {day_index} up to hour {hour}: {result['error']}")
            return {"revenue": 0, "error": result["error"]}

        rows = result.get("tableData", {}).get("rows", [])
        total_revenue = sum(float(row.get("total_sales", 0) or 0) for row in rows)

        return {
            "year": year,
            "date": target_date,
            "hour": hour,
            "revenue": total_revenue
        }

    async def get_today_comparison(self, db: AsyncSession) -> Dict[str, Any]:
        """Compare today up to current hour vs same day/hour in previous years"""
        # Use EST timezone (America/Toronto) for iDrinkCoffee store
        try:
            from zoneinfo import ZoneInfo
            est_tz = ZoneInfo("America/Toronto")
        except ImportError:
            # Fallback for Python < 3.9
            est_tz = timezone(timedelta(hours=-5))  # EST without DST handling

        now = datetime.now(est_tz)
        years = [2022, 2023, 2024, 2025]

        # Get 2025 BFCM start date (in EST)
        start_2025_str, end_2025_str = self.get_bfcm_dates(2025)
        start_2025 = datetime.strptime(start_2025_str, "%Y-%m-%d").replace(tzinfo=est_tz)
        end_2025 = datetime.strptime(end_2025_str, "%Y-%m-%d").replace(tzinfo=est_tz)

        # Check if we're in BFCM period
        if now.date() < start_2025.date():
            return {
                "status": "not_started",
                "message": "BFCM 2025 has not started yet",
                "starts_at": start_2025_str
            }

        if now.date() > end_2025.date():
            return {
                "status": "ended",
                "message": "BFCM 2025 has ended",
                "ended_at": end_2025_str
            }

        # Calculate current day index (0-5) and hour (in EST)
        day_index = (now.date() - start_2025.date()).days
        current_hour = now.hour

        # Cap day_index at 6 (max 7 days)
        day_index = min(day_index, 6)

        logger.info(f"[BFCM] Today comparison: Day {day_index} ({self.get_day_name(day_index)}), Hour {current_hour}")

        # Fetch data for all years in parallel
        data_list = await asyncio.gather(*[
            self.fetch_today_up_to_hour(year, day_index, current_hour) for year in years
        ])

        comparison_data = []
        for data in data_list:
            data["day_name"] = self.get_day_name(day_index)
            data["day_label"] = self.get_day_label(day_index)
            comparison_data.append(data)

        # Calculate vs previous years
        current_2025 = next((d["revenue"] for d in comparison_data if d["year"] == 2025), 0)
        comparisons = []

        for year in [2024, 2023, 2022]:
            year_revenue = next((d["revenue"] for d in comparison_data if d["year"] == year), 0)
            if year_revenue > 0:
                diff = current_2025 - year_revenue
                pct = ((current_2025 - year_revenue) / year_revenue) * 100
                comparisons.append({
                    "year": year,
                    "revenue": year_revenue,
                    "difference": diff,
                    "percent_change": round(pct, 1),
                    "ahead": diff > 0
                })
            else:
                comparisons.append({
                    "year": year,
                    "revenue": 0,
                    "difference": current_2025,
                    "percent_change": None,
                    "ahead": True
                })

        return {
            "status": "active",
            "day_index": day_index,
            "day_name": self.get_day_name(day_index),
            "day_label": self.get_day_label(day_index),
            "current_hour": current_hour,
            "current_2025": current_2025,
            "data": comparison_data,
            "comparisons": comparisons,
            "timestamp": now.isoformat()
        }

    async def get_day_comparison(self, db: AsyncSession) -> Dict[str, Any]:
        """Get day-by-day comparison across all years"""
        years = [2022, 2023, 2024, 2025]
        day_data = {i: {} for i in range(7)}  # 7 days of BFCM

        # Fetch all years in parallel
        year_data_list = await asyncio.gather(*[self.fetch_year_data(year) for year in years])

        for year, year_data in zip(years, year_data_list):
            daily = year_data.get("daily", [])

            for entry in daily:
                date_str = entry.get("date")
                if date_str:
                    day_idx = self.get_day_index(date_str, year)
                    if 0 <= day_idx < 7:
                        day_data[day_idx][str(year)] = {
                            "revenue": entry.get("revenue", 0),
                            "date": date_str
                        }

        # Format for chart consumption
        comparison = []
        for day_idx in range(7):
            day_entry = {
                "day_index": day_idx,
                "day_label": self.get_day_label(day_idx),
                "day_name": self.get_day_name(day_idx),
            }
            for year in years:
                year_str = str(year)
                if year_str in day_data[day_idx]:
                    day_entry[year_str] = day_data[day_idx][year_str]["revenue"]
                else:
                    day_entry[year_str] = 0

            comparison.append(day_entry)

        return {
            "days": comparison,
            "years": years,
            "day_labels": [self.get_day_label(i) for i in range(7)],
            "day_names": [self.get_day_name(i) for i in range(7)]
        }

    async def get_hourly_comparison(self, db: AsyncSession) -> Dict[str, Any]:
        """Get hourly cumulative comparison (pace) across all years"""
        years = [2022, 2023, 2024, 2025]

        # Use EST timezone (America/Toronto) for iDrinkCoffee store
        try:
            from zoneinfo import ZoneInfo
            est_tz = ZoneInfo("America/Toronto")
        except ImportError:
            est_tz = timezone(timedelta(hours=-5))

        # Calculate current position in BFCM 2025 (in EST)
        now = datetime.now(est_tz)
        start_2025_str, _ = self.get_bfcm_dates(2025)
        start_2025 = datetime.strptime(start_2025_str, "%Y-%m-%d").replace(tzinfo=est_tz)

        # Hours elapsed since start of BFCM 2025 (midnight EST on start day)
        if now >= start_2025:
            hours_elapsed = int((now - start_2025).total_seconds() / 3600)
        else:
            hours_elapsed = 0

        # Cap at max hours (7 days * 24 hours = 168 hours)
        max_hours = 7 * 24
        hours_elapsed = min(hours_elapsed, max_hours)

        # Fetch hourly data for all years in parallel
        hourly_data_list = await asyncio.gather(*[self.fetch_hourly_data(year) for year in years])
        all_hourly = dict(zip(years, hourly_data_list))

        # Build cumulative data by hour offset from start
        cumulative_by_year = {year: [] for year in years}

        for year in years:
            hourly = all_hourly[year]
            start_str, _ = self.get_bfcm_dates(year)
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()

            # Group by hour offset
            hourly_revenue = {}
            for entry in hourly:
                entry_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                day_offset = (entry_date - start_date).days
                hour_offset = day_offset * 24 + entry["hour"]
                hourly_revenue[hour_offset] = entry["revenue"]

            # Build cumulative series
            cumulative = 0
            for hour in range(max_hours):
                cumulative += hourly_revenue.get(hour, 0)
                cumulative_by_year[year].append({
                    "hour": hour,
                    "revenue": cumulative
                })

        # Build comparison data points (every 4 hours for readability)
        pace_data = []
        for hour in range(0, max_hours, 4):
            point = {
                "hour": hour,
                "label": f"Day {hour // 24 + 1}, {hour % 24}:00"
            }
            for year in years:
                if hour < len(cumulative_by_year[year]):
                    point[str(year)] = cumulative_by_year[year][hour]["revenue"]
                else:
                    point[str(year)] = 0
            pace_data.append(point)

        # Get current pace comparison (at same hour mark)
        current_pace = {}
        if hours_elapsed > 0:
            for year in years:
                # Get revenue at same hour mark
                if hours_elapsed < len(cumulative_by_year[year]):
                    current_pace[str(year)] = cumulative_by_year[year][hours_elapsed - 1]["revenue"]
                else:
                    # Year data ended, use final value
                    current_pace[str(year)] = cumulative_by_year[year][-1]["revenue"] if cumulative_by_year[year] else 0

        return {
            "pace_data": pace_data,
            "current_hour": hours_elapsed,
            "current_pace": current_pace,
            "years": years,
            "is_live": self.is_bfcm_active(2025)
        }

    async def get_pace_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get a summary of current pace vs previous years"""
        hourly_comparison = await self.get_hourly_comparison(db)
        current_pace = hourly_comparison.get("current_pace", {})
        current_hour = hourly_comparison.get("current_hour", 0)

        if not current_pace or current_hour == 0:
            return {
                "summary": "BFCM has not started yet",
                "comparisons": [],
                "current_hour": 0
            }

        current_2025 = current_pace.get("2025", 0)
        comparisons = []

        for year in ["2024", "2023", "2022"]:
            year_value = current_pace.get(year, 0)
            if year_value > 0:
                diff = current_2025 - year_value
                pct_change = ((current_2025 - year_value) / year_value) * 100 if year_value > 0 else 0
                comparisons.append({
                    "year": int(year),
                    "value_at_same_point": year_value,
                    "difference": diff,
                    "percent_change": round(pct_change, 1),
                    "ahead": diff > 0
                })

        # Day and hour breakdown
        day_num = (current_hour // 24) + 1
        hour_of_day = current_hour % 24

        return {
            "summary": f"At hour {current_hour} (Day {day_num}, {hour_of_day}:00), 2025 is at ${current_2025:,.0f}",
            "current_2025": current_2025,
            "current_hour": current_hour,
            "day_number": day_num,
            "hour_of_day": hour_of_day,
            "comparisons": comparisons
        }

    async def get_cached_data(
        self, db: AsyncSession, year: int
    ) -> Optional[Dict[str, Any]]:
        """Get cached BFCM data for a year"""
        start_str, end_str = self.get_bfcm_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")

        # Calculate expected number of days (inclusive)
        expected_days = (end - start).days + 1  # Should be 7 days

        # Query all cached data for this year's BFCM period
        result = await db.execute(
            select(BFCMAnalyticsCache).where(
                and_(
                    BFCMAnalyticsCache.year == year,
                    BFCMAnalyticsCache.date >= start,
                    BFCMAnalyticsCache.date <= end,
                    BFCMAnalyticsCache.hour.is_(None)  # Daily aggregates only
                )
            ).order_by(BFCMAnalyticsCache.date)
        )
        rows = result.scalars().all()

        # Return None if no cache or incomplete cache (missing days like Wednesday)
        if not rows or len(rows) < expected_days:
            if rows:
                logger.info(f"[BFCM] Cache incomplete for {year}: {len(rows)}/{expected_days} days, will re-fetch")
            return None

        # Aggregate the cached data
        total_revenue = sum(row.revenue or 0 for row in rows)
        total_orders = sum(row.order_count or 0 for row in rows)
        daily_data = [
            {
                "date": row.date.strftime("%Y-%m-%d"),
                "revenue": float(row.revenue or 0),
                "orders": row.order_count or 0
            }
            for row in rows
        ]

        # Get top products from the most recent cached entry
        top_products = rows[-1].top_products if rows else []
        category_breakdown = rows[-1].category_breakdown if rows else []

        return {
            "year": year,
            "start_date": start_str,
            "end_date": end_str,
            "total_revenue": float(total_revenue),
            "order_count": total_orders,
            "aov": float(total_revenue / total_orders) if total_orders > 0 else 0,
            "daily": daily_data,
            "top_products": top_products or [],
            "category_breakdown": category_breakdown or [],
            "cached": True
        }

    async def save_to_cache(
        self, db: AsyncSession, year: int, data: Dict[str, Any]
    ) -> None:
        """Save BFCM data to cache"""
        for day_data in data.get("daily", []):
            day_date = datetime.strptime(day_data["date"], "%Y-%m-%d")

            # Check if entry exists
            result = await db.execute(
                select(BFCMAnalyticsCache).where(
                    and_(
                        BFCMAnalyticsCache.year == year,
                        BFCMAnalyticsCache.date == day_date,
                        BFCMAnalyticsCache.hour.is_(None)
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing entry
                existing.revenue = day_data.get("revenue", 0)
                existing.order_count = day_data.get("orders", 0)
                existing.top_products = data.get("top_products")
                existing.category_breakdown = data.get("category_breakdown")
                existing.is_live = (year == 2025)
                existing.updated_at = utc_now_naive()
            else:
                # Create new entry
                cache_entry = BFCMAnalyticsCache(
                    year=year,
                    date=day_date,
                    hour=None,
                    revenue=day_data.get("revenue", 0),
                    order_count=day_data.get("orders", 0),
                    aov=day_data.get("aov", 0),
                    top_products=data.get("top_products"),
                    category_breakdown=data.get("category_breakdown"),
                    is_live=(year == 2025)
                )
                db.add(cache_entry)

        await db.commit()

    async def fetch_order_metrics(self, year: int) -> Dict[str, Any]:
        """Fetch order count and AOV via GraphQL for a year"""
        start_date, end_date = self.get_bfcm_dates(year)
        order_count = 0
        aov = 0

        try:
            order_tool = OrderAnalyticsTool()
            order_result = await order_tool.execute(
                start_date=start_date,
                end_date=end_date,
                include_products=False
            )

            if order_result.get("success") and order_result.get("data"):
                summary = order_result["data"].get("summary", {})
                order_count = summary.get("order_count", 0)
                aov = summary.get("average_order_value", 0)
                logger.info(f"[BFCM] {year} GraphQL orders: {order_count} orders, AOV: ${aov}")
        except Exception as e:
            logger.error(f"[BFCM] Error fetching {year} GraphQL orders: {e}")

        return {"order_count": order_count, "aov": aov}

    async def _fetch_fresh_year_data(self, year: int) -> Tuple[int, Dict[str, Any]]:
        """Fetch fresh data for a single year from APIs (no database - safe for parallel)"""
        # Parallelize year_data, top_products, and categories API calls
        data, top_products, categories = await asyncio.gather(
            self.fetch_year_data(year),
            self.fetch_top_products(year),
            self.fetch_category_breakdown(year)
        )

        data["top_products"] = top_products
        data["category_breakdown"] = categories
        data["cached"] = False

        return (year, data)

    async def get_all_years_comparison(
        self, db: AsyncSession
    ) -> Dict[str, Any]:
        """Get comparison data for all BFCM years (2022-2025)"""
        years = [2022, 2023, 2024, 2025]
        years_data = {}
        years_to_fetch = []

        # Step 1: Check cache SEQUENTIALLY (database operations)
        for year in years:
            if year < 2025:
                cached = await self.get_cached_data(db, year)
                if cached:
                    years_data[str(year)] = cached
                    continue
            years_to_fetch.append(year)

        # Step 2: Fetch fresh data IN PARALLEL (API calls only - no database)
        if years_to_fetch:
            results = await asyncio.gather(*[
                self._fetch_fresh_year_data(year) for year in years_to_fetch
            ])
            for year, data in results:
                years_data[str(year)] = data

        # Step 3: Fetch order metrics for cached years with missing order counts IN PARALLEL
        years_needing_orders = [
            int(year) for year, data in years_data.items()
            if data.get("cached") and data.get("order_count", 0) == 0
        ]
        if years_needing_orders:
            order_metrics_list = await asyncio.gather(*[
                self.fetch_order_metrics(year) for year in years_needing_orders
            ])
            for year, metrics in zip(years_needing_orders, order_metrics_list):
                years_data[str(year)]["order_count"] = metrics["order_count"]
                years_data[str(year)]["aov"] = metrics["aov"]

        # Step 4: Cache new data SEQUENTIALLY (database operations)
        for year in years_to_fetch:
            year_str = str(year)
            if year < 2025 and years_data.get(year_str, {}).get("daily"):
                await self.save_to_cache(db, year, years_data[year_str])

        # Calculate YoY comparisons
        yoy_comparisons = self._calculate_yoy(years_data)

        return {
            "years": years_data,
            "yoy_comparison": yoy_comparisons
        }

    def _calculate_yoy(self, years_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate year-over-year growth percentages"""
        comparisons = {}
        years = ["2025", "2024", "2023", "2022"]

        for i in range(len(years) - 1):
            current_year = years[i]
            previous_year = years[i + 1]

            current_revenue = years_data.get(current_year, {}).get("total_revenue", 0)
            previous_revenue = years_data.get(previous_year, {}).get("total_revenue", 0)

            if previous_revenue > 0:
                growth = ((current_revenue - previous_revenue) / previous_revenue) * 100
                comparisons[f"{current_year}_vs_{previous_year}"] = round(growth, 1)
            else:
                comparisons[f"{current_year}_vs_{previous_year}"] = None

        return comparisons

    async def get_milestones(
        self, db: AsyncSession, year: int = 2025
    ) -> List[Dict[str, Any]]:
        """Get milestone status for a year"""
        result = await db.execute(
            select(BFCMMilestone).where(
                BFCMMilestone.year == year
            ).order_by(BFCMMilestone.threshold)
        )
        milestones = result.scalars().all()

        return [
            {
                "threshold": float(m.threshold),
                "achieved": m.achieved,
                "achieved_at": m.achieved_at.isoformat() if m.achieved_at else None,
                "notified": m.notified
            }
            for m in milestones
        ]

    async def check_and_update_milestones(
        self, db: AsyncSession, current_revenue: float, year: int = 2025
    ) -> List[Dict[str, Any]]:
        """Check if any new milestones have been achieved"""
        newly_achieved = []

        result = await db.execute(
            select(BFCMMilestone).where(
                and_(
                    BFCMMilestone.year == year,
                    BFCMMilestone.achieved == False
                )
            ).order_by(BFCMMilestone.threshold)
        )
        pending_milestones = result.scalars().all()

        for milestone in pending_milestones:
            if current_revenue >= float(milestone.threshold):
                milestone.achieved = True
                milestone.achieved_at = utc_now_naive()
                newly_achieved.append({
                    "threshold": float(milestone.threshold),
                    "achieved_at": milestone.achieved_at.isoformat()
                })

        if newly_achieved:
            await db.commit()

        return newly_achieved

    async def mark_milestone_notified(
        self, db: AsyncSession, threshold: float, year: int = 2025
    ) -> None:
        """Mark a milestone as notified (toast shown)"""
        result = await db.execute(
            select(BFCMMilestone).where(
                and_(
                    BFCMMilestone.year == year,
                    BFCMMilestone.threshold == threshold
                )
            )
        )
        milestone = result.scalar_one_or_none()

        if milestone:
            milestone.notified = True
            await db.commit()

    async def get_dashboard_data(
        self, db: AsyncSession
    ) -> Dict[str, Any]:
        """Get complete BFCM dashboard data"""
        # Get all years comparison
        comparison_data = await self.get_all_years_comparison(db)

        # Get current year data
        current_year = 2025
        current_data = comparison_data["years"].get(str(current_year), {})

        # Get milestones
        milestones = await self.get_milestones(db, current_year)

        # Check for newly achieved milestones
        current_revenue = current_data.get("total_revenue", 0)
        newly_achieved = await self.check_and_update_milestones(
            db, current_revenue, current_year
        )

        # Calculate next milestone ETA (simple linear projection)
        next_milestone = None
        for m in milestones:
            if not m["achieved"]:
                next_milestone = m["threshold"]
                break

        eta = None
        if next_milestone and current_revenue > 0:
            # Get hours elapsed in BFCM period
            start_str, _ = self.get_bfcm_dates(current_year)
            start = datetime.strptime(start_str, "%Y-%m-%d")
            now = utc_now_naive()
            hours_elapsed = (now - start.replace(tzinfo=timezone.utc)).total_seconds() / 3600

            if hours_elapsed > 0:
                revenue_per_hour = current_revenue / hours_elapsed
                if revenue_per_hour > 0:
                    hours_to_milestone = (next_milestone - current_revenue) / revenue_per_hour
                    eta = (now + timedelta(hours=hours_to_milestone)).isoformat()

        return {
            "current_year": current_year,
            "is_live": self.is_bfcm_active(current_year),
            "years": comparison_data["years"],
            "yoy_comparison": comparison_data["yoy_comparison"],
            "milestones": milestones,
            "newly_achieved_milestones": newly_achieved,
            "next_milestone": {
                "threshold": next_milestone,
                "eta": eta
            } if next_milestone else None,
            "last_updated": utc_now_naive().isoformat(),
            "next_refresh": (utc_now_naive() + timedelta(minutes=5)).isoformat()
        }

    async def get_live_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """Get lightweight live metrics for 5-minute polling"""
        current_year = 2025

        # Fetch current year data only
        data = await self.fetch_year_data(current_year)
        top_products = await self.fetch_top_products(current_year, limit=5)

        # Get milestones
        milestones = await self.get_milestones(db, current_year)

        # Check for newly achieved milestones
        current_revenue = data.get("total_revenue", 0)
        newly_achieved = await self.check_and_update_milestones(
            db, current_revenue, current_year
        )

        return {
            "year": current_year,
            "total_revenue": data.get("total_revenue", 0),
            "order_count": data.get("order_count", 0),
            "aov": data.get("aov", 0),
            "top_products": top_products,
            "milestones": milestones,
            "newly_achieved_milestones": newly_achieved,
            "last_updated": utc_now_naive().isoformat()
        }

    async def backfill_historical_year(
        self, db: AsyncSession, year: int
    ) -> Dict[str, Any]:
        """Backfill historical BFCM data (admin function)"""
        if year >= 2025:
            return {"error": "Cannot backfill current or future years"}

        logger.info(f"[BFCM] Backfilling data for {year}...")

        # Fetch all data
        data = await self.fetch_year_data(year)
        top_products = await self.fetch_top_products(year)
        categories = await self.fetch_category_breakdown(year)

        data["top_products"] = top_products
        data["category_breakdown"] = categories

        # Save to cache
        await self.save_to_cache(db, year, data)

        return {
            "year": year,
            "total_revenue": data.get("total_revenue", 0),
            "days_cached": len(data.get("daily", [])),
            "top_products_count": len(top_products),
            "categories_count": len(categories)
        }


# Global service instance
_bfcm_service: Optional[BFCMService] = None


def get_bfcm_service() -> BFCMService:
    """Get or create the global BFCM service"""
    global _bfcm_service

    if _bfcm_service is None:
        _bfcm_service = BFCMService()

    return _bfcm_service
