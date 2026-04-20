import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  Flame, Plus, Trash2, Loader2, Power, PowerOff, ChevronDown, ChevronUp,
  AlertTriangle, X, TrendingUp, TrendingDown, CircleDot, Square, Clock,
  Activity,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../components/catalyst/dialog';
import { Badge } from '../components/catalyst/badge';
import { Input } from '../components/catalyst/input';

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

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    underlying: 'NIFTY',
    expiry: '',
    lots: 1,
    indicator_timeframe: '1m',
    utbot_period: 10,
    utbot_sensitivity: 1.0,
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

  const toggleEnabled = async (id: number, enabled: boolean) => {
    try {
      await fetch(`/api/scalp/sessions/${id}`, {
        method: 'PATCH', headers, body: JSON.stringify({ enabled: !enabled }),
      });
      showAction(enabled ? 'Session disabled' : 'Session enabled');
      await fetchSessions();
    } catch { setError('Failed to toggle'); }
  };

  const deleteSession = async (id: number) => {
    if (!confirm('Delete this session?')) return;
    try {
      await fetch(`/api/scalp/sessions/${id}`, { method: 'DELETE', headers });
      showAction('Session deleted');
      if (expandedId === id) setExpandedId(null);
      await fetchSessions();
    } catch { setError('Failed to delete'); }
  };

  const manualExit = async (id: number) => {
    try {
      await fetch(`/api/scalp/sessions/${id}/manual-exit`, { method: 'POST', headers });
      showAction('Manual exit triggered');
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
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100">Scalp Sessions</h1>
              <p className="text-sm text-zinc-500">Stateful options scalping with mutual exclusion</p>
            </div>
          </div>
          <Button onClick={() => { setFormData({ name: '', underlying: 'NIFTY', expiry: expiries[0] || '', lots: 1, indicator_timeframe: '1m', utbot_period: 10, utbot_sensitivity: 1.0, sl_points: '', target_points: '', trail_percent: '', trail_points: '', trail_arm_points: '', squareoff_time: '15:15', max_trades: 20, cooldown_seconds: 60 }); setShowCreate(true); }}>
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
                      {!s.enabled && <Badge color="zinc">disabled</Badge>}
                    </div>
                    <div className="text-xs text-zinc-500 flex items-center gap-3 flex-wrap">
                      <span>{s.underlying} {s.expiry}</span>
                      <span>{s.lots} lot(s)</span>
                      <span>UT Bot {s.indicator_timeframe} p={s.utbot_period} s={s.utbot_sensitivity}</span>
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
                                <div key={log.id} className="flex items-center gap-3 text-xs py-1.5 border-b border-zinc-200/50 dark:border-zinc-700/30 last:border-0">
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
                                  <span className="ml-auto text-zinc-400">
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
                {log.option_type && log.strike != null && (
                  <span className="text-zinc-600 dark:text-zinc-400">
                    {log.option_type} {log.strike}
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

      {/* Create Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)}>
        <DialogTitle>Create Scalp Session</DialogTitle>
        <DialogBody>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Name</label>
              <Input value={formData.name} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, name: e.target.value }))} placeholder="e.g. NIFTY ATM Scalper" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Underlying</label>
                <select value={formData.underlying} onChange={e => setFormData(p => ({ ...p, underlying: e.target.value, expiry: '' }))}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm">
                  {['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'].map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Expiry</label>
                <select value={formData.expiry} onChange={e => setFormData(p => ({ ...p, expiry: e.target.value }))}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm">
                  {expiries.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Lots</label>
                <Input type="number" value={formData.lots} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, lots: Number(e.target.value) }))} min={1} />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Timeframe</label>
                <select value={formData.indicator_timeframe} onChange={e => setFormData(p => ({ ...p, indicator_timeframe: e.target.value }))}
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm">
                  {['1m', '3m', '5m', '15m'].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Squareoff</label>
                <Input value={formData.squareoff_time} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, squareoff_time: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">UT Bot Period</label>
                <Input type="number" value={formData.utbot_period} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, utbot_period: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">UT Bot Sensitivity</label>
                <Input type="number" step="0.1" value={formData.utbot_sensitivity} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData(p => ({ ...p, utbot_sensitivity: Number(e.target.value) }))} />
              </div>
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
          <Button plain onClick={() => setShowCreate(false)}>Cancel</Button>
          <Button onClick={handleCreate} disabled={creating || !formData.name || !formData.expiry}>
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}
