import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  Flame, Plus, Trash2, Loader2, Power, PowerOff, ChevronDown, ChevronUp,
  AlertTriangle, X, TrendingUp, TrendingDown, CircleDot, Square, Clock,
  Activity, Pencil,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../components/catalyst/dialog';
import { Badge } from '../components/catalyst/badge';
import { Input } from '../components/catalyst/input';
import { SnapshotChartButton, type DecisionSnapshot } from '../components/scalp/SnapshotChart';

// Indicator catalogs and per-indicator default param schemas. Used to render
// dynamic param inputs as the user picks a primary or confirm indicator.
const PRIMARY_INDICATORS: { value: string; label: string }[] = [
  { value: 'utbot', label: 'UT Bot' },
  { value: 'halftrend', label: 'HalfTrend' },
  { value: 'ssl_hybrid', label: 'SSL Hybrid' },
  { value: 'ema_crossover', label: 'EMA Crossover' },
  { value: 'supertrend', label: 'Supertrend' },
  { value: 'renko', label: 'Renko' },
];

const CONFIRM_INDICATORS: { value: string; label: string }[] = [
  { value: '', label: '— None —' },
  { value: 'qqe_mod', label: 'QQE MOD' },
  { value: 'macd', label: 'MACD' },
  { value: 'halftrend', label: 'HalfTrend' },
  { value: 'ssl_hybrid', label: 'SSL Hybrid' },
  { value: 'utbot', label: 'UT Bot' },
];

const PARAM_DEFAULTS: Record<string, Record<string, number>> = {
  utbot: { period: 10, sensitivity: 1.0 },
  halftrend: { amplitude: 2, channel_dev: 2.0, atr_period: 100 },
  ssl_hybrid: { period: 10 },
  ema_crossover: { fast: 9, slow: 21 },
  supertrend: { period: 10, multiplier: 3.0 },
  renko: { brick_size: 10 },
  qqe_mod: { rsi_period: 6, smoothing: 5 },
  macd: {},
};

const PARAM_LABELS: Record<string, string> = {
  period: 'Period',
  sensitivity: 'Sensitivity',
  amplitude: 'Amplitude',
  channel_dev: 'Channel Dev',
  atr_period: 'ATR Period',
  fast: 'Fast EMA',
  slow: 'Slow EMA',
  multiplier: 'Multiplier',
  brick_size: 'Brick Size',
  rsi_period: 'RSI Period',
  smoothing: 'Smoothing',
  baseline_period: 'Baseline EMA',
};

function IndicatorParams({
  indicator, params, onChange,
}: {
  indicator: string;
  params: Record<string, number>;
  onChange: (next: Record<string, number>) => void;
}) {
  const schema = PARAM_DEFAULTS[indicator] || {};
  const keys = Object.keys(schema);
  if (keys.length === 0) {
    return <p className="text-xs text-zinc-500 italic">No parameters.</p>;
  }
  return (
    <div className={`grid gap-3 ${keys.length === 1 ? 'grid-cols-1' : keys.length === 2 ? 'grid-cols-2' : 'grid-cols-3'}`}>
      {keys.map(k => (
        <div key={k}>
          <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            {PARAM_LABELS[k] || k}
          </label>
          <Input
            type="number"
            step="0.1"
            value={params[k] ?? schema[k]}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              const v = e.target.value === '' ? schema[k] : Number(e.target.value);
              onChange({ ...params, [k]: v });
            }}
          />
        </div>
      ))}
    </div>
  );
}

// Equity symbol autocomplete used by equity_intraday / equity_swing modes.
// Reuses /api/monitor/symbols (same backend search the rule builder uses).
function EquitySymbolPicker({
  authToken, value, onSelect,
}: {
  authToken: string;
  value: string;
  onSelect: (symbol: string) => void;
}) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<{ symbol: string; name: string }[]>([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setQuery(value); }, [value]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const search = useCallback(async (term: string) => {
    if (term.length < 1) { setResults([]); return; }
    try {
      const res = await fetch(`/api/monitor/symbols?q=${encodeURIComponent(term)}&limit=8`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setOpen(true);
      }
    } catch { /* ignore */ }
  }, [authToken]);

  return (
    <div ref={wrapRef} className="relative">
      <Input
        value={query}
        placeholder="Search equity symbol (e.g. RELIANCE)"
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          const v = e.target.value;
          setQuery(v);
          if (debounceRef.current) clearTimeout(debounceRef.current);
          debounceRef.current = setTimeout(() => search(v), 250);
        }}
        onFocus={() => { if (results.length > 0) setOpen(true); }}
      />
      {open && results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-60 overflow-auto rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 shadow-lg">
          {results.map(r => (
            <button
              key={r.symbol}
              type="button"
              className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-700"
              onClick={() => { setQuery(r.symbol); setOpen(false); onSelect(r.symbol); }}
            >
              <div className="font-medium text-zinc-900 dark:text-zinc-100">{r.symbol}</div>
              <div className="text-xs text-zinc-500">{r.name}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const SESSION_MODES: { value: string; label: string; description: string }[] = [
  { value: 'options_scalp', label: 'Options Scalp', description: 'ATM CE/PE on index, intraday' },
  { value: 'equity_intraday', label: 'Equity Intraday', description: 'Equity LONG/SHORT, daily squareoff' },
  { value: 'equity_swing', label: 'Equity Swing', description: 'Multi-day delivery, LONG only' },
];

interface AuthContext {
  authToken: string;
  user?: any;
}

interface ScalpSession {
  id: number;
  name: string;
  enabled: boolean;
  underlying: string;
  underlying_instrument_token: string;
  expiry: string;
  lots: number;
  product: string;
  indicator_timeframe: string;
  utbot_period: number;
  utbot_sensitivity: number;
  sl_points: number | null;
  target_points: number | null;
  trail_percent: number | null;
  trail_points: number | null;
  trail_arm_points: number | null;
  pending_action: string | null;
  session_mode?: string;
  quantity?: number | null;
  primary_indicator?: string;
  primary_params?: Record<string, number> | null;
  confirm_indicator?: string | null;
  confirm_params?: Record<string, number> | null;
  squareoff_time: string;
  state: string;
  current_option_type: string | null;
  current_strike: number | null;
  current_instrument_token: string | null;
  entry_price: number | null;
  entry_time: string | null;
  highest_premium: number | null;
  trade_count: number;
  max_trades: number;
  cooldown_seconds: number;
  created_at: string | null;
}

interface SessionLog {
  id: number;
  event_type: string;
  option_type: string | null;
  strike: number | null;
  entry_price: number | null;
  exit_price: number | null;
  quantity: number | null;
  pnl_points: number | null;
  pnl_amount: number | null;
  order_id: string | null;
  underlying_price: number | null;
  trigger_snapshot: DecisionSnapshot | null;
  created_at: string | null;
  session_id?: number;
  session_name?: string;
}

interface PnlSummary {
  total_exits: number;
  total_pnl: number;
  wins: number;
  losses: number;
}

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

export default function ScalpSessionsRoute() {
  const { authToken } = useOutletContext<AuthContext>();

  const [sessions, setSessions] = useState<ScalpSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // Create / Edit dialog (shared form). editingSession=null → create mode.
  const [showCreate, setShowCreate] = useState(false);
  const [editingSession, setEditingSession] = useState<ScalpSession | null>(null);
  const [creating, setCreating] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [formData, setFormData] = useState<any>({
    name: '',
    session_mode: 'options_scalp',
    underlying: 'NIFTY',
    expiry: '',
    lots: 1,
    quantity: '',
    indicator_timeframe: '1m',
    utbot_period: 10,
    utbot_sensitivity: 1.0,
    primary_indicator: 'utbot',
    primary_params: { period: 10, sensitivity: 1.0 },
    confirm_indicator: '',
    confirm_params: {},
    sl_points: '',
    target_points: '',
    trail_percent: '',
    trail_points: '',
    trail_arm_points: '',
    squareoff_time: '15:15',
    max_trades: 20,
    cooldown_seconds: 60,
  });

  // Expanded session detail
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [sessionLogs, setSessionLogs] = useState<SessionLog[]>([]);
  const [sessionPnl, setSessionPnl] = useState<PnlSummary | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Active tab
  const [activeTab, setActiveTab] = useState<'sessions' | 'logs'>('sessions');
  const [allLogs, setAllLogs] = useState<SessionLog[]>([]);

  // Expiry options
  const [expiries, setExpiries] = useState<string[]>([]);

  const headers = { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' };

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch('/api/scalp/sessions', { headers: { Authorization: `Bearer ${authToken}` } });
      if (!res.ok) throw new Error('Failed to fetch sessions');
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const fetchAllLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/scalp/logs?limit=200', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to fetch logs');
      const data = await res.json();
      setAllLogs(data.logs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
    }
  }, [authToken]);

  useEffect(() => {
    if (activeTab === 'logs') fetchAllLogs();
  }, [activeTab, fetchAllLogs]);

  // Fetch expiries when underlying changes
  useEffect(() => {
    if (!formData.underlying) return;
    fetch(`/api/strategies/expiries?underlying=${formData.underlying}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then(r => r.json())
      .then(d => {
        setExpiries(d.expiries || []);
        if (d.expiries?.length && !formData.expiry) {
          setFormData(prev => ({ ...prev, expiry: d.expiries[0] }));
        }
      })
      .catch(() => setExpiries([]));
  }, [formData.underlying, authToken]);

  const showAction = (msg: string) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(null), 3000);
  };

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const body: any = { ...formData };
      body.sl_points = body.sl_points ? Number(body.sl_points) : null;
      body.target_points = body.target_points ? Number(body.target_points) : null;
      body.trail_percent = body.trail_percent ? Number(body.trail_percent) : null;
      body.trail_points = body.trail_points ? Number(body.trail_points) : null;
      body.trail_arm_points = body.trail_arm_points ? Number(body.trail_arm_points) : null;
      // Confirm indicator: empty string means none — send null, drop params
      if (!body.confirm_indicator) {
        body.confirm_indicator = null;
        body.confirm_params = null;
      }
      // Keep utbot_period/utbot_sensitivity in sync when primary is utbot,
      // so legacy code paths and back-compat fallbacks see consistent values.
      if (body.primary_indicator === 'utbot' && body.primary_params) {
        body.utbot_period = body.primary_params.period ?? body.utbot_period;
        body.utbot_sensitivity = body.primary_params.sensitivity ?? body.utbot_sensitivity;
      }
      // Mode-specific normalization: equity uses quantity, no expiry/lots;
      // options uses expiry/lots, no quantity.
      if (body.session_mode === 'equity_intraday' || body.session_mode === 'equity_swing') {
        body.quantity = body.quantity ? Number(body.quantity) : null;
        body.expiry = '';
        delete body.lots;
      } else {
        body.quantity = null;
      }
      const res = await fetch('/api/scalp/sessions', { method: 'POST', headers, body: JSON.stringify(body) });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create');
      }
      setShowCreate(false);
      showAction('Session created');
      await fetchSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create');
    } finally {
      setCreating(false);
    }
  };

  const openEdit = (s: ScalpSession) => {
    const primary = s.primary_indicator || 'utbot';
    setFormData({
      name: s.name,
      session_mode: s.session_mode || 'options_scalp',
      underlying: s.underlying || '',
      expiry: s.expiry || '',
      lots: s.lots ?? 1,
      quantity: s.quantity ?? '',
      indicator_timeframe: s.indicator_timeframe,
      utbot_period: s.utbot_period,
      utbot_sensitivity: s.utbot_sensitivity,
      primary_indicator: primary,
      primary_params: s.primary_params || { ...(PARAM_DEFAULTS[primary] || {}) },
      confirm_indicator: s.confirm_indicator || '',
      confirm_params: s.confirm_params || {},
      sl_points: s.sl_points ?? '',
      target_points: s.target_points ?? '',
      trail_percent: s.trail_percent ?? '',
      trail_points: s.trail_points ?? '',
      trail_arm_points: s.trail_arm_points ?? '',
      squareoff_time: s.squareoff_time,
      max_trades: s.max_trades,
      cooldown_seconds: s.cooldown_seconds,
    });
    setEditingSession(s);
  };

  const handleSave = async () => {
    if (!editingSession) return;
    setSavingEdit(true);
    setError(null);
    try {
      const isHolding = editingSession.state !== 'IDLE';
      const body: any = {
        name: formData.name,
        sl_points: formData.sl_points === '' ? null : Number(formData.sl_points),
        target_points: formData.target_points === '' ? null : Number(formData.target_points),
        trail_percent: formData.trail_percent === '' ? null : Number(formData.trail_percent),
        trail_points: formData.trail_points === '' ? null : Number(formData.trail_points),
        trail_arm_points: formData.trail_arm_points === '' ? null : Number(formData.trail_arm_points),
        squareoff_time: formData.squareoff_time,
        max_trades: Number(formData.max_trades),
        cooldown_seconds: Number(formData.cooldown_seconds),
        primary_indicator: formData.primary_indicator,
        primary_params: formData.primary_params || null,
        confirm_indicator: formData.confirm_indicator || null,
        confirm_params: formData.confirm_indicator ? (formData.confirm_params || {}) : null,
      };
      if (formData.primary_indicator === 'utbot' && formData.primary_params) {
        body.utbot_period = formData.primary_params.period ?? formData.utbot_period;
        body.utbot_sensitivity = formData.primary_params.sensitivity ?? formData.utbot_sensitivity;
      }
      // Instrument-shape fields are only sent when IDLE — locked otherwise.
      if (!isHolding) {
        body.session_mode = formData.session_mode;
        body.underlying = formData.underlying;
        body.indicator_timeframe = formData.indicator_timeframe;
        if (formData.session_mode === 'options_scalp') {
          body.expiry = formData.expiry;
          body.lots = Number(formData.lots);
          body.quantity = null;
        } else {
          body.expiry = '';
          body.quantity = formData.quantity === '' ? null : Number(formData.quantity);
        }
      }
      const res = await fetch(`/api/scalp/sessions/${editingSession.id}`, {
        method: 'PATCH', headers, body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save');
      }
      setEditingSession(null);
      showAction('Session updated');
      await fetchSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSavingEdit(false);
    }
  };

  const toggleEnabled = async (id: number, enabled: boolean) => {
    try {
      const res = await fetch(`/api/scalp/sessions/${id}`, {
        method: 'PATCH', headers, body: JSON.stringify({ enabled: !enabled }),
      });
      const data = await res.json().catch(() => ({}));
      if (!enabled) {
        showAction('Session enabled');
      } else if (data.pending_action === 'exit_and_disable') {
        showAction('Exit scheduled — daemon will square off, then disable');
      } else {
        showAction('Session disabled');
      }
      await fetchSessions();
    } catch { setError('Failed to toggle'); }
  };

  const deleteSession = async (id: number) => {
    if (!confirm('Delete this session?')) return;
    try {
      const res = await fetch(`/api/scalp/sessions/${id}`, { method: 'DELETE', headers });
      const data = await res.json().catch(() => ({}));
      if (data.status === 'exit_pending') {
        showAction('Delete scheduled — daemon will square off first');
      } else {
        showAction('Session deleted');
        if (expandedId === id) setExpandedId(null);
      }
      await fetchSessions();
    } catch { setError('Failed to delete'); }
  };

  const manualExit = async (id: number) => {
    try {
      const res = await fetch(`/api/scalp/sessions/${id}/manual-exit`, { method: 'POST', headers });
      const data = await res.json().catch(() => ({}));
      if (data.pending_action === 'exit_and_disable') {
        showAction('Exit scheduled — daemon will square off, then disable');
      } else {
        showAction('Session disabled (was IDLE)');
      }
      await fetchSessions();
    } catch { setError('Failed to exit'); }
  };

  const toggleExpand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    setLoadingDetail(true);
    try {
      const [logsRes, pnlRes] = await Promise.all([
        fetch(`/api/scalp/sessions/${id}/logs?limit=20`, { headers: { Authorization: `Bearer ${authToken}` } }),
        fetch(`/api/scalp/sessions/${id}/pnl`, { headers: { Authorization: `Bearer ${authToken}` } }),
      ]);
      if (logsRes.ok) setSessionLogs((await logsRes.json()).logs || []);
      if (pnlRes.ok) setSessionPnl(await pnlRes.json());
    } catch { /* ignore */ } finally { setLoadingDetail(false); }
  };

  const stateBadge = (state: string, optionType: string | null) => {
    if (state === 'IDLE') return <Badge color="zinc">IDLE</Badge>;
    if (state === 'HOLDING_CE') return <Badge color="green">HOLDING CE</Badge>;
    if (state === 'HOLDING_PE') return <Badge color="red">HOLDING PE</Badge>;
    return <Badge>{state}</Badge>;
  };

  const eventBadge = (type: string) => {
    if (type.startsWith('entry')) return <Badge color="blue">{type}</Badge>;
    if (type === 'exit_target') return <Badge color="green">{type}</Badge>;
    if (type === 'exit_sl') return <Badge color="red">{type}</Badge>;
    if (type === 'exit_trail') return <Badge color="amber">{type}</Badge>;
    if (type === 'exit_reversal') return <Badge color="purple">{type}</Badge>;
    if (type === 'exit_squareoff') return <Badge color="zinc">{type}</Badge>;
    if (type === 'order_failed') return <Badge color="red">{type}</Badge>;
    return <Badge>{type}</Badge>;
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-red-600">
              <Flame className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100">Signal Sessions</h1>
              <p className="text-sm text-zinc-500">Stateful indicator-driven trading — options scalp, equity intraday, equity swing</p>
            </div>
          </div>
          <Button onClick={() => { setFormData({ name: '', session_mode: 'options_scalp', underlying: 'NIFTY', expiry: expiries[0] || '', lots: 1, quantity: '', indicator_timeframe: '1m', utbot_period: 10, utbot_sensitivity: 1.0, primary_indicator: 'utbot', primary_params: { ...PARAM_DEFAULTS.utbot }, confirm_indicator: '', confirm_params: {}, sl_points: '', target_points: '', trail_percent: '', trail_points: '', trail_arm_points: '', squareoff_time: '15:15', max_trades: 20, cooldown_seconds: 60 }); setShowCreate(true); }}>
            <Plus className="w-4 h-4" /> New Session
          </Button>
        </div>
      </div>

      {/* Action message */}
      {actionMsg && (
        <div className="mb-4 px-4 py-2 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-lg text-sm">
          {actionMsg}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-2 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> {error}
          <button onClick={() => setError(null)} className="ml-auto"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-zinc-200 dark:border-zinc-800">
        {(['sessions', 'logs'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === tab
                ? 'border-orange-500 text-orange-600 dark:text-orange-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}>
            {tab === 'sessions' ? <Activity className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
            {tab === 'sessions' ? 'Sessions' : 'All Logs'}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-12"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-400" /></div>
      ) : error && sessions.length === 0 ? null : activeTab === 'sessions' ? (
        sessions.length === 0 ? (
          <div className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50 p-12 text-center">
            <Flame className="w-8 h-8 text-zinc-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-2">No scalp sessions</h3>
            <p className="text-sm text-zinc-500 mb-4">Create your first session to start stateful options scalping</p>
            <Button onClick={() => setShowCreate(true)}>Create Session</Button>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map(s => (
              <div key={s.id} className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50">
                <div className="p-4 flex items-center gap-3 cursor-pointer" onClick={() => toggleExpand(s.id)}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-zinc-900 dark:text-zinc-100">{s.name}</span>
                      {stateBadge(s.state, s.current_option_type)}
                      {s.session_mode && s.session_mode !== 'options_scalp' && (
                        <Badge color="indigo">{s.session_mode === 'equity_swing' ? 'swing' : 'intraday'}</Badge>
                      )}
                      {s.pending_action && <Badge color="amber">exit pending</Badge>}
                      {!s.enabled && <Badge color="zinc">disabled</Badge>}
                    </div>
                    <div className="text-xs text-zinc-500 flex items-center gap-3 flex-wrap">
                      <span>{s.underlying}{s.expiry ? ` ${s.expiry}` : ''}</span>
                      <span>{s.session_mode && s.session_mode !== 'options_scalp' ? `${s.quantity ?? 0} sh` : `${s.lots} lot(s)`}</span>
                      <span>
                        {(s as any).primary_indicator || 'utbot'} {s.indicator_timeframe}
                        {(s as any).confirm_indicator ? ` + ${(s as any).confirm_indicator}` : ''}
                      </span>
                      {s.sl_points && <span>SL: {s.sl_points}pts</span>}
                      {s.target_points && <span>TP: {s.target_points}pts</span>}
                      {s.trail_points ? (
                        <span>Trail: {s.trail_points}pts{s.trail_arm_points ? ` arm +${s.trail_arm_points}` : ''}</span>
                      ) : s.trail_percent ? (
                        <span>Trail: {s.trail_percent}%{s.trail_arm_points ? ` arm +${s.trail_arm_points}` : ''}</span>
                      ) : null}
                      <span>Trades: {s.trade_count}/{s.max_trades}</span>
                    </div>
                    {s.state !== 'IDLE' && s.current_strike && (
                      <div className="text-xs text-zinc-600 dark:text-zinc-400 mt-1 flex items-center gap-2">
                        {s.current_option_type === 'CE' ? <TrendingUp className="w-3 h-3 text-green-500" /> : <TrendingDown className="w-3 h-3 text-red-500" />}
                        Strike: {s.current_strike} | Entry: {s.entry_price ?? 'pending'}
                        {s.highest_premium && <span>| High: {s.highest_premium}</span>}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {s.state !== 'IDLE' && (
                      <Button plain onClick={(e: React.MouseEvent) => { e.stopPropagation(); manualExit(s.id); }} title="Manual exit">
                        <Square className="w-4 h-4 text-red-500" />
                      </Button>
                    )}
                    <Button plain onClick={(e: React.MouseEvent) => { e.stopPropagation(); openEdit(s); }} title="Edit settings">
                      <Pencil className="w-4 h-4 text-zinc-400 hover:text-blue-500" />
                    </Button>
                    <Button plain onClick={(e: React.MouseEvent) => { e.stopPropagation(); toggleEnabled(s.id, s.enabled); }} title={s.enabled ? 'Disable' : 'Enable'}>
                      {s.enabled ? <Power className="w-4 h-4 text-green-500" /> : <PowerOff className="w-4 h-4 text-zinc-400" />}
                    </Button>
                    <Button plain onClick={(e: React.MouseEvent) => { e.stopPropagation(); deleteSession(s.id); }} title="Delete">
                      <Trash2 className="w-4 h-4 text-zinc-400 hover:text-red-500" />
                    </Button>
                    {expandedId === s.id ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
                  </div>
                </div>

                {expandedId === s.id && (
                  <div className="border-t border-zinc-200 dark:border-zinc-700/50 p-4">
                    {loadingDetail ? (
                      <Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-400" />
                    ) : (
                      <div className="space-y-4">
                        {/* P&L Summary */}
                        {sessionPnl && (
                          <div className="grid grid-cols-4 gap-3">
                            {[
                              { label: 'Total P&L', value: `${sessionPnl.total_pnl >= 0 ? '+' : ''}${sessionPnl.total_pnl.toFixed(2)}`, color: sessionPnl.total_pnl >= 0 ? 'text-green-600' : 'text-red-600' },
                              { label: 'Exits', value: sessionPnl.total_exits, color: 'text-zinc-600 dark:text-zinc-400' },
                              { label: 'Wins', value: sessionPnl.wins, color: 'text-green-600' },
                              { label: 'Losses', value: sessionPnl.losses, color: 'text-red-600' },
                            ].map(item => (
                              <div key={item.label} className="bg-white dark:bg-zinc-900/50 rounded-lg p-3 text-center">
                                <div className="text-xs text-zinc-500 mb-1">{item.label}</div>
                                <div className={`text-lg font-semibold ${item.color}`}>{item.value}</div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Recent logs */}
                        <div>
                          <h4 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">Recent Events</h4>
                          {sessionLogs.length === 0 ? (
                            <p className="text-sm text-zinc-500">No events yet</p>
                          ) : (
                            <div className="space-y-1">
                              {sessionLogs.map(log => (
                                <div key={log.id} className="flex items-center gap-3 text-xs py-2 border-b border-zinc-200/50 dark:border-zinc-700/30 last:border-0">
                                  {eventBadge(log.event_type)}
                                  <span className="text-zinc-500">
                                    {log.option_type && `${log.option_type} `}
                                    {log.strike && `${log.strike} `}
                                    {log.entry_price && `entry=${log.entry_price} `}
                                    {log.exit_price && `exit=${log.exit_price} `}
                                    {log.pnl_amount != null && (
                                      <span className={log.pnl_amount >= 0 ? 'text-green-600' : 'text-red-600'}>
                                        P&L: {log.pnl_amount >= 0 ? '+' : ''}{log.pnl_amount.toFixed(2)}
                                      </span>
                                    )}
                                  </span>
                                  {log.trigger_snapshot && (
                                    <SnapshotChartButton
                                      snapshot={log.trigger_snapshot}
                                      eventType={log.event_type}
                                      optionType={log.option_type}
                                      strike={log.strike}
                                    />
                                  )}
                                  <span className="ml-auto text-zinc-400 whitespace-nowrap">
                                    {log.created_at && new Date(log.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'Asia/Kolkata' })} IST
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        allLogs.length === 0 ? (
          <div className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50 p-12 text-center">
            <Clock className="w-8 h-8 text-zinc-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-2">No logs yet</h3>
            <p className="text-sm text-zinc-500">Logs appear as sessions fire entries, exits, and errors.</p>
          </div>
        ) : (
          <div className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50 divide-y divide-zinc-200 dark:divide-zinc-700/50">
            {allLogs.map(log => (
              <div key={log.id} className="p-3 flex items-center gap-3 flex-wrap text-xs">
                {eventBadge(log.event_type)}
                <span className="font-medium text-zinc-700 dark:text-zinc-300">
                  {log.session_name || `Session ${log.session_id ?? ''}`}
                </span>
                {log.option_type && (
                  <span className="text-zinc-600 dark:text-zinc-400">
                    {log.option_type}{log.strike != null ? ` ${log.strike}` : ''}
                  </span>
                )}
                {log.entry_price != null && (
                  <span className="text-zinc-500">entry={log.entry_price}</span>
                )}
                {log.exit_price != null && (
                  <span className="text-zinc-500">exit={log.exit_price}</span>
                )}
                {log.pnl_amount != null && (
                  <span className={log.pnl_amount >= 0 ? 'text-green-600' : 'text-red-600'}>
                    P&amp;L: {log.pnl_amount >= 0 ? '+' : ''}{log.pnl_amount.toFixed(2)}
                  </span>
                )}
                <span className="ml-auto text-zinc-400">
                  {log.created_at && new Date(log.created_at).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', day: '2-digit', month: 'short', timeZone: 'Asia/Kolkata' })} IST
                </span>
              </div>
            ))}
          </div>
        )
      )}

      {/* Create / Edit Dialog (shared) */}
      {(() => {
        const isEditing = editingSession !== null;
        const isHolding = isEditing && editingSession!.state !== 'IDLE';
        const lockInstrument = isHolding;
        const dialogOpen = showCreate || isEditing;
        const closeDialog = () => {
          if (isEditing) setEditingSession(null);
          else setShowCreate(false);
        };
        const submitting = isEditing ? savingEdit : creating;
        const onSubmit = isEditing ? handleSave : handleCreate;
        const submitDisabled = submitting || !formData.name || (
          !isEditing &&
          formData.session_mode !== 'equity_intraday' &&
          formData.session_mode !== 'equity_swing' &&
          !formData.expiry
        );
      return (
      <Dialog open={dialogOpen} onClose={closeDialog}>
        <DialogTitle>
          {isEditing ? `Edit: ${editingSession!.name}` : 'Create Signal Session'}
        </DialogTitle>
        <DialogBody>
          {isHolding && (
            <div className="mb-4 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700/50 text-amber-800 dark:text-amber-300 rounded-lg text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                Session is <b>{editingSession!.state}</b>. Instrument fields (mode, underlying, expiry, lots/qty, timeframe) are locked until IDLE — changing them mid-position would orphan the open contract. Other params (SL, target, trail, indicators, max trades, cooldown) take effect on the next tick.
              </div>
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Name</label>
              <Input value={formData.name} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, name: e.target.value }))} placeholder="e.g. NIFTY ATM Scalper" />
            </div>
            {/* Mode selector */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Mode</label>
              <select
                value={formData.session_mode}
                disabled={lockInstrument}
                onChange={e => {
                  const next = e.target.value;
                  setFormData((p: any) => ({
                    ...p,
                    session_mode: next,
                    // Reset underlying/expiry/lots vs symbol/quantity per mode.
                    underlying: next === 'options_scalp' ? 'NIFTY' : '',
                    expiry: '',
                    lots: 1,
                    quantity: '',
                    // Swing uses 1d by default; intraday/options 1m.
                    indicator_timeframe: next === 'equity_swing' ? '1d' : '1m',
                  }));
                }}
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                {SESSION_MODES.map(m => (
                  <option key={m.value} value={m.value}>{m.label} — {m.description}</option>
                ))}
              </select>
            </div>
            {/* Mode-specific instrument fields */}
            {formData.session_mode === 'options_scalp' ? (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Underlying</label>
                  <select value={formData.underlying} disabled={lockInstrument} onChange={e => setFormData((p: any) => ({ ...p, underlying: e.target.value, expiry: '' }))}
                    className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                    {['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'].map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Expiry</label>
                  <select value={formData.expiry} disabled={lockInstrument} onChange={e => setFormData((p: any) => ({ ...p, expiry: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                    {/* When editing, the session's current expiry may not be in the live list — show it explicitly */}
                    {isEditing && formData.expiry && !expiries.includes(formData.expiry) && (
                      <option value={formData.expiry}>{formData.expiry}</option>
                    )}
                    {expiries.map(e => <option key={e} value={e}>{e}</option>)}
                  </select>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Symbol</label>
                  {lockInstrument ? (
                    <Input value={formData.underlying} disabled />
                  ) : (
                    <EquitySymbolPicker
                      authToken={authToken}
                      value={formData.underlying}
                      onSelect={(sym) => setFormData((p: any) => ({ ...p, underlying: sym }))}
                    />
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Quantity</label>
                  <Input type="number" min={1} value={formData.quantity}
                    disabled={lockInstrument}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData((p: any) => ({ ...p, quantity: e.target.value }))}
                    placeholder="shares" />
                </div>
              </div>
            )}
            <div className={`grid gap-3 ${formData.session_mode === 'options_scalp' ? 'grid-cols-3' : 'grid-cols-2'}`}>
              {formData.session_mode === 'options_scalp' && (
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Lots</label>
                  <Input type="number" value={formData.lots} disabled={lockInstrument} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData((p: any) => ({ ...p, lots: Number(e.target.value) }))} min={1} />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Timeframe</label>
                <select value={formData.indicator_timeframe} disabled={lockInstrument} onChange={e => setFormData((p: any) => ({ ...p, indicator_timeframe: e.target.value }))}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                  {(formData.session_mode === 'equity_swing'
                    ? ['15m', '1h', '1d']
                    : ['1m', '3m', '5m', '15m']
                  ).map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              {formData.session_mode !== 'equity_swing' && (
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Squareoff</label>
                  <Input value={formData.squareoff_time} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData((p: any) => ({ ...p, squareoff_time: e.target.value }))} />
                </div>
              )}
            </div>
            <div className="space-y-3 rounded-lg border border-zinc-200 dark:border-zinc-700 p-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Primary Indicator</label>
                  <select
                    value={formData.primary_indicator}
                    onChange={e => {
                      const next = e.target.value;
                      setFormData((p: any) => ({
                        ...p,
                        primary_indicator: next,
                        primary_params: { ...(PARAM_DEFAULTS[next] || {}) },
                      }));
                    }}
                    className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm">
                    {PRIMARY_INDICATORS.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Confirm (optional)</label>
                  <select
                    value={formData.confirm_indicator}
                    onChange={e => {
                      const next = e.target.value;
                      setFormData((p: any) => ({
                        ...p,
                        confirm_indicator: next,
                        confirm_params: next ? { ...(PARAM_DEFAULTS[next] || {}) } : {},
                      }));
                    }}
                    className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm">
                    {CONFIRM_INDICATORS.map(i => <option key={i.value || 'none'} value={i.value}>{i.label}</option>)}
                  </select>
                </div>
              </div>
              <IndicatorParams
                indicator={formData.primary_indicator}
                params={formData.primary_params || {}}
                onChange={(next) => setFormData((p: any) => ({ ...p, primary_params: next }))}
              />
              {formData.confirm_indicator && (
                <div className="pt-2 border-t border-zinc-200 dark:border-zinc-700">
                  <p className="text-xs text-zinc-500 mb-2">Confirm params:</p>
                  <IndicatorParams
                    indicator={formData.confirm_indicator}
                    params={formData.confirm_params || {}}
                    onChange={(next) => setFormData((p: any) => ({ ...p, confirm_params: next }))}
                  />
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">SL Points</label>
                <Input type="number" value={formData.sl_points} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, sl_points: e.target.value }))} placeholder="optional" />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Target Points</label>
                <Input type="number" value={formData.target_points} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, target_points: e.target.value }))} placeholder="optional" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Trail Points</label>
                <Input type="number" step="0.5" value={formData.trail_points} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, trail_points: e.target.value }))} placeholder="optional, preferred" />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Trail %</label>
                <Input type="number" step="0.5" value={formData.trail_percent} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, trail_percent: e.target.value }))} placeholder="fallback" />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Arm at +Points</label>
                <Input type="number" step="0.5" value={formData.trail_arm_points} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, trail_arm_points: e.target.value }))} placeholder="0 = immediate" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Max Trades</label>
                <Input type="number" value={formData.max_trades} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, max_trades: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Cooldown (sec)</label>
                <Input type="number" value={formData.cooldown_seconds} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, cooldown_seconds: Number(e.target.value) }))} />
              </div>
            </div>
          </div>
        </DialogBody>
        <DialogActions>
          <Button plain onClick={closeDialog}>Cancel</Button>
          <Button onClick={onSubmit} disabled={submitDisabled}>
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : (isEditing ? 'Save' : 'Create')}
          </Button>
        </DialogActions>
      </Dialog>
      );
      })()}
    </div>
  );
}
