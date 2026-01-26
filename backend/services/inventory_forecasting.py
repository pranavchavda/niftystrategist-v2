"""
Inventory Forecasting Service

Prophet-based demand forecasting using SkuVault historical data.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import pandas as pd

logger = logging.getLogger(__name__)

# Prophet import with fallback
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    logger.warning("Prophet not installed. Install with: pip install prophet")
    PROPHET_AVAILABLE = False

from services.skuvault_forecasting import (
    get_skuvault_forecasting_service,
    SkuVaultSalesCacheService,
    InventorySnapshot
)
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ForecastResult:
    """Result of a single forecast prediction"""
    sku: str
    forecast_date: datetime
    predicted_units: int
    confidence_low: int
    confidence_high: int
    trend_component: float
    seasonal_component: float
    holiday_component: float
    warehouse_id: Optional[str] = None


@dataclass
class ForecastSummary:
    """Summary of a forecast run"""
    model_id: str
    sku: str
    warehouse_id: Optional[str]
    forecast_horizon_days: int
    method: str
    mape: Optional[float]  # Mean Absolute Percentage Error
    forecasts: List[ForecastResult]
    current_inventory: int
    days_until_stockout: Optional[int]
    reorder_recommendation: Optional[str]
    created_at: datetime


class IDCHolidays:
    """
    iDrinkCoffee-specific holidays and events that affect sales.
    Used as custom holidays in Prophet.

    Key insight: Prophet learns holiday effects from historical data.
    - Positive windows = days of increased sales (before/during event)
    - The model will learn BFCM has huge positive effect
    - The model will learn January has negative effect (post-holiday slump)
    """

    @staticmethod
    def get_holidays_df(years: List[int] = None) -> pd.DataFrame:
        """Get holidays DataFrame for Prophet"""
        if years is None:
            years = [2023, 2024, 2025, 2026]

        holidays = []

        for year in years:
            # =================================================================
            # MAJOR SALES EVENTS (huge positive effect)
            # =================================================================

            # BFCM Week (Black Friday through Cyber Monday + buffer)
            # This is THE biggest sales period - extended window
            holidays.append({
                "holiday": "bfcm_week",
                "ds": IDCHolidays._get_black_friday(year),
                "lower_window": -7,   # Week before (early deals)
                "upper_window": 4     # Through Cyber Monday + 1
            })

            # Boxing Week (Dec 26 - Jan 1) - Canada's biggest sale
            holidays.append({
                "holiday": "boxing_week",
                "ds": f"{year}-12-26",
                "lower_window": 0,
                "upper_window": 6     # Full week of sales
            })

            # Pre-Christmas rush (Dec 1-24)
            holidays.append({
                "holiday": "christmas_rush",
                "ds": f"{year}-12-15",
                "lower_window": -14,  # From Dec 1
                "upper_window": 9     # Through Dec 24
            })

            # =================================================================
            # POST-HOLIDAY SLUMP (negative effect - Prophet learns this)
            # =================================================================

            # January slump (Jan 5 - Jan 31)
            # After Boxing Week ends, sales crater
            holidays.append({
                "holiday": "january_slump",
                "ds": f"{year}-01-15",
                "lower_window": -10,  # From ~Jan 5
                "upper_window": 16    # Through Jan 31
            })

            # February slow period (typically slow before Valentine's)
            holidays.append({
                "holiday": "february_slow",
                "ds": f"{year}-02-01",
                "lower_window": 0,
                "upper_window": 7     # First week of Feb
            })

            # =================================================================
            # GIFT-GIVING HOLIDAYS (moderate positive effect)
            # =================================================================

            # Valentine's Day
            holidays.append({
                "holiday": "valentines",
                "ds": f"{year}-02-14",
                "lower_window": -10,
                "upper_window": 0
            })

            # Mother's Day (2nd Sunday of May)
            holidays.append({
                "holiday": "mothers_day",
                "ds": IDCHolidays._get_mothers_day(year),
                "lower_window": -14,
                "upper_window": 0
            })

            # Father's Day (3rd Sunday of June)
            holidays.append({
                "holiday": "fathers_day",
                "ds": IDCHolidays._get_fathers_day(year),
                "lower_window": -14,
                "upper_window": 0
            })

            # =================================================================
            # OTHER EVENTS
            # =================================================================

            # Prime Day (mid-July) - competitor pressure
            holidays.append({
                "holiday": "prime_day",
                "ds": f"{year}-07-16",
                "lower_window": -2,
                "upper_window": 1
            })

            # Labour Day weekend
            holidays.append({
                "holiday": "labour_day",
                "ds": IDCHolidays._get_labour_day(year),
                "lower_window": -3,
                "upper_window": 0
            })

        df = pd.DataFrame(holidays)
        df["ds"] = pd.to_datetime(df["ds"])
        return df

    @staticmethod
    def _get_black_friday(year: int) -> str:
        """Get Black Friday date (4th Friday of November)"""
        nov_first = datetime(year, 11, 1)
        # Find first Friday
        days_until_friday = (4 - nov_first.weekday()) % 7
        first_friday = nov_first + timedelta(days=days_until_friday)
        # 4th Friday
        black_friday = first_friday + timedelta(weeks=3)
        return black_friday.strftime("%Y-%m-%d")

    @staticmethod
    def _get_cyber_monday(year: int) -> str:
        """Get Cyber Monday date (Monday after Black Friday)"""
        bf = datetime.strptime(IDCHolidays._get_black_friday(year), "%Y-%m-%d")
        return (bf + timedelta(days=3)).strftime("%Y-%m-%d")

    @staticmethod
    def _get_mothers_day(year: int) -> str:
        """Get Mother's Day (2nd Sunday of May)"""
        may_first = datetime(year, 5, 1)
        days_until_sunday = (6 - may_first.weekday()) % 7
        first_sunday = may_first + timedelta(days=days_until_sunday)
        return (first_sunday + timedelta(weeks=1)).strftime("%Y-%m-%d")

    @staticmethod
    def _get_fathers_day(year: int) -> str:
        """Get Father's Day (3rd Sunday of June)"""
        june_first = datetime(year, 6, 1)
        days_until_sunday = (6 - june_first.weekday()) % 7
        first_sunday = june_first + timedelta(days=days_until_sunday)
        return (first_sunday + timedelta(weeks=2)).strftime("%Y-%m-%d")

    @staticmethod
    def _get_labour_day(year: int) -> str:
        """Get Labour Day (1st Monday of September)"""
        sept_first = datetime(year, 9, 1)
        days_until_monday = (0 - sept_first.weekday()) % 7
        return (sept_first + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")


class ProphetForecaster:
    """
    Prophet-based forecaster for inventory prediction.
    """

    def __init__(
        self,
        seasonality_mode: str = "multiplicative",
        include_holidays: bool = True,
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = False
    ):
        self.seasonality_mode = seasonality_mode
        self.include_holidays = include_holidays
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.model = None
        self.is_fitted = False

    def fit(self, df: pd.DataFrame) -> "ProphetForecaster":
        """
        Fit Prophet model on historical sales data.

        Args:
            df: DataFrame with columns 'ds' (date) and 'y' (units sold)

        Returns:
            self for chaining
        """
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet is not installed. Run: pip install prophet")

        if len(df) < 30:
            logger.warning(f"Limited data: only {len(df)} rows. Forecast may be unreliable.")

        # Initialize Prophet with IDC-specific settings
        holidays = IDCHolidays.get_holidays_df() if self.include_holidays else None

        self.model = Prophet(
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            seasonality_mode=self.seasonality_mode,
            holidays=holidays,
            interval_width=0.80,  # 80% confidence interval
            changepoint_prior_scale=0.05,  # More conservative trend changes
            holidays_prior_scale=15.0,  # Stronger holiday effects (default=10)
            seasonality_prior_scale=15.0  # Stronger seasonality (default=10)
        )

        # Fit the model
        logger.info(f"Fitting Prophet model on {len(df)} data points")
        self.model.fit(df)
        self.is_fitted = True

        return self

    def predict(self, periods: int = 30) -> pd.DataFrame:
        """
        Generate forecast for future periods.

        Args:
            periods: Number of days to forecast

        Returns:
            DataFrame with columns: ds, yhat, yhat_lower, yhat_upper, trend, seasonal
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before predicting")

        future = self.model.make_future_dataframe(periods=periods)
        forecast = self.model.predict(future)

        # Extract relevant columns
        result = forecast[[
            "ds", "yhat", "yhat_lower", "yhat_upper",
            "trend", "yearly", "weekly"
        ]].copy()

        # Add holiday component if available
        if "holidays" in forecast.columns:
            result["holidays"] = forecast["holidays"]
        else:
            result["holidays"] = 0

        # Only return future dates
        result = result.tail(periods)

        return result

    def get_components(self) -> Dict[str, Any]:
        """Get model components for explainability"""
        if not self.is_fitted:
            return {}

        return {
            "trend": "increasing" if self.model.params["trend"][-1] > 0 else "decreasing",
            "seasonality_mode": self.seasonality_mode,
            "changepoints": len(self.model.changepoints)
        }


class InventoryForecastingService:
    """
    Main service for inventory prediction.

    Combines SkuVault data fetching with Prophet forecasting.
    Uses cached data when available to avoid hitting SkuVault API.
    """

    # Class-level inventory cache with TTL (5 minutes)
    _inventory_cache: Dict[str, Tuple[int, datetime]] = {}
    _cache_ttl = timedelta(minutes=5)

    @staticmethod
    def _remove_outliers(df: pd.DataFrame, column: str = "y", multiplier: float = 3.0) -> Tuple[pd.DataFrame, int]:
        """
        Remove outliers from sales data using IQR method.

        Uses only non-zero values to calculate thresholds, since retail data
        has many zero-sale days that shouldn't affect outlier detection.

        Args:
            df: DataFrame with sales data
            column: Column to check for outliers
            multiplier: IQR multiplier (3.0 = aggressive, 1.5 = standard)

        Returns:
            Tuple of (cleaned DataFrame, number of outliers capped)
        """
        if df.empty or column not in df.columns:
            return df, 0

        df = df.copy()

        # Only consider non-zero values for threshold calculation
        non_zero = df[df[column] > 0][column]

        if len(non_zero) < 5:
            # Not enough data points to detect outliers
            return df, 0

        q1 = non_zero.quantile(0.25)
        q3 = non_zero.quantile(0.75)
        iqr = q3 - q1

        # Upper bound (we don't cap lower since negative sales don't exist)
        upper_bound = q3 + (multiplier * iqr)

        # Also ensure minimum threshold (don't cap values under 10 units)
        upper_bound = max(upper_bound, 10)

        # Count and cap outliers
        outlier_mask = df[column] > upper_bound
        outlier_count = outlier_mask.sum()

        if outlier_count > 0:
            original_values = df.loc[outlier_mask, column].tolist()
            df.loc[outlier_mask, column] = upper_bound
            logger.info(
                f"Capped {outlier_count} outliers at {upper_bound:.0f} units. "
                f"Original values: {original_values}"
            )

        return df, outlier_count

    def __init__(self, db: AsyncSession = None):
        self.skuvault_api = get_skuvault_forecasting_service()
        self.db = db
        # Cache service requires db session
        self.cache_service = SkuVaultSalesCacheService(db) if db else None

    def _prefetch_inventory(self, skus: List[str]) -> None:
        """Pre-fetch inventory for multiple SKUs in a single API call"""
        try:
            logger.info(f"Pre-fetching inventory for {len(skus)} SKUs in single batch call")
            snapshots = self.skuvault_api.get_inventory_by_warehouse(skus)

            now = datetime.now()
            sku_totals: Dict[str, int] = {}

            for snap in snapshots:
                if snap.sku not in sku_totals:
                    sku_totals[snap.sku] = 0
                sku_totals[snap.sku] += snap.quantity_available

            # Cache the results
            for sku, total in sku_totals.items():
                self._inventory_cache[sku] = (total, now)

            logger.info(f"Cached inventory for {len(sku_totals)} SKUs")
        except Exception as e:
            logger.error(f"Error pre-fetching inventory: {e}")

    async def create_forecast(
        self,
        sku: str,
        horizon_days: int = 30,
        warehouse_id: Optional[str] = None,
        method: str = "prophet",
        training_days: int = 365
    ) -> ForecastSummary:
        """
        Create a forecast for a specific SKU.

        Args:
            sku: SkuVault SKU to forecast
            horizon_days: Number of days to forecast
            warehouse_id: Optional warehouse filter (None = aggregate)
            method: Forecasting method (currently only 'prophet')
            training_days: Days of historical data to use

        Returns:
            ForecastSummary with predictions and recommendations
        """
        model_id = str(uuid.uuid4())
        logger.info(f"Creating forecast for SKU={sku}, horizon={horizon_days}d, warehouse={warehouse_id}")

        # 1. Fetch historical sales (from cache if available, otherwise API)
        if self.cache_service:
            logger.info(f"Using cached sales data for {sku}")
            sales_df = await self.cache_service.get_sales_for_prophet(
                sku=sku,
                days=training_days,
                warehouse_id=warehouse_id
            )
        else:
            logger.info(f"No cache available, fetching from SkuVault API for {sku}")
            sales_df = self.skuvault_api.get_sales_for_prophet(
                sku=sku,
                days=training_days,
                warehouse_id=warehouse_id
            )

        if sales_df.empty or len(sales_df) < 14:
            logger.warning(f"Insufficient sales data for {sku}")
            return await self._create_insufficient_data_summary(sku, warehouse_id, model_id)

        # 2. Remove outliers before training (wholesale orders, etc.)
        # Keep original for reference, use cleaned for Prophet
        training_df, outliers_removed = self._remove_outliers(sales_df.copy())
        if outliers_removed > 0:
            logger.info(f"Removed {outliers_removed} outlier(s) from training data for {sku}")

        # 3. Fit Prophet model on cleaned data
        forecaster = ProphetForecaster()
        forecaster.fit(training_df[["ds", "y"]])

        # 4. Generate forecast
        forecast_df = forecaster.predict(periods=horizon_days)

        # 5. Get current inventory (from cache - no API calls)
        current_inventory = await self._get_current_inventory_async(sku, warehouse_id)

        # 6. Build forecast results
        forecasts = []
        cumulative_demand = 0

        for _, row in forecast_df.iterrows():
            predicted = max(0, round(row["yhat"]))
            cumulative_demand += predicted

            forecasts.append(ForecastResult(
                sku=sku,
                forecast_date=row["ds"].to_pydatetime(),
                predicted_units=predicted,
                confidence_low=max(0, round(row["yhat_lower"])),
                confidence_high=max(0, round(row["yhat_upper"])),
                trend_component=round(row["trend"], 2),
                seasonal_component=round(row["yearly"] + row["weekly"], 2),
                holiday_component=round(row["holidays"], 2),
                warehouse_id=warehouse_id
            ))

        # 6. Calculate days until stockout
        days_until_stockout = self._calculate_stockout_days(
            current_inventory, forecasts
        )

        # 7. Generate reorder recommendation (use cleaned historical data for sanity check)
        historical_avg_daily = training_df["y"].sum() / len(training_df) if len(training_df) > 0 else 0
        reorder_rec = self._generate_reorder_recommendation(
            current_inventory, days_until_stockout, forecasts, historical_avg_daily
        )

        # 8. Calculate MAPE on historical data (last 30 days)
        mape = self._calculate_mape(sales_df, forecaster)

        return ForecastSummary(
            model_id=model_id,
            sku=sku,
            warehouse_id=warehouse_id,
            forecast_horizon_days=horizon_days,
            method=method,
            mape=mape,
            forecasts=forecasts,
            current_inventory=current_inventory,
            days_until_stockout=days_until_stockout,
            reorder_recommendation=reorder_rec,
            created_at=datetime.now()
        )

    async def _get_current_inventory_async(
        self,
        sku: str,
        warehouse_id: Optional[str]
    ) -> int:
        """Get current inventory level from cache (async version)"""
        if self.cache_service:
            qty = await self.cache_service.get_cached_inventory(sku, warehouse_id)
            logger.debug(f"Cached inventory for {sku}: {qty}")
            return qty
        return 0

    def _get_current_inventory(
        self,
        sku: str,
        warehouse_id: Optional[str]
    ) -> int:
        """Get current inventory level from cache (sync wrapper)"""
        # Use in-memory cache first (for batch operations)
        if not warehouse_id and sku in self._inventory_cache:
            cached_qty, cached_time = self._inventory_cache[sku]
            if datetime.now() - cached_time < self._cache_ttl:
                logger.debug(f"Memory cache hit for inventory {sku}: {cached_qty}")
                return cached_qty

        # For sync context, we can't call async cache_service
        # Return 0 and let create_forecast use async version
        logger.debug(f"No cached inventory for {sku}, returning 0")
        return 0

    def _calculate_stockout_days(
        self,
        current_inventory: int,
        forecasts: List[ForecastResult]
    ) -> Optional[int]:
        """Calculate days until stockout based on forecast"""
        remaining = current_inventory

        for i, forecast in enumerate(forecasts):
            remaining -= forecast.predicted_units
            if remaining <= 0:
                return i + 1

        return None  # No stockout in forecast period

    def _generate_reorder_recommendation(
        self,
        current_inventory: int,
        days_until_stockout: Optional[int],
        forecasts: List[ForecastResult],
        historical_avg_daily: float = 0
    ) -> Optional[str]:
        """
        Generate actionable reorder recommendation.

        Uses the more conservative of forecast vs historical average to avoid
        over-ordering due to forecast spikes.
        """
        if not forecasts:
            return None

        forecast_avg_daily = sum(f.predicted_units for f in forecasts) / len(forecasts)

        # Use the more conservative (lower) of forecast or historical average
        # This prevents wholesale spikes from inflating reorder quantities
        if historical_avg_daily > 0:
            avg_daily = min(forecast_avg_daily, historical_avg_daily * 1.2)  # Allow 20% growth
        else:
            avg_daily = forecast_avg_daily

        if days_until_stockout is None:
            # Calculate days of stock
            if avg_daily > 0:
                days_of_stock = current_inventory / avg_daily
                if days_of_stock > 90:
                    return f"Overstock alert: {days_of_stock:.0f} days of inventory"
            return "Inventory sufficient for forecast period"

        # Calculate reorder quantity based on lead time + safety stock
        # Assume 2-week lead time + 2-week safety stock = 28 days
        lead_time_days = 28
        reorder_qty = round(avg_daily * lead_time_days)

        # Sanity check: never recommend more than 3 months of historical average
        max_reorder = round(historical_avg_daily * 90) if historical_avg_daily > 0 else reorder_qty
        reorder_qty = min(reorder_qty, max_reorder) if max_reorder > 0 else reorder_qty

        if days_until_stockout <= 7:
            return f"URGENT: Reorder {reorder_qty} units immediately (stockout in {days_until_stockout} days)"
        elif days_until_stockout <= 14:
            return f"Reorder soon: {reorder_qty} units needed (stockout in {days_until_stockout} days)"
        elif days_until_stockout <= 21:
            return f"Plan reorder: stockout expected in {days_until_stockout} days"

        return None

    def _calculate_mape(
        self,
        historical_df: pd.DataFrame,
        forecaster: ProphetForecaster
    ) -> Optional[float]:
        """Calculate Mean Absolute Percentage Error on historical data"""
        try:
            if len(historical_df) < 60:
                return None

            # Use last 30 days as test set
            train = historical_df.iloc[:-30]
            test = historical_df.iloc[-30:]

            if len(train) < 30:
                return None

            # Refit on training data
            test_forecaster = ProphetForecaster()
            test_forecaster.fit(train[["ds", "y"]])
            predictions = test_forecaster.predict(30)

            # Calculate MAPE
            actuals = test["y"].values
            preds = predictions["yhat"].values[:len(actuals)]

            # Avoid division by zero
            mask = actuals > 0
            if not mask.any():
                return None

            mape = (abs(actuals[mask] - preds[mask]) / actuals[mask]).mean() * 100
            return round(mape, 2)
        except Exception as e:
            logger.warning(f"Error calculating MAPE: {e}")
            return None

    async def _create_insufficient_data_summary(
        self,
        sku: str,
        warehouse_id: Optional[str],
        model_id: str
    ) -> ForecastSummary:
        """Create summary for SKUs with insufficient data"""
        # Get inventory from cache (async)
        inventory = await self._get_current_inventory_async(sku, warehouse_id)
        return ForecastSummary(
            model_id=model_id,
            sku=sku,
            warehouse_id=warehouse_id,
            forecast_horizon_days=0,
            method="insufficient_data",
            mape=None,
            forecasts=[],
            current_inventory=inventory,
            days_until_stockout=None,
            reorder_recommendation="Insufficient sales history for forecasting",
            created_at=datetime.now()
        )

    async def batch_forecast(
        self,
        skus: List[str],
        horizon_days: int = 30,
        warehouse_id: Optional[str] = None
    ) -> List[ForecastSummary]:
        """
        Create forecasts for multiple SKUs.

        Uses cached inventory data - no real-time API calls.

        Args:
            skus: List of SKUs to forecast
            horizon_days: Forecast horizon
            warehouse_id: Optional warehouse filter

        Returns:
            List of ForecastSummary objects
        """

        results = []

        for sku in skus:
            try:
                summary = await self.create_forecast(
                    sku=sku,
                    horizon_days=horizon_days,
                    warehouse_id=warehouse_id
                )
                results.append(summary)
            except Exception as e:
                logger.error(f"Error forecasting {sku}: {e}")
                results.append(await self._create_insufficient_data_summary(
                    sku, warehouse_id, str(uuid.uuid4())
                ))

        return results

    async def get_stockout_risks(
        self,
        threshold_days: int = 14,
        warehouse_id: Optional[str] = None
    ) -> List[ForecastSummary]:
        """
        Get all SKUs at risk of stockout within threshold.

        Args:
            threshold_days: Days threshold for stockout risk
            warehouse_id: Optional warehouse filter

        Returns:
            List of at-risk ForecastSummary objects, sorted by urgency
        """
        # Get all active SKUs
        all_skus = self.skuvault_api.get_all_active_skus()

        # Forecast each (this is slow - consider caching)
        forecasts = await self.batch_forecast(
            skus=all_skus[:100],  # Limit for now
            horizon_days=threshold_days,
            warehouse_id=warehouse_id
        )

        # Filter to at-risk items
        at_risk = [
            f for f in forecasts
            if f.days_until_stockout is not None
            and f.days_until_stockout <= threshold_days
        ]

        # Sort by urgency (days until stockout ascending)
        at_risk.sort(key=lambda x: x.days_until_stockout or float("inf"))

        return at_risk


# Factory function - creates instance with db session for cache access
def get_inventory_forecasting_service(db: AsyncSession = None) -> InventoryForecastingService:
    """
    Get an inventory forecasting service instance.

    Args:
        db: Database session for cache access. If provided, forecasts will
            use cached sales data instead of hitting the SkuVault API.
    """
    return InventoryForecastingService(db=db)
