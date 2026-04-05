"""TimesFM price forecasting service.

Uses Google's TimesFM 2.5 (200M params, PyTorch backend) for zero-shot
time series forecasting on stock prices. Optionally uses PFN's finance-tuned
weights when available via the JAX backend.

Model loading is lazy (singleton) — first call takes ~10-15s, subsequent
calls ~1-2s per symbol.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

# Check availability at import time
TIMESFM_AVAILABLE = False
_TIMESFM_API_VERSION = None  # "2.5" or "1.0"

try:
    import torch
    import timesfm

    if hasattr(timesfm, "TimesFM_2p5_200M_torch"):
        TIMESFM_AVAILABLE = True
        _TIMESFM_API_VERSION = "2.5"
    elif hasattr(timesfm, "TimesFm"):
        TIMESFM_AVAILABLE = True
        _TIMESFM_API_VERSION = "1.0"
except ImportError:
    pass


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class PredictionPoint:
    """A single day's forecast."""

    date: str  # YYYY-MM-DD
    price: float
    lower: float  # lower confidence bound
    upper: float  # upper confidence bound


@dataclass
class ForecastResult:
    """Complete forecast for one symbol."""

    symbol: str
    current_price: float
    forecast_horizon: int  # days
    signal: str  # "bullish", "bearish", "neutral"
    confidence: float  # 0.0 to 1.0
    predicted_change_pct: float
    predictions: list[PredictionPoint] = field(default_factory=list)
    model: str = ""
    inference_time_ms: int = 0
    data_points_used: int = 0
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "forecast_horizon": self.forecast_horizon,
            "signal": self.signal,
            "confidence": round(self.confidence, 3),
            "predicted_change_pct": round(self.predicted_change_pct, 2),
            "predictions": [
                {
                    "date": p.date,
                    "price": round(p.price, 2),
                    "lower": round(p.lower, 2),
                    "upper": round(p.upper, 2),
                }
                for p in self.predictions
            ],
            "model": self.model,
            "inference_time_ms": self.inference_time_ms,
            "data_points_used": self.data_points_used,
            "generated_at": self.generated_at,
        }


# ── Provider protocol ────────────────────────────────────────────────────


class ForecastProvider(Protocol):
    """Interface for forecast backends (local, remote, etc.)."""

    def forecast(
        self,
        close_prices: np.ndarray,
        horizon: int,
    ) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
        """Run inference on a single time series.

        Args:
            close_prices: 1D array of historical close prices.
            horizon: Number of future steps to predict.

        Returns:
            (point_forecast, lower_bounds, upper_bounds)
            Each is shape (horizon,). Bounds may be None if not available.
        """
        ...


# ── TimesFM 2.5 (PyTorch) provider ──────────────────────────────────────


class LocalTimesFM25Provider:
    """Loads TimesFM 2.5 (200M, PyTorch) and runs inference locally.

    Supports loading fine-tuned weights on top of the base model via
    the NF_TIMESFM_WEIGHTS environment variable or fine_tuned_weights
    constructor arg. The weights file should be a state_dict .pt file
    produced by finetune_timesfm.py (best_model.pt or final_model.pt).
    """

    MODEL_ID = "google/timesfm-2.5-200m-pytorch"

    def __init__(self, fine_tuned_weights: str | None = None):
        self._model = None
        self._compiled = False
        self._weights_path = fine_tuned_weights or os.environ.get("NF_TIMESFM_WEIGHTS")

    def _ensure_model(self, horizon: int) -> None:
        """Lazy-load the model on first use."""
        if self._model is not None and self._compiled:
            return

        import torch
        import timesfm

        torch.set_float32_matmul_precision("high")

        logger.info("Loading TimesFM 2.5 model (first load takes ~10-15s)...")
        t0 = time.time()

        self._model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self.MODEL_ID)

        # Load fine-tuned weights if available
        if self._weights_path and os.path.exists(self._weights_path):
            logger.info(f"Loading fine-tuned weights from {self._weights_path}")
            state_dict = torch.load(self._weights_path, map_location="cpu", weights_only=True)
            self._model.model.load_state_dict(state_dict)
            logger.info("Fine-tuned weights loaded successfully")

        self._model.compile(
            timesfm.ForecastConfig(
                max_context=2048,
                max_horizon=max(horizon, 128),
                normalize_inputs=True,
                use_continuous_quantile_head=True,
            )
        )
        self._compiled = True

        elapsed = time.time() - t0
        logger.info(f"TimesFM 2.5 loaded in {elapsed:.1f}s")

    def forecast(
        self,
        close_prices: np.ndarray,
        horizon: int,
    ) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
        self._ensure_model(horizon)

        # TimesFM expects a list of 1D arrays
        inputs = [close_prices.astype(np.float32)]

        point_forecast, quantile_forecast = self._model.forecast(
            horizon=horizon,
            inputs=inputs,
        )

        # point_forecast: shape (1, horizon)
        # quantile_forecast: shape (1, horizon, num_quantiles)
        # Layout: [mean, q_low, ..., q_high] — 10 values, not strictly sorted.
        # Use min/max of quantiles (excluding mean at index 0) for robust bounds.
        points = point_forecast[0]  # (horizon,)

        lower = None
        upper = None
        if quantile_forecast is not None and len(quantile_forecast.shape) == 3:
            qf = quantile_forecast[0]  # (horizon, num_quantiles)
            if qf.shape[1] >= 3:
                # Skip index 0 (mean), use min/max of remaining quantiles
                quantiles_only = qf[:, 1:]
                lower = np.min(quantiles_only, axis=1)
                upper = np.max(quantiles_only, axis=1)

        return points, lower, upper

    @staticmethod
    def download_model():
        """Pre-download model weights without running inference."""
        from huggingface_hub import snapshot_download

        logger.info(f"Downloading {LocalTimesFM25Provider.MODEL_ID}...")
        path = snapshot_download(LocalTimesFM25Provider.MODEL_ID)
        logger.info(f"Model downloaded to: {path}")
        return path


# ── Main forecaster class ────────────────────────────────────────────────


class TimesFMForecaster:
    """High-level forecaster that fetches data and runs predictions."""

    # Singleton provider instance (shared across calls to avoid reloading)
    _provider_instance: ForecastProvider | None = None

    def __init__(self):
        if not TIMESFM_AVAILABLE:
            raise ImportError(
                "TimesFM not available. Install with:\n"
                "  pip install 'torch>=2.0' --index-url https://download.pytorch.org/whl/cpu\n"
                "  pip install timesfm\n"
                "Or install all forecast deps:\n"
                "  pip install -r requirements-forecast.txt"
            )

    @classmethod
    def _get_provider(cls) -> ForecastProvider:
        if cls._provider_instance is None:
            if _TIMESFM_API_VERSION == "2.5":
                cls._provider_instance = LocalTimesFM25Provider()
            else:
                raise RuntimeError(
                    f"Unsupported TimesFM API version: {_TIMESFM_API_VERSION}. "
                    "Install timesfm>=1.3.0 for the v2.5 PyTorch API."
                )
        return cls._provider_instance

    def forecast_single(
        self,
        symbol: str,
        close_prices: list[float],
        current_price: float,
        horizon: int = 5,
        start_date: datetime | None = None,
    ) -> ForecastResult:
        """Run forecast for a single symbol.

        Args:
            symbol: Stock symbol (e.g. "RELIANCE").
            close_prices: Historical daily close prices (oldest first).
            current_price: Latest price (for signal calculation).
            horizon: Number of trading days to forecast.
            start_date: Date of the first forecast day. Defaults to tomorrow.
        """
        provider = self._get_provider()
        prices_arr = np.array(close_prices, dtype=np.float32)

        t0 = time.time()
        points, lower, upper = provider.forecast(prices_arr, horizon)
        inference_ms = int((time.time() - t0) * 1000)

        # Build prediction points with dates
        if start_date is None:
            start_date = datetime.utcnow() + timedelta(days=1)

        predictions = []
        forecast_date = start_date
        for i in range(horizon):
            # Skip weekends
            while forecast_date.weekday() >= 5:
                forecast_date += timedelta(days=1)

            pred_price = float(points[i])
            pred_lower = float(lower[i]) if lower is not None else pred_price * 0.97
            pred_upper = float(upper[i]) if upper is not None else pred_price * 1.03

            predictions.append(
                PredictionPoint(
                    date=forecast_date.strftime("%Y-%m-%d"),
                    price=pred_price,
                    lower=pred_lower,
                    upper=pred_upper,
                )
            )
            forecast_date += timedelta(days=1)

        # Derive signal from predictions
        signal, confidence, change_pct = self._derive_signal(
            current_price, predictions
        )

        provider = self._get_provider()
        weights_path = getattr(provider, "_weights_path", None)
        if weights_path:
            model_name = f"timesfm-2.5-200m-nse-finetuned"
        else:
            model_name = LocalTimesFM25Provider.MODEL_ID

        return ForecastResult(
            symbol=symbol,
            current_price=current_price,
            forecast_horizon=horizon,
            signal=signal,
            confidence=confidence,
            predicted_change_pct=change_pct,
            predictions=predictions,
            model=model_name,
            inference_time_ms=inference_ms,
            data_points_used=len(close_prices),
            generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def forecast_batch(
        self,
        symbols_data: list[dict],
        horizon: int = 5,
    ) -> list[ForecastResult]:
        """Run forecasts for multiple symbols.

        Args:
            symbols_data: List of dicts with keys:
                - symbol: str
                - close_prices: list[float]
                - current_price: float
            horizon: Number of trading days to forecast.
        """
        results = []
        for item in symbols_data:
            try:
                result = self.forecast_single(
                    symbol=item["symbol"],
                    close_prices=item["close_prices"],
                    current_price=item["current_price"],
                    horizon=horizon,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Forecast failed for {item['symbol']}: {e}")
                results.append(
                    ForecastResult(
                        symbol=item["symbol"],
                        current_price=item.get("current_price", 0),
                        forecast_horizon=horizon,
                        signal="error",
                        confidence=0,
                        predicted_change_pct=0,
                        model="error",
                        generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                    )
                )
        return results

    @staticmethod
    def _derive_signal(
        current_price: float,
        predictions: list[PredictionPoint],
    ) -> tuple[str, float, float]:
        """Derive trading signal from forecast predictions.

        Returns:
            (signal, confidence, predicted_change_pct)
        """
        if not predictions or current_price <= 0:
            return "neutral", 0.3, 0.0

        # Use the mean of the last 3 predictions (or all if fewer)
        tail = predictions[-min(3, len(predictions)) :]
        avg_predicted = sum(p.price for p in tail) / len(tail)
        change_pct = ((avg_predicted - current_price) / current_price) * 100

        # Signal thresholds
        if change_pct > 2.0:
            signal = "bullish"
        elif change_pct < -2.0:
            signal = "bearish"
        else:
            signal = "neutral"

        # Confidence: based on how tight the prediction interval is
        # relative to the price level. Tighter intervals = higher confidence.
        avg_lower = sum(p.lower for p in tail) / len(tail)
        avg_upper = sum(p.upper for p in tail) / len(tail)
        interval_width = avg_upper - avg_lower

        if current_price > 0 and interval_width > 0:
            # Narrower interval relative to price = higher confidence
            relative_width = interval_width / current_price
            # Map: 1% width → 0.95, 5% → 0.75, 10% → 0.55, 20%+ → 0.30
            confidence = max(0.30, min(0.95, 1.0 - relative_width * 4))
        else:
            confidence = 0.5

        return signal, confidence, change_pct
