import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useOutletContext, useSearchParams } from 'react-router';
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  LineStyle,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type CandlestickData,
  type LineData,
  type HistogramData,
  type SeriesMarker,
  type LogicalRange,
  type MouseEventParams,
  type WhitespaceData,
} from 'lightweight-charts';
import { Search, Plus, X, Loader2, TrendingUp, TrendingDown, Radio, Activity, Settings as SettingsIcon, RotateCcw } from 'lucide-react';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('dashboard.access');
  return null;
}

interface Candle {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface LinePoint {
  time: string | number;
  value: number;
}

interface IndicatorPane {
  id: string;
  title: string;
  lines: Record<string, LinePoint[]>;
  histogram?: { time: string | number; value: number }[];
  range?: [number, number];
  levels?: number[];
}

interface IndicatorResponse {
  lines: Record<string, LinePoint[]>;
  markers: { time: string | number; type: 'buy' | 'sell'; text?: string }[];
  panes: IndicatorPane[];
}

interface SymbolResult {
  symbol: string;
  name?: string;
  instrument_key?: string;
  kind?: 'index' | 'equity';
}

const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1D', '1W', '1M'] as const;
type Timeframe = (typeof TIMEFRAMES)[number];

interface IndicatorDef {
  key: string;
  label: string;
  apiName: string;
  kind: 'overlay' | 'pane';
  params?: Record<string, number>;
}

interface ParamSpec {
  key: string;
  label: string;
  type: 'int' | 'float';
  min?: number;
  max?: number;
  step?: number;
  default: number;
}

// Per-indicator parameter schemas. The "base" key matches the leading
// portion of apiName before any "_<period>" suffix (so "sma_20" → "sma").
// `period` is treated specially for SMA/EMA: the chip's apiName is
// rewritten to `${base}_${period}` so multiple periods coexist as
// separate chips. Other indicators stay single-instance per chip and
// just send overrides via the `params` query.
const INDICATOR_PARAM_SPECS: Record<string, ParamSpec[]> = {
  sma: [{ key: 'period', label: 'Period', type: 'int', min: 2, max: 500, default: 20 }],
  ema: [{ key: 'period', label: 'Period', type: 'int', min: 2, max: 500, default: 20 }],
  bbands: [
    { key: 'period', label: 'Period', type: 'int', min: 2, max: 200, default: 20 },
    { key: 'stddev', label: 'Std Dev', type: 'float', min: 0.5, max: 5, step: 0.1, default: 2 },
  ],
  rsi: [{ key: 'period', label: 'Period', type: 'int', min: 2, max: 100, default: 14 }],
  macd: [
    { key: 'fast', label: 'Fast', type: 'int', min: 2, max: 50, default: 12 },
    { key: 'slow', label: 'Slow', type: 'int', min: 2, max: 100, default: 26 },
    { key: 'signal', label: 'Signal', type: 'int', min: 2, max: 50, default: 9 },
  ],
  stoch: [
    { key: 'k', label: '%K', type: 'int', min: 2, max: 50, default: 14 },
    { key: 'd', label: '%D', type: 'int', min: 1, max: 20, default: 3 },
    { key: 'smooth', label: 'Smooth', type: 'int', min: 1, max: 20, default: 3 },
  ],
  atr: [{ key: 'period', label: 'Period', type: 'int', min: 2, max: 100, default: 14 }],
  utbot: [
    { key: 'period', label: 'ATR Period', type: 'int', min: 2, max: 100, default: 10 },
    { key: 'sensitivity', label: 'Sensitivity', type: 'float', min: 0.1, max: 10, step: 0.1, default: 1 },
  ],
  supertrend: [
    { key: 'period', label: 'Period', type: 'int', min: 2, max: 100, default: 10 },
    { key: 'multiplier', label: 'Multiplier', type: 'float', min: 0.5, max: 10, step: 0.1, default: 3 },
  ],
  halftrend: [
    { key: 'amplitude', label: 'Amplitude', type: 'int', min: 1, max: 20, default: 2 },
    { key: 'atr_period', label: 'ATR Period', type: 'int', min: 2, max: 200, default: 100 },
  ],
  ssl_hybrid: [{ key: 'period', label: 'Period', type: 'int', min: 2, max: 100, default: 10 }],
  ema_crossover: [
    { key: 'fast', label: 'Fast', type: 'int', min: 2, max: 50, default: 9 },
    { key: 'slow', label: 'Slow', type: 'int', min: 2, max: 100, default: 21 },
  ],
  qqe_mod: [
    { key: 'rsi_period', label: 'RSI Period', type: 'int', min: 2, max: 50, default: 6 },
    { key: 'smoothing', label: 'Smoothing', type: 'int', min: 1, max: 20, default: 5 },
  ],
  renko: [
    { key: 'brick_size', label: 'Brick Size (0=auto)', type: 'float', min: 0, max: 10000, step: 0.01, default: 0 },
    { key: 'atr_period', label: 'ATR Period (0=off)', type: 'int', min: 0, max: 200, default: 0 },
  ],
};

// Bases whose `period` param is encoded in apiName as "_<period>" suffix.
const SUFFIX_PERIOD_BASES = new Set(['sma', 'ema']);

function indicatorBase(apiName: string): string {
  const parts = apiName.split('_');
  const last = parts[parts.length - 1];
  if (parts.length > 1 && /^\d+$/.test(last)) {
    return parts.slice(0, -1).join('_');
  }
  return apiName;
}

function getParamSpec(apiName: string): ParamSpec[] {
  return INDICATOR_PARAM_SPECS[indicatorBase(apiName)] || [];
}

const OVERLAY_COLORS = [
  '#f59e0b', '#3b82f6', '#10b981', '#ec4899', '#8b5cf6',
  '#ef4444', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

const OVERLAY_STYLE: Record<string, { color: string; title?: string }> = {
  utbot_stop: { color: '#f59e0b', title: 'UT Bot' },
  bb_upper: { color: '#8b5cf6', title: 'BB Upper' },
  bb_middle: { color: '#8b5cf6', title: 'BB Middle' },
  bb_lower: { color: '#8b5cf6', title: 'BB Lower' },
  vwap: { color: '#06b6d4', title: 'VWAP' },
  halftrend_line: { color: '#22d3ee', title: 'HalfTrend' },
  ssl_line: { color: '#a855f7', title: 'SSL Hybrid' },
  ema_fast: { color: '#10b981', title: 'EMA 9' },
  ema_slow: { color: '#ef4444', title: 'EMA 21' },
  supertrend_line: { color: '#facc15', title: 'Supertrend' },
};

const PRESET_INDICATORS: IndicatorDef[] = [
  { key: 'sma_20', label: 'SMA 20', apiName: 'sma_20', kind: 'overlay' },
  { key: 'sma_50', label: 'SMA 50', apiName: 'sma_50', kind: 'overlay' },
  { key: 'sma_200', label: 'SMA 200', apiName: 'sma_200', kind: 'overlay' },
  { key: 'ema_9', label: 'EMA 9', apiName: 'ema_9', kind: 'overlay' },
  { key: 'ema_21', label: 'EMA 21', apiName: 'ema_21', kind: 'overlay' },
  { key: 'ema_50', label: 'EMA 50', apiName: 'ema_50', kind: 'overlay' },
  { key: 'bbands', label: 'Bollinger Bands', apiName: 'bbands', kind: 'overlay' },
  { key: 'vwap', label: 'VWAP', apiName: 'vwap', kind: 'overlay' },
  { key: 'utbot', label: 'UT Bot', apiName: 'utbot', kind: 'overlay' },
  { key: 'halftrend', label: 'HalfTrend', apiName: 'halftrend', kind: 'overlay' },
  { key: 'ssl_hybrid', label: 'SSL Hybrid', apiName: 'ssl_hybrid', kind: 'overlay' },
  { key: 'ema_crossover', label: 'EMA Cross 9/21', apiName: 'ema_crossover', kind: 'overlay' },
  { key: 'supertrend', label: 'Supertrend', apiName: 'supertrend', kind: 'overlay' },
  { key: 'rsi', label: 'RSI (14)', apiName: 'rsi', kind: 'pane' },
  { key: 'macd', label: 'MACD', apiName: 'macd', kind: 'pane' },
  { key: 'stoch', label: 'Stochastic', apiName: 'stoch', kind: 'pane' },
  { key: 'atr', label: 'ATR', apiName: 'atr', kind: 'pane' },
  { key: 'qqe_mod', label: 'QQE MOD', apiName: 'qqe_mod', kind: 'pane' },
  { key: 'renko', label: 'Renko Trend', apiName: 'renko', kind: 'pane' },
];

const POPULAR_INDICES = ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'NIFTY MID SELECT', 'SENSEX'];

// Bar-bucket size in seconds for each intraday timeframe. Daily+ timeframes
// never create a new bar from ticks — they only update the latest bar's h/l/c.
const BUCKET_SECONDS: Record<Timeframe, number | null> = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '30m': 1800,
  '1D': null,
  '1W': null,
  '1M': null,
};
const POPULAR_SYMBOLS = [
  'RELIANCE', 'HDFCBANK', 'TCS', 'INFY', 'ICICIBANK',
  'BHARTIARTL', 'SBIN', 'ITC', 'LT', 'HINDUNILVR',
];

// Map indicator API name -> expected pane id returned by the backend.
const PANE_ID_FOR: Record<string, string> = {
  rsi: 'rsi',
  macd: 'macd',
  stoch: 'stoch',
  atr: 'atr',
  qqe_mod: 'qqe_mod',
  renko: 'renko',
};

function useDarkMode(): boolean {
  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    const check = () => setIsDark(document.documentElement.classList.contains('dark'));
    check();
    const observer = new MutationObserver(check);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return isDark;
}

// localStorage-backed UI state. Survives tab close. Versioned so a future
// breaking change to the shape can invalidate stale entries instead of
// crashing on load.
const STORAGE_VERSION = 2;
const STORAGE_KEY = `nf.charts.state.v${STORAGE_VERSION}`;

interface PersistedChartState {
  symbol?: string;
  timeframe?: Timeframe;
  // Full IndicatorDef array — preserves user-customized params and any
  // dynamically-renamed apiNames (e.g. SMA period → "sma_30").
  indicators?: IndicatorDef[];
  technicalsOpen?: boolean;
}

interface TechnicalIndicatorEntry {
  value?: number | null;
  state?: string;
  label: string;
  signal?: number | null;
  hist?: number | null;
  upper?: number | null;
  middle?: number | null;
  lower?: number | null;
  pct_b?: number | null;
  pct?: number | null;
  k?: number | null;
  d?: number | null;
}

interface TechnicalsSnapshot {
  symbol: string;
  timeframe: string;
  price: number;
  indicators: Record<string, TechnicalIndicatorEntry>;
  summary: {
    bullish: number;
    bearish: number;
    neutral: number;
    verdict: 'bullish' | 'bearish' | 'neutral';
    signals: Record<string, string>;
  };
}

function loadPersistedState(): PersistedChartState {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as PersistedChartState;
  } catch {
    return {};
  }
}

function savePersistedState(patch: PersistedChartState) {
  if (typeof window === 'undefined') return;
  try {
    const current = loadPersistedState();
    const next = { ...current, ...patch };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* quota / private mode — ignore */
  }
}

function SymbolSearch({
  value,
  onSelect,
  authToken,
}: {
  value: string;
  onSelect: (sym: string) => void;
  authToken: string;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SymbolResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(
        `/api/charts/symbols?q=${encodeURIComponent(q)}&limit=12`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  const onChange = (v: string) => {
    setQuery(v);
    setIsOpen(true);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => doSearch(v), 150);
  };

  const pick = (s: string) => {
    onSelect(s);
    setQuery('');
    setResults([]);
    setIsOpen(false);
  };

  return (
    <div ref={wrapperRef} className="relative w-64">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
        <input
          type="text"
          value={query}
          placeholder={value || 'Search symbol...'}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsOpen(true)}
          className="w-full pl-8 pr-2 py-1.5 text-sm font-medium bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
        />
        {loading && (
          <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 animate-spin" />
        )}
      </div>
      {isOpen && (results.length > 0 || query.trim() === '') && (
        <div className="absolute z-50 mt-1 w-80 max-h-80 overflow-y-auto bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-md shadow-lg">
          {results.length > 0 ? (
            results.map((r) => (
              <button
                key={r.symbol + (r.kind || '')}
                onClick={() => pick(r.symbol)}
                className="w-full text-left px-3 py-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-baseline gap-2 border-b border-zinc-100 dark:border-zinc-800 last:border-b-0"
              >
                {r.kind === 'index' && (
                  <span className="text-[9px] px-1.5 py-0.5 font-bold uppercase tracking-wider bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
                    Index
                  </span>
                )}
                <span className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">{r.symbol}</span>
                {r.name && (
                  <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate">{r.name}</span>
                )}
              </button>
            ))
          ) : (
            <div className="px-3 py-2 space-y-2">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">Indices</div>
                <div className="flex flex-wrap gap-1">
                  {POPULAR_INDICES.map((s) => (
                    <button
                      key={s}
                      onClick={() => pick(s)}
                      className="px-2 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50 rounded text-blue-700 dark:text-blue-300"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">Popular</div>
                <div className="flex flex-wrap gap-1">
                  {POPULAR_SYMBOLS.map((s) => (
                    <button
                      key={s}
                      onClick={() => pick(s)}
                      className="px-2 py-0.5 text-xs font-medium bg-zinc-100 dark:bg-zinc-800 hover:bg-amber-100 dark:hover:bg-amber-900/30 rounded text-zinc-700 dark:text-zinc-300"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function IndicatorChip({
  ind,
  onRemove,
  onUpdate,
}: {
  ind: IndicatorDef;
  onRemove: (key: string) => void;
  onUpdate: (key: string, params: Record<string, number>) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const specs = getParamSpec(ind.apiName);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  // Local draft state so typing doesn't trigger a refetch on every keystroke.
  const [draft, setDraft] = useState<Record<string, number>>(() => {
    const d: Record<string, number> = {};
    for (const s of specs) {
      d[s.key] = ind.params?.[s.key] ?? s.default;
    }
    // SMA/EMA: prefer the period encoded in apiName over the spec default.
    const base = indicatorBase(ind.apiName);
    if (SUFFIX_PERIOD_BASES.has(base)) {
      const tail = ind.apiName.split('_').pop()!;
      if (/^\d+$/.test(tail)) d.period = parseInt(tail, 10);
    }
    return d;
  });

  // Re-seed draft when the chip itself changes (e.g. SMA period rewrite).
  useEffect(() => {
    const d: Record<string, number> = {};
    for (const s of specs) {
      d[s.key] = ind.params?.[s.key] ?? s.default;
    }
    const base = indicatorBase(ind.apiName);
    if (SUFFIX_PERIOD_BASES.has(base)) {
      const tail = ind.apiName.split('_').pop()!;
      if (/^\d+$/.test(tail)) d.period = parseInt(tail, 10);
    }
    setDraft(d);
  }, [ind.apiName, ind.params, specs]);

  const apply = () => {
    onUpdate(ind.key, draft);
    setOpen(false);
  };

  const reset = () => {
    const d: Record<string, number> = {};
    for (const s of specs) d[s.key] = s.default;
    setDraft(d);
  };

  return (
    <span
      ref={ref}
      className="relative inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded"
    >
      {ind.label}
      {specs.length > 0 && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="hover:text-amber-900 dark:hover:text-amber-200"
          title="Settings"
        >
          <SettingsIcon className="w-3 h-3" />
        </button>
      )}
      <button
        onClick={() => onRemove(ind.key)}
        className="hover:text-red-600 dark:hover:text-red-400"
        title="Remove"
      >
        <X className="w-3 h-3" />
      </button>

      {open && specs.length > 0 && (
        <div className="absolute z-50 top-full mt-1 right-0 w-64 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-md shadow-lg">
          <div className="px-3 py-2 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-bold text-zinc-500">
              {ind.label} Settings
            </span>
            <button
              onClick={reset}
              title="Reset to defaults"
              className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>
          <div className="px-3 py-2 space-y-2">
            {specs.map((s) => (
              <label key={s.key} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-zinc-600 dark:text-zinc-400">{s.label}</span>
                <input
                  type="number"
                  value={draft[s.key]}
                  min={s.min}
                  max={s.max}
                  step={s.step ?? (s.type === 'int' ? 1 : 0.1)}
                  onChange={(e) => {
                    const v = e.target.value === '' ? 0 : Number(e.target.value);
                    setDraft((d) => ({ ...d, [s.key]: s.type === 'int' ? Math.round(v) : v }));
                  }}
                  className="w-20 px-2 py-1 text-xs tabular-nums bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
                />
              </label>
            ))}
          </div>
          <div className="px-3 py-2 border-t border-zinc-100 dark:border-zinc-800 flex justify-end gap-1">
            <button
              onClick={() => setOpen(false)}
              className="px-2 py-1 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            >
              Cancel
            </button>
            <button
              onClick={apply}
              className="px-2.5 py-1 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white rounded"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </span>
  );
}

function IndicatorPicker({
  active,
  onAdd,
  onRemove,
  onUpdate,
}: {
  active: IndicatorDef[];
  onAdd: (d: IndicatorDef) => void;
  onRemove: (key: string) => void;
  onUpdate: (key: string, params: Record<string, number>) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const activeKeys = useMemo(() => new Set(active.map((i) => i.key)), [active]);

  return (
    <div ref={ref} className="relative flex items-center gap-1 flex-wrap">
      {active.map((ind) => (
        <IndicatorChip
          key={ind.key}
          ind={ind}
          onRemove={onRemove}
          onUpdate={onUpdate}
        />
      ))}
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 rounded"
      >
        <Plus className="w-3 h-3" />
        Indicator
      </button>
      {open && (
        <div className="absolute z-50 top-full mt-1 left-0 w-64 max-h-96 overflow-y-auto bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-md shadow-lg">
          {(['overlay', 'pane'] as const).map((kind) => {
            const filtered = PRESET_INDICATORS.filter((i) => i.kind === kind);
            return (
              <div key={kind}>
                <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider font-semibold bg-zinc-50 dark:bg-zinc-800/50 text-zinc-500 dark:text-zinc-400 border-b border-zinc-100 dark:border-zinc-800 sticky top-0">
                  {kind === 'overlay' ? 'On Chart' : 'Separate Pane'}
                </div>
                {filtered.map((ind) => {
                  const isActive = activeKeys.has(ind.key);
                  return (
                    <button
                      key={ind.key}
                      onClick={() => {
                        if (isActive) onRemove(ind.key);
                        else onAdd(ind);
                      }}
                      className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                        isActive ? 'text-amber-700 dark:text-amber-400 font-semibold' : 'text-zinc-700 dark:text-zinc-300'
                      }`}
                    >
                      {ind.label}
                      {isActive && <span className="text-xs">✓</span>}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function makeChart(
  container: HTMLDivElement,
  isDark: boolean,
  intraday: boolean,
  showTimeAxis: boolean,
): { chart: IChartApi; ro: ResizeObserver } {
  const fmtIstTime = (t: Time): string => {
    if (typeof t === 'number') {
      return new Date(t * 1000).toLocaleTimeString('en-IN', {
        hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
      });
    }
    return String(t);
  };
  const fmtIstDateTime = (t: Time): string => {
    if (typeof t === 'number') {
      return new Date(t * 1000).toLocaleString('en-IN', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
        hour12: false, timeZone: 'Asia/Kolkata',
      }) + ' IST';
    }
    return String(t);
  };

  const chart = createChart(container, {
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: isDark ? '#a1a1aa' : '#71717a',
      fontFamily: "'Inter', system-ui, sans-serif",
      fontSize: 11,
    },
    grid: {
      vertLines: { color: isDark ? 'rgba(63, 63, 70, 0.25)' : 'rgba(228, 228, 231, 0.5)' },
      horzLines: { color: isDark ? 'rgba(63, 63, 70, 0.25)' : 'rgba(228, 228, 231, 0.5)' },
    },
    crosshair: {
      mode: 0,
      vertLine: {
        color: isDark ? 'rgba(245, 158, 11, 0.4)' : 'rgba(245, 158, 11, 0.3)',
        width: 1,
        style: LineStyle.Dashed,
        labelBackgroundColor: isDark ? '#27272a' : '#f4f4f5',
      },
      horzLine: {
        color: isDark ? 'rgba(245, 158, 11, 0.4)' : 'rgba(245, 158, 11, 0.3)',
        width: 1,
        style: LineStyle.Dashed,
        labelBackgroundColor: isDark ? '#27272a' : '#f4f4f5',
      },
    },
    rightPriceScale: {
      borderColor: isDark ? 'rgba(63, 63, 70, 0.5)' : 'rgba(228, 228, 231, 0.7)',
      scaleMargins: { top: 0.1, bottom: 0.1 },
    },
    timeScale: {
      borderColor: isDark ? 'rgba(63, 63, 70, 0.5)' : 'rgba(228, 228, 231, 0.7)',
      timeVisible: intraday,
      visible: showTimeAxis,
      tickMarkFormatter: intraday ? (t: Time) => fmtIstTime(t) : undefined,
    },
    localization: {
      timeFormatter: intraday ? fmtIstDateTime : undefined,
    },
    handleScroll: { vertTouchDrag: false },
  });

  const ro = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      chart.applyOptions({ width, height });
    }
  });
  ro.observe(container);

  return { chart, ro };
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function stateBadgeClass(state: string | undefined): string {
  switch (state) {
    case 'bullish':
    case 'above':
      return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300';
    case 'bearish':
    case 'below':
      return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300';
    case 'overbought':
      return 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300';
    case 'oversold':
      return 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300';
    default:
      return 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400';
  }
}

function TechnicalsPanel({
  symbol,
  timeframe,
  authToken,
  onClose,
}: {
  symbol: string;
  timeframe: Timeframe;
  authToken: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<TechnicalsSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/charts/technicals/${encodeURIComponent(symbol)}?timeframe=${timeframe}`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      if (!res.ok) {
        let msg = `${res.status}`;
        try { const b = await res.json(); if (b?.detail) msg = b.detail; } catch { /* ignore */ }
        throw new Error(msg);
      }
      setData(await res.json());
    } catch (e: any) {
      setError(e?.message || 'Failed');
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, authToken]);

  useEffect(() => { refresh(); }, [refresh]);

  const ind = data?.indicators;
  const sum = data?.summary;

  return (
    <div className="w-72 flex-shrink-0 border-l border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 overflow-y-auto">
      <div className="sticky top-0 bg-zinc-50 dark:bg-zinc-900/50 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 px-3 py-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
          <span className="text-xs font-bold uppercase tracking-wide text-zinc-700 dark:text-zinc-300">
            Technicals
          </span>
          <span className="text-[10px] text-zinc-500">{timeframe}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={refresh}
            title="Refresh"
            className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500"
          >
            <Loader2 className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onClose}
            title="Close"
            className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 text-xs text-red-600 dark:text-red-400">Error: {error}</div>
      )}

      {sum && (
        <div className="px-3 py-3 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Verdict</span>
            <span className={`px-2 py-0.5 text-[11px] font-bold uppercase rounded ${stateBadgeClass(sum.verdict)}`}>
              {sum.verdict}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className="bg-green-50 dark:bg-green-950/30 rounded px-2 py-1.5">
              <div className="text-base font-bold text-green-700 dark:text-green-400 tabular-nums">{sum.bullish}</div>
              <div className="text-[9px] uppercase tracking-wider text-zinc-500">Bull</div>
            </div>
            <div className="bg-zinc-100 dark:bg-zinc-800 rounded px-2 py-1.5">
              <div className="text-base font-bold text-zinc-600 dark:text-zinc-400 tabular-nums">{sum.neutral}</div>
              <div className="text-[9px] uppercase tracking-wider text-zinc-500">Neut</div>
            </div>
            <div className="bg-red-50 dark:bg-red-950/30 rounded px-2 py-1.5">
              <div className="text-base font-bold text-red-700 dark:text-red-400 tabular-nums">{sum.bearish}</div>
              <div className="text-[9px] uppercase tracking-wider text-zinc-500">Bear</div>
            </div>
          </div>
        </div>
      )}

      {ind && (
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {/* Momentum */}
          <Row label={ind.rsi.label} value={fmtNum(ind.rsi.value, 1)} state={ind.rsi.state} />
          <Row
            label={ind.macd.label}
            value={`${fmtNum(ind.macd.value, 2)} / ${fmtNum(ind.macd.signal, 2)}`}
            sub={`hist ${fmtNum(ind.macd.hist, 2)}`}
            state={ind.macd.state}
          />
          <Row
            label={ind.stoch.label}
            value={`%K ${fmtNum(ind.stoch.k, 1)} / %D ${fmtNum(ind.stoch.d, 1)}`}
            state={ind.stoch.state}
          />

          {/* Trend */}
          <Row label={ind.ema_20.label} value={fmtNum(ind.ema_20.value, 2)} state={ind.ema_20.state} />
          <Row label={ind.ema_50.label} value={fmtNum(ind.ema_50.value, 2)} state={ind.ema_50.state} />
          <Row label={ind.ema_200.label} value={fmtNum(ind.ema_200.value, 2)} state={ind.ema_200.state} />
          <Row label={ind.vwap.label} value={fmtNum(ind.vwap.value, 2)} state={ind.vwap.state} />

          {/* Volatility */}
          <Row
            label={ind.bbands.label}
            value={`${fmtNum(ind.bbands.lower, 2)} – ${fmtNum(ind.bbands.upper, 2)}`}
            sub={ind.bbands.pct_b !== null && ind.bbands.pct_b !== undefined ? `%B ${fmtNum(ind.bbands.pct_b, 2)}` : undefined}
          />
          <Row
            label={ind.atr.label}
            value={fmtNum(ind.atr.value, 2)}
            sub={ind.atr.pct !== null && ind.atr.pct !== undefined ? `${fmtNum(ind.atr.pct, 2)}%` : undefined}
          />
        </div>
      )}

      {!data && !error && loading && (
        <div className="px-3 py-6 text-center text-xs text-zinc-500">Loading…</div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  sub,
  state,
}: {
  label: string;
  value: string;
  sub?: string;
  state?: string;
}) {
  return (
    <div className="px-3 py-2 flex items-center justify-between gap-2">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500">{label}</div>
        <div className="text-xs font-bold tabular-nums text-zinc-900 dark:text-zinc-100">{value}</div>
        {sub && <div className="text-[10px] text-zinc-500 tabular-nums">{sub}</div>}
      </div>
      {state && state !== 'n/a' && (
        <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded ${stateBadgeClass(state)}`}>
          {state}
        </span>
      )}
    </div>
  );
}

function ChartsView({ authToken }: { authToken: string }) {
  const isDark = useDarkMode();
  const [searchParams, setSearchParams] = useSearchParams();

  const persistedRef = useRef<PersistedChartState>(loadPersistedState());
  const persisted = persistedRef.current;

  const [symbol, setSymbol] = useState<string>(() => {
    const fromQuery = searchParams.get('symbol');
    if (fromQuery && fromQuery.trim()) return fromQuery.trim().toUpperCase();
    if (persisted.symbol && persisted.symbol.trim()) return persisted.symbol.trim().toUpperCase();
    return 'NIFTY 50';
  });
  const [timeframe, setTimeframe] = useState<Timeframe>(() => {
    const tf = persisted.timeframe;
    return tf && (TIMEFRAMES as readonly string[]).includes(tf) ? tf : '1D';
  });
  const [candles, setCandles] = useState<Candle[]>([]);
  // Live quote (LTP + prior-day close) returned alongside candles. Used
  // to render the header price independent of bucket lag — without this,
  // higher-TF charts show a stale header price (e.g. 30m's last bucket
  // can be up to 30 min behind the live tape).
  const [liveQuote, setLiveQuote] = useState<{
    ltp: number;
    prev_close: number | null;
    net_change: number | null;
    pct_change: number | null;
  } | null>(null);
  const [indicatorData, setIndicatorData] = useState<IndicatorResponse | null>(null);
  const [activeIndicators, setActiveIndicators] = useState<IndicatorDef[]>(() => {
    const stored = persisted.indicators;
    if (Array.isArray(stored) && stored.length > 0) {
      const restored = stored
        .filter((i): i is IndicatorDef => Boolean(i?.key && i?.apiName && i?.kind && i?.label));
      if (restored.length > 0) return restored;
    }
    return [
      PRESET_INDICATORS.find((i) => i.key === 'ema_21')!,
      PRESET_INDICATORS.find((i) => i.key === 'rsi')!,
    ];
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [liveStatus, setLiveStatus] = useState<'off' | 'connecting' | 'open' | 'waiting' | 'reconnecting' | 'error'>('off');
  const [liveBackend, setLiveBackend] = useState<'ws' | 'poll' | null>(null);
  const [lastTickPrice, setLastTickPrice] = useState<number | null>(null);
  const [technicalsOpen, setTechnicalsOpen] = useState<boolean>(() => Boolean(persisted.technicalsOpen));

  const intraday = timeframe === '1m' || timeframe === '5m' || timeframe === '15m' || timeframe === '30m';

  // Keep the URL's ?symbol= param in sync with the active symbol so the
  // chart view is shareable / bookmarkable.
  useEffect(() => {
    const current = searchParams.get('symbol') || '';
    if (current.toUpperCase() !== symbol) {
      const next = new URLSearchParams(searchParams);
      next.set('symbol', symbol);
      setSearchParams(next, { replace: true });
    }
  }, [symbol, searchParams, setSearchParams]);

  useEffect(() => {
    savePersistedState({
      symbol,
      timeframe,
      indicators: activeIndicators,
      technicalsOpen,
    });
  }, [symbol, timeframe, activeIndicators, technicalsOpen]);

  const paneIndicators = useMemo(
    () => activeIndicators.filter((i) => i.kind === 'pane'),
    [activeIndicators],
  );

  const fetchCandles = useCallback(async () => {
    try {
      const res = await fetch(
        `/api/charts/candles/${encodeURIComponent(symbol)}?timeframe=${timeframe}`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      if (!res.ok) {
        let msg = `${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) msg = `${res.status} — ${body.detail}`;
        } catch { /* ignore */ }
        throw new Error(msg);
      }
      const data = await res.json();
      setCandles(data.candles || []);
      const q = data.quote;
      if (q && typeof q.ltp === 'number') {
        setLiveQuote({
          ltp: q.ltp,
          prev_close: typeof q.prev_close === 'number' ? q.prev_close : null,
          net_change: typeof q.net_change === 'number' ? q.net_change : null,
          pct_change: typeof q.pct_change === 'number' ? q.pct_change : null,
        });
      } else {
        setLiveQuote(null);
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load candles');
    }
  }, [symbol, timeframe, authToken]);

  const fetchIndicators = useCallback(async () => {
    if (activeIndicators.length === 0) {
      setIndicatorData({ lines: {}, markers: [], panes: [] });
      return;
    }
    try {
      const names = activeIndicators.map((i) => i.apiName).join(',');
      const paramMap: Record<string, Record<string, number>> = {};
      for (const ind of activeIndicators) {
        if (ind.params && Object.keys(ind.params).length > 0) {
          // Skip period params already encoded in the apiName suffix —
          // sending them again is harmless but pollutes the URL.
          const base = indicatorBase(ind.apiName);
          const filtered: Record<string, number> = {};
          for (const [k, v] of Object.entries(ind.params)) {
            if (k === 'period' && SUFFIX_PERIOD_BASES.has(base)) continue;
            filtered[k] = v;
          }
          if (Object.keys(filtered).length > 0) paramMap[ind.apiName] = filtered;
        }
      }
      const paramsQs = Object.keys(paramMap).length
        ? `&params=${encodeURIComponent(JSON.stringify(paramMap))}`
        : '';
      const res = await fetch(
        `/api/charts/indicators/${encodeURIComponent(symbol)}?timeframe=${timeframe}&indicators=${encodeURIComponent(names)}${paramsQs}`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      if (!res.ok) throw new Error(`${res.status}`);
      const data: IndicatorResponse = await res.json();
      setIndicatorData(data);
    } catch {
      setIndicatorData({ lines: {}, markers: [], panes: [] });
    }
  }, [symbol, timeframe, activeIndicators, authToken]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchCandles().finally(() => setLoading(false));
  }, [fetchCandles]);

  useEffect(() => {
    fetchIndicators();
  }, [fetchIndicators]);

  // Expose to the SSE stream so it can refresh on candle close — see the
  // applyServerCandle handler. Refs avoid restarting the SSE useEffect on
  // every dep change.
  const refreshHistoryRef = useRef<() => void>(() => {});
  useEffect(() => {
    refreshHistoryRef.current = () => {
      fetchCandles();
      fetchIndicators();
    };
  }, [fetchCandles, fetchIndicators]);

  const priceRef = useRef<HTMLDivElement>(null);
  const volumeRef = useRef<HTMLDivElement>(null);
  const paneRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const priceChartRef = useRef<IChartApi | null>(null);
  const priceCandleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const overlayLinesRef = useRef<Record<string, ISeriesApi<'Line'>>>({});
  const markersPluginRef = useRef<ReturnType<typeof createSeriesMarkers> | null>(null);

  const volumeChartRef = useRef<IChartApi | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const paneChartsRef = useRef<Record<string, IChartApi>>({});

  const syncingRef = useRef(false);

  // Live-bar state — the currently-forming candle that ticks mutate in place.
  // Re-initialized whenever candle history reloads (symbol/timeframe change).
  const liveBarRef = useRef<Candle | null>(null);

  useEffect(() => {
    const priceContainer = priceRef.current;
    const volContainer = volumeRef.current;
    if (!priceContainer || !volContainer) return;

    if (priceChartRef.current) {
      try { priceChartRef.current.remove(); } catch { /* ignore */ }
      priceChartRef.current = null;
      priceCandleRef.current = null;
      overlayLinesRef.current = {};
      markersPluginRef.current = null;
    }
    if (volumeChartRef.current) {
      try { volumeChartRef.current.remove(); } catch { /* ignore */ }
      volumeChartRef.current = null;
      volumeSeriesRef.current = null;
    }
    for (const key in paneChartsRef.current) {
      try { paneChartsRef.current[key].remove(); } catch { /* ignore */ }
    }
    paneChartsRef.current = {};

    const { chart: priceChart, ro: priceRo } = makeChart(priceContainer, isDark, intraday, false);
    const candleSeries = priceChart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    });
    priceChartRef.current = priceChart;
    priceCandleRef.current = candleSeries;

    const { chart: volChart, ro: volRo } = makeChart(volContainer, isDark, intraday, false);
    const volSeries = volChart.addSeries(HistogramSeries, {
      color: isDark ? 'rgba(113, 113, 122, 0.6)' : 'rgba(161, 161, 170, 0.7)',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } });
    volumeChartRef.current = volChart;
    volumeSeriesRef.current = volSeries;

    const getSyncTargets = () => [priceChart, volChart, ...Object.values(paneChartsRef.current)];

    const syncRange = (source: IChartApi) => (range: LogicalRange | null) => {
      if (!range || syncingRef.current) return;
      syncingRef.current = true;
      for (const other of getSyncTargets()) {
        if (other !== source) {
          try { other.timeScale().setVisibleLogicalRange(range); } catch { /* ignore */ }
        }
      }
      syncingRef.current = false;
    };

    priceChart.timeScale().subscribeVisibleLogicalRangeChange(syncRange(priceChart));
    volChart.timeScale().subscribeVisibleLogicalRangeChange(syncRange(volChart));

    const syncCrosshair = (source: IChartApi) => (param: MouseEventParams) => {
      const targets = getSyncTargets();
      for (const other of targets) {
        if (other === source) continue;
        if (!param.time || !param.point) {
          try { (other as any).clearCrosshairPosition?.(); } catch { /* ignore */ }
          continue;
        }
        try {
          const firstSeries =
            other === priceChart ? priceCandleRef.current
            : other === volChart ? volumeSeriesRef.current
            : null;
          if (firstSeries) {
            other.setCrosshairPosition(NaN, param.time, firstSeries);
          }
        } catch { /* ignore */ }
      }
    };

    priceChart.subscribeCrosshairMove(syncCrosshair(priceChart));
    volChart.subscribeCrosshairMove(syncCrosshair(volChart));

    return () => {
      try { priceRo.disconnect(); } catch { /* ignore */ }
      try { volRo.disconnect(); } catch { /* ignore */ }
      try { priceChart.remove(); } catch { /* ignore */ }
      try { volChart.remove(); } catch { /* ignore */ }
      priceChartRef.current = null;
      volumeChartRef.current = null;
      priceCandleRef.current = null;
      volumeSeriesRef.current = null;
      overlayLinesRef.current = {};
      markersPluginRef.current = null;
    };
  }, [isDark, intraday, timeframe]);

  useEffect(() => {
    const chart = priceChartRef.current;
    const candleSeries = priceCandleRef.current;
    const volSeries = volumeSeriesRef.current;
    if (!chart || !candleSeries || !volSeries || candles.length === 0) return;

    const candleData: CandlestickData<Time>[] = candles.map((c) => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(candleData);

    const volData: HistogramData<Time>[] = candles.map((c, i) => {
      const prev = i > 0 ? candles[i - 1].close : c.open;
      const up = c.close >= prev;
      return {
        time: c.time as Time,
        value: c.volume || 0,
        color: up ? 'rgba(22, 163, 74, 0.5)' : 'rgba(220, 38, 38, 0.5)',
      };
    });
    volSeries.setData(volData);

    chart.timeScale().fitContent();

    // Seed live-bar state from the last historical candle so ticks
    // extend/replace it smoothly.
    const last = candles[candles.length - 1];
    liveBarRef.current = last ? { ...last } : null;
  }, [candles]);

  // Live SSE stream: open when user toggles Live on + candles are loaded.
  useEffect(() => {
    if (!live) {
      setLiveStatus('off');
      setLiveBackend(null);
      return;
    }
    if (candles.length === 0) return;

    let cancelled = false;
    let activeController: AbortController | null = null;
    let waitingTimer: number | null = null;
    let reconnectTimer: number | null = null;
    let attempt = 0; // 0 = first try, then 1, 2, ... for retries
    let lastSeenMs = Date.now();

    setLiveStatus('connecting');

    const armWaitingTimer = () => {
      if (waitingTimer) window.clearTimeout(waitingTimer);
      waitingTimer = window.setTimeout(() => {
        if (Date.now() - lastSeenMs > 15000) setLiveStatus('waiting');
      }, 16000);
    };

    const backoffMs = (n: number) => {
      // 1s, 2s, 4s, 8s, 15s, cap 30s — small jitter avoids thundering-herd
      // when many tabs reconnect together after a backend blip.
      const base = Math.min(30000, 1000 * 2 ** Math.min(n, 5));
      const jitter = Math.floor(Math.random() * 500);
      return base + jitter;
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      const delay = backoffMs(attempt);
      attempt += 1;
      setLiveStatus('reconnecting');
      reconnectTimer = window.setTimeout(() => {
        if (!cancelled) connect();
      }, delay);
    };

    // Sticky once flipped on — when the backend is emitting server-built
    // candles (`event: candle`) we trust those exclusively and stop folding
    // ticks into the live bar to avoid double-counting.
    let serverCandlesActive = false;

    const applyTick = (ltp: number, lttMs: number) => {
      if (serverCandlesActive) return;
      const series = priceCandleRef.current;
      if (!series) return;
      const tickTimeSec = Math.floor(lttMs / 1000);
      const bucket = BUCKET_SECONDS[timeframe];

      const live = liveBarRef.current;
      if (!live) return;

      if (bucket !== null && intraday) {
        const bucketStart = tickTimeSec - (tickTimeSec % bucket);
        const liveTime = typeof live.time === 'number' ? live.time : 0;

        if (bucketStart > liveTime) {
          // Roll over — finalize previous, open new bar.
          const newBar: Candle = {
            time: bucketStart,
            open: ltp,
            high: ltp,
            low: ltp,
            close: ltp,
          };
          liveBarRef.current = newBar;
          series.update({
            time: bucketStart as Time,
            open: ltp, high: ltp, low: ltp, close: ltp,
          });
          // Tick-fold rollover (no server candles): refresh historicals so
          // pane time-axis and indicators advance with the new closed bar.
          refreshHistoryRef.current();
          return;
        }
        // Ignore ticks older than the live bar (shouldn't happen).
        if (bucketStart < liveTime) return;
      }

      live.high = Math.max(live.high, ltp);
      live.low = Math.min(live.low, ltp);
      live.close = ltp;
      series.update({
        time: live.time as Time,
        open: live.open, high: live.high, low: live.low, close: live.close,
      });
    };

    const applyServerCandle = (c: {
      time: number; open: number; high: number; low: number; close: number;
      volume?: number; closed?: boolean;
    }) => {
      const series = priceCandleRef.current;
      if (!series) return;
      serverCandlesActive = true;
      const newBar: Candle = {
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      };
      liveBarRef.current = newBar;
      series.update({
        time: c.time as Time,
        open: c.open, high: c.high, low: c.low, close: c.close,
      });
      // On bar close, pull fresh candles + indicator data so the RSI/MACD
      // panes pick up the new closed bar (their time axes and whitespace
      // padding are driven by the historical candles state, which the
      // live SSE stream alone can't extend).
      if (c.closed) refreshHistoryRef.current();
    };

    const connect = async () => {
      if (cancelled) return;
      const controller = new AbortController();
      activeController = controller;
      if (attempt === 0) setLiveStatus('connecting');

      try {
        const res = await fetch(
          `/api/charts/stream/${encodeURIComponent(symbol)}?timeframe=${timeframe}`,
          {
            headers: {
              Authorization: `Bearer ${authToken}`,
              Accept: 'text/event-stream',
            },
            signal: controller.signal,
          },
        );
        if (!res.ok || !res.body) {
          if (!cancelled) scheduleReconnect();
          return;
        }
        setLiveStatus('open');
        armWaitingTimer();

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let sawData = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';
          for (const frame of frames) {
            const lines = frame.split('\n');
            const eventLine = lines.find((l) => l.startsWith('event: '));
            const dataLine = lines.find((l) => l.startsWith('data: '));
            if (eventLine?.startsWith('event: error')) {
              // Backend gave up — kill this connection and let the
              // reconnect loop try again with backoff.
              try { controller.abort(); } catch { /* ignore */ }
              if (!cancelled) scheduleReconnect();
              return;
            }
            if (!dataLine) continue;
            const payload = dataLine.slice(6).trim();
            if (!payload) continue;
            try {
              const parsed = JSON.parse(payload);
              if (eventLine?.startsWith('event: ready')) {
                if (parsed.backend === 'ws' || parsed.backend === 'poll') {
                  setLiveBackend(parsed.backend);
                }
                continue;
              }
              if (eventLine?.startsWith('event: candle')) {
                if (
                  typeof parsed.time === 'number' &&
                  typeof parsed.open === 'number' &&
                  typeof parsed.high === 'number' &&
                  typeof parsed.low === 'number' &&
                  typeof parsed.close === 'number'
                ) {
                  applyServerCandle(parsed);
                  setLastTickPrice(parsed.close);
                  lastSeenMs = Date.now();
                  setLiveStatus('open');
                  armWaitingTimer();
                  sawData = true;
                  attempt = 0; // healthy stream — reset backoff
                }
              } else if (typeof parsed.ltp === 'number') {
                applyTick(parsed.ltp, parsed.ltt || Date.now());
                setLastTickPrice(parsed.ltp);
                lastSeenMs = Date.now();
                setLiveStatus('open');
                armWaitingTimer();
                sawData = true;
                attempt = 0;
              }
            } catch {
              /* ignore bad frames */
            }
          }
        }
        // Stream ended without an explicit error — backend dropped us
        // (deploy, idle timeout, network). If the user still wants live,
        // try again. Reset backoff if we actually saw data this round.
        if (!cancelled) {
          if (sawData) attempt = 0;
          scheduleReconnect();
        }
      } catch (e: any) {
        if (cancelled || e?.name === 'AbortError') return;
        scheduleReconnect();
      }
    };

    connect();

    return () => {
      cancelled = true;
      if (activeController) {
        try { activeController.abort(); } catch { /* ignore */ }
      }
      if (waitingTimer) window.clearTimeout(waitingTimer);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      setLastTickPrice(null);
      setLiveBackend(null);
    };
    // candles.length > 0 is what we actually need — use sentinel to avoid
    // re-subscribing on every candle mutation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, symbol, timeframe, authToken, candles.length === 0]);

  useEffect(() => {
    const chart = priceChartRef.current;
    const candleSeries = priceCandleRef.current;
    if (!chart || !candleSeries || !indicatorData) return;

    for (const key in overlayLinesRef.current) {
      try { chart.removeSeries(overlayLinesRef.current[key]); } catch { /* ignore */ }
    }
    overlayLinesRef.current = {};

    let colorIdx = 0;
    for (const [name, points] of Object.entries(indicatorData.lines || {})) {
      if (!points || points.length === 0) continue;
      const style = OVERLAY_STYLE[name] || {
        color: OVERLAY_COLORS[colorIdx % OVERLAY_COLORS.length],
        title: name.toUpperCase().replace(/_/g, ' '),
      };
      colorIdx++;
      const series = chart.addSeries(LineSeries, {
        color: style.color,
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: true,
        title: style.title,
      });
      const lineData: LineData<Time>[] = points.map((p) => ({
        time: p.time as Time,
        value: p.value,
      }));
      series.setData(lineData);
      overlayLinesRef.current[name] = series;
    }

    const backendMarkers: SeriesMarker<Time>[] = (indicatorData.markers || []).map((m) => ({
      time: m.time as Time,
      position: m.type === 'buy' ? 'belowBar' : 'aboveBar',
      color: m.type === 'buy' ? '#16a34a' : '#dc2626',
      shape: m.type === 'buy' ? 'arrowUp' : 'arrowDown',
      text: m.text || '',
    }));

    // Detect moving-average crosses when exactly two MA overlays are active.
    // Works for any pair of ema_N / sma_N lines.
    const maLines = Object.entries(indicatorData.lines || {})
      .filter(([name]) => /^(ema|sma)_\d+$/.test(name))
      .map(([name, points]) => {
        const [kind, periodStr] = name.split('_');
        return { name, kind, period: parseInt(periodStr, 10), points };
      })
      .sort((a, b) => a.period - b.period);

    const crossMarkers: SeriesMarker<Time>[] = [];
    if (maLines.length === 2) {
      const [fast, slow] = maLines;
      const slowByTime = new Map(slow.points.map((p) => [String(p.time), p.value]));
      let prevDiff: number | null = null;
      const fastLabel = fast.name.toUpperCase().replace('_', ' ');
      const slowLabel = slow.name.toUpperCase().replace('_', ' ');
      for (const p of fast.points) {
        const slowValue = slowByTime.get(String(p.time));
        if (slowValue === undefined) continue;
        const diff = p.value - slowValue;
        if (prevDiff !== null) {
          if (prevDiff <= 0 && diff > 0) {
            crossMarkers.push({
              time: p.time as Time,
              position: 'belowBar',
              color: '#16a34a',
              shape: 'circle',
              text: `${fastLabel} × ${slowLabel} ↑`,
            });
          } else if (prevDiff >= 0 && diff < 0) {
            crossMarkers.push({
              time: p.time as Time,
              position: 'aboveBar',
              color: '#dc2626',
              shape: 'circle',
              text: `${fastLabel} × ${slowLabel} ↓`,
            });
          }
        }
        prevDiff = diff;
      }
    }

    const timeValue = (t: Time): number =>
      typeof t === 'number' ? t : Date.parse(String(t)) / 1000;
    const allMarkers = [...backendMarkers, ...crossMarkers].sort(
      (a, b) => timeValue(a.time) - timeValue(b.time),
    );

    if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers(allMarkers);
    } else {
      markersPluginRef.current = createSeriesMarkers(candleSeries, allMarkers);
    }
  }, [indicatorData]);

  useEffect(() => {
    if (!indicatorData) return;

    const existingKeys = new Set(Object.keys(paneChartsRef.current));
    const newPaneIds = new Set(indicatorData.panes.map((p) => p.id));

    for (const key of existingKeys) {
      if (!newPaneIds.has(key)) {
        try { paneChartsRef.current[key].remove(); } catch { /* ignore */ }
        delete paneChartsRef.current[key];
      }
    }

    indicatorData.panes.forEach((pane, i) => {
      const container = paneRefs.current[pane.id];
      if (!container) return;

      if (paneChartsRef.current[pane.id]) {
        try { paneChartsRef.current[pane.id].remove(); } catch { /* ignore */ }
      }

      const isLast = i === indicatorData.panes.length - 1;
      const { chart } = makeChart(container, isDark, intraday, isLast);
      paneChartsRef.current[pane.id] = chart;

      if (pane.levels && pane.levels.length > 0 && pane.lines && candles.length > 0) {
        // Span the full chart by anchoring level lines to the first/last
        // candle time, not the indicator's first/last point — the indicator
        // typically has a warm-up gap (e.g. RSI(14)) and we want the dashed
        // levels to reach both edges so they line up with the price pane.
        const firstTime = candles[0].time as Time;
        const lastTime = candles[candles.length - 1].time as Time;
        for (const lvl of pane.levels) {
          const lineSeries = chart.addSeries(LineSeries, {
            color: isDark ? 'rgba(113, 113, 122, 0.5)' : 'rgba(161, 161, 170, 0.6)',
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          lineSeries.setData([
            { time: firstTime, value: lvl },
            { time: lastTime, value: lvl },
          ]);
        }
      }

      const lineColors: Record<string, string> = {
        rsi: '#8b5cf6',
        macd: '#3b82f6',
        signal: '#f59e0b',
        k: '#3b82f6',
        d: '#f59e0b',
        atr: '#10b981',
      };
      // Pad pane series to one entry per candle so logical-range sync
      // with the price pane stays aligned. Bars without an indicator value
      // (e.g. the RSI(14) warm-up window) become whitespace entries —
      // they consume a logical bar slot but draw nothing.
      let colorIdx = 0;
      for (const [name, points] of Object.entries(pane.lines || {})) {
        if (!points || points.length === 0) continue;
        const color = lineColors[name] || OVERLAY_COLORS[colorIdx % OVERLAY_COLORS.length];
        colorIdx++;
        const series = chart.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          title: name.toUpperCase(),
          priceLineVisible: false,
          lastValueVisible: true,
        });
        const valueByTime = new Map(points.map((p) => [p.time, p.value]));
        const data: (LineData<Time> | WhitespaceData<Time>)[] = candles.length > 0
          ? candles.map((c) => {
              const v = valueByTime.get(c.time);
              return v !== undefined
                ? { time: c.time as Time, value: v }
                : { time: c.time as Time };
            })
          : points.map((p) => ({ time: p.time as Time, value: p.value }));
        series.setData(data);
      }

      if (pane.histogram && pane.histogram.length > 0) {
        const hist = chart.addSeries(HistogramSeries, {
          priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
          priceLineVisible: false,
        });
        const histByTime = new Map(pane.histogram.map((h) => [h.time, h.value]));
        const histData: (HistogramData<Time> | WhitespaceData<Time>)[] = candles.length > 0
          ? candles.map((c) => {
              const v = histByTime.get(c.time);
              return v !== undefined
                ? {
                    time: c.time as Time,
                    value: v,
                    color: v >= 0 ? 'rgba(22, 163, 74, 0.6)' : 'rgba(220, 38, 38, 0.6)',
                  }
                : { time: c.time as Time };
            })
          : pane.histogram.map((h) => ({
              time: h.time as Time,
              value: h.value,
              color: h.value >= 0 ? 'rgba(22, 163, 74, 0.6)' : 'rgba(220, 38, 38, 0.6)',
            }));
        hist.setData(histData);
      }

      const priceChart = priceChartRef.current;
      const volChart = volumeChartRef.current;
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || syncingRef.current) return;
        syncingRef.current = true;
        try {
          if (priceChart) priceChart.timeScale().setVisibleLogicalRange(range);
          if (volChart) volChart.timeScale().setVisibleLogicalRange(range);
          for (const c of Object.values(paneChartsRef.current)) {
            if (c !== chart) c.timeScale().setVisibleLogicalRange(range);
          }
        } catch { /* ignore */ }
        syncingRef.current = false;
      });

      if (priceChart) {
        try {
          const range = priceChart.timeScale().getVisibleLogicalRange();
          if (range) chart.timeScale().setVisibleLogicalRange(range);
        } catch { /* ignore */ }
      }
    });
  }, [indicatorData, isDark, intraday, candles]);

  const lastCandle = candles[candles.length - 1];
  const prevCandle = candles[candles.length - 2];
  // Header price priority: live tick > backend quote LTP > last bar close.
  // Backend quote keeps the displayed price consistent across timeframes
  // (otherwise lower TFs lead higher TFs by up to one bucket).
  const displayPrice =
    live && lastTickPrice !== null
      ? lastTickPrice
      : liveQuote?.ltp ?? lastCandle?.close ?? 0;
  // Day-change reference: prefer Upstox's authoritative `net_change`
  // (today's move vs prior-day close). Fall back to prev-bar diff on
  // intraday TFs when the quote payload is missing.
  let priceChange = 0;
  let priceChangePct = 0;
  if (live && lastTickPrice !== null && liveQuote?.prev_close) {
    priceChange = lastTickPrice - liveQuote.prev_close;
    priceChangePct = (priceChange / liveQuote.prev_close) * 100;
  } else if (liveQuote && liveQuote.net_change !== null) {
    priceChange = liveQuote.net_change;
    priceChangePct = liveQuote.pct_change ?? (
      liveQuote.prev_close ? (liveQuote.net_change / liveQuote.prev_close) * 100 : 0
    );
  } else if (lastCandle && prevCandle) {
    priceChange = displayPrice - prevCandle.close;
    priceChangePct = (priceChange / prevCandle.close) * 100;
  }
  const isUp = priceChange >= 0;

  const addIndicator = (d: IndicatorDef) => {
    setActiveIndicators((prev) => (prev.some((p) => p.key === d.key) ? prev : [...prev, d]));
  };
  const removeIndicator = (key: string) => {
    setActiveIndicators((prev) => prev.filter((p) => p.key !== key));
  };
  const updateIndicator = (key: string, params: Record<string, number>) => {
    setActiveIndicators((prev) =>
      prev.map((ind) => {
        if (ind.key !== key) return ind;
        const base = indicatorBase(ind.apiName);
        const next: IndicatorDef = { ...ind, params: { ...params } };
        // SMA/EMA encode the period in the apiName so the line color
        // map and pane lookup stays stable. Rewriting the apiName here
        // also collapses an active period change into a re-fetch.
        if (SUFFIX_PERIOD_BASES.has(base) && typeof params.period === 'number') {
          const p = Math.max(2, Math.round(params.period));
          next.apiName = `${base}_${p}`;
          next.key = `${base}_${p}`;
          next.label = `${base.toUpperCase()} ${p}`;
        }
        return next;
      }),
    );
  };

  return (
    <div className="flex flex-col h-[calc(100dvh-1rem)] min-h-[500px] bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 overflow-hidden lg:rounded-lg">
      <div className="flex items-center gap-3 px-3 py-2 border-b border-zinc-200 dark:border-zinc-800 flex-wrap">
        <SymbolSearch value={symbol} onSelect={setSymbol} authToken={authToken} />

        {lastCandle && (
          <div className="flex items-baseline gap-2">
            <h2 className="text-base font-bold">{symbol}</h2>
            <span className="text-xl font-bold tabular-nums">
              {displayPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </span>
            <span className={`text-xs font-semibold tabular-nums flex items-center gap-0.5 ${
              isUp ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
            }`}>
              {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {isUp ? '+' : ''}{priceChange.toFixed(2)} ({isUp ? '+' : ''}{priceChangePct.toFixed(2)}%)
            </span>
          </div>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-0.5 bg-zinc-100 dark:bg-zinc-800 rounded-md p-0.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-2.5 py-1 text-[11px] font-bold rounded transition-colors ${
                timeframe === tf
                  ? 'bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        <button
          onClick={() => setLive((v) => !v)}
          title={
            live
              ? `Stop live stream${liveBackend ? ` (${liveBackend})` : ''}`
              : 'Start live stream'
          }
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-bold rounded transition-colors ${
            live
              ? liveStatus === 'open'
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : liveStatus === 'waiting'
                  ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                  : liveStatus === 'reconnecting'
                    ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                    : liveStatus === 'error'
                      ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                      : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
          }`}
        >
          <span className="relative flex items-center">
            <Radio className={`w-3 h-3 ${live && liveStatus === 'open' ? 'text-green-600 dark:text-green-400' : ''}`} />
            {live && liveStatus === 'open' && (
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-green-500 animate-ping" />
            )}
          </span>
          {live
            ? liveStatus === 'open'
              ? `LIVE${liveBackend === 'poll' ? ' · poll' : ''}`
              : liveStatus === 'connecting'
                ? '…'
                : liveStatus === 'waiting'
                  ? 'idle'
                  : liveStatus === 'reconnecting'
                    ? 'reconn…'
                    : liveStatus === 'error'
                      ? 'err'
                      : 'LIVE'
            : 'LIVE'}
        </button>

        <button
          onClick={() => setTechnicalsOpen((v) => !v)}
          title={technicalsOpen ? 'Hide technicals' : 'Show technicals'}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-bold rounded transition-colors ${
            technicalsOpen
              ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
          }`}
        >
          <Activity className="w-3 h-3" />
          Technicals
        </button>

        <IndicatorPicker
          active={activeIndicators}
          onAdd={addIndicator}
          onRemove={removeIndicator}
          onUpdate={updateIndicator}
        />
      </div>

      {(loading || error) && (
        <div className={`px-3 py-1 text-xs ${error ? 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400' : 'bg-zinc-50 dark:bg-zinc-900 text-zinc-500'}`}>
          {error ? `Error: ${error}` : 'Loading…'}
        </div>
      )}

      <div className="flex-1 flex min-h-0">
       <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 min-h-[300px] relative">
          <div ref={priceRef} className="absolute inset-0" />
        </div>

        <div className="h-20 border-t border-zinc-200 dark:border-zinc-800 relative flex-shrink-0">
          <div ref={volumeRef} className="absolute inset-0" />
          <div className="absolute top-1 left-2 text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 pointer-events-none">
            Volume
          </div>
        </div>

        {paneIndicators.map((ind) => {
          const paneId = PANE_ID_FOR[ind.apiName] || ind.apiName;
          const paneData = indicatorData?.panes.find((p) => p.id === paneId);
          return (
            <div key={ind.key} className="h-32 border-t border-zinc-200 dark:border-zinc-800 relative flex-shrink-0">
              <div
                ref={(el) => { paneRefs.current[paneId] = el; }}
                className="absolute inset-0"
              />
              <div className="absolute top-1 left-2 text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 pointer-events-none">
                {paneData?.title || ind.label}
              </div>
            </div>
          );
        })}
       </div>
        {technicalsOpen && (
          <TechnicalsPanel
            symbol={symbol}
            timeframe={timeframe}
            authToken={authToken}
            onClose={() => setTechnicalsOpen(false)}
          />
        )}
      </div>
    </div>
  );
}

export default function ChartsRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <ChartsView authToken={authToken} />;
}
