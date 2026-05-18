import React, { useState, useMemo } from 'react';
import { useOutletContext, Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { requirePermission } from '../utils/route-permissions';
import {
  Radar, Play, Loader2, TrendingUp, TrendingDown, Info, X,
  Crown, Medal, Award, Newspaper, Rocket, Bug, ArrowUpRight,
  ArrowDownRight, AlertTriangle, CheckCircle2, ShoppingCart, LineChart,
} from 'lucide-react';
import { Tooltip } from '../components/Tooltip';

interface AuthContext {
  authToken: string;
  user?: any;
}

// ─── Types mirroring nf-morning-scan --json output ──────────────────────────

interface Candidate {
  symbol: string;
  price: number;
  score: number;
  gap_pct: number;
  rel_strength_pct: number;
  change_pct: number;
  volume: number;
  rsi: number | null;
  vwap: number | null;
  above_vwap: boolean | null;
  rvol_t: number | null;
  vol_expansion: number | null;
  setup: string;
  opening_range?: { or_high: number; or_low: number; breakout: string | null };
  news?: { heading: string }[];
}

interface ScanResult {
  scan_time: string;
  elapsed_seconds: number;
  market_context: { nifty_50: number | null; nifty_change_pct: number };
  candidates: Candidate[];
  market_news?: string;
  market_news_citations?: string[];
}

interface Deployment {
  symbol: string;
  rules_count?: number;
  group_id?: string;
  error?: string;
}

interface AutoDeploy {
  template: string;
  capital_per_strategy: number;
  risk_percent: number;
  dry_run: boolean;
  deployments: Deployment[];
  succeeded: number;
  failed: number;
}

// ─── Reference copy for tooltips ────────────────────────────────────────────

const SCORE_HELP = (
  <div className="space-y-1">
    <p className="font-semibold text-amber-300">Momentum Score (0–8)</p>
    <p>Sum of six institutional signals. Higher = stronger intraday edge.</p>
    <ul className="mt-1 space-y-0.5 text-zinc-400">
      <li>Gap: +1 (≥1%), +2 (≥2%)</li>
      <li>Rel. Strength: +1 (≥0.5%), +2 (≥1%)</li>
      <li>Volume: +1 (RVOL-T ≥1.5×), +2 (≥2×)</li>
      <li>RSI: +1 (≥60 or ≤40)</li>
      <li>VWAP: +1 (price above VWAP)</li>
      <li>Alignment: +1 (gap & move same way)</li>
    </ul>
  </div>
);

const INDICATOR_HELP: Record<string, React.ReactNode> = {
  Gap: 'Overnight gap = (open − prev close) / prev close. A large gap signals fresh interest before the bell.',
  RS: 'Relative Strength vs Nifty 50 = stock’s % move minus the index’s % move. Positive = leading the market.',
  'RVOL-T': 'Relative Volume by Time. Today’s cumulative volume vs the 20-day average for the same time of day. ≥2× means institutional participation. A ✻ marks a basic volume-expansion fallback when RVOL-T can’t be computed.',
  RSI: 'Relative Strength Index (14, 15-min). ≥60 = strong upside momentum; ≤40 = strong downside. The extremes are what the scanner rewards.',
  VWAP: 'Volume-Weighted Average Price for the session. Trading above VWAP is bullish (buyers in control); below is bearish.',
  Setup: 'The trade pattern the scanner detected for this stock — see the legend below the table for what each one means.',
  Change: 'Change since the previous close.',
  Price: 'Last traded price.',
};

const SETUP_HELP: Record<string, string> = {
  'ORB breakout': 'Price broke above the first 15-minute opening range — classic bullish breakout entry.',
  'ORB breakdown': 'Price broke below the opening range — bearish breakdown entry.',
  'VWAP pullback': 'Price pulled back to VWAP support from above (within 0.3%) — buy-the-dip continuation.',
  'VWAP rejection': 'Price is being rejected at VWAP from below — bearish continuation.',
  'Momentum continuation': 'Strong gap + relative strength in the same direction — trend likely to extend.',
  'Gap fade candidate': 'Gapped down with weakness — a candidate to fade (short) rather than chase.',
  'Relative strength leader': 'Outperforming Nifty meaningfully — a market leader for long setups.',
  'Relative weakness': 'Underperforming Nifty meaningfully — a laggard, better for short setups.',
  'Watching': 'No clean setup yet — keep on the radar but no edge to act on.',
  'Not analyzed': 'Outside the deep-analysis window — only Phase 1 (gap + relative strength) was computed.',
};

const TEMPLATES = ['orb', 'breakout', 'mean-reversion', 'vwap-bounce', 'scalp'];

// ─── Formatting helpers ─────────────────────────────────────────────────────

const inr = (n: number | null | undefined) =>
  n == null ? '—' : '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 2 });

const pct = (n: number | null | undefined) =>
  n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;

const vol = (n: number | null | undefined) => {
  if (n == null) return '—';
  if (n >= 1e7) return (n / 1e7).toFixed(1) + 'Cr';
  if (n >= 1e5) return (n / 1e5).toFixed(1) + 'L';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
};

/** Score → tint. 6+ hot, 4–5 warm, 2–3 mild, else cold. */
const scoreTint = (s: number) => {
  if (s >= 6) return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/30';
  if (s >= 4) return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-amber-500/30';
  if (s >= 2) return 'bg-sky-500/10 text-sky-600 dark:text-sky-400 ring-sky-500/30';
  return 'bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 ring-zinc-500/20';
};

const rowTint = (s: number) =>
  s >= 6 ? 'bg-emerald-500/[0.04]' : s >= 4 ? 'bg-amber-500/[0.03]' : '';

const selectCls =
  'w-full rounded-lg bg-white dark:bg-zinc-900/50 border border-zinc-300 dark:border-zinc-700 text-sm text-zinc-800 dark:text-zinc-200 px-3 py-2 focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 focus:outline-none';

// ────────────────────────────────────────────────────────────────────────────

export function clientLoader() {
  // Same gate as the other trading routes (monitor, strategies, backtest).
  requirePermission('settings.access');
  return null;
}

// ─── Order modal ────────────────────────────────────────────────────────────

interface OrderModalProps {
  authToken: string;
  candidate: Candidate;
  defaultSide: 'buy' | 'sell';
  onClose: () => void;
}

function OrderModal({ authToken, candidate, defaultSide, onClose }: OrderModalProps) {
  const [side, setSide] = useState<'buy' | 'sell'>(defaultSide);
  const [qty, setQty] = useState('1');
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('MARKET');
  const [price, setPrice] = useState(String(candidate.price ?? ''));
  const [product, setProduct] = useState<'I' | 'D'>('I');
  const [preview, setPreview] = useState<any>(null);
  const [placed, setPlaced] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const body = () => ({
    symbol: candidate.symbol,
    action: side,
    quantity: parseInt(qty) || 0,
    order_type: orderType,
    price: orderType === 'LIMIT' ? parseFloat(price) || null : null,
    product,
  });

  const call = async (dryRun: boolean) => {
    const n = parseInt(qty);
    if (!n || n < 1) { setError('Quantity must be at least 1'); return; }
    if (orderType === 'LIMIT' && !(parseFloat(price) > 0)) {
      setError('Limit orders need a price'); return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/hero-scanner/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ ...body(), dry_run: dryRun }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Order failed');
      if (dryRun) setPreview(data);
      else setPlaced(data);
    } catch (e: any) {
      setError(e.message || 'Network error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-fade-in" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-zinc-200 dark:border-zinc-700/60 bg-white dark:bg-zinc-900 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 px-5 py-4">
          <div className="flex items-center gap-2">
            <ShoppingCart className="h-5 w-5 text-amber-500" />
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
              Trade {candidate.symbol}
            </h3>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200">
            <X className="h-5 w-5" />
          </button>
        </div>

        {placed ? (
          /* ─── Confirmation ─── */
          <div className="px-5 py-8 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
            <p className="mt-3 font-semibold text-zinc-900 dark:text-zinc-100">Order Placed</p>
            <p className="mt-1 text-sm text-zinc-500">
              {placed.action} {placed.quantity}× {placed.symbol}
            </p>
            {placed.order_id && (
              <p className="mt-2 font-mono text-xs text-zinc-400">ID: {placed.order_id}</p>
            )}
            {placed.status && (
              <p className="mt-1 text-xs text-zinc-500">Status: {placed.status}</p>
            )}
            <button
              onClick={onClose}
              className="mt-5 rounded-lg bg-zinc-900 dark:bg-zinc-100 px-4 py-2 text-sm font-medium text-white dark:text-zinc-900"
            >
              Done
            </button>
          </div>
        ) : (
          <div className="space-y-4 px-5 py-4">
            {/* Side toggle */}
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 p-1">
              {(['buy', 'sell'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => { setSide(s); setPreview(null); }}
                  className={`rounded-md py-1.5 text-sm font-semibold uppercase transition ${
                    side === s
                      ? s === 'buy'
                        ? 'bg-emerald-500 text-white'
                        : 'bg-rose-500 text-white'
                      : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-500">Quantity</label>
                <input
                  type="number" min="1" value={qty}
                  onChange={e => { setQty(e.target.value); setPreview(null); }}
                  className={selectCls}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-500">Product</label>
                <select value={product} onChange={e => { setProduct(e.target.value as any); setPreview(null); }} className={selectCls}>
                  <option value="I">Intraday (MIS)</option>
                  <option value="D">Delivery (CNC)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-500">Order Type</label>
                <select value={orderType} onChange={e => { setOrderType(e.target.value as any); setPreview(null); }} className={selectCls}>
                  <option value="MARKET">Market</option>
                  <option value="LIMIT">Limit</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-500">
                  Limit Price {orderType === 'MARKET' && <span className="text-zinc-400">(n/a)</span>}
                </label>
                <input
                  type="number" step="0.05" value={price}
                  disabled={orderType === 'MARKET'}
                  onChange={e => { setPrice(e.target.value); setPreview(null); }}
                  className={`${selectCls} disabled:opacity-40`}
                />
              </div>
            </div>

            <p className="text-xs text-zinc-400">
              Last traded price: <span className="font-medium text-zinc-600 dark:text-zinc-300">{inr(candidate.price)}</span>
            </p>

            {/* Preview box */}
            {preview && (
              <div className="rounded-lg border border-amber-300/50 bg-amber-50 dark:bg-amber-900/15 px-4 py-3 text-sm">
                <p className="mb-1 font-semibold text-amber-700 dark:text-amber-400">Dry-run preview</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-zinc-600 dark:text-zinc-300">
                  <span>Side</span><span className="text-right font-medium uppercase">{preview.action}</span>
                  <span>Quantity</span><span className="text-right font-medium">{preview.quantity}</span>
                  <span>Type</span><span className="text-right font-medium">{preview.order_type}</span>
                  {preview.current_ltp != null && (<><span>Current LTP</span><span className="text-right font-medium">{inr(preview.current_ltp)}</span></>)}
                  {preview.estimated_value != null && (<><span>Est. value</span><span className="text-right font-medium">{inr(preview.estimated_value)}</span></>)}
                </div>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-rose-50 dark:bg-rose-900/20 px-3 py-2 text-sm text-rose-600 dark:text-rose-400">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Two-step actions */}
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => call(true)}
                disabled={busy}
                className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 px-3 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-50"
              >
                {busy && !preview ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : 'Preview'}
              </button>
              <button
                onClick={() => call(false)}
                disabled={busy || !preview}
                title={!preview ? 'Preview the order first' : undefined}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold text-white disabled:opacity-40 ${
                  side === 'buy' ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-rose-600 hover:bg-rose-500'
                }`}
              >
                {busy && preview ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : 'Place Order'}
              </button>
            </div>
            <p className="text-center text-[11px] text-zinc-400">
              Preview is required before a live order can be placed.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main page ──────────────────────────────────────────────────────────────

export default function HeroScannerPage() {
  const { authToken } = useOutletContext<AuthContext>();

  // Scan options
  const [universe, setUniverse] = useState<'nifty50' | 'nifty100' | 'nifty500'>('nifty50');
  const [top, setTop] = useState('10');
  const [minScore, setMinScore] = useState('0');
  const [deep, setDeep] = useState('15');
  const [news, setNews] = useState(false);
  const [debugMode, setDebugMode] = useState(false);
  const [debugSymbol, setDebugSymbol] = useState('');

  // Auto-deploy options
  const [deployOn, setDeployOn] = useState(false);
  const [template, setTemplate] = useState('orb');
  const [capital, setCapital] = useState('50000');
  const [riskPct, setRiskPct] = useState('2');
  const [deployDryRun, setDeployDryRun] = useState(true);

  // Run state
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [autoDeploy, setAutoDeploy] = useState<AutoDeploy | null>(null);
  const [scannedDebug, setScannedDebug] = useState<string | null>(null);

  // Order modal
  const [orderFor, setOrderFor] = useState<Candidate | null>(null);

  const runScan = async () => {
    setRunning(true);
    setError(null);
    setScan(null);
    setAutoDeploy(null);
    try {
      const payload: any = {
        universe,
        top: parseInt(top) || 10,
        min_score: parseInt(minScore) || 0,
        deep: parseInt(deep) || 15,
        news,
        debug: debugMode && debugSymbol.trim() ? debugSymbol.trim().toUpperCase() : null,
      };
      if (deployOn) {
        payload.auto_deploy = template;
        payload.capital = parseFloat(capital) || 0;
        payload.risk_percent = parseFloat(riskPct) || 2;
        payload.dry_run = deployDryRun;
        if (!payload.capital) { setError('Capital is required for auto-deploy'); setRunning(false); return; }
      }
      const res = await fetch('/api/hero-scanner/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Scan failed');
      setScan(data.scan);
      setAutoDeploy(data.auto_deploy || null);
      setScannedDebug(payload.debug || null);
    } catch (e: any) {
      setError(e.message || 'Network error');
    } finally {
      setRunning(false);
    }
  };

  const candidates = scan?.candidates ?? [];
  const podium = useMemo(() => candidates.slice(0, 3), [candidates]);
  const niftyUp = (scan?.market_context.nifty_change_pct ?? 0) >= 0;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

        {/* ── Header ── */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="relative rounded-xl bg-amber-100 p-2.5 dark:bg-amber-900/30">
              <Radar className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              <span className="absolute inset-0 rounded-xl ring-1 ring-inset ring-amber-400/40" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                Hero Scanner
              </h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Morning momentum scan — gap, relative strength &amp; volume leaders
              </p>
            </div>
          </div>
          {scan && (
            <div className="hidden text-right sm:block">
              <div className={`flex items-center justify-end gap-1.5 text-lg font-semibold tabular-nums ${niftyUp ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {niftyUp ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                Nifty {pct(scan.market_context.nifty_change_pct)}
              </div>
              <p className="text-xs text-zinc-400">
                {scan.scan_time} · {scan.elapsed_seconds}s
              </p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">

          {/* ── Config panel ── */}
          <div className="lg:col-span-1">
            <div className="sticky top-8 space-y-5 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-700/50 dark:bg-zinc-900/50">

              <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Scan Settings</h2>

              {/* Universe */}
              <div>
                <label className="mb-1 flex items-center gap-1 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                  Universe
                  <Tooltip content="How many stocks to scan. nifty50 is fastest (~10s); nifty500 is the deepest sweep but can take a few minutes.">
                    <Info className="h-3.5 w-3.5 text-zinc-400" />
                  </Tooltip>
                </label>
                <select value={universe} onChange={e => setUniverse(e.target.value as any)} className={selectCls}>
                  <option value="nifty50">Nifty 50 — fastest</option>
                  <option value="nifty100">Nifty 100</option>
                  <option value="nifty500">Nifty 500 — deepest</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 flex items-center gap-1 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                    Top N
                    <Tooltip content="How many top-ranked candidates to show in the results table.">
                      <Info className="h-3.5 w-3.5 text-zinc-400" />
                    </Tooltip>
                  </label>
                  <input type="number" min="1" max="50" value={top} onChange={e => setTop(e.target.value)} className={selectCls} />
                </div>
                <div>
                  <label className="mb-1 flex items-center gap-1 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                    Min Score
                    <Tooltip content="Hide candidates scoring below this threshold (0–8). Use 4+ to see only strong setups.">
                      <Info className="h-3.5 w-3.5 text-zinc-400" />
                    </Tooltip>
                  </label>
                  <input type="number" min="0" max="8" value={minScore} onChange={e => setMinScore(e.target.value)} className={selectCls} />
                </div>
              </div>

              <div>
                <label className="mb-1 flex items-center gap-1 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                  Deep-analyze count
                  <Tooltip content="Phase 2 runs RSI, VWAP and RVOL-T on this many top Phase-1 candidates. Higher = more thorough but slower.">
                    <Info className="h-3.5 w-3.5 text-zinc-400" />
                  </Tooltip>
                </label>
                <input type="number" min="1" max="50" value={deep} onChange={e => setDeep(e.target.value)} className={selectCls} />
              </div>

              {/* News toggle */}
              <label className="flex cursor-pointer items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                  <Newspaper className="h-4 w-4" /> Market news briefing
                  <Tooltip content="Adds a Perplexity-sourced macro/news overview for the day. Per-candidate news from Upstox is always included.">
                    <Info className="h-3.5 w-3.5 text-zinc-400" />
                  </Tooltip>
                </span>
                <input type="checkbox" checked={news} onChange={e => setNews(e.target.checked)} className="h-4 w-4 accent-amber-500" />
              </label>

              {/* Debug mode */}
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700/50">
                <label className="flex cursor-pointer items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                    <Bug className="h-4 w-4" /> Debug single stock
                    <Tooltip content="Forces one symbol into deep analysis and shows all its raw indicators, even if it wouldn't otherwise rank.">
                      <Info className="h-3.5 w-3.5 text-zinc-400" />
                    </Tooltip>
                  </span>
                  <input type="checkbox" checked={debugMode} onChange={e => setDebugMode(e.target.checked)} className="h-4 w-4 accent-amber-500" />
                </label>
                {debugMode && (
                  <input
                    value={debugSymbol}
                    onChange={e => setDebugSymbol(e.target.value.toUpperCase())}
                    placeholder="e.g. TATAMOTORS"
                    className={`${selectCls} mt-2 font-mono text-xs`}
                  />
                )}
              </div>

              {/* Auto-deploy */}
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700/50">
                <label className="flex cursor-pointer items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm font-medium text-zinc-600 dark:text-zinc-400">
                    <Rocket className="h-4 w-4" /> Auto-deploy strategy
                    <Tooltip content="After scanning, deploy a strategy template on the top candidates via the monitor rules engine. Keep dry-run on to preview the rules without creating them." width={260}>
                      <Info className="h-3.5 w-3.5 text-zinc-400" />
                    </Tooltip>
                  </span>
                  <input type="checkbox" checked={deployOn} onChange={e => setDeployOn(e.target.checked)} className="h-4 w-4 accent-amber-500" />
                </label>
                {deployOn && (
                  <div className="mt-3 space-y-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-zinc-500">Template</label>
                      <select value={template} onChange={e => setTemplate(e.target.value)} className={selectCls}>
                        {TEMPLATES.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500">Capital each (₹)</label>
                        <input type="number" min="1" value={capital} onChange={e => setCapital(e.target.value)} className={selectCls} />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500">Risk %</label>
                        <input type="number" step="0.5" min="0.5" value={riskPct} onChange={e => setRiskPct(e.target.value)} className={selectCls} />
                      </div>
                    </div>
                    <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-zinc-600 dark:text-zinc-400">
                      <input type="checkbox" checked={deployDryRun} onChange={e => setDeployDryRun(e.target.checked)} className="h-4 w-4 accent-amber-500" />
                      Dry-run (preview rules, don't create)
                    </label>
                    {!deployDryRun && (
                      <p className="flex items-start gap-1.5 rounded-md bg-rose-50 px-2 py-1.5 text-[11px] text-rose-600 dark:bg-rose-900/20 dark:text-rose-400">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        Live deploy will create real monitor rules on the top {top} candidates.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Run */}
              <button
                onClick={runScan}
                disabled={running}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-60"
              >
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {running ? 'Scanning…' : 'Run Scan'}
              </button>
              {running && (
                <p className="text-center text-xs text-zinc-400">
                  {universe === 'nifty500' ? 'Deep sweep — this can take a few minutes.' : 'Hang tight…'}
                </p>
              )}
            </div>
          </div>

          {/* ── Results ── */}
          <div className="space-y-6 lg:col-span-2">

            {error && (
              <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-900/20 dark:text-rose-400">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {!scan && !running && !error && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 py-24 text-center dark:border-zinc-700">
                <Radar className="h-10 w-10 text-zinc-300 dark:text-zinc-600" />
                <p className="mt-3 text-sm font-medium text-zinc-500">No scan yet</p>
                <p className="mt-1 max-w-xs text-xs text-zinc-400">
                  Pick a universe and hit Run Scan. Best run 9:20–9:30 IST, just after the open.
                </p>
              </div>
            )}

            {running && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-zinc-200 py-24 dark:border-zinc-700/50">
                <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
                <p className="mt-3 text-sm text-zinc-500">Scanning {universe.replace('nifty', 'Nifty ')}…</p>
              </div>
            )}

            {scan && (
              <>
                {/* Podium */}
                {podium.length > 0 && (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {podium.map((c, i) => {
                      const Icon = [Crown, Medal, Award][i];
                      const accent = ['text-amber-500', 'text-zinc-400', 'text-orange-400'][i];
                      return (
                        <div
                          key={c.symbol}
                          className="group rounded-xl border border-zinc-200 bg-white p-4 transition hover:border-amber-300 hover:shadow-md dark:border-zinc-700/50 dark:bg-zinc-900/50 dark:hover:border-amber-500/40"
                        >
                          <div className="flex items-center justify-between">
                            <Icon className={`h-5 w-5 ${accent}`} />
                            <span className={`rounded-md px-2 py-0.5 text-sm font-bold tabular-nums ring-1 ring-inset ${scoreTint(c.score)}`}>
                              {c.score}
                            </span>
                          </div>
                          <p className="mt-2 font-bold text-zinc-900 dark:text-zinc-100">{c.symbol}</p>
                          <p className="text-sm text-zinc-500 tabular-nums">{inr(c.price)}</p>
                          <p className="mt-1 text-xs font-medium text-amber-600 dark:text-amber-400">{c.setup}</p>
                          <div className="mt-3 flex gap-2">
                            <button
                              onClick={() => setOrderFor(c)}
                              className="flex-1 rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                            >
                              Trade
                            </button>
                            <Link
                              to={`/charts?symbol=${encodeURIComponent(c.symbol)}`}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-600 transition hover:border-amber-300 hover:text-amber-600 dark:border-zinc-700 dark:text-zinc-300 dark:hover:text-amber-400"
                            >
                              <LineChart className="h-3.5 w-3.5" /> Chart
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Table */}
                {candidates.length === 0 ? (
                  <div className="rounded-xl border border-zinc-200 py-12 text-center text-sm text-zinc-500 dark:border-zinc-700/50">
                    No candidates matched your filters.
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-700/50">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-700/50 dark:bg-zinc-800/50">
                            <th className="px-3 py-2.5 font-semibold">Symbol</th>
                            {([
                              ['Price', 'text-right'],
                              ['Score', 'text-center'],
                              ['Gap', 'text-right'],
                              ['RS', 'text-right'],
                              ['RVOL-T', 'text-right'],
                              ['RSI', 'text-right'],
                              ['VWAP', 'text-center'],
                              ['Setup', 'text-left'],
                            ] as const).map(([label, align]) => (
                              <th key={label} className={`px-3 py-2.5 font-semibold ${align}`}>
                                <Tooltip
                                  content={label === 'Score' ? SCORE_HELP : INDICATOR_HELP[label]}
                                  width={label === 'Score' ? 260 : 230}
                                >
                                  <span className="inline-flex items-center gap-1 border-b border-dotted border-zinc-400/50 cursor-help">
                                    {label}
                                    <Info className="h-3 w-3 opacity-50" />
                                  </span>
                                </Tooltip>
                              </th>
                            ))}
                            <th className="px-3 py-2.5 text-right font-semibold">Trade</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                          {candidates.map(c => {
                            const rvolDisplay = c.rvol_t != null
                              ? `${c.rvol_t.toFixed(1)}×`
                              : c.vol_expansion != null
                                ? `${c.vol_expansion.toFixed(1)}×✻`
                                : '—';
                            const isDebug = scannedDebug != null && c.symbol === scannedDebug;
                            return (
                              <tr key={c.symbol} className={`${isDebug ? 'bg-amber-500/[0.12] ring-1 ring-inset ring-amber-400/50' : rowTint(c.score)} transition hover:bg-amber-500/[0.06]`}>
                                <td className="px-3 py-2.5 font-semibold text-zinc-900 dark:text-zinc-100">
                                  <span className="inline-flex items-center gap-1.5">
                                    {c.symbol}
                                    <Tooltip content={`Open ${c.symbol} on the charts page`}>
                                      <Link
                                        to={`/charts?symbol=${encodeURIComponent(c.symbol)}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="text-zinc-400 transition hover:text-amber-500"
                                        aria-label={`Chart for ${c.symbol}`}
                                      >
                                        <LineChart className="h-3.5 w-3.5" />
                                      </Link>
                                    </Tooltip>
                                    {isDebug && (
                                      <span className="inline-flex items-center gap-0.5 rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold uppercase text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                                        <Bug className="h-2.5 w-2.5" /> debug
                                      </span>
                                    )}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-zinc-600 dark:text-zinc-300">{inr(c.price)}</td>
                                <td className="px-3 py-2.5 text-center">
                                  <span className={`inline-block min-w-[1.75rem] rounded-md px-1.5 py-0.5 text-xs font-bold tabular-nums ring-1 ring-inset ${scoreTint(c.score)}`}>
                                    {c.score}
                                  </span>
                                </td>
                                <td className={`px-3 py-2.5 text-right tabular-nums ${c.gap_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                                  {pct(c.gap_pct)}
                                </td>
                                <td className={`px-3 py-2.5 text-right tabular-nums ${c.rel_strength_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                                  {pct(c.rel_strength_pct)}
                                </td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-zinc-600 dark:text-zinc-300">{rvolDisplay}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-zinc-600 dark:text-zinc-300">
                                  {c.rsi != null ? c.rsi.toFixed(0) : '—'}
                                </td>
                                <td className="px-3 py-2.5 text-center">
                                  {c.above_vwap == null ? (
                                    <span className="text-zinc-400">—</span>
                                  ) : (
                                    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${c.above_vwap ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                                      {c.above_vwap ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                                      {c.above_vwap ? 'Above' : 'Below'}
                                    </span>
                                  )}
                                </td>
                                <td className="px-3 py-2.5">
                                  <Tooltip content={SETUP_HELP[c.setup] ?? c.setup} width={240}>
                                    <span className="cursor-help border-b border-dotted border-zinc-400/50 text-xs font-medium text-amber-600 dark:text-amber-400">
                                      {c.setup}
                                    </span>
                                  </Tooltip>
                                </td>
                                <td className="px-3 py-2.5 text-right">
                                  <button
                                    onClick={() => setOrderFor(c)}
                                    className="rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                                  >
                                    Trade
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <p className="border-t border-zinc-100 px-3 py-2 text-[11px] text-zinc-400 dark:border-zinc-800">
                      ✻ = basic volume expansion (RVOL-T unavailable). Hover any column header or setup name for an explanation.
                    </p>
                  </div>
                )}

                {/* Setup legend */}
                <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700/50 dark:bg-zinc-900/50">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">Setup styles</h3>
                  <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
                    {Object.entries(SETUP_HELP).map(([name, desc]) => (
                      <div key={name} className="text-xs">
                        <span className="font-medium text-amber-600 dark:text-amber-400">{name}</span>
                        <span className="text-zinc-500 dark:text-zinc-400"> — {desc}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Per-candidate news */}
                {candidates.some(c => c.news && c.news.length > 0) && (
                  <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700/50 dark:bg-zinc-900/50">
                    <h3 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                      <Newspaper className="h-4 w-4" /> Candidate news
                    </h3>
                    <div className="space-y-3">
                      {candidates.filter(c => c.news && c.news.length).map(c => (
                        <div key={c.symbol}>
                          <p className="text-xs font-bold text-zinc-800 dark:text-zinc-200">{c.symbol}</p>
                          <ul className="mt-0.5 space-y-0.5">
                            {c.news!.slice(0, 3).map((a, i) => (
                              <li key={i} className="text-xs text-zinc-500 dark:text-zinc-400">• {a.heading}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Market overview */}
                {scan.market_news && (
                  <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700/50 dark:bg-zinc-900/50">
                    <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                      <Newspaper className="h-4 w-4" /> Market overview
                    </h3>
                    <div className="prose prose-sm prose-zinc max-w-none text-zinc-600 dark:prose-invert dark:text-zinc-300 prose-headings:text-zinc-800 prose-headings:text-sm prose-headings:font-semibold dark:prose-headings:text-zinc-200 prose-strong:text-zinc-800 dark:prose-strong:text-zinc-100 prose-a:text-sky-600 dark:prose-a:text-sky-400 prose-li:my-0.5">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {scan.market_news}
                      </ReactMarkdown>
                    </div>
                    {scan.market_news_citations && scan.market_news_citations.length > 0 && (
                      <div className="mt-2 border-t border-zinc-100 pt-2 dark:border-zinc-800">
                        <p className="text-[11px] font-semibold text-zinc-500">Sources</p>
                        {scan.market_news_citations.slice(0, 5).map((u, i) => (
                          <a key={i} href={u} target="_blank" rel="noreferrer"
                             className="block truncate text-[11px] text-sky-600 hover:underline dark:text-sky-400">
                            [{i + 1}] {u}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Auto-deploy summary */}
                {autoDeploy && (
                  <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700/50 dark:bg-zinc-900/50">
                    <h3 className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                      <Rocket className="h-4 w-4" />
                      Auto-deploy: {autoDeploy.template}
                      {autoDeploy.dry_run && (
                        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                          Dry run
                        </span>
                      )}
                    </h3>
                    <p className="mb-3 text-xs text-zinc-500">
                      ₹{autoDeploy.capital_per_strategy.toLocaleString('en-IN')} each · {autoDeploy.risk_percent}% risk ·{' '}
                      <span className="text-emerald-600 dark:text-emerald-400">{autoDeploy.succeeded} deployed</span>
                      {autoDeploy.failed > 0 && <span className="text-rose-600 dark:text-rose-400">, {autoDeploy.failed} failed</span>}
                    </p>
                    <div className="space-y-1">
                      {autoDeploy.deployments.map((d, i) => (
                        <div key={i} className="flex items-center justify-between rounded-md bg-zinc-50 px-3 py-1.5 text-xs dark:bg-zinc-800/50">
                          <span className="font-medium text-zinc-800 dark:text-zinc-200">{d.symbol}</span>
                          {d.error ? (
                            <span className="text-rose-600 dark:text-rose-400">{d.error}</span>
                          ) : (
                            <span className="text-zinc-500">
                              {d.rules_count} rules{d.group_id ? ` · ${d.group_id}` : ''}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {orderFor && (
        <OrderModal
          authToken={authToken}
          candidate={orderFor}
          defaultSide={
            orderFor.gap_pct >= 0 || orderFor.rel_strength_pct >= 0 || orderFor.above_vwap === true
              ? 'buy' : 'sell'
          }
          onClose={() => setOrderFor(null)}
        />
      )}
    </div>
  );
}
