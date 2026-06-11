import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  FlaskConical, Play, Loader2, TrendingUp, TrendingDown,
  BarChart3, Clock, Target, AlertTriangle, Trophy,
  ArrowUpRight, ArrowDownRight, Minus, Info, X, Trash2,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Badge } from '../components/catalyst/badge';
import { Input } from '../components/catalyst/input';
import { EquitySymbolPicker } from '../components/EquitySymbolPicker';
import { FnoUnderlyingPicker } from '../components/FnoUnderlyingPicker';

interface AuthContext {
  authToken: string;
  user?: any;
}

interface BacktestTemplate {
  name: string;
  description: string;
  category: string;
  required_params: string[];
  optional_params: Record<string, any>;
}

interface Trade {
  side: string;
  entry_price: number;
  entry_time: string;
  exit_price: number;
  exit_time: string;
  quantity: number;
  pnl: number;
  pnl_pct?: number;
  exit_reason: string;
}

interface BacktestMetrics {
  total_trades: number;
  winners: number;
  losers: number;
  win_rate: number;
  net_pnl: number;
  return_pct: number;
  profit_factor: number | string;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  expectancy: number;
  avg_holding_minutes: number;
}

interface LegTrade {
  instrument_key: string;
  label: string;
  side: string;
  quantity: number;
  entry_price: number;
  exit_price: number;
  entry_time: string;
  exit_time: string;
  exit_reason: string;
  gross_pnl: number;
  charges: Record<string, number>;
  net_pnl: number;
  holding_minutes: number;
}

interface FnODayResult {
  date: string;
  gross_pnl: number;
  charges: number;
  net_pnl: number;
  legs: LegTrade[];
}

interface BacktestResult {
  // Equity fields
  metrics: BacktestMetrics;
  trades?: Trade[];
  equity_curve: number[];
  initial_capital: number;
  // F&O fields
  day_results?: FnODayResult[];
  all_leg_trades?: LegTrade[];
  total_charges?: number;
  days_traded?: number;
  // Scalp-replay extras
  metrics_net?: BacktestMetrics;
  charges_total?: number;
  slippage_total?: number;
  // Plausibility flags computed server-side (backtesting/metrics.py) — render
  // verbatim so artifact-shaped results can't be read without the caveats.
  warnings?: string[];
  first_trade_date?: string;
  last_trade_date?: string;
  // For options_scalp runs with expiry === "rolling": ISO dates actually
  // traded (the front-of-book weekly resolved per signal flip). Absent on
  // fixed-expiry runs and on pre-rolling historic runs.
  expiries_used?: string[];
  diagnostics?: {
    intra_bar_ambiguity: number;
    primary_flips: number;
    confirm_blocks: number;
    cooldown_blocks: number;
    max_trades_blocks: number;
    squareoff_exits: number;
    entry_side_blocks?: number;
  };
  // Snapshot of the ScalpSessionConfig the run used — drives the Strategy card
  // so a historic run shows the indicator/confirm/position that produced it.
  config?: Record<string, any>;
  session_mode?: string;
  candle_count?: number;
  session_days?: number;
  // Top-level run descriptors (present on scalp results).
  symbol?: string;
  underlying?: string;
  expiry?: string;
  interval?: string;
  days?: number;
}

// Indicators usable as a scalp PRIMARY (must return signed scalar so the
// flip contract `prev<=0 → curr>0 = bullish` works).
// Full indicator catalog. Every indicator is available as both PRIMARY and
// CONFIRM here and in the live signal-session UI (scalp-sessions.tsx) — the
// two must stay in sync so a backtested config behaves identically live.
// Each must emit a SIGNED scalar (sign = direction, zero-cross = flip); the
// signed `output`/`band` is baked into defaultParams for indicators whose raw
// reading isn't directional (rsi→centered, linear_regression→slope,
// vwap→centered, bollinger→centered, volume_spike→directional).
const SCALP_PRIMARY_INDICATORS = [
  { value: 'utbot', label: 'UT Bot (ATR trailing stop)',
    defaultParams: '{"period":10,"sensitivity":1.0}' },
  { value: 'ema_crossover', label: 'EMA Crossover',
    defaultParams: '{"fast":9,"slow":21}' },
  { value: 'supertrend', label: 'Supertrend',
    defaultParams: '{"period":10,"multiplier":3.0}' },
  { value: 'halftrend', label: 'HalfTrend',
    defaultParams: '{"amplitude":2,"atr_period":100}' },
  { value: 'ssl_hybrid', label: 'SSL Hybrid',
    defaultParams: '{"period":10}' },
  { value: 'hilega_milega', label: 'Hilega Milega (RSI EMA/WMA cross)',
    defaultParams: '{"rsi_period":9,"wma_period":21,"ema_period":3}' },
  { value: 'qqe_mod', label: 'QQE MOD', defaultParams: '{"rsi_period":6,"smoothing":5}' },
  { value: 'linear_regression', label: 'Linear Regression (slope)',
    defaultParams: '{"period":20,"output":"slope"}' },
  { value: 'macd', label: 'MACD Histogram', defaultParams: '{}' },
  { value: 'rsi', label: 'RSI (centered)', defaultParams: '{"period":14,"output":"centered"}' },
  { value: 'renko', label: 'Renko', defaultParams: '{"brick_size":10.0}' },
  { value: 'vwap', label: 'VWAP (close − vwap)', defaultParams: '{"output":"centered"}' },
  { value: 'bollinger', label: 'Bollinger (%B centered)',
    defaultParams: '{"period":20,"band":"centered"}' },
  { value: 'volume_spike', label: 'Volume Spike (directional)',
    defaultParams: '{"lookback":20,"threshold":1.5,"output":"directional"}' },
];

const SCALP_CONFIRM_INDICATORS = [
  { value: '', label: '(none)' },
  ...SCALP_PRIMARY_INDICATORS,
];

// value → human label, for rendering a saved run's strategy (the result.config
// only stores the raw indicator key like "utbot").
const INDICATOR_LABELS: Record<string, string> = Object.fromEntries(
  SCALP_PRIMARY_INDICATORS.map(i => [i.value, i.label]),
);
const indicatorLabel = (v?: string | null): string =>
  v ? (INDICATOR_LABELS[v] || v) : '';

// entry_side → human label (mode-aware: options use CE/PE language).
const positionLabel = (side?: string | null, mode?: string | null): string => {
  const s = (side || 'both').toLowerCase();
  const isOpt = mode === 'options_scalp';
  if (s === 'long') return isOpt ? 'CE only (bullish)' : 'Long only';
  if (s === 'short') return isOpt ? 'PE only (bearish)' : 'Short only';
  return isOpt ? 'Both (CE + PE)' : 'Both (long + short)';
};

// Indicators that have a native O(n) series implementation — used to flag
// slow-path indicators in the UI so users know what'll cost them on long
// ranges. Mirrors monitor/indicator_series.py:_SERIES_REGISTRY.
const NATIVE_SERIES_INDICATORS = new Set([
  'rsi', 'macd', 'ema_crossover', 'volume_spike', 'vwap', 'bollinger',
  'supertrend', 'utbot', 'halftrend', 'qqe_mod', 'hilega_milega', 'ssl_hybrid',
]);

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

// ─── SSE helper ──────────────────────────────────────────────────────
// Browsers' built-in EventSource doesn't support custom headers, so we
// open the SSE connection via fetch + ReadableStream and parse the
// "data: ..." lines ourselves. Returns an object with a .close() method
// so callers can abort.

function openSseStream(
  jobId: number,
  authToken: string,
  handlers: { onEvent: (data: any) => void; onError: (msg: string) => void }
): { close: () => void } {
  const controller = new AbortController();
  let cancelled = false;

  (async () => {
    try {
      const res = await fetch(`/api/backtest/jobs/${jobId}/stream`, {
        headers: { Authorization: `Bearer ${authToken}` },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        if (!cancelled) handlers.onError('SSE connection failed');
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // SSE messages are separated by blank lines.
        let sep;
        while ((sep = buf.indexOf('\n\n')) !== -1) {
          const raw = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          for (const line of raw.split('\n')) {
            if (line.startsWith('data: ')) {
              const payload = line.slice(6);
              try {
                handlers.onEvent(JSON.parse(payload));
              } catch {
                // Malformed event — skip rather than tearing down the stream.
              }
            }
            // ":<text>" comments (heartbeats) are ignored.
          }
        }
      }
    } catch (e: any) {
      // AbortError from controller.abort() is expected on close()
      if (!cancelled && e?.name !== 'AbortError') {
        handlers.onError(e?.message || 'SSE stream error');
      }
    }
  })();

  return {
    close: () => {
      cancelled = true;
      controller.abort();
    },
  };
}


// ─── Tooltip ─────────────────────────────────────────────────────────

function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex ml-1 align-middle">
      <Info className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 cursor-help" />
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs text-zinc-200 bg-zinc-800 dark:bg-zinc-700 rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none w-56 text-left leading-relaxed z-50 whitespace-normal">
        {text}
      </span>
    </span>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────

function formatINR(value: number): string {
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${value < 0 ? '-' : ''}₹${formatted}`;
}

function formatDateTime(iso: string): string {
  if (!iso) return '--';
  // Backend emits trade times as explicit-offset IST ISO (…+05:30). Only
  // legacy/naive strings lack a tz marker — those are IST wall-clock, so
  // tag them as IST rather than the old (wrong) assumption of UTC.
  const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso.trim());
  const d = new Date(hasTz ? iso : iso.trim() + '+05:30');
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

function exitReasonColor(reason: string): string {
  switch (reason?.toLowerCase()) {
    case 'sl': case 'stoploss': case 'stop_loss': return 'red';
    case 'target': case 'tp': case 'take_profit': return 'emerald';
    case 'trailing': case 'trailing_stop': return 'blue';
    case 'squareoff': case 'time': case 'eod': return 'amber';
    default: return 'zinc';
  }
}

const selectClassName = "w-full rounded-lg bg-white dark:bg-zinc-900/50 border border-zinc-300 dark:border-zinc-700 text-sm text-zinc-800 dark:text-zinc-200 px-3 py-2 focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30";

// Params that are always strings (not numbers)
const STRING_PARAMS = new Set([
  'underlying', 'expiry', 'product', 'side', 'direction',
  'squareoff_time', 'entry_time', 'symbol', 'rsi_timeframe', 'timeframe',
  'option_type',
]);

// Jargon tooltips for strategy params and terms
const PARAM_TOOLTIPS: Record<string, string> = {
  // General
  capital: 'Total money allocated for this strategy. Position sizes are calculated from this.',
  risk_percent: 'Max % of capital risked per trade. E.g. 2% of ₹1L = ₹2,000 max loss per trade.',
  rr_ratio: 'Reward-to-Risk ratio. If risk is ₹1,000 and RR is 2, target profit is ₹2,000.',
  trail_percent: 'Trailing stop distance as % from peak. Locks in profit as price moves favorably.',
  squareoff_time: 'Time to auto-close all positions (HH:MM). Default 15:09, before market close at 15:30. On coarse intervals the exit lands on the bar live at this time (e.g. a 15:09 cutoff on 15-min bars squares off on the 15:00–15:15 bar).',
  entry_time: 'Time to enter the trade (HH:MM). Common: 09:20 (after opening volatility settles).',
  product: 'Order product type. "I" = Intraday (auto-squared off), "D" = Delivery (hold overnight).',
  side: 'Trade direction. "both" takes long and short signals, "long" only buys, "short" only sells.',
  // Equity specific
  range_minutes: 'Duration of opening range in minutes. ORB uses the first N-minute candle as the range.',
  range_high: 'Upper boundary of the opening range. Auto-detected from first candle if left empty.',
  range_low: 'Lower boundary of the opening range. Auto-detected from first candle if left empty.',
  entry_pct: 'Entry trigger as % above day open. E.g. 0.5% above open = breakout entry.',
  sl_pct: 'Stop-loss as % from entry price. Overrides risk_percent for SL calculation.',
  sl_percent: 'Stop-loss trigger as % premium increase. E.g. 30% means SL hits when premium rises 30% from entry.',
  // F&O specific
  underlying: 'Index or stock name. E.g. NIFTY, BANKNIFTY, RELIANCE.',
  expiry: 'Option expiry date (YYYY-MM-DD). Weekly expiries are every Thursday.',
  strike: 'Strike price of the option. ATM = near current market price.',
  lots: 'Number of lots. Each lot has a fixed size (e.g. NIFTY = 75 units/lot).',
  direction: '"sell" = short (collect premium, profit from decay), "buy" = long (pay premium, profit from big moves).',
  call_strike: 'Strike price for the Call (CE) leg.',
  put_strike: 'Strike price for the Put (PE) leg.',
  buy_strike: 'Strike price of the option you BUY (the protection/debit leg).',
  sell_strike: 'Strike price of the option you SELL (the income/credit leg).',
  call_sell_strike: 'Strike of the Call you SELL (short call). Should be above current price (OTM).',
  call_buy_strike: 'Strike of the Call you BUY (protection). Higher than call_sell_strike.',
  put_sell_strike: 'Strike of the Put you SELL (short put). Should be below current price (OTM).',
  put_buy_strike: 'Strike of the Put you BUY (protection). Lower than put_sell_strike.',
  // EMA-Stochastic Scalper
  atm_strike: 'At-the-money strike price. Use the strike closest to current underlying price.',
  target_points: 'Profit target in premium points (e.g. 15 = exit when option premium rises ₹15).',
  sl_points: 'Stop-loss in premium points (e.g. 10 = exit when option premium drops ₹10).',
  max_fires: 'Max number of entries per direction. Higher = more trades, more exposure.',
  rsi_oversold: 'RSI level below which the underlying is "oversold" — triggers CE (bullish) entry.',
  rsi_overbought: 'RSI level above which the underlying is "overbought" — triggers PE (bearish) entry.',
  rsi_timeframe: 'Candle timeframe for RSI calculation (e.g. "1m" for 1-minute scalping).',
  // EMA Cross
  fast_ema: 'Fast EMA period. Shorter period reacts faster to price changes.',
  slow_ema: 'Slow EMA period. Longer period smooths out noise. Crossover signals trend change.',
  timeframe: 'Candle timeframe for indicator calculation (e.g. "5m", "15m").',
};

// Strategy-level descriptions for n00bs
const STRATEGY_TOOLTIPS: Record<string, string> = {
  orb: 'Opening Range Breakout: Waits for the first candle to form a "range", then buys if price breaks above or sells if it breaks below. Simple momentum strategy.',
  breakout: 'Level Breakout: Enters when price crosses a key support/resistance level. Good for stocks showing consolidation patterns.',
  'mean-reversion': 'Mean Reversion: Bets that price will return to its average after an extreme move. Buys dips and sells rallies using RSI.',
  'vwap-bounce': 'VWAP Bounce: Trades bounces off the Volume-Weighted Average Price — an institutional benchmark. Price touching VWAP often acts as support/resistance.',
  scalp: 'Scalp: Quick in-and-out trades capturing small price moves. Tight stops, small targets, high frequency.',
  straddle: 'Straddle: Buy or sell both a Call and Put at the SAME strike. Short straddle profits from low volatility (premium decay). Long straddle profits from big moves in either direction.',
  strangle: 'Strangle: Like a straddle but with DIFFERENT strikes (OTM). Cheaper than straddle, needs a bigger move to profit if long. Wider profit zone if short.',
  'bull-call-spread': 'Bull Call Spread: Buy a lower-strike Call, sell a higher-strike Call. Profits when price rises moderately. Capped profit but also capped risk (net debit).',
  'bear-put-spread': 'Bear Put Spread: Buy a higher-strike Put, sell a lower-strike Put. Profits when price falls moderately. Defined risk, defined reward.',
  'bear-call-spread': 'Bear Call Spread: Sell a lower-strike Call, buy a higher-strike Call. You collect a net credit upfront ("earn first") and keep it if price stays below the sold strike. Bearish/sideways. Defined risk, defined reward.',
  'bull-put-spread': 'Bull Put Spread: Sell a higher-strike Put, buy a lower-strike Put. You collect a net credit upfront ("earn first") and keep it if price stays above the sold strike. Bullish/sideways. Defined risk, defined reward.',
  'iron-condor': 'Iron Condor: Sell both a call spread and a put spread simultaneously. Profits when price stays in a range. 4 legs, defined risk on both sides. The "bread and butter" of premium sellers.',
  'ema-stochastic-scalper': 'EMA-Stochastic Scalper: Bilateral Bank Nifty options scalping. Uses RSI oversold/overbought as entry trigger (proxy for Stochastic) with trend confirmation. Buys CE on dips, PE on rallies. 15-pt target, 10-pt SL, up to 5 trades per direction.',
  'ema-cross-long': 'EMA Cross Long: Buys when a fast EMA crosses above a slow EMA, signaling bullish momentum. Simple trend-following entry.',
  'ema-cross-short': 'EMA Cross Short: Sells when a fast EMA crosses below a slow EMA, signaling bearish momentum.',
  'ema-cross-pair': 'EMA Cross Pair: Complete round-trip — buys on bullish EMA cross, auto-exits on bearish cross. Captures the full trend move.',
};

// ─── Equity Curve SVG ────────────────────────────────────────────────

function EquityCurve({ data, initialCapital }: { data: number[]; initialCapital: number }) {
  if (!data || data.length < 2) return null;

  const W = 800;
  const H = 250;
  const padX = 60;
  const padY = 30;
  const plotW = W - padX * 2;
  const plotH = H - padY * 2;

  const minVal = Math.min(...data);
  const maxVal = Math.max(...data);
  const range = maxVal - minVal || 1;

  const points = data.map((v, i) => {
    const x = padX + (i / (data.length - 1)) * plotW;
    const y = padY + plotH - ((v - minVal) / range) * plotH;
    return `${x},${y}`;
  }).join(' ');

  const finalUp = data[data.length - 1] >= initialCapital;
  const lineColor = finalUp ? '#22c55e' : '#ef4444';

  // Grid lines (5 horizontal)
  const gridLines = [];
  for (let i = 0; i <= 4; i++) {
    const y = padY + (i / 4) * plotH;
    const val = maxVal - (i / 4) * range;
    gridLines.push({ y, label: formatINR(val) });
  }

  // X-axis labels (every ~25% of trades)
  const xLabels = [];
  const step = Math.max(1, Math.floor(data.length / 4));
  for (let i = 0; i < data.length; i += step) {
    const x = padX + (i / (data.length - 1)) * plotW;
    xLabels.push({ x, label: `#${i + 1}` });
  }
  // Always include last
  if ((data.length - 1) % step !== 0) {
    xLabels.push({ x: padX + plotW, label: `#${data.length}` });
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 250 }}>
      {/* Grid */}
      {gridLines.map((g, i) => (
        <g key={i}>
          <line x1={padX} y1={g.y} x2={W - padX} y2={g.y} stroke="currentColor" strokeOpacity={0.1} strokeDasharray="4,4" />
          <text x={padX - 8} y={g.y + 4} textAnchor="end" className="fill-zinc-400 dark:fill-zinc-500" fontSize={10}>{g.label}</text>
        </g>
      ))}
      {/* X labels */}
      {xLabels.map((l, i) => (
        <text key={i} x={l.x} y={H - 6} textAnchor="middle" className="fill-zinc-400 dark:fill-zinc-500" fontSize={10}>{l.label}</text>
      ))}
      {/* Initial capital line */}
      {(() => {
        const iy = padY + plotH - ((initialCapital - minVal) / range) * plotH;
        return <line x1={padX} y1={iy} x2={W - padX} y2={iy} stroke="#f59e0b" strokeOpacity={0.4} strokeDasharray="6,3" />;
      })()}
      {/* Equity line */}
      <polyline
        points={points}
        fill="none"
        stroke={lineColor}
        strokeWidth={2.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ─── Metric Card ─────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  subValue,
  icon: Icon,
  color = 'zinc',
}: {
  label: string;
  value: string;
  subValue?: string;
  icon: any;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/30',
    red: 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30',
    amber: 'text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30',
    blue: 'text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30',
    purple: 'text-purple-600 dark:text-purple-400 bg-purple-100 dark:bg-purple-900/30',
    zinc: 'text-zinc-600 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800',
  };

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-lg ${colorMap[color] || colorMap.zinc}`}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{label}</span>
      </div>
      <div className="text-xl font-bold text-zinc-800 dark:text-zinc-200">{value}</div>
      {subValue && <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{subValue}</div>}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

export default function BacktestPage() {
  const { authToken } = useOutletContext<AuthContext>();

  // Mode toggle: template-based vs scalp-replay
  const [mode, setMode] = useState<'templates' | 'scalp'>('templates');

  // Template-mode state
  const [templates, setTemplates] = useState<BacktestTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [symbol, setSymbol] = useState('');
  const [days, setDays] = useState(30);
  const [interval, setInterval_] = useState('15minute');
  const [params, setParams] = useState<Record<string, any>>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Scalp-mode state
  const [scalpSessionMode, setScalpSessionMode] = useState<'equity_intraday' | 'equity_swing' | 'options_scalp'>('equity_intraday');
  const [scalpPrimary, setScalpPrimary] = useState('utbot');
  const [scalpPrimaryParams, setScalpPrimaryParams] = useState(SCALP_PRIMARY_INDICATORS[0].defaultParams);
  const [scalpConfirm, setScalpConfirm] = useState('');
  const [scalpConfirmParams, setScalpConfirmParams] = useState('');
  const [scalpSL, setScalpSL] = useState<string>('');
  const [scalpTarget, setScalpTarget] = useState<string>('');
  const [scalpTrailPoints, setScalpTrailPoints] = useState<string>('');
  const [scalpTrailArm, setScalpTrailArm] = useState<string>('');
  const [scalpSquareoff, setScalpSquareoff] = useState('15:09');
  // Direction gate for new entries. "both" | "long" | "short". For options
  // scalp, long → CE-only, short → PE-only. Mirrors live session entry_side.
  const [scalpEntrySide, setScalpEntrySide] = useState<'both' | 'long' | 'short'>('both');
  const [scalpQuantity, setScalpQuantity] = useState<string>('10');
  const [scalpMaxTrades, setScalpMaxTrades] = useState<string>('20');
  const [scalpCooldown, setScalpCooldown] = useState<string>('60');
  const [scalpSlippageBps, setScalpSlippageBps] = useState<string>('0');
  // Options scalp specific state. Mirrors /scalp-sessions field layout so a
  // backtested config can be saved as a live session without remapping.
  const [scalpUnderlying, setScalpUnderlying] = useState<string>('NIFTY');
  const [scalpExpiry, setScalpExpiry] = useState<string>('');
  const [scalpLots, setScalpLots] = useState<string>('1');
  const [scalpExpiries, setScalpExpiries] = useState<string[]>([]);
  // Fixed expiry (pick one date) vs rolling front weekly (engine resolves the
  // front-of-book weekly per signal flip → sends sentinel expiry "rolling").
  const [scalpExpiryMode, setScalpExpiryMode] = useState<'fixed' | 'rolling'>('fixed');

  // Results + job state
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [progressDone, setProgressDone] = useState<number | null>(null);
  const [progressTotal, setProgressTotal] = useState<number | null>(null);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  // Wall-clock since the job started — gives the user a "this is taking N
  // seconds" signal, which paired with bars/sec makes long runs feel alive.
  const [jobStartedAt, setJobStartedAt] = useState<number | null>(null);
  const [jobElapsedMs, setJobElapsedMs] = useState<number>(0);
  const eventSourceRef = React.useRef<EventSource | null>(null);

  // Run history (sidebar)
  const [history, setHistory] = useState<any[]>([]);

  // Tick the elapsed timer once per second while a job is running.
  useEffect(() => {
    if (!jobStartedAt) return;
    const id = setInterval(() => {
      setJobElapsedMs(Date.now() - jobStartedAt);
    }, 250);
    return () => clearInterval(id);
  }, [jobStartedAt]);

  // Fetch templates
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/backtest/templates', {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          setTemplates(data.templates || data || []);
        }
      } catch (e) {
        console.error('Failed to fetch backtest templates:', e);
      }
    })();
  }, [authToken]);

  // Fetch option expiries when underlying changes (options-scalp mode only).
  // Mirrors /scalp-sessions: same endpoint, default to first expiry on load.
  useEffect(() => {
    if (scalpSessionMode !== 'options_scalp' || !scalpUnderlying) return;
    fetch(`/api/strategies/expiries?underlying=${scalpUnderlying}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then(r => r.ok ? r.json() : { expiries: [] })
      .then(d => {
        const list = d.expiries || [];
        setScalpExpiries(list);
        if (list.length && (!scalpExpiry || !list.includes(scalpExpiry))) {
          setScalpExpiry(list[0]);
        }
      })
      .catch(() => setScalpExpiries([]));
    // scalpExpiry intentionally excluded — we only want to refetch on
    // underlying or auth change, not when the user picks a different expiry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scalpUnderlying, scalpSessionMode, authToken]);

  // Update params when template changes — seed required params with defaults too
  useEffect(() => {
    const t = templates.find(t => t.name === selectedTemplate);
    const newParams: Record<string, any> = {};
    if (t?.optional_params) {
      Object.assign(newParams, t.optional_params);
    }
    // Seed required params with sensible defaults
    if (t?.required_params) {
      for (const p of t.required_params) {
        if (!(p in newParams)) {
          if (p === 'capital') newParams[p] = 200000;
          else if (p === 'lots') newParams[p] = 1;
          else if (p === 'symbol') continue; // handled separately
        }
      }
    }
    setParams(newParams);
  }, [selectedTemplate, templates]);

  const currentTemplate = templates.find(t => t.name === selectedTemplate);

  const isFnO = currentTemplate?.category === 'fno';

  // ── Job-based run helpers ──────────────────────────────────────────
  // The legacy single-fetch pattern (still left in place server-side as a
  // safety net) blocked uvicorn for the duration of a run. The new flow:
  // 1) POST /api/backtest/jobs → returns {job_id} immediately
  // 2) Open SSE on /api/backtest/jobs/{id}/stream → live progress + final result
  // 3) DELETE /api/backtest/jobs/{id} → cancel mid-run

  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/backtest/jobs?limit=25', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.jobs || []);
      }
    } catch {
      // History is non-critical — silent.
    }
  }, [authToken]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  // Remove a single history row. Backend semantics: cancels active jobs,
  // hard-deletes terminal ones — same DELETE endpoint either way. After
  // the call we refresh and, if the user was viewing that run's result,
  // clear the results panel so they aren't looking at a deleted run.
  const deleteHistoryRow = useCallback(async (id: number) => {
    try {
      const res = await fetch(`/api/backtest/jobs/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) return;
      if (jobId === id) {
        setResult(null);
        setJobId(null);
        setJobStatus(null);
      }
      await refreshHistory();
    } catch {
      // Non-critical — user can retry.
    }
  }, [authToken, jobId, refreshHistory]);

  // Clear all terminal history rows in one call. Confirms via window.confirm
  // because it can't be undone — the rows are gone after this. Active jobs
  // are preserved server-side, so a clear during a running replay won't
  // wipe the in-flight row.
  const clearAllHistory = useCallback(async () => {
    if (!window.confirm('Clear all completed backtest runs from history? Active runs are kept.')) return;
    try {
      const res = await fetch('/api/backtest/jobs', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) return;
      // If the currently-viewed result was a terminal job, clear it too.
      if (result && jobStatus !== 'running' && jobStatus !== 'queued') {
        setResult(null);
        setJobId(null);
        setJobStatus(null);
      }
      await refreshHistory();
    } catch {
      // Non-critical.
    }
  }, [authToken, refreshHistory, result, jobStatus]);

  const startJob = useCallback(async (kind: string, name: string, config: any) => {
    closeStream();
    setError(null);
    setResult(null);
    setJobId(null);
    setJobStatus(null);
    setProgressDone(null);
    setProgressTotal(null);
    setProgressMessage(null);
    setRunning(true);
    setJobStartedAt(Date.now());
    setJobElapsedMs(0);

    let createdId: number | null = null;
    try {
      const res = await fetch('/api/backtest/jobs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ kind, name, config }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Failed to create backtest job');
        setRunning(false);
        setJobStartedAt(null);
        return;
      }
      createdId = data.job_id;
      setJobId(createdId);
      setJobStatus('queued');
    } catch (e: any) {
      setError(e.message || 'Network error creating job');
      setRunning(false);
      setJobStartedAt(null);
      return;
    }

    // Open SSE. EventSource doesn't support custom headers, so we pass the
    // token via query param. The backend reads it via the same auth path.
    // (If we don't already accept tokens via query string, we'll need to —
    // but checking auth.py shows it reads Authorization header only. Fall
    // back to a manual fetch+ReadableStream parser.)
    const stream = openSseStream(createdId!, authToken, {
      onEvent: (data) => {
        setJobStatus(data.status);
        setProgressDone(data.progress_done);
        setProgressTotal(data.progress_total);
        setProgressMessage(data.progress_message);
        if (data.status === 'completed' && data.result) {
          setResult(data.result);
          setRunning(false);
          setJobStartedAt(null);
          refreshHistory();
        } else if (data.status === 'failed') {
          setError(data.error_message || 'Backtest failed');
          setRunning(false);
          setJobStartedAt(null);
          refreshHistory();
        } else if (data.status === 'cancelled') {
          setError('Backtest cancelled');
          setRunning(false);
          setJobStartedAt(null);
          refreshHistory();
        }
      },
      onError: (msg) => {
        setError(msg);
        setRunning(false);
        setJobStartedAt(null);
      },
    });
    eventSourceRef.current = stream as any;
  }, [authToken, closeStream, refreshHistory]);

  const cancelCurrentJob = useCallback(async () => {
    if (!jobId) return;
    try {
      await fetch(`/api/backtest/jobs/${jobId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      // Don't close the stream — let the SSE drive UI to "cancelled" state
      // so the user sees the transition.
    } catch (e: any) {
      setError('Cancel request failed: ' + (e.message || ''));
    }
  }, [authToken, jobId]);

  // Click a row in the history sidebar — load that run's saved result
  // straight into the results panel without re-running.
  const loadHistoricRun = useCallback(async (id: number) => {
    closeStream();
    setError(null);
    setRunning(false);
    setJobStartedAt(null);
    try {
      const res = await fetch(`/api/backtest/jobs/${id}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Failed to load run');
        return;
      }
      setJobId(id);
      setJobStatus(data.status);
      if (data.status === 'completed') {
        setResult(data.result);
      } else if (data.status === 'failed') {
        setError(data.error_message || 'This run failed');
        setResult(null);
      } else {
        // Re-attach to a still-running job (possible after a refresh).
        setRunning(true);
        setJobStartedAt(Date.now());
        const stream = openSseStream(id, authToken, {
          onEvent: (d) => {
            setJobStatus(d.status);
            setProgressDone(d.progress_done);
            setProgressTotal(d.progress_total);
            setProgressMessage(d.progress_message);
            if (d.status === 'completed' && d.result) {
              setResult(d.result);
              setRunning(false);
              setJobStartedAt(null);
              refreshHistory();
            } else if (d.status === 'failed' || d.status === 'cancelled') {
              setRunning(false);
              setJobStartedAt(null);
              refreshHistory();
            }
          },
          onError: (msg) => {
            setError(msg);
            setRunning(false);
            setJobStartedAt(null);
          },
        });
        eventSourceRef.current = stream as any;
      }
    } catch (e: any) {
      setError(e.message || 'Network error');
    }
  }, [authToken, closeStream, refreshHistory]);

  // Clean up the stream on unmount.
  useEffect(() => {
    return () => closeStream();
  }, [closeStream]);

  const runBacktest = async () => {
    const kind = isFnO ? 'fno' : 'equity';
    const config = isFnO
      ? { template: selectedTemplate, days, interval, params }
      : { template: selectedTemplate, symbol, days, interval, params };
    const name = isFnO
      ? `${selectedTemplate} · ${params?.underlying || ''} · ${days}d`
      : `${selectedTemplate} · ${symbol} · ${days}d`;
    await startJob(kind, name, config);
  };

  const runScalpBacktest = async () => {
    const parseJson = (s: string, fallback: any): any => {
      if (!s.trim()) return fallback;
      try {
        return JSON.parse(s);
      } catch {
        return null;
      }
    };
    const primaryParams = parseJson(scalpPrimaryParams, null);
    if (scalpPrimaryParams.trim() && primaryParams === null) {
      setError('Primary params must be valid JSON');
      return;
    }
    const confirmParams = scalpConfirm
      ? parseJson(scalpConfirmParams, {}) : null;
    if (scalpConfirm && scalpConfirmParams.trim() && confirmParams === null) {
      setError('Confirm params must be valid JSON');
      return;
    }

    const toNum = (s: string): number | null =>
      s.trim() === '' ? null : Number(s);

    const isOptions = scalpSessionMode === 'options_scalp';
    const config: Record<string, any> = {
      days,
      interval,
      session_mode: scalpSessionMode,
      primary_indicator: scalpPrimary,
      primary_params: primaryParams,
      confirm_indicator: scalpConfirm || null,
      confirm_params: confirmParams,
      sl_points: toNum(scalpSL),
      target_points: toNum(scalpTarget),
      trail_points: toNum(scalpTrailPoints),
      trail_arm_points: toNum(scalpTrailArm),
      squareoff_time: scalpSquareoff,
      entry_side: scalpEntrySide,
      max_trades: parseInt(scalpMaxTrades) || 20,
      cooldown_seconds: parseInt(scalpCooldown) || 0,
      slippage_bps: parseFloat(scalpSlippageBps) || 0,
    };

    if (isOptions) {
      // Options-scalp uses underlying/expiry/lots; the engine resolves ATM
      // dynamically at each flip and fetches the matching CE/PE leg.
      const rolling = scalpExpiryMode === 'rolling';
      if (!scalpUnderlying || (!rolling && !scalpExpiry)) {
        setError('Underlying and expiry are required for options scalp');
        return;
      }
      config.underlying = scalpUnderlying;
      // Backend also reads `symbol` as a fallback for the underlying name —
      // populate both so result-rendering paths that key off `symbol` keep
      // working without a frontend code change.
      config.symbol = scalpUnderlying;
      // Rolling sends the sentinel; the engine resolves the front-of-book
      // weekly that was live on each signal-flip date.
      config.expiry = rolling ? 'rolling' : scalpExpiry;
      config.lots = parseInt(scalpLots) || 1;
    } else {
      if (!symbol) {
        setError('Symbol is required for equity scalp');
        return;
      }
      config.symbol = symbol;
      config.quantity = parseInt(scalpQuantity) || 0;
    }

    const labelLeft = isOptions
      ? `${scalpUnderlying} ${scalpExpiryMode === 'rolling' ? 'rolling' : scalpExpiry}`
      : symbol;
    const name = `scalp · ${labelLeft} · ${interval} · ${days}d · ${scalpPrimary}`;
    await startJob('scalp', name, config);
  };

  const onScalpPrimaryChange = (value: string) => {
    setScalpPrimary(value);
    const spec = SCALP_PRIMARY_INDICATORS.find(i => i.value === value);
    setScalpPrimaryParams(spec?.defaultParams ?? '{}');
  };

  const onScalpConfirmChange = (value: string) => {
    setScalpConfirm(value);
    const spec = SCALP_CONFIRM_INDICATORS.find(i => i.value === value);
    setScalpConfirmParams(spec?.defaultParams ?? '');
  };

  const updateParam = (key: string, value: any) => {
    setParams(prev => ({ ...prev, [key]: value }));
  };

  const m = result?.metrics;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-xl bg-blue-100 dark:bg-blue-900/30">
              <FlaskConical className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Strategy Backtester</h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Test strategies against historical data</p>
            </div>
          </div>
        </div>

        {/* Mode tabs */}
        <div className="mb-6 flex items-center gap-1 rounded-lg bg-zinc-100 dark:bg-zinc-800/50 p-1 w-fit">
          <button
            type="button"
            onClick={() => { setMode('templates'); setResult(null); setError(null); }}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${
              mode === 'templates'
                ? 'bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}
          >
            Strategy Templates
          </button>
          <button
            type="button"
            onClick={() => { setMode('scalp'); setResult(null); setError(null); }}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${
              mode === 'scalp'
                ? 'bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}
          >
            Scalp Replay
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Config Panel */}
          <div className="lg:col-span-1">
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-5 sticky top-8">
              <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-4">
                {mode === 'templates' ? 'Configuration' : 'Scalp Replay Config'}
              </h2>

              {mode === 'templates' && (
              <div className="space-y-4">
                {/* Template */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Strategy Template</label>
                  <select
                    className={selectClassName}
                    value={selectedTemplate}
                    onChange={e => setSelectedTemplate(e.target.value)}
                  >
                    <option value="">Select a template</option>
                    <optgroup label="Equity">
                      {templates.filter(t => t.category === 'equity').map(t => (
                        <option key={t.name} value={t.name}>
                          {t.name.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="F&amp;O">
                      {templates.filter(t => t.category === 'fno').map(t => (
                        <option key={t.name} value={t.name}>
                          {t.name.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                  {currentTemplate && (
                    <div className="mt-1">
                      <p className="text-xs text-zinc-400">{currentTemplate.description}</p>
                      {STRATEGY_TOOLTIPS[currentTemplate.name] && (
                        <p className="text-xs text-blue-500/70 dark:text-blue-400/60 mt-1 leading-relaxed">
                          {STRATEGY_TOOLTIPS[currentTemplate.name]}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Symbol (equity only) — autocomplete against /api/monitor/symbols */}
                {!isFnO && (
                  <div>
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Symbol</label>
                    <EquitySymbolPicker
                      authToken={authToken}
                      value={symbol}
                      onSelect={setSymbol}
                      placeholder="e.g. RELIANCE"
                    />
                  </div>
                )}

                {/* Days */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Lookback (days)</label>
                  <Input
                    type="number"
                    value={days}
                    onChange={e => setDays(parseInt(e.target.value) || 30)}
                    min={1}
                    max={365}
                  />
                </div>

                {/* Interval */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Candle Interval</label>
                  <select
                    className={selectClassName}
                    value={interval}
                    onChange={e => setInterval_(e.target.value)}
                  >
                    <option value="1minute">1 minute</option>
                    <option value="5minute">5 minutes</option>
                    <option value="15minute">15 minutes</option>
                    <option value="30minute">30 minutes</option>
                  </select>
                </div>

                {/* Dynamic Params */}
                {currentTemplate && currentTemplate.required_params.length > 0 && (
                  <div className="pt-2 border-t border-zinc-200 dark:border-zinc-700">
                    <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3">Strategy Parameters</h3>
                    {currentTemplate.required_params.filter(p => p !== 'symbol').map(p => {
                      const isString = STRING_PARAMS.has(p);
                      if (p === 'option_type') {
                        return (
                          <div key={p} className="mb-3">
                            <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                              Option Type
                              <span className="text-red-400 ml-1">*</span>
                            </label>
                            <select
                              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
                              value={params[p] ?? ''}
                              onChange={e => updateParam(p, e.target.value)}
                            >
                              <option value="">Select</option>
                              <option value="CE">Call (CE)</option>
                              <option value="PE">Put (PE)</option>
                            </select>
                          </div>
                        );
                      }
                      return (
                        <div key={p} className="mb-3">
                          <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                            {p.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                            <span className="text-red-400 ml-1">*</span>
                            {PARAM_TOOLTIPS[p] && <InfoTip text={PARAM_TOOLTIPS[p]} />}
                          </label>
                          <Input
                            type={isString ? 'text' : 'number'}
                            value={params[p] ?? ''}
                            onChange={e => updateParam(p, isString ? e.target.value.toUpperCase() : (parseFloat(e.target.value) || ''))}
                            placeholder="Required"
                          />
                        </div>
                      );
                    })}
                    {currentTemplate.optional_params && Object.keys(currentTemplate.optional_params).map(p => {
                      const defaultVal = currentTemplate.optional_params[p];
                      const isString = STRING_PARAMS.has(p) || (typeof defaultVal === 'string' && defaultVal !== '');
                      if (p === 'option_type') {
                        return (
                          <div key={p} className="mb-3">
                            <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                              Option Type
                            </label>
                            <select
                              className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
                              value={params[p] ?? ''}
                              onChange={e => updateParam(p, e.target.value)}
                            >
                              <option value="">Select</option>
                              <option value="CE">Call (CE)</option>
                              <option value="PE">Put (PE)</option>
                            </select>
                          </div>
                        );
                      }
                      return (
                        <div key={p} className="mb-3">
                          <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                            {p.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                            {PARAM_TOOLTIPS[p] && <InfoTip text={PARAM_TOOLTIPS[p]} />}
                          </label>
                          <Input
                            type={isString ? 'text' : 'number'}
                            value={params[p] ?? ''}
                            onChange={e => updateParam(p, isString ? e.target.value : (parseFloat(e.target.value) || ''))}
                            placeholder={`Default: ${defaultVal}`}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Run Button */}
                <Button
                  color="amber"
                  className="w-full justify-center mt-2"
                  onClick={runBacktest}
                  disabled={running || !selectedTemplate || (!isFnO && !symbol)}
                >
                  {running ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="ml-2">Running backtest...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span className="ml-2">Run Backtest</span>
                    </>
                  )}
                </Button>

                {error && (
                  <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    {error}
                  </div>
                )}
              </div>
              )}

              {/* Run history (sidebar bottom) ─────────────────────────
                   Shown after the form so the active form stays at the
                   top. Click any row to reload its result without
                   re-running. */}
              {mode === 'scalp' && (
              <div className="space-y-4">
                {/* Session mode — drives whether we render Symbol (equity) or
                    Underlying+Expiry (options). Kept above the instrument
                    fields so toggling the mode visually swaps them in place. */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Session Mode</label>
                  <select
                    className={selectClassName}
                    value={scalpSessionMode}
                    onChange={e => setScalpSessionMode(e.target.value as any)}
                  >
                    <option value="equity_intraday">Intraday (squareoff at cutoff)</option>
                    <option value="equity_swing">Swing / Delivery (hold across days)</option>
                    <option value="options_scalp">Options Scalp (ATM CE/PE on index)</option>
                  </select>
                </div>

                {/* Instrument — equity uses Symbol, options uses Underlying + Expiry. */}
                {scalpSessionMode === 'options_scalp' ? (
                  <div className="space-y-3">
                    {/* Fixed expiry vs rolling front weekly. Rolling sends the
                        sentinel expiry "rolling" — the engine resolves the
                        front-of-book weekly per signal-flip date. */}
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Expiry resolution</label>
                      <div className="flex items-center gap-1 rounded-lg bg-zinc-100 dark:bg-zinc-800/50 p-1 w-fit">
                        <button
                          type="button"
                          onClick={() => setScalpExpiryMode('fixed')}
                          className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                            scalpExpiryMode === 'fixed'
                              ? 'bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 shadow-sm'
                              : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                          }`}
                        >
                          Fixed expiry
                        </button>
                        <button
                          type="button"
                          onClick={() => setScalpExpiryMode('rolling')}
                          className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                            scalpExpiryMode === 'rolling'
                              ? 'bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 shadow-sm'
                              : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                          }`}
                        >
                          Rolling front weekly
                        </button>
                      </div>
                      {scalpExpiryMode === 'rolling' && (
                        <p className="mt-1.5 text-xs text-zinc-400 leading-relaxed">
                          Each signal resolves to the weekly that was front-of-book on that date — spans
                          multiple expiries, no young-contract truncation. Requires Upstox Plus.
                        </p>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Underlying</label>
                        <FnoUnderlyingPicker
                          authToken={authToken}
                          value={scalpUnderlying}
                          onSelect={(s) => { setScalpUnderlying(s); setScalpExpiry(''); }}
                        />
                      </div>
                      {scalpExpiryMode === 'fixed' && (
                        <div>
                          <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Expiry</label>
                          <select
                            className={selectClassName}
                            value={scalpExpiry}
                            onChange={e => setScalpExpiry(e.target.value)}
                          >
                            {scalpExpiries.length === 0 && <option value="">Loading…</option>}
                            {scalpExpiries.map(e => <option key={e} value={e}>{e}</option>)}
                          </select>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Symbol</label>
                    <EquitySymbolPicker
                      authToken={authToken}
                      value={symbol}
                      onSelect={setSymbol}
                      placeholder="e.g. RELIANCE, HDFCBANK"
                    />
                  </div>
                )}

                {/* Days */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Lookback (days)</label>
                  <Input
                    type="number"
                    value={days}
                    onChange={e => setDays(parseInt(e.target.value) || 30)}
                    min={1}
                    max={365}
                  />
                  <p className="mt-1 text-xs text-zinc-400">1-minute bars cap at ~30 days. Daily bars go back much further.</p>
                </div>

                {/* Interval */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Candle Interval</label>
                  <select
                    className={selectClassName}
                    value={interval}
                    onChange={e => setInterval_(e.target.value)}
                  >
                    <option value="1minute">1 minute</option>
                    <option value="5minute">5 minutes</option>
                    <option value="15minute">15 minutes</option>
                    <option value="30minute">30 minutes</option>
                    <option value="day">Daily</option>
                  </select>
                </div>

                {/* Indicator config */}
                <div className="pt-2 border-t border-zinc-200 dark:border-zinc-700">
                  <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3">Signal</h3>
                  <div className="mb-3">
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Primary Indicator</label>
                    <select
                      className={selectClassName}
                      value={scalpPrimary}
                      onChange={e => onScalpPrimaryChange(e.target.value)}
                    >
                      {SCALP_PRIMARY_INDICATORS.map(i => (
                        <option key={i.value} value={i.value}>{i.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="mb-3">
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Primary Params (JSON)</label>
                    <textarea
                      className={`${selectClassName} font-mono text-xs`}
                      rows={2}
                      value={scalpPrimaryParams}
                      onChange={e => setScalpPrimaryParams(e.target.value)}
                    />
                  </div>
                  <div className="mb-3">
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                      Confirm Indicator
                      <InfoTip text="Optional filter — must agree with primary flip direction before entry. Leave as (none) to skip." />
                    </label>
                    <select
                      className={selectClassName}
                      value={scalpConfirm}
                      onChange={e => onScalpConfirmChange(e.target.value)}
                    >
                      {SCALP_CONFIRM_INDICATORS.map(i => (
                        <option key={i.value} value={i.value}>{i.label}</option>
                      ))}
                    </select>
                  </div>
                  {scalpConfirm && (
                    <div className="mb-3">
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Confirm Params (JSON)</label>
                      <textarea
                        className={`${selectClassName} font-mono text-xs`}
                        rows={2}
                        value={scalpConfirmParams}
                        onChange={e => setScalpConfirmParams(e.target.value)}
                      />
                    </div>
                  )}
                  <div>
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                      Position
                      <InfoTip text={scalpSessionMode === 'options_scalp'
                        ? 'Which side to take. "Both" buys CE on bullish flips and PE on bearish. "CE only" / "PE only" restrict to one direction.'
                        : 'Which side to take. "Both" goes long on bullish flips and short on bearish. "Long only" / "Short only" restrict to one direction. (Swing mode is delivery-only — shorts are skipped.)'} />
                    </label>
                    <select
                      className={selectClassName}
                      value={scalpEntrySide}
                      onChange={e => setScalpEntrySide(e.target.value as 'both' | 'long' | 'short')}
                    >
                      {scalpSessionMode === 'options_scalp' ? (
                        <>
                          <option value="both">Both (CE + PE)</option>
                          <option value="long">CE only (bullish)</option>
                          <option value="short">PE only (bearish)</option>
                        </>
                      ) : (
                        <>
                          <option value="both">Both (long + short)</option>
                          <option value="long">Long only</option>
                          <option value="short">Short only</option>
                        </>
                      )}
                    </select>
                  </div>
                </div>

                {/* Exits */}
                <div className="pt-2 border-t border-zinc-200 dark:border-zinc-700">
                  <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3">Exits</h3>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">SL Points</label>
                      <Input type="number" value={scalpSL} onChange={e => setScalpSL(e.target.value)} placeholder="optional" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Target Points</label>
                      <Input type="number" value={scalpTarget} onChange={e => setScalpTarget(e.target.value)} placeholder="optional" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Trail Arm</label>
                      <Input type="number" value={scalpTrailArm} onChange={e => setScalpTrailArm(e.target.value)} placeholder="profit pts" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Trail Points</label>
                      <Input type="number" value={scalpTrailPoints} onChange={e => setScalpTrailPoints(e.target.value)} placeholder="giveback" />
                    </div>
                  </div>
                  {scalpSessionMode !== 'equity_swing' && (
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                        Squareoff Time (IST)
                        <InfoTip text="Auto-close all positions at this time. Default 15:09. The exit lands on the bar live at the cutoff — on 15-min bars a 15:09 cutoff squares off on the 15:00–15:15 bar (shows ~15:15)." />
                      </label>
                      <Input type="text" value={scalpSquareoff} onChange={e => setScalpSquareoff(e.target.value)} placeholder="HH:MM" />
                    </div>
                  )}
                </div>

                {/* Sizing + discipline */}
                <div className="pt-2 border-t border-zinc-200 dark:border-zinc-700">
                  <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3">Sizing & Discipline</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {scalpSessionMode === 'options_scalp' ? (
                      <div>
                        <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                          Lots
                          <InfoTip text="Each lot = the contract's standard lot size (e.g. NIFTY 65, SENSEX 20, BANKEX 30). Stock options have their own per-symbol lot, which can differ by expiry — sizing uses the resolved contract's lot." />
                        </label>
                        <Input type="number" value={scalpLots} onChange={e => setScalpLots(e.target.value)} min={1} />
                      </div>
                    ) : (
                      <div>
                        <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Quantity</label>
                        <Input type="number" value={scalpQuantity} onChange={e => setScalpQuantity(e.target.value)} min={1} />
                      </div>
                    )}
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Max Trades / Day</label>
                      <Input type="number" value={scalpMaxTrades} onChange={e => setScalpMaxTrades(e.target.value)} />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Cooldown (s)</label>
                      <Input type="number" value={scalpCooldown} onChange={e => setScalpCooldown(e.target.value)} />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                        Slippage (bps)
                        <InfoTip text="Fill haircut in basis points. 1 bp = 0.01%. Default 0 for v1." />
                      </label>
                      <Input type="number" value={scalpSlippageBps} onChange={e => setScalpSlippageBps(e.target.value)} />
                    </div>
                  </div>
                </div>

                {/* Run Button */}
                <Button
                  color="amber"
                  className="w-full justify-center mt-2"
                  onClick={runScalpBacktest}
                  disabled={
                    running
                    || (scalpSessionMode === 'options_scalp'
                        ? (!scalpUnderlying || !scalpLots
                           || (scalpExpiryMode === 'fixed' && !scalpExpiry))
                        : (!symbol || !scalpQuantity))
                  }
                >
                  {running ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="ml-2">Running replay...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span className="ml-2">Run Scalp Replay</span>
                    </>
                  )}
                </Button>

                {error && (
                  <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    {error}
                  </div>
                )}
              </div>
              )}

              {/* Run history — last N completed/failed runs. Click a row
                   to reload its result without re-running. Stays in the
                   sticky config sidebar so it's always visible. */}
              {history.length > 0 && (
                <div className="mt-6 pt-4 border-t border-zinc-200 dark:border-zinc-700">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
                      Recent Runs
                    </h3>
                    <button
                      type="button"
                      onClick={clearAllHistory}
                      className="text-[10px] uppercase tracking-wide text-zinc-400 hover:text-red-500 dark:hover:text-red-400 flex items-center gap-1 transition-colors"
                      title="Delete all completed runs"
                    >
                      <Trash2 className="w-3 h-3" />
                      Clear
                    </button>
                  </div>
                  <div className="space-y-1 max-h-72 overflow-y-auto">
                    {history.map((j: any) => {
                      const isActive = j.id === jobId;
                      const statusColor =
                        j.status === 'completed' ? 'emerald' :
                        j.status === 'failed' ? 'red' :
                        j.status === 'cancelled' ? 'zinc' : 'amber';
                      const ts = j.created_at ? new Date(j.created_at + 'Z') : null;
                      const isTerminal = ['completed', 'failed', 'cancelled'].includes(j.status);
                      return (
                        <div
                          key={j.id}
                          className={`group relative rounded transition-colors ${
                            isActive
                              ? 'bg-amber-50 dark:bg-amber-900/20 ring-1 ring-amber-500/40'
                              : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
                          }`}
                        >
                          <button
                            onClick={() => loadHistoricRun(j.id)}
                            className="w-full text-left px-2 py-1.5 pr-7"
                          >
                            <div className="flex items-center justify-between gap-2 text-xs">
                              <span className="font-medium text-zinc-700 dark:text-zinc-300 truncate">
                                {j.config_summary || j.name || `${j.kind} #${j.id}`}
                              </span>
                              <Badge color={statusColor as any}>{j.status}</Badge>
                            </div>
                            <div className="text-[10px] text-zinc-400 mt-0.5">
                              {ts ? ts.toLocaleString('en-IN', {
                                timeZone: 'Asia/Kolkata',
                                month: 'short', day: 'numeric',
                                hour: '2-digit', minute: '2-digit', hour12: true,
                              }) : ''}
                            </div>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); deleteHistoryRow(j.id); }}
                            className="absolute top-1.5 right-1.5 p-0.5 rounded text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 opacity-0 group-hover:opacity-100 transition-opacity"
                            title={isTerminal ? 'Remove from history' : 'Cancel run'}
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-2">
            {!result && !running && (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <FlaskConical className="w-16 h-16 text-zinc-200 dark:text-zinc-800 mb-4" />
                <p className="text-zinc-500 dark:text-zinc-400 font-medium">No results yet</p>
                <p className="text-sm text-zinc-400 dark:text-zinc-500 mt-1 max-w-sm">
                  Select a strategy template, enter a symbol, and click "Run Backtest" to see how the strategy would have performed historically.
                </p>
              </div>
            )}

            {running && (
              <div className="rounded-xl border border-amber-200 dark:border-amber-800/50 bg-amber-50/50 dark:bg-amber-900/10 p-6">
                <div className="flex items-start gap-4">
                  <Loader2 className="w-6 h-6 animate-spin text-amber-500 flex-shrink-0 mt-1" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-3 mb-1">
                      <p className="font-semibold text-zinc-700 dark:text-zinc-200">
                        {jobStatus === 'queued' ? 'Queued' :
                         jobStatus === 'running' ? 'Running backtest' :
                         jobStatus === 'cancelled' ? 'Cancelling…' :
                         'Starting…'}
                      </p>
                      <span className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                        {(jobElapsedMs / 1000).toFixed(1)}s
                      </span>
                    </div>
                    {progressMessage && (
                      <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">{progressMessage}</p>
                    )}
                    {progressTotal && progressTotal > 0 ? (
                      <>
                        <div className="h-2 rounded-full bg-amber-200/40 dark:bg-amber-900/30 overflow-hidden mb-1">
                          <div
                            className="h-full bg-amber-500 transition-all duration-200"
                            style={{ width: `${Math.min(100, ((progressDone ?? 0) / progressTotal) * 100)}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                          <span>{(progressDone ?? 0).toLocaleString()} / {progressTotal.toLocaleString()}</span>
                          <span>
                            {(() => {
                              const done = progressDone ?? 0;
                              const pct = progressTotal > 0 ? (done / progressTotal) * 100 : 0;
                              const elapsed = jobElapsedMs / 1000;
                              const rate = elapsed > 0 && done > 0 ? done / elapsed : 0;
                              return `${pct.toFixed(1)}%${rate > 0 ? ` · ${Math.round(rate).toLocaleString()}/s` : ''}`;
                            })()}
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="h-2 rounded-full bg-amber-200/40 dark:bg-amber-900/30 overflow-hidden">
                        <div className="h-full w-1/3 bg-amber-500 animate-pulse" />
                      </div>
                    )}
                    <div className="mt-4 flex items-center gap-2">
                      <Button
                        outline
                        onClick={cancelCurrentJob}
                        disabled={!jobId || jobStatus === 'cancelled'}
                      >
                        Cancel
                      </Button>
                      {jobId && (
                        <span className="text-xs text-zinc-400 font-mono">job #{jobId}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result && m && (
              <div className="space-y-6">
                {/* Plausibility warnings — server-computed red flags, shown
                    first so a 10+ Sharpe never renders without its caveats. */}
                {result.warnings && result.warnings.length > 0 && (
                  <div className="rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 p-4">
                    <div className="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-300 mb-2">
                      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                      Plausibility check — read before believing the numbers
                    </div>
                    <ul className="space-y-1.5 text-sm text-amber-800 dark:text-amber-200 list-disc pl-5">
                      {result.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                    {result.first_trade_date && result.last_trade_date && (
                      <div className="mt-2 text-xs text-amber-700 dark:text-amber-400">
                        Effective trade span: {result.first_trade_date} → {result.last_trade_date}
                        {result.days ? ` (requested window: ${result.days}d)` : ''}
                      </div>
                    )}
                  </div>
                )}

                {/* Strategy summary — what produced this run. Renders from the
                    saved config so a historic run reloaded from the sidebar
                    shows its indicator / confirm / position / squareoff. */}
                {result.config && (() => {
                  const cfg = result.config!;
                  const mode = cfg.session_mode || result.session_mode;
                  const isOpt = mode === 'options_scalp';
                  // Rolling runs carry expiry === "rolling"; show the weeklies
                  // span from expiries_used when present (absent on old runs).
                  const expiriesUsed = result.expiries_used;
                  let expiryLabel = '';
                  if (isOpt) {
                    if (cfg.expiry === 'rolling') {
                      expiryLabel = ' · rolling weeklies';
                      if (expiriesUsed?.length) {
                        const span = expiriesUsed.length > 1
                          ? ` (${expiriesUsed[0]} → ${expiriesUsed[expiriesUsed.length - 1]})`
                          : ` (${expiriesUsed[0]})`;
                        expiryLabel += ` · ${expiriesUsed.length} expir${expiriesUsed.length === 1 ? 'y' : 'ies'}${span}`;
                      }
                    } else if (cfg.expiry) {
                      expiryLabel = ` · ${cfg.expiry}`;
                    }
                  }
                  const instrument = isOpt
                    ? `${cfg.underlying || cfg.symbol || result.symbol || '?'}${expiryLabel}`
                    : (cfg.symbol || cfg.underlying || result.symbol || '?');
                  const sizing = isOpt
                    ? `${cfg.lots ?? '?'} lot${(cfg.lots ?? 0) === 1 ? '' : 's'}`
                    : `${cfg.quantity ?? '?'} qty`;
                  const rows: Array<[string, string]> = [
                    ['Instrument', instrument],
                    ['Mode', String(mode || '?').replace(/_/g, ' ')],
                    ['Primary', `${indicatorLabel(cfg.primary_indicator)}${
                      cfg.primary_params && Object.keys(cfg.primary_params).length
                        ? `  ${JSON.stringify(cfg.primary_params)}` : ''}`],
                    ['Confirm', cfg.confirm_indicator
                      ? `${indicatorLabel(cfg.confirm_indicator)}${
                          cfg.confirm_params && Object.keys(cfg.confirm_params).length
                            ? `  ${JSON.stringify(cfg.confirm_params)}` : ''}`
                      : '(none)'],
                    ['Position', positionLabel(cfg.entry_side, mode)],
                    ['Interval / Window', `${result.interval || cfg.indicator_timeframe || '?'} · ${cfg.days ?? result.days ?? '?'}d`],
                    ['Squareoff', mode === 'equity_swing' ? '— (swing)' : (cfg.squareoff_time || '15:09')],
                    ['Sizing', sizing],
                  ];
                  return (
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-5">
                      <div className="flex items-center gap-2 mb-3">
                        <FlaskConical className="w-4 h-4 text-amber-500" />
                        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Strategy</h3>
                      </div>
                      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-3">
                        {rows.map(([k, v]) => (
                          <div key={k} className="min-w-0">
                            <dt className="text-[10px] uppercase tracking-wide text-zinc-400 dark:text-zinc-500">{k}</dt>
                            <dd className="text-sm font-medium text-zinc-700 dark:text-zinc-200 break-words font-mono">{v}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  );
                })()}

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {/* Shared metrics (both equity and F&O) */}
                  <MetricCard
                    label={m.total_days != null ? 'Days Traded' : 'Total Trades'}
                    value={String(m.total_days ?? m.total_trades ?? 0)}
                    subValue={m.total_days != null
                      ? `${m.winning_days ?? 0}W / ${m.losing_days ?? 0}L`
                      : `${m.winners ?? 0}W / ${m.losers ?? 0}L`}
                    icon={BarChart3}
                    color="zinc"
                  />
                  <MetricCard
                    label="Win Rate"
                    value={`${(m.win_rate ?? 0).toFixed(1)}%`}
                    icon={Target}
                    color={(m.win_rate ?? 0) >= 50 ? 'emerald' : 'red'}
                  />
                  {(() => {
                    // When result.metrics_net is present (scalp replay), prefer its net P&L in
                    // the headline card so Net actually means net-of-charges. Otherwise fall
                    // back to metrics.net_pnl (template backtests don't model charges).
                    const netSource = result.metrics_net ?? m;
                    const netVal = netSource.net_pnl ?? 0;
                    const retPct = netSource.return_pct ?? m.return_pct ?? 0;
                    return (
                      <MetricCard
                        label="Net P&L"
                        value={formatINR(netVal)}
                        subValue={`${retPct >= 0 ? '+' : ''}${retPct.toFixed(2)}%`}
                        icon={netVal >= 0 ? TrendingUp : TrendingDown}
                        color={netVal >= 0 ? 'emerald' : 'red'}
                      />
                    );
                  })()}
                  <MetricCard
                    label="Profit Factor"
                    value={m.profit_factor === 'inf' || m.profit_factor === Infinity ? '--' : Number(m.profit_factor ?? 0).toFixed(2)}
                    icon={Trophy}
                    color={Number(m.profit_factor ?? 0) >= 1.5 ? 'emerald' : Number(m.profit_factor ?? 0) >= 1 ? 'amber' : 'red'}
                  />
                  <MetricCard
                    label="Sharpe Ratio"
                    value={(m.sharpe_ratio ?? 0).toFixed(2)}
                    icon={BarChart3}
                    color={(m.sharpe_ratio ?? 0) >= 1 ? 'emerald' : (m.sharpe_ratio ?? 0) >= 0 ? 'amber' : 'red'}
                  />
                  <MetricCard
                    label="Max Drawdown"
                    value={`${(m.max_drawdown_pct ?? 0).toFixed(2)}%`}
                    icon={TrendingDown}
                    color={(m.max_drawdown_pct ?? 0) <= 5 ? 'emerald' : (m.max_drawdown_pct ?? 0) <= 15 ? 'amber' : 'red'}
                  />
                  {/* F&O: charges + avg day P&L. Equity: expectancy + hold time */}
                  {m.total_charges != null ? (
                    <>
                      <MetricCard
                        label="Total Charges"
                        value={formatINR(m.total_charges)}
                        subValue={`${m.total_legs_traded ?? 0} legs traded`}
                        icon={ArrowDownRight}
                        color="red"
                      />
                      <MetricCard
                        label="Avg Day P&L"
                        value={formatINR(m.avg_day_pnl ?? 0)}
                        subValue={`Best: ${formatINR(m.best_day ?? 0)}`}
                        icon={(m.avg_day_pnl ?? 0) >= 0 ? ArrowUpRight : ArrowDownRight}
                        color={(m.avg_day_pnl ?? 0) >= 0 ? 'emerald' : 'red'}
                      />
                    </>
                  ) : (
                    <>
                      <MetricCard
                        label="Expectancy"
                        value={formatINR(m.expectancy ?? 0)}
                        subValue="per trade"
                        icon={ArrowUpRight}
                        color={(m.expectancy ?? 0) >= 0 ? 'emerald' : 'red'}
                      />
                      <MetricCard
                        label="Avg Hold Time"
                        value={m.avg_holding_minutes ? `${m.avg_holding_minutes.toFixed(0)} min` : '--'}
                        icon={Clock}
                        color="blue"
                      />
                    </>
                  )}
                </div>

                {/* Equity Curve */}
                {result.equity_curve && result.equity_curve.length > 1 && (
                  <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-5">
                    <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-3">Equity Curve</h3>
                    <EquityCurve data={result.equity_curve} initialCapital={result.initial_capital} />
                  </div>
                )}

                {/* Scalp Replay: gross vs net + diagnostics */}
                {result.diagnostics && result.metrics_net && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-5">
                      <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-3">
                        Gross vs Net P&L
                      </h3>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-zinc-500 dark:text-zinc-400">Gross P&L</span>
                          <span className={`font-mono font-semibold ${result.metrics.net_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                            {formatINR(result.metrics.net_pnl ?? 0)}
                          </span>
                        </div>
                        <div className="flex justify-between text-zinc-400">
                          <span>Charges (round-trip)</span>
                          <span className="font-mono">−{formatINR(result.charges_total ?? 0)}</span>
                        </div>
                        {(result.slippage_total ?? 0) > 0 && (
                          <div className="flex justify-between text-zinc-400">
                            <span>Slippage</span>
                            <span className="font-mono">−{formatINR(result.slippage_total ?? 0)}</span>
                          </div>
                        )}
                        <div className="border-t border-zinc-200 dark:border-zinc-700 pt-2 flex justify-between">
                          <span className="text-zinc-600 dark:text-zinc-300 font-medium">Net P&L</span>
                          <span className={`font-mono font-bold ${result.metrics_net.net_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                            {formatINR(result.metrics_net.net_pnl ?? 0)}
                          </span>
                        </div>
                      </div>

                      {/* Cost-drag callout. The single biggest reason
                          equity scalp Net looks brutal vs Gross is the
                          fixed ₹60 round-trip brokerage on Upstox Plus —
                          it dominates small-quantity trades. Surface
                          this directly so users don't blame the strategy
                          for what's actually a sizing issue. */}
                      {(() => {
                        const trades = result.trades ?? [];
                        if (trades.length === 0) return null;
                        const totalNotional = trades.reduce(
                          (s: number, t: any) => s + (t.entry_price ?? 0) * (t.quantity ?? 0), 0
                        );
                        const avgNotional = totalNotional / trades.length;
                        const totalCharges = result.charges_total ?? 0;
                        const chargesPerTrade = totalCharges / trades.length;
                        const drag = totalNotional > 0 ? (totalCharges / totalNotional) * 100 : 0;
                        const lowSize = avgNotional > 0 && avgNotional < 50000;
                        return (
                          <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800/50 space-y-1 text-xs">
                            <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                              <span>Avg notional / trade</span>
                              <span className="font-mono">{formatINR(avgNotional)}</span>
                            </div>
                            <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                              <span>Avg charges / trade</span>
                              <span className="font-mono">{formatINR(chargesPerTrade)}</span>
                            </div>
                            <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                              <span>Cost drag (charges / turnover)</span>
                              <span className={`font-mono ${drag > 1 ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                                {drag.toFixed(2)}%
                              </span>
                            </div>
                            {lowSize && (
                              <div className="mt-2 p-2 rounded bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/50 leading-relaxed">
                                ⚠️ Avg notional below ₹50k. Upstox Plus equity intraday charges
                                ~₹75/round-trip (mostly the ₹60 brokerage flat fee). Strategies
                                at this size pay ~7%+ in charges before any move — the issue is
                                sizing, not the signal. Increase quantity or test on Kotak Neo
                                (zero brokerage on API orders) when that integration ships.
                              </div>
                            )}
                          </div>
                        );
                      })()}
                    </div>

                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-5">
                      <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-3">
                        Replay Diagnostics
                      </h3>
                      <div className="space-y-1.5 text-sm">
                        <div className="flex justify-between">
                          <span className="text-zinc-500 dark:text-zinc-400">Primary flips</span>
                          <span className="font-mono text-zinc-700 dark:text-zinc-300">{result.diagnostics.primary_flips}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500 dark:text-zinc-400">Blocked by confirm</span>
                          <span className="font-mono text-zinc-700 dark:text-zinc-300">{result.diagnostics.confirm_blocks}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500 dark:text-zinc-400">Blocked by cooldown</span>
                          <span className="font-mono text-zinc-700 dark:text-zinc-300">{result.diagnostics.cooldown_blocks}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500 dark:text-zinc-400">Blocked by max-trades</span>
                          <span className="font-mono text-zinc-700 dark:text-zinc-300">{result.diagnostics.max_trades_blocks}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500 dark:text-zinc-400">Squareoff exits</span>
                          <span className="font-mono text-zinc-700 dark:text-zinc-300">{result.diagnostics.squareoff_exits}</span>
                        </div>
                        {(result.diagnostics.entry_side_blocks ?? 0) > 0 && (
                          <div className="flex justify-between">
                            <span className="text-zinc-500 dark:text-zinc-400">Blocked by position filter</span>
                            <span className="font-mono text-zinc-700 dark:text-zinc-300">{result.diagnostics.entry_side_blocks}</span>
                          </div>
                        )}
                        {(() => {
                          const total = result.trades?.length ?? 0;
                          const ambig = result.diagnostics!.intra_bar_ambiguity;
                          const pct = total > 0 ? (100 * ambig / total) : 0;
                          const warn = pct > 20;
                          return (
                            <div className="flex justify-between items-center">
                              <span className="text-zinc-500 dark:text-zinc-400">Intra-bar ambiguity</span>
                              <span className={`font-mono ${warn ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-zinc-700 dark:text-zinc-300'}`}>
                                {ambig}/{total} ({pct.toFixed(1)}%)
                              </span>
                            </div>
                          );
                        })()}
                        {(() => {
                          const total = result.trades?.length ?? 0;
                          const ambig = result.diagnostics!.intra_bar_ambiguity;
                          const pct = total > 0 ? (100 * ambig / total) : 0;
                          if (pct > 20) {
                            return (
                              <div className="mt-2 p-2 text-xs rounded bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/50">
                                ⚠️ High intra-bar ambiguity — results approximate. Consider a smaller interval.
                              </div>
                            );
                          }
                          return null;
                        })()}
                      </div>
                    </div>
                  </div>
                )}

                {/* F&O Day Results */}
                {result.day_results && result.day_results.length > 0 && (
                  <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 overflow-hidden">
                    <div className="px-5 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                      <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                        Day-by-Day Breakdown ({result.day_results.length} days)
                      </h3>
                    </div>
                    <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                      {result.day_results.map((day, di) => (
                        <div key={di} className="border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
                          <div className={`px-5 py-2.5 flex items-center justify-between ${day.net_pnl >= 0 ? 'bg-emerald-50/50 dark:bg-emerald-900/10' : 'bg-red-50/50 dark:bg-red-900/10'}`}>
                            <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{day.date}</span>
                            <div className="flex items-center gap-4 text-xs">
                              <span className={`font-semibold font-mono ${day.net_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                                Net: {formatINR(day.net_pnl)}
                              </span>
                              <span className="text-zinc-400">Charges: {formatINR(day.charges)}</span>
                            </div>
                          </div>
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-zinc-50/50 dark:bg-zinc-800/30">
                                <th className="text-left px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Leg</th>
                                <th className="text-left px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Side</th>
                                <th className="text-right px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Entry</th>
                                <th className="text-right px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Exit</th>
                                <th className="text-right px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Qty</th>
                                <th className="text-right px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Gross</th>
                                <th className="text-right px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Charges</th>
                                <th className="text-right px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Net</th>
                                <th className="text-left px-4 py-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Exit</th>
                              </tr>
                            </thead>
                            <tbody>
                              {day.legs.map((lt, li) => (
                                <tr key={li} className="border-t border-zinc-50 dark:border-zinc-800/30">
                                  <td className="px-4 py-1.5 text-xs text-zinc-600 dark:text-zinc-400">{lt.label}</td>
                                  <td className="px-4 py-1.5">
                                    <Badge color={lt.side === 'BUY' ? 'emerald' : 'red'}>{lt.side}</Badge>
                                  </td>
                                  <td className="px-4 py-1.5 text-right font-mono text-xs text-zinc-700 dark:text-zinc-300">{formatINR(lt.entry_price)}</td>
                                  <td className="px-4 py-1.5 text-right font-mono text-xs text-zinc-700 dark:text-zinc-300">{formatINR(lt.exit_price)}</td>
                                  <td className="px-4 py-1.5 text-right text-xs text-zinc-500">{lt.quantity}</td>
                                  <td className={`px-4 py-1.5 text-right font-mono text-xs ${lt.gross_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                                    {formatINR(lt.gross_pnl)}
                                  </td>
                                  <td className="px-4 py-1.5 text-right font-mono text-xs text-zinc-400">{formatINR(lt.charges.total)}</td>
                                  <td className={`px-4 py-1.5 text-right font-semibold font-mono text-xs ${lt.net_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                                    {formatINR(lt.net_pnl)}
                                  </td>
                                  <td className="px-4 py-1.5">
                                    <Badge color={exitReasonColor(lt.exit_reason)}>{lt.exit_reason}</Badge>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Equity Trades Table */}
                {result.trades && result.trades.length > 0 && (
                  <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 overflow-hidden">
                    <div className="px-5 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                      <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                        Trade Log ({result.trades.length} trades)
                      </h3>
                    </div>
                    <div className="overflow-x-auto max-h-96 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-zinc-50 dark:bg-zinc-800/50">
                          <tr>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">#</th>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Side</th>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Entry</th>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Entry Time</th>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Exit</th>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Exit Time</th>
                            <th className="text-right px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Qty</th>
                            <th className="text-right px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">P&L</th>
                            <th className="text-right px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">P&L %</th>
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Exit Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.trades.map((t, i) => (
                            <tr
                              key={i}
                              className="border-t border-zinc-100 dark:border-zinc-800/50 hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors"
                            >
                              <td className="px-4 py-2 text-zinc-500">{i + 1}</td>
                              <td className="px-4 py-2">
                                <Badge color={t.side?.toLowerCase() === 'buy' || t.side?.toLowerCase() === 'long' ? 'emerald' : 'red'}>
                                  {t.side}
                                </Badge>
                              </td>
                              <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300 font-mono text-xs">{formatINR(t.entry_price)}</td>
                              <td className="px-4 py-2 text-zinc-500 text-xs">{formatDateTime(t.entry_time)}</td>
                              <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300 font-mono text-xs">{formatINR(t.exit_price)}</td>
                              <td className="px-4 py-2 text-zinc-500 text-xs">{formatDateTime(t.exit_time)}</td>
                              <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400">{t.quantity}</td>
                              <td className={`px-4 py-2 text-right font-semibold font-mono text-xs ${t.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                                {formatINR(t.pnl)}
                              </td>
                              <td className={`px-4 py-2 text-right font-mono text-xs ${(t.pnl_pct ?? t.pnl) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                                {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : '--'}
                              </td>
                              <td className="px-4 py-2">
                                <Badge color={exitReasonColor(t.exit_reason)}>{t.exit_reason}</Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
