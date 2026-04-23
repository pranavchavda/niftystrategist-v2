import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  FlaskConical, Play, Loader2, TrendingUp, TrendingDown,
  BarChart3, Clock, Target, AlertTriangle, Trophy,
  ArrowUpRight, ArrowDownRight, Minus, Info,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Badge } from '../components/catalyst/badge';
import { Input } from '../components/catalyst/input';

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
  diagnostics?: {
    intra_bar_ambiguity: number;
    primary_flips: number;
    confirm_blocks: number;
    cooldown_blocks: number;
    max_trades_blocks: number;
    squareoff_exits: number;
  };
  session_mode?: string;
  candle_count?: number;
  session_days?: number;
}

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
  { value: 'macd', label: 'MACD Histogram', defaultParams: '{}' },
];

const SCALP_CONFIRM_INDICATORS = [
  { value: '', label: '(none)' },
  { value: 'qqe_mod', label: 'QQE MOD', defaultParams: '{"rsi_period":6,"smoothing":5}' },
  { value: 'linear_regression', label: 'Linear Regression',
    defaultParams: '{"period":20,"output":"slope"}' },
  { value: 'rsi', label: 'RSI', defaultParams: '{"period":14}' },
  { value: 'bollinger', label: 'Bollinger', defaultParams: '{"period":20,"band":"pctb"}' },
  { value: 'renko', label: 'Renko', defaultParams: '{"brick_size":10.0}' },
  { value: 'vwap', label: 'VWAP', defaultParams: '{}' },
];

export function clientLoader() {
  requirePermission('settings.access');
  return null;
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
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
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
  squareoff_time: 'Time to auto-close all positions (HH:MM). Usually 15:15, before market close at 15:30.',
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
  const [scalpSessionMode, setScalpSessionMode] = useState<'equity_intraday' | 'equity_swing'>('equity_intraday');
  const [scalpPrimary, setScalpPrimary] = useState('utbot');
  const [scalpPrimaryParams, setScalpPrimaryParams] = useState(SCALP_PRIMARY_INDICATORS[0].defaultParams);
  const [scalpConfirm, setScalpConfirm] = useState('');
  const [scalpConfirmParams, setScalpConfirmParams] = useState('');
  const [scalpSL, setScalpSL] = useState<string>('');
  const [scalpTarget, setScalpTarget] = useState<string>('');
  const [scalpTrailPoints, setScalpTrailPoints] = useState<string>('');
  const [scalpTrailArm, setScalpTrailArm] = useState<string>('');
  const [scalpSquareoff, setScalpSquareoff] = useState('15:15');
  const [scalpQuantity, setScalpQuantity] = useState<string>('10');
  const [scalpMaxTrades, setScalpMaxTrades] = useState<string>('20');
  const [scalpCooldown, setScalpCooldown] = useState<string>('60');
  const [scalpSlippageBps, setScalpSlippageBps] = useState<string>('0');

  // Results
  const [result, setResult] = useState<BacktestResult | null>(null);

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

  const runBacktest = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const endpoint = isFnO ? '/api/backtest/run-fno' : '/api/backtest/run';
      const body = isFnO
        ? { template: selectedTemplate, days, interval, params }
        : { template: selectedTemplate, symbol, days, interval, params };
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Backtest failed');
        return;
      }
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Network error');
    } finally {
      setRunning(false);
    }
  };

  const runScalpBacktest = async () => {
    setRunning(true);
    setError(null);
    setResult(null);

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
      setRunning(false);
      return;
    }
    const confirmParams = scalpConfirm
      ? parseJson(scalpConfirmParams, {}) : null;
    if (scalpConfirm && scalpConfirmParams.trim() && confirmParams === null) {
      setError('Confirm params must be valid JSON');
      setRunning(false);
      return;
    }

    const toNum = (s: string): number | null =>
      s.trim() === '' ? null : Number(s);

    const body: Record<string, any> = {
      symbol,
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
      max_trades: parseInt(scalpMaxTrades) || 20,
      cooldown_seconds: parseInt(scalpCooldown) || 0,
      quantity: parseInt(scalpQuantity) || 0,
      slippage_bps: parseFloat(scalpSlippageBps) || 0,
    };

    try {
      const res = await fetch('/api/backtest/scalp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Backtest failed');
        return;
      }
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Network error');
    } finally {
      setRunning(false);
    }
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

                {/* Symbol (equity only) */}
                {!isFnO && (
                  <div>
                    <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Symbol</label>
                    <Input
                      type="text"
                      value={symbol}
                      onChange={e => setSymbol(e.target.value.toUpperCase())}
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

              {mode === 'scalp' && (
              <div className="space-y-4">
                {/* Symbol */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Symbol</label>
                  <Input
                    type="text"
                    value={symbol}
                    onChange={e => setSymbol(e.target.value.toUpperCase())}
                    placeholder="e.g. RELIANCE, HDFCBANK"
                  />
                </div>

                {/* Session mode */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Session Mode</label>
                  <select
                    className={selectClassName}
                    value={scalpSessionMode}
                    onChange={e => setScalpSessionMode(e.target.value as any)}
                  >
                    <option value="equity_intraday">Intraday (squareoff at cutoff)</option>
                    <option value="equity_swing">Swing / Delivery (hold across days)</option>
                  </select>
                </div>

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
                  {scalpSessionMode === 'equity_intraday' && (
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Squareoff Time (IST)</label>
                      <Input type="text" value={scalpSquareoff} onChange={e => setScalpSquareoff(e.target.value)} placeholder="HH:MM" />
                    </div>
                  )}
                </div>

                {/* Sizing + discipline */}
                <div className="pt-2 border-t border-zinc-200 dark:border-zinc-700">
                  <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3">Sizing & Discipline</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">Quantity</label>
                      <Input type="number" value={scalpQuantity} onChange={e => setScalpQuantity(e.target.value)} min={1} />
                    </div>
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
                  disabled={running || !symbol || !scalpQuantity}
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
              <div className="flex flex-col items-center justify-center py-24">
                <Loader2 className="w-10 h-10 animate-spin text-amber-500 mb-4" />
                <p className="text-zinc-500 dark:text-zinc-400 font-medium">Running backtest...</p>
                <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">This may take a moment for longer lookback periods.</p>
              </div>
            )}

            {result && m && (
              <div className="space-y-6">
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
