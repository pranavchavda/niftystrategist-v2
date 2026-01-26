"""
Boxing Week Analytics Service
Provides multi-year comparison data for the Boxing Week tracker dashboard.
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

from database.models import BoxingWeekAnalyticsCache, BoxingWeekMilestone

# Import the MCP tools for GraphQL order queries
from mcp_tools.analytics.order_analytics import OrderAnalyticsTool

logger = logging.getLogger(__name__)

# Boxing Week date ranges per year (Dec 24 - Jan 5)
# Including Dec 24 for "pre-Boxing Day" traffic, and extending into Jan
BOXING_WEEK_DATE_RANGES = {
    2022: ("2022-12-23", "2023-01-05"),
    2023: ("2023-12-23", "2024-01-05"),
    2024: ("2024-12-23", "2025-01-05"),
    2025: ("2025-12-23", "2026-01-05"),
}

# Revenue milestones for alerts (up to $1M)
REVENUE_MILESTONES = [50000, 100000, 250000, 400000, 500000, 750000, 1000000]

# Path to analytics.py bash tool
ANALYTICS_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "bash-tools", "analytics", "analytics.py"
)


class BoxingWeekService:
    """Service for Boxing Week analytics with multi-year comparison support"""

    def __init__(self):
        self.date_ranges = BOXING_WEEK_DATE_RANGES
        self.milestones = REVENUE_MILESTONES

    def get_boxing_week_dates(self, year: int) -> Tuple[str, str]:
        """Get Boxing Week start and end dates for a given year"""
        if year in self.date_ranges:
            return self.date_ranges[year]
        # Estimate for future years (Dec 23 - Jan 5)
        return (f"{year}-12-23", f"{year + 1}-01-05")

    def is_boxing_week_active(self, year: int = 2025) -> bool:
        """Check if we're currently in the Boxing Week period"""
        start_str, end_str = self.get_boxing_week_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        today = date.today()
        return start <= today <= end

    async def execute_shopifyql(self, query: str) -> List[Dict[str, Any]]:
        """Execute a ShopifyQL query via the analytics.py script"""
        try:
            logger.info(f"[BoxingWeek] Executing ShopifyQL: {query[:100]}...")

            # Run analytics.py with the query
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, ANALYTICS_SCRIPT, query, "--output", "json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"[BoxingWeek] ShopifyQL error: {result.stderr}")
                return []

            # Parse JSON output
            data = json.loads(result.stdout)
            # data is a list of records from analytics.py --output json
            return data

        except subprocess.TimeoutExpired:
            logger.error("[BoxingWeek] ShopifyQL query timed out")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"[BoxingWeek] Failed to parse ShopifyQL response: {e}")
            return []
        except Exception as e:
            logger.error(f"[BoxingWeek] Error executing ShopifyQL: {e}")
            return []

    async def fetch_year_sales(self, year: int) -> Dict[str, Any]:
        """Fetch Boxing Week sales data for a specific year (ShopifyQL only - no GraphQL)"""
        start_date, end_date = self.get_boxing_week_dates(year)

        # Query for daily sales via ShopifyQL
        sales_query = f"""
        FROM sales
        SHOW total_sales, gross_sales, net_sales
        GROUP BY day
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY day
        """

        rows = await self.execute_shopifyql(sales_query)

        if not rows and "error" in str(rows): # This check is redundant with new return type but keeping safety
             return {
                "year": year,
                "total_revenue": 0,
                "daily": [],
            }

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
        """Fetch Boxing Week sales data for a specific year (ShopifyQL + GraphQL in parallel)"""
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
        """Fetch top products for Boxing Week period"""
        start_date, end_date = self.get_boxing_week_dates(year)

        query = f"""
        FROM sales
        SHOW total_sales, quantity_ordered
        GROUP BY product_title
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY total_sales DESC
        LIMIT {limit}
        """

        rows = await self.execute_shopifyql(query)

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
        start_date, end_date = self.get_boxing_week_dates(year)

        query = f"""
        FROM sales
        SHOW total_sales
        GROUP BY product_type
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY total_sales DESC
        """

        rows = await self.execute_shopifyql(query)

        categories = []

        for row in rows:
            categories.append({
                "category": row.get("product_type", "Other") or "Other",
                "revenue": float(row.get("total_sales", 0) or 0)
            })

        return categories

    def _parse_hour_value(self, hour_value) -> int:
        """Parse hour value from ShopifyQL"""
        if hour_value is None:
            return 0
        if isinstance(hour_value, int):
            return hour_value
        if isinstance(hour_value, str):
            if 'T' in hour_value:
                try:
                    dt = datetime.fromisoformat(hour_value.replace('Z', '+00:00'))
                    return dt.hour
                except (ValueError, AttributeError):
                    pass
            try:
                return int(hour_value)
            except ValueError:
                pass
        return 0

    async def fetch_hourly_data(self, year: int) -> List[Dict[str, Any]]:
        """Fetch hourly sales data for a Boxing Week period"""
        start_date, end_date = self.get_boxing_week_dates(year)

        query = f"""
        FROM sales
        SHOW total_sales
        GROUP BY day, hour
        SINCE {start_date}
        UNTIL {end_date}
        ORDER BY day, hour
        """

        rows = await self.execute_shopifyql(query)

        hourly_data = []

        for row in rows:
            hourly_data.append({
                "date": row.get("day"),
                "hour": self._parse_hour_value(row.get("hour")),
                "revenue": float(row.get("total_sales", 0) or 0)
            })

        return hourly_data

    def get_day_index(self, date_str: str, year: int) -> int:
        """Get the day index (0-12) within Boxing Week period (13 days)"""
        start_str, _ = self.get_boxing_week_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        current = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (current - start).days

    def get_day_label(self, day_index: int) -> str:
        """Get day label from index"""
        # Dec 23 = Day 0
        # Dec 24 = Day 1
        # Dec 25 = Day 2
        # Dec 26 = Day 3 (Boxing Day)
        # ...
        # Jan 5 = Day 13
        if day_index == 0:
            return "Dec 23"
        elif day_index == 1:
            return "Dec 24"
        elif day_index == 2:
            return "Dec 25"
        elif day_index == 3:
            return "Dec 26"
        elif day_index == 8:
            return "Dec 31"
        elif day_index == 9:
            return "Jan 1"
        
        # Calculate date label based on index
        # Assuming Dec 23 start
        d = date(2022, 12, 23) + timedelta(days=day_index)
        return d.strftime("%b %d")

    def get_day_name(self, day_index: int) -> str:
        """Get full day name from index"""
        if day_index == 0:
            return "Dec 23"
        elif day_index == 1:
            return "Christmas Eve"
        elif day_index == 2:
            return "Christmas Day"
        elif day_index == 3:
            return "Boxing Day"
        elif day_index == 8:
            return "New Year's Eve"
        elif day_index == 9:
            return "New Year's Day"
        
        return self.get_day_label(day_index)

    def get_equivalent_date(self, day_index: int, year: int) -> str:
        """Get the date for a given day index in a specific year"""
        start_str, _ = self.get_boxing_week_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d")
        target = start + timedelta(days=day_index)
        return target.strftime("%Y-%m-%d")

    async def fetch_today_up_to_hour(self, year: int, day_index: int, hour: int) -> Dict[str, Any]:
        """Fetch sales for a specific day up to a specific hour"""
        target_date = self.get_equivalent_date(day_index, year)

        # ShopifyQL with datetime for hour precision
        query = f"""
        FROM sales
        SHOW total_sales
        SINCE {target_date}
        UNTIL {target_date}T{hour:02d}:59:59
        """

        rows = await self.execute_shopifyql(query)

        total_revenue = sum(float(row.get("total_sales", 0) or 0) for row in rows)

        return {
            "year": year,
            "date": target_date,
            "hour": hour,
            "revenue": total_revenue
        }

    async def get_today_comparison(self, db: AsyncSession) -> Dict[str, Any]:
        """Compare today up to current hour vs same day/hour in previous years"""
        # Use EST timezone (America/Toronto)
        try:
            from zoneinfo import ZoneInfo
            est_tz = ZoneInfo("America/Toronto")
        except ImportError:
            est_tz = timezone(timedelta(hours=-5))

        now = datetime.now(est_tz)
        years = [2022, 2023, 2024, 2025]

        # Get 2025 Boxing Week start date
        start_2025_str, end_2025_str = self.get_boxing_week_dates(2025)
        start_2025 = datetime.strptime(start_2025_str, "%Y-%m-%d").replace(tzinfo=est_tz)
        end_2025 = datetime.strptime(end_2025_str, "%Y-%m-%d").replace(tzinfo=est_tz)
        end_2025 = end_2025 + timedelta(days=1) # Include the end date fully

        # Check if we're in Boxing Week period
        # If BEFORE start, show Not Started
        if now < start_2025:
             # Just for testing purposes or pre-launch, check if it's close?
             return {
                "status": "not_started",
                "message": "Boxing Week 2025 has not started yet",
                "starts_at": start_2025_str
            }

        if now > end_2025:
            return {
                "status": "ended",
                "message": "Boxing Week 2025 has ended",
                "ended_at": end_2025_str
            }

        # Calculate current day index (0-12) and hour
        day_index = (now.date() - start_2025.date()).days
        current_hour = now.hour

        # Cap day_index at 13 (14 days total)
        day_index = min(day_index, 13)

        logger.info(f"[BoxingWeek] Today comparison: Day {day_index} ({self.get_day_name(day_index)}), Hour {current_hour}")

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
        days_count = 14 # Dec 23 to Jan 5 = 14 days
        day_data = {i: {} for i in range(days_count)}

        # Fetch all years in parallel
        year_data_list = await asyncio.gather(*[self.fetch_year_data(year) for year in years])

        for year, year_data in zip(years, year_data_list):
            daily = year_data.get("daily", [])

            for entry in daily:
                date_str = entry.get("date")
                if date_str:
                    day_idx = self.get_day_index(date_str, year)
                    if 0 <= day_idx < days_count:
                        day_data[day_idx][str(year)] = {
                            "revenue": entry.get("revenue", 0),
                            "date": date_str
                        }

        # Format for chart consumption
        comparison = []
        for day_idx in range(days_count):
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
            "day_labels": [self.get_day_label(i) for i in range(days_count)],
            "day_names": [self.get_day_name(i) for i in range(days_count)]
        }

    async def get_hourly_comparison(self, db: AsyncSession) -> Dict[str, Any]:
        """Get hourly cumulative comparison (pace) across all years"""
        years = [2022, 2023, 2024, 2025]

        # Use EST timezone
        try:
            from zoneinfo import ZoneInfo
            est_tz = ZoneInfo("America/Toronto")
        except ImportError:
            est_tz = timezone(timedelta(hours=-5))

        # Calculate current position in Boxing Week 2025
        now = datetime.now(est_tz)
        start_2025_str, _ = self.get_boxing_week_dates(2025)
        start_2025 = datetime.strptime(start_2025_str, "%Y-%m-%d").replace(tzinfo=est_tz)

        # Hours elapsed since start of Boxing Week 2025 (midnight EST on Dec 24)
        if now >= start_2025:
            hours_elapsed = int((now - start_2025).total_seconds() / 3600)
        else:
            hours_elapsed = 0

        # Cap at max hours (14 days * 24 hours = 336 hours)
        max_hours = 14 * 24
        hours_elapsed = min(hours_elapsed, max_hours)

        # Fetch hourly data for all years in parallel
        hourly_data_list = await asyncio.gather(*[self.fetch_hourly_data(year) for year in years])
        all_hourly = dict(zip(years, hourly_data_list))

        # Build cumulative data by hour offset from start
        cumulative_by_year = {year: [] for year in years}

        for year in years:
            hourly = all_hourly[year]
            start_str, _ = self.get_boxing_week_dates(year)
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()

            # Group by hour offset
            hourly_revenue = {}
            for entry in hourly:
                try:
                    entry_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                    day_offset = (entry_date - start_date).days
                    hour_offset = day_offset * 24 + entry["hour"]
                    hourly_revenue[hour_offset] = entry["revenue"]
                except Exception as e:
                    logger.warning(f"Error parsing date {entry.get('date')}: {e}")

            # Build cumulative series
            cumulative = 0
            for hour in range(max_hours):
                cumulative += hourly_revenue.get(hour, 0)
                cumulative_by_year[year].append({
                    "hour": hour,
                    "revenue": cumulative
                })

        # Build comparison data points (every 6 hours for readability, spanning longer period)
        pace_data = []
        for hour in range(0, max_hours, 6):
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
                if hours_elapsed < len(cumulative_by_year[year]):
                    current_pace[str(year)] = cumulative_by_year[year][hours_elapsed - 1]["revenue"]
                else:
                    current_pace[str(year)] = cumulative_by_year[year][-1]["revenue"] if cumulative_by_year[year] else 0

        return {
            "pace_data": pace_data,
            "current_hour": hours_elapsed,
            "current_pace": current_pace,
            "years": years,
            "is_live": self.is_boxing_week_active(2025)
        }

    async def get_pace_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get a summary of current pace vs previous years"""
        hourly_comparison = await self.get_hourly_comparison(db)
        current_pace = hourly_comparison.get("current_pace", {})
        current_hour = hourly_comparison.get("current_hour", 0)

        if not current_pace or current_hour == 0:
            return {
                "summary": "Boxing Week has not started yet",
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
        """Get cached Boxing Week data for a year"""
        start_str, end_str = self.get_boxing_week_dates(year)
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")

        # Calculate expected number of days
        expected_days = (end - start).days + 1

        # Query all cached data for this year's period
        result = await db.execute(
            select(BoxingWeekAnalyticsCache).where(
                and_(
                    BoxingWeekAnalyticsCache.year == year,
                    BoxingWeekAnalyticsCache.date >= start,
                    BoxingWeekAnalyticsCache.date <= end,
                    BoxingWeekAnalyticsCache.hour.is_(None)
                )
            ).order_by(BoxingWeekAnalyticsCache.date)
        )
        rows = result.scalars().all()

        if not rows or len(rows) < expected_days:
            if rows:
                logger.info(f"[BoxingWeek] Cache incomplete for {year}: {len(rows)}/{expected_days} days, will re-fetch")
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
        """Save Boxing Week data to cache"""
        for day_data in data.get("daily", []):
            try:
                day_date = datetime.strptime(day_data["date"], "%Y-%m-%d")

                # Check if entry exists
                result = await db.execute(
                    select(BoxingWeekAnalyticsCache).where(
                        and_(
                            BoxingWeekAnalyticsCache.year == year,
                            BoxingWeekAnalyticsCache.date == day_date,
                            BoxingWeekAnalyticsCache.hour.is_(None)
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.revenue = day_data.get("revenue", 0)
                    existing.order_count = day_data.get("orders", 0)
                    existing.top_products = data.get("top_products")
                    existing.category_breakdown = data.get("category_breakdown")
                    existing.is_live = (year == 2025)
                    existing.updated_at = utc_now_naive()
                else:
                    cache_entry = BoxingWeekAnalyticsCache(
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
            except Exception as e:
                logger.error(f"[BoxingWeek] Error saving cache for {day_data.get('date')}: {e}")

        await db.commit()

    async def fetch_order_metrics(self, year: int) -> Dict[str, Any]:
        """Fetch order count and AOV via GraphQL for a year"""
        start_date, end_date = self.get_boxing_week_dates(year)
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
                logger.info(f"[BoxingWeek] {year} GraphQL orders: {order_count} orders, AOV: ${aov}")
        except Exception as e:
            logger.error(f"[BoxingWeek] Error fetching {year} GraphQL orders: {e}")

        return {"order_count": order_count, "aov": aov}

    async def _fetch_fresh_year_data(self, year: int) -> Tuple[int, Dict[str, Any]]:
        """Fetch fresh data for a single year from APIs"""
        data, top_products, categories = await asyncio.gather(
            self.fetch_year_data(year),
            self.fetch_top_products(year),
            self.fetch_category_breakdown(year)
        )

        data["top_products"] = top_products
        data["category_breakdown"] = categories
        data["cached"] = False

        return (year, data)

    def _calculate_yoy(self, years_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate Year-over-Year growth"""
        comparisons = {}
        for year in [2025, 2024, 2023]:
            current = years_data.get(str(year), {}).get("total_revenue", 0)
            previous = years_data.get(str(year - 1), {}).get("total_revenue", 0)

            if previous > 0:
                growth = ((current - previous) / previous) * 100
                comparisons[f"{year}_vs_{year - 1}"] = round(growth, 1)
            else:
                comparisons[f"{year}_vs_{year - 1}"] = None
        return comparisons

    async def get_dashboard_data(self, db: AsyncSession) -> Dict[str, Any]:
        """Get complete dashboard data"""
        # Sequential DB queries to avoid AsyncSession concurrency issues
        all_years = await self.get_all_years_comparison(db)
        
        milestones_result = await db.execute(
            select(BoxingWeekMilestone).where(BoxingWeekMilestone.year == 2025)
        )
        milestones = milestones_result.scalars().all()

        current_revenue = all_years["years"].get("2025", {}).get("total_revenue", 0)
        newly_achieved = []

        # Check for new milestones
        for ms in milestones:
            if not ms.achieved and current_revenue >= ms.threshold:
                ms.achieved = True
                ms.achieved_at = utc_now_naive()
                newly_achieved.append({
                    "threshold": ms.threshold,
                    "achieved_at": ms.achieved_at.isoformat()
                })
        
        if newly_achieved:
            await db.commit()

        # Format milestones for response
        formatted_milestones = [
            {
                "threshold": ms.threshold,
                "achieved": ms.achieved,
                "achieved_at": ms.achieved_at.isoformat() if ms.achieved_at else None,
                "notified": ms.notified
            }
            for ms in milestones
        ]
        
        # Sort milestones
        formatted_milestones.sort(key=lambda x: x["threshold"])

        # Determine next milestone
        next_milestone = next((m for m in formatted_milestones if not m["achieved"]), None)

        return {
            "years_data": all_years["years"],
            "yoy_comparison": all_years["yoy_comparison"],
            "milestones": formatted_milestones,
            "next_milestone": next_milestone,
            "newly_achieved_milestones": newly_achieved,
            "current_year": 2025,
            "is_active": self.is_boxing_week_active(2025)
        }

    async def get_all_years_comparison(self, db: AsyncSession) -> Dict[str, Any]:
        """Get comparison data for all Boxing Week years"""
        years = [2022, 2023, 2024, 2025]
        years_data = {}
        years_to_fetch = []

        # Step 1: Check cache SEQUENTIALLY to avoid session concurrency issues
        for year in years:
            if year < 2025:
                cached = await self.get_cached_data(db, year)
                if cached:
                    years_data[str(year)] = cached
                    continue
            years_to_fetch.append(year)

        # Step 2: Fetch fresh data IN PARALLEL
        if years_to_fetch:
            results = await asyncio.gather(*[
                self._fetch_fresh_year_data(year) for year in years_to_fetch
            ])
            for year, data in results:
                years_data[str(year)] = data

        # Step 3: Fetch order metrics for cached years with missing order counts
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

        # Step 4: Cache new data SEQUENTIALLY to avoid session concurrency issues
        for year in years_to_fetch:
            year_str = str(year)
            if year < 2025 and years_data.get(year_str, {}).get("daily"):
                await self.save_to_cache(db, year, years_data[year_str])

        yoy_comparisons = self._calculate_yoy(years_data)

        return {
            "years": years_data,
            "yoy_comparison": yoy_comparisons
        }

    async def get_live_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """Get lightweight live metrics"""
        # Fetch only 2025 data
        sales_data = await self.fetch_year_sales(2025)
        
        # Get milestones
        milestones_result = await db.execute(
            select(BoxingWeekMilestone).where(BoxingWeekMilestone.year == 2025)
        )
        milestones = milestones_result.scalars().all()
        
        current_revenue = sales_data.get("total_revenue", 0)
        
        # Check milestones
        newly_achieved = []
        for ms in milestones:
            if not ms.achieved and current_revenue >= ms.threshold:
                ms.achieved = True
                ms.achieved_at = utc_now_naive()
                newly_achieved.append({
                    "threshold": ms.threshold,
                    "achieved_at": ms.achieved_at.isoformat()
                })
        
        if newly_achieved:
            await db.commit()
            
        return {
            "current_revenue": current_revenue,
            "newly_achieved_milestones": newly_achieved
        }

    async def get_milestones(self, db: AsyncSession, year: int) -> List[Dict[str, Any]]:
        """Get milestones for a year"""
        result = await db.execute(
            select(BoxingWeekMilestone).where(BoxingWeekMilestone.year == year)
        )
        milestones = result.scalars().all()
        
        return [
            {
                "threshold": ms.threshold,
                "achieved": ms.achieved,
                "achieved_at": ms.achieved_at.isoformat() if ms.achieved_at else None,
                "notified": ms.notified
            }
            for ms in milestones
        ]

    async def mark_milestone_notified(self, db: AsyncSession, threshold: float, year: int) -> None:
        """Mark a milestone as notified"""
        result = await db.execute(
            select(BoxingWeekMilestone).where(
                and_(
                    BoxingWeekMilestone.year == year,
                    BoxingWeekMilestone.threshold == threshold
                )
            )
        )
        milestone = result.scalar_one_or_none()
        
        if milestone:
            milestone.notified = True
            await db.commit()

def get_boxing_week_service() -> BoxingWeekService:
    """Singleton getter"""
    return BoxingWeekService()
