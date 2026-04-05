#!/usr/bin/env python3
"""Backtest TimesFM forecast directional accuracy.

Walk-forward evaluation: for each test date, use the preceding N days
as context, predict the next H days, and compare predicted direction
(up/down) against actual. Reports directional hit rate, simulated
returns, and Sharpe ratio.

Can compare base model vs fine-tuned model side by side.

Usage:
  # Quick test (5 symbols, last 60 days)
  python scripts/backtest_forecast.py --data data/nse_nifty500_10y.parquet \
    --symbols RELIANCE TCS INFY --test-days 60

  # Compare base vs fine-tuned
  python scripts/backtest_forecast.py --data data/nse_nifty500_10y.parquet \
    --symbols RELIANCE TCS HDFCBANK INFY ICICIBANK \
    --weights checkpoints/best_model.pt --compare-base

  # Full Nifty 50 backtest
  python scripts/backtest_forecast.py --data data/nse_nifty500_10y.parquet \
    --universe nifty50 --test-days 120 --weights checkpoints/best_model.pt

  # JSON output for further analysis
  python scripts/backtest_forecast.py --data data/nse_nifty500_10y.parquet \
    --symbols RELIANCE --json
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

try:
    import pandas as pd
except ImportError:
    print("pandas required: pip install pandas pyarrow", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class ForecastCall:
    """A single forecast prediction and its outcome."""

    date: str             # Date the forecast was made
    symbol: str
    predicted_price: float  # Predicted price H days ahead
    actual_price: float     # Actual price H days ahead
    current_price: float    # Price at forecast time
    predicted_direction: str  # "up" or "down"
    actual_direction: str     # "up" or "down"
    correct: bool
    predicted_return_pct: float
    actual_return_pct: float


@dataclass
class BacktestResult:
    """Aggregate results for one model on one symbol."""

    symbol: str
    model: str
    calls: list[ForecastCall] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.calls)

    @property
    def correct(self) -> int:
        return sum(1 for c in self.calls if c.correct)

    @property
    def hit_rate(self) -> float:
        return (self.correct / self.total * 100) if self.total else 0.0

    @property
    def returns(self) -> list[float]:
        """Simulated returns: go long if predicted up, short if predicted down."""
        return [
            c.actual_return_pct if c.predicted_direction == "up" else -c.actual_return_pct
            for c in self.calls
        ]

    @property
    def cumulative_return(self) -> float:
        r = 1.0
        for ret in self.returns:
            r *= (1 + ret / 100)
        return (r - 1) * 100

    @property
    def sharpe(self) -> float:
        rets = self.returns
        if len(rets) < 2:
            return 0.0
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
        std_r = math.sqrt(var) if var > 0 else 0.0
        if std_r == 0:
            return 0.0
        # Annualize: assume each call is spaced ~horizon trading days apart
        calls_per_year = 252 / max(len(rets), 1) * len(rets)
        return (mean_r / std_r) * math.sqrt(min(calls_per_year, 252))

    @property
    def max_drawdown(self) -> float:
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for ret in self.returns:
            equity *= (1 + ret / 100)
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "model": self.model,
            "total_calls": self.total,
            "correct": self.correct,
            "hit_rate_pct": round(self.hit_rate, 1),
            "cumulative_return_pct": round(self.cumulative_return, 2),
            "sharpe_ratio": round(self.sharpe, 2),
            "max_drawdown_pct": round(self.max_drawdown, 1),
            "avg_predicted_return_pct": round(
                sum(abs(c.predicted_return_pct) for c in self.calls) / max(self.total, 1), 2
            ),
            "avg_actual_return_pct": round(
                sum(c.actual_return_pct for c in self.calls) / max(self.total, 1), 2
            ),
        }


# ── Backtesting engine ───────────────────────────────────────────────────


def run_backtest(
    closes: np.ndarray,
    dates: list[str],
    symbol: str,
    model_label: str,
    forecaster,
    context_len: int = 512,
    horizon: int = 5,
    step: int = 5,
    test_days: int = 120,
) -> BacktestResult:
    """Walk-forward backtest on a single symbol.

    Args:
        closes: Array of daily close prices (oldest first).
        dates: Corresponding date strings.
        symbol: Stock symbol.
        model_label: Label for the model being tested.
        forecaster: TimesFMForecaster instance.
        context_len: Number of historical days to use as context.
        horizon: Days ahead to forecast.
        step: Days between successive forecasts (non-overlapping if == horizon).
        test_days: Number of most recent days to use as test period.
    """
    n = len(closes)
    test_start = max(context_len, n - test_days)

    result = BacktestResult(symbol=symbol, model=model_label)

    for i in range(test_start, n - horizon, step):
        context = closes[i - context_len : i]
        current_price = closes[i]
        actual_future_price = closes[i + horizon]

        # Run forecast
        try:
            forecast = forecaster.forecast_single(
                symbol=symbol,
                close_prices=context.tolist(),
                current_price=float(current_price),
                horizon=horizon,
            )
        except Exception as e:
            logger.warning(f"  {symbol} date={dates[i]}: forecast failed: {e}")
            continue

        # Get predicted price at horizon
        if forecast.predictions:
            predicted_price = forecast.predictions[-1].price
        else:
            continue

        # Directions
        predicted_dir = "up" if predicted_price > current_price else "down"
        actual_dir = "up" if actual_future_price > current_price else "down"

        predicted_return = ((predicted_price - current_price) / current_price) * 100
        actual_return = ((actual_future_price - current_price) / current_price) * 100

        result.calls.append(ForecastCall(
            date=dates[i],
            symbol=symbol,
            predicted_price=predicted_price,
            actual_price=actual_future_price,
            current_price=current_price,
            predicted_direction=predicted_dir,
            actual_direction=actual_dir,
            correct=(predicted_dir == actual_dir),
            predicted_return_pct=predicted_return,
            actual_return_pct=actual_return,
        ))

    return result


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Backtest TimesFM forecast directional accuracy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data", required=True, help="Parquet file with historical data")
    parser.add_argument("--symbols", nargs="+", help="Symbols to backtest")
    parser.add_argument("--universe", choices=["nifty50", "nifty100"],
                        help="Use a predefined universe instead of --symbols")
    parser.add_argument("--weights", default=None, help="Fine-tuned weights file")
    parser.add_argument("--compare-base", action="store_true",
                        help="Also run base model for comparison")
    parser.add_argument("--horizon", type=int, default=5, help="Forecast horizon in days (default: 5)")
    parser.add_argument("--test-days", type=int, default=120, help="Test period in trading days (default: 120)")
    parser.add_argument("--step", type=int, default=5, help="Days between forecasts (default: horizon)")
    parser.add_argument("--context-len", type=int, default=512, help="Context length (default: 512)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--interval", default="daily",
                        help="Which interval data to use from the parquet (default: daily)")

    args = parser.parse_args()
    if args.step == 5 and args.horizon != 5:
        args.step = args.horizon  # Default step = horizon (non-overlapping)

    # ── Load data ────────────────────────────────────────────────────
    logger.info(f"Loading data from {args.data}...")
    df = pd.read_parquet(args.data)

    # Filter to requested interval if the column exists
    if "interval" in df.columns:
        df = df[df["interval"] == args.interval]
        logger.info(f"Filtered to interval={args.interval}: {len(df):,} candles")

    # Determine timestamp column
    ts_col = "timestamp" if "timestamp" in df.columns else "date"

    # Resolve symbols
    if args.universe:
        from services.instruments_cache import ensure_loaded, get_universe
        ensure_loaded()
        symbols = sorted(get_universe(args.universe))
        # Filter to symbols present in data
        available = set(df["symbol"].unique())
        symbols = [s for s in symbols if s in available]
        logger.info(f"Universe {args.universe}: {len(symbols)} symbols in data")
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:
        parser.error("Specify --symbols or --universe")

    # ── Setup models ─────────────────────────────────────────────────
    from services.timesfm_forecaster import TimesFMForecaster, TIMESFM_AVAILABLE

    if not TIMESFM_AVAILABLE:
        logger.error("TimesFM not installed. pip install -r requirements-forecast.txt")
        sys.exit(1)

    # Determine which models to test
    models_to_test = []

    if args.weights:
        os.environ["NF_TIMESFM_WEIGHTS"] = args.weights
        models_to_test.append(("fine-tuned", args.weights))

    if args.compare_base or not args.weights:
        models_to_test.append(("base", None))

    # ── Run backtests ────────────────────────────────────────────────
    all_results: list[BacktestResult] = []

    for model_label, weights_path in models_to_test:
        # Reset singleton provider for each model
        TimesFMForecaster._provider_instance = None
        if weights_path:
            os.environ["NF_TIMESFM_WEIGHTS"] = weights_path
        elif "NF_TIMESFM_WEIGHTS" in os.environ:
            del os.environ["NF_TIMESFM_WEIGHTS"]

        forecaster = TimesFMForecaster()
        logger.info(f"\n{'='*60}")
        logger.info(f"Model: {model_label}" + (f" ({weights_path})" if weights_path else ""))
        logger.info(f"{'='*60}")

        for sym in symbols:
            sym_df = df[df["symbol"] == sym].sort_values(ts_col)
            closes = sym_df["close"].values.astype(np.float32)
            dates = sym_df[ts_col].astype(str).tolist()

            min_required = args.context_len + args.test_days + args.horizon
            if len(closes) < min_required:
                logger.warning(f"  {sym}: only {len(closes)} candles, need {min_required}, skipping")
                continue

            logger.info(f"  {sym}: {len(closes)} candles, testing last {args.test_days} days...")
            t0 = time.time()

            result = run_backtest(
                closes=closes,
                dates=dates,
                symbol=sym,
                model_label=model_label,
                forecaster=forecaster,
                context_len=args.context_len,
                horizon=args.horizon,
                step=args.step,
                test_days=args.test_days,
            )

            elapsed = time.time() - t0
            all_results.append(result)

            if result.total > 0:
                logger.info(
                    f"  {sym}: {result.hit_rate:.1f}% hit rate "
                    f"({result.correct}/{result.total}), "
                    f"return={result.cumulative_return:+.1f}%, "
                    f"sharpe={result.sharpe:.2f}, "
                    f"time={elapsed:.1f}s"
                )

    # ── Output results ───────────────────────────────────────────────
    if args.json:
        output = [r.to_dict() for r in all_results]
        print(json.dumps(output, indent=2))
        return

    # Print summary table
    for model_label, _ in models_to_test:
        model_results = [r for r in all_results if r.model == model_label]
        if not model_results:
            continue

        print(f"\n{'='*75}")
        print(f"  {model_label.upper()} MODEL — {args.horizon}-day directional forecast")
        print(f"  Test period: last {args.test_days} trading days, step={args.step}d")
        print(f"{'='*75}")
        print(f"{'Symbol':<14} {'Calls':>6} {'Hit%':>7} {'Return%':>9} {'Sharpe':>8} {'MaxDD%':>8}")
        print("-" * 55)

        total_calls = 0
        total_correct = 0

        for r in model_results:
            if r.total == 0:
                continue
            print(
                f"{r.symbol:<14} {r.total:>6} {r.hit_rate:>6.1f}% "
                f"{r.cumulative_return:>+8.1f}% {r.sharpe:>7.2f} "
                f"{r.max_drawdown:>7.1f}%"
            )
            total_calls += r.total
            total_correct += r.correct

        if total_calls > 0:
            agg_hit = total_correct / total_calls * 100
            agg_returns = [ret for r in model_results for ret in r.returns]
            agg_cum = 1.0
            for ret in agg_returns:
                agg_cum *= (1 + ret / 100)
            agg_cum = (agg_cum - 1) * 100

            if len(agg_returns) >= 2:
                mean_r = sum(agg_returns) / len(agg_returns)
                var = sum((r - mean_r) ** 2 for r in agg_returns) / (len(agg_returns) - 1)
                agg_sharpe = (mean_r / math.sqrt(var)) * math.sqrt(252) if var > 0 else 0.0
            else:
                agg_sharpe = 0.0

            print("-" * 55)
            print(
                f"{'AGGREGATE':<14} {total_calls:>6} {agg_hit:>6.1f}% "
                f"{agg_cum:>+8.1f}% {agg_sharpe:>7.2f}"
            )

    # Compare models if both were tested
    if len(models_to_test) == 2:
        print(f"\n{'='*75}")
        print("  HEAD-TO-HEAD COMPARISON")
        print(f"{'='*75}")
        print(f"{'Symbol':<14} {'Base Hit%':>10} {'FT Hit%':>10} {'Delta':>8} {'Winner':>10}")
        print("-" * 55)

        base_results = {r.symbol: r for r in all_results if r.model == "base"}
        ft_results = {r.symbol: r for r in all_results if r.model == "fine-tuned"}

        ft_wins = 0
        base_wins = 0

        for sym in symbols:
            base = base_results.get(sym)
            ft = ft_results.get(sym)
            if not base or not ft or base.total == 0 or ft.total == 0:
                continue

            delta = ft.hit_rate - base.hit_rate
            winner = "FT" if delta > 0 else "BASE" if delta < 0 else "TIE"
            if delta > 0:
                ft_wins += 1
            elif delta < 0:
                base_wins += 1

            print(
                f"{sym:<14} {base.hit_rate:>9.1f}% {ft.hit_rate:>9.1f}% "
                f"{delta:>+7.1f}% {winner:>10}"
            )

        print("-" * 55)
        print(f"  Fine-tuned wins: {ft_wins}, Base wins: {base_wins}")


if __name__ == "__main__":
    main()
