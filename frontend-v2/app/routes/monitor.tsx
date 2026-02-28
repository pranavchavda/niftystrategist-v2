import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  Shield, Plus, Zap, Clock, TrendingUp, TrendingDown,
  BarChart3, XCircle, Power, Trash2, History,
  AlertTriangle, ChevronRight, Activity, Target,
  Loader2, RefreshCw, Eye, ChevronDown, Search,
} from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../components/catalyst/dialog';
import { Button } from '../components/catalyst/button';
import { Badge } from '../components/catalyst/badge';
import { Switch } from '../components/catalyst/switch';
import { Input } from '../components/catalyst/input';

interface AuthContext {
  authToken: string;
  user?: any;
}

// ─── Types ───────────────────────────────────────────────────────────
interface MonitorRule {
  id: number;
  user_id: number;
  name: string;
  enabled: boolean;
  trigger_type: string;
  trigger_config: Record<string, any>;
  action_type: string;
  action_config: Record<string, any>;
  symbol: string | null;
  instrument_token: string | null;
  linked_trade_id: number | null;
  linked_order_id: string | null;
  fire_count: number;
  max_fires: number | null;
  expires_at: string | null;
  fired_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface MonitorLog {
  id: number;
  rule_id: number | null;
  user_id: number;
  trigger_snapshot: Record<string, any> | null;
  action_taken: string;
  action_result: Record<string, any> | null;
  created_at: string | null;
}

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

// ─── Helpers ─────────────────────────────────────────────────────────

const TRIGGER_TYPES = [
  { value: 'price', label: 'Price', icon: TrendingUp, desc: 'When price crosses a level' },
  { value: 'indicator', label: 'Indicator', icon: BarChart3, desc: 'When indicator hits threshold' },
  { value: 'time', label: 'Time', icon: Clock, desc: 'At a specific time' },
  { value: 'order_status', label: 'Order Status', icon: Activity, desc: 'When order status changes' },
];

const PRICE_CONDITIONS = [
  { value: 'gte', label: '>= (at or above)' },
  { value: 'lte', label: '<= (at or below)' },
  { value: 'gt', label: '> (above)' },
  { value: 'lt', label: '< (below)' },
  { value: 'crosses_above', label: 'Crosses above' },
  { value: 'crosses_below', label: 'Crosses below' },
];

const INDICATORS = [
  { value: 'SMA', label: 'SMA (Simple Moving Avg)' },
  { value: 'EMA', label: 'EMA (Exponential Moving Avg)' },
  { value: 'RSI', label: 'RSI (Relative Strength Index)' },
  { value: 'MACD', label: 'MACD' },
];

const TIMEFRAMES = [
  { value: '1m', label: '1 min' },
  { value: '5m', label: '5 min' },
  { value: '15m', label: '15 min' },
  { value: '30m', label: '30 min' },
  { value: '1h', label: '1 hour' },
];

const ACTION_TYPES = [
  { value: 'place_order', label: 'Place Order', icon: Zap },
  { value: 'cancel_order', label: 'Cancel Order', icon: XCircle },
  { value: 'cancel_rule', label: 'Disable Rule', icon: Power },
];

const selectClassName = "w-full rounded-lg bg-white dark:bg-zinc-900/50 border border-zinc-300 dark:border-zinc-700 text-sm text-zinc-800 dark:text-zinc-200 px-3 py-2 focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30";

function triggerSummary(rule: MonitorRule): string {
  const tc = rule.trigger_config;
  switch (rule.trigger_type) {
    case 'price': {
      const condMap: Record<string, string> = {
        gte: '>=', lte: '<=', gt: '>', lt: '<',
        crosses_above: 'crosses above', crosses_below: 'crosses below',
      };
      return `Price ${condMap[tc.condition] || tc.condition} ${tc.price}`;
    }
    case 'indicator':
      return `${tc.indicator}(${tc.params?.period || ''}) ${tc.condition} ${tc.threshold}`;
    case 'time':
      return `At ${tc.at} IST`;
    case 'order_status':
      return `Order ${tc.order_id?.slice(-8) || '?'} → ${tc.status}`;
    case 'compound':
      return `${(tc.conditions || []).length} conditions (${tc.operator || 'AND'})`;
    case 'trailing_stop':
      return `Trail ${tc.trail_percent}% from ${tc.highest_price || tc.initial_price}`;
    default:
      return rule.trigger_type;
  }
}

function actionSummary(rule: MonitorRule): string {
  const ac = rule.action_config;
  switch (rule.action_type) {
    case 'place_order':
      return `${ac.transaction_type} ${ac.quantity} ${ac.symbol || rule.symbol || '?'} @ ${ac.order_type}`;
    case 'cancel_order':
      return `Cancel order ${ac.order_id?.slice(-8) || '?'}`;
    case 'cancel_rule':
      return `Disable rule #${ac.rule_id}`;
    default:
      return rule.action_type;
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  // DB stores naive UTC timestamps (no Z suffix), so append Z to ensure
  // JS interprets them as UTC, then display in IST.
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
    hour12: true,
  });
}

function triggerTypeColor(type: string): string {
  switch (type) {
    case 'price': return 'blue';
    case 'indicator': return 'purple';
    case 'time': return 'amber';
    case 'order_status': return 'cyan';
    case 'compound': return 'indigo';
    default: return 'zinc';
  }
}

function actionTypeColor(type: string): string {
  switch (type) {
    case 'place_order': return 'emerald';
    case 'cancel_order': return 'red';
    case 'cancel_rule': return 'orange';
    default: return 'zinc';
  }
}

// ─── Symbol Search Component ─────────────────────────────────────────

interface SymbolResult {
  symbol: string;
  name: string;
  nifty50: boolean;
  instrument_key: string | null;
}

function SymbolSearch({
  authToken,
  value,
  onSelect,
  placeholder = 'Search symbol (e.g. RELIANCE)',
  label = 'Symbol',
}: {
  authToken: string;
  value: string;
  onSelect: (symbol: string, instrumentKey: string, displayName: string) => void;
  placeholder?: string;
  label?: string;
}) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<SymbolResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Sync external value changes
  useEffect(() => { setQuery(value); }, [value]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const searchSymbols = useCallback(async (term: string) => {
    if (term.length < 1) { setResults([]); return; }
    setSearching(true);
    try {
      const res = await fetch(`/api/monitor/symbols?q=${encodeURIComponent(term)}&limit=8`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setIsOpen(true);
      }
    } catch { /* ignore */ }
    finally { setSearching(false); }
  }, [authToken]);

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchSymbols(val), 250);
  };

  const handleSelect = (r: SymbolResult) => {
    setQuery(r.symbol);
    setIsOpen(false);
    onSelect(r.symbol, r.instrument_key || '', r.name);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">{label}</label>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400 pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={handleInput}
          onFocus={() => { if (results.length > 0) setIsOpen(true); }}
          placeholder={placeholder}
          className="w-full rounded-lg bg-white dark:bg-zinc-900/50 border border-zinc-300 dark:border-zinc-700 text-sm text-zinc-800 dark:text-zinc-200 pl-9 pr-8 py-2 focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 focus:outline-none"
        />
        {searching && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400 animate-spin" />
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-lg shadow-lg max-h-56 overflow-y-auto">
          {results.map(r => (
            <button
              key={r.symbol}
              onClick={() => handleSelect(r)}
              className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors first:rounded-t-lg last:rounded-b-lg"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{r.symbol}</span>
                  {r.nifty50 && (
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400">N50</span>
                  )}
                </div>
                <span className="text-xs text-zinc-500 truncate block">{r.name}</span>
              </div>
              <span className="text-[10px] text-zinc-400 font-mono flex-shrink-0 hidden sm:block">
                {r.instrument_key?.split('|')[0]}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

export default function MonitorRoute() {
  const { authToken } = useOutletContext<AuthContext>();

  // Tab state
  const [activeTab, setActiveTab] = useState<'rules' | 'oco' | 'logs'>('rules');

  // Data state
  const [rules, setRules] = useState<MonitorRule[]>([]);
  const [logs, setLogs] = useState<MonitorLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showLogDetail, setShowLogDetail] = useState(false);
  const [selectedLog, setSelectedLog] = useState<MonitorLog | null>(null);

  // Create form state
  const [createStep, setCreateStep] = useState(0); // 0: trigger type, 1: trigger config, 2: action type, 3: action config, 4: limits
  const [formData, setFormData] = useState({
    name: '',
    trigger_type: 'price',
    trigger_config: { condition: 'gte', price: 0, reference: 'ltp' } as Record<string, any>,
    action_type: 'place_order',
    action_config: { symbol: '', transaction_type: 'SELL', quantity: 1, order_type: 'MARKET', product: 'D' } as Record<string, any>,
    symbol: '',
    instrument_token: '',
    max_fires: 1 as number | null,
    expires_at: '' as string,
  });
  const [saving, setSaving] = useState(false);

  // OCO form state
  const [ocoForm, setOcoForm] = useState({
    symbol: '',
    qty: 1,
    product: 'I',
    side: 'SELL' as 'SELL' | 'BUY',  // SELL = exit long, BUY = exit short
    sl: 0,
    target: 0,
    expires_at: '',
  });
  const [ocoSaving, setOcoSaving] = useState(false);

  // ─── Data Fetching ─────────────────────────────────────────────────

  const fetchRules = useCallback(async () => {
    try {
      const res = await fetch('/api/monitor/rules', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to fetch rules');
      const data = await res.json();
      setRules(data.rules || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rules');
    }
  }, [authToken]);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/monitor/logs?limit=50', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to fetch logs');
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
    }
  }, [authToken]);

  useEffect(() => {
    async function loadAll() {
      setLoading(true);
      await Promise.all([fetchRules(), fetchLogs()]);
      setLoading(false);
    }
    loadAll();
  }, [fetchRules, fetchLogs]);

  // ─── Rule Actions ──────────────────────────────────────────────────

  const toggleRule = async (rule: MonitorRule) => {
    try {
      const res = await fetch(`/api/monitor/rules/${rule.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      if (!res.ok) throw new Error('Failed to toggle rule');
      setRules(prev =>
        prev.map(r => r.id === rule.id ? { ...r, enabled: !r.enabled } : r)
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle rule');
    }
  };

  const deleteRule = async (ruleId: number) => {
    try {
      const res = await fetch(`/api/monitor/rules/${ruleId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to delete rule');
      setRules(prev => prev.filter(r => r.id !== ruleId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
    }
  };

  // ─── Create Rule ───────────────────────────────────────────────────

  const resetCreateForm = () => {
    setCreateStep(0);
    setFormData({
      name: '',
      trigger_type: 'price',
      trigger_config: { condition: 'gte', price: 0, reference: 'ltp' },
      action_type: 'place_order',
      action_config: { symbol: '', transaction_type: 'SELL', quantity: 1, order_type: 'MARKET', product: 'D' },
      symbol: '',
      instrument_token: '',
      max_fires: 1,
      expires_at: '',
    });
  };

  const openCreateModal = () => {
    resetCreateForm();
    setShowCreateModal(true);
  };

  const handleCreateRule = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = {
        name: formData.name || `${formData.trigger_type} rule on ${formData.symbol || 'unknown'}`,
        trigger_type: formData.trigger_type,
        trigger_config: formData.trigger_config,
        action_type: formData.action_type,
        action_config: formData.action_config,
        symbol: formData.symbol || null,
        instrument_token: formData.instrument_token || null,
        max_fires: formData.max_fires,
      };
      if (formData.expires_at) {
        payload.expires_at = new Date(formData.expires_at).toISOString();
      }

      const res = await fetch('/api/monitor/rules', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create rule');
      }
      const newRule = await res.json();
      setRules(prev => [newRule, ...prev]);
      setShowCreateModal(false);
      resetCreateForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule');
    } finally {
      setSaving(false);
    }
  };

  // ─── Create OCO ────────────────────────────────────────────────────

  const handleCreateOCO = async () => {
    setOcoSaving(true);
    setError(null);
    try {
      const payload: any = {
        symbol: ocoForm.symbol,
        qty: ocoForm.qty,
        product: ocoForm.product,
        side: ocoForm.side,
        sl: ocoForm.sl,
        target: ocoForm.target,
      };
      if (ocoForm.expires_at) {
        payload.expires_at = new Date(ocoForm.expires_at).toISOString();
      }

      const res = await fetch('/api/monitor/oco', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create OCO pair');
      }
      const data = await res.json();
      setRules(prev => [data.sl_rule, data.target_rule, ...prev]);
      setOcoForm({ symbol: '', qty: 1, product: 'I', side: 'SELL', sl: 0, target: 0, expires_at: '' });
      setActiveTab('rules');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create OCO pair');
    } finally {
      setOcoSaving(false);
    }
  };

  // ─── Trigger Config Form ──────────────────────────────────────────

  const updateTriggerType = (type: string) => {
    const defaults: Record<string, Record<string, any>> = {
      price: { condition: 'gte', price: 0, reference: 'ltp' },
      indicator: { indicator: 'RSI', timeframe: '15m', params: { period: 14 }, condition: 'gte', threshold: 70 },
      time: { time: '15:15', timezone: 'Asia/Kolkata' },
      order_status: { order_id: '', expected_status: 'complete' },
    };
    setFormData(prev => ({
      ...prev,
      trigger_type: type,
      trigger_config: defaults[type] || {},
    }));
  };

  // ─── Render ────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
          <span className="text-sm text-zinc-500">Loading monitor rules...</span>
        </div>
      </div>
    );
  }

  const enabledCount = rules.filter(r => r.enabled).length;
  const totalFires = rules.reduce((sum, r) => sum + r.fire_count, 0);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">

        {/* ── Header ──────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-amber-500/20">
                <Shield className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100">Trade Monitor</h1>
                <p className="text-sm text-zinc-500">IFTTT-style rules that watch markets and act for you</p>
              </div>
            </div>
            <Button
              onClick={openCreateModal}
              className="bg-amber-500 hover:bg-amber-600 text-white shadow-lg shadow-amber-500/20 font-medium"
            >
              <Plus data-slot="icon" className="w-4 h-4" />
              New Rule
            </Button>
          </div>

          {/* Stats strip */}
          <div className="flex items-center gap-6 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-zinc-600 dark:text-zinc-400">{enabledCount} active</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-300 dark:text-zinc-600">|</span>
              <span className="text-zinc-500">{rules.length} total rules</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-300 dark:text-zinc-600">|</span>
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-zinc-500">{totalFires} fires</span>
            </div>
            <button
              onClick={() => { fetchRules(); fetchLogs(); }}
              className="ml-auto p-1.5 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-300 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Error banner ────────────────────────────────────── */}
        {error && (
          <div className="mb-6 p-3 bg-red-50 dark:bg-red-900/30 border border-red-300 dark:border-red-800/50 rounded-lg flex items-center gap-3 text-sm text-red-700 dark:text-red-300">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-200">
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ── Tab bar ─────────────────────────────────────────── */}
        <div className="flex items-center gap-1 mb-6 border-b border-zinc-200 dark:border-zinc-800">
          {[
            { key: 'rules' as const, label: 'Rules', icon: Shield, count: rules.length },
            { key: 'oco' as const, label: 'OCO Builder', icon: Target },
            { key: 'logs' as const, label: 'Fire Log', icon: History, count: logs.length },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                activeTab === tab.key
                  ? 'border-amber-500 text-amber-600 dark:text-amber-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:border-zinc-300 dark:hover:border-zinc-700'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
              {tab.count !== undefined && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                  activeTab === tab.key ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400' : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Tab Content ─────────────────────────────────────── */}

        {activeTab === 'rules' && (
          <RulesTab
            rules={rules}
            onToggle={toggleRule}
            onDelete={deleteRule}
            onCreate={openCreateModal}
          />
        )}

        {activeTab === 'oco' && (
          <OCOTab
            form={ocoForm}
            onChange={setOcoForm}
            onSubmit={handleCreateOCO}
            saving={ocoSaving}
            authToken={authToken}
          />
        )}

        {activeTab === 'logs' && (
          <LogsTab
            logs={logs}
            rules={rules}
            onSelectLog={(log) => { setSelectedLog(log); setShowLogDetail(true); }}
          />
        )}

      </div>

      {/* ── Create Rule Modal ─────────────────────────────────── */}
      <Dialog open={showCreateModal} onClose={() => setShowCreateModal(false)} size="xl">
        <DialogTitle>
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/20">
              <Plus className="h-4 w-4 text-amber-500 dark:text-amber-400" />
            </div>
            Create Monitor Rule
          </div>
        </DialogTitle>
        <DialogBody className="mt-4">
          <CreateRuleWizard
            step={createStep}
            setStep={setCreateStep}
            formData={formData}
            setFormData={setFormData}
            updateTriggerType={updateTriggerType}
            authToken={authToken}
          />
        </DialogBody>
        <DialogActions>
          {createStep > 0 && (
            <Button plain onClick={() => setCreateStep(s => s - 1)}>
              Back
            </Button>
          )}
          <Button plain onClick={() => setShowCreateModal(false)}>
            Cancel
          </Button>
          {createStep < 4 ? (
            <Button
              className="bg-amber-500 hover:bg-amber-600 text-white"
              onClick={() => setCreateStep(s => s + 1)}
            >
              Next
              <ChevronRight data-slot="icon" className="w-4 h-4" />
            </Button>
          ) : (
            <Button
              className="bg-amber-500 hover:bg-amber-600 text-white"
              onClick={handleCreateRule}
              disabled={saving}
            >
              {saving ? (
                <>
                  <Loader2 data-slot="icon" className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Zap data-slot="icon" className="w-4 h-4" />
                  Create Rule
                </>
              )}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* ── Log Detail Modal ──────────────────────────────────── */}
      <Dialog open={showLogDetail} onClose={() => setShowLogDetail(false)} size="md">
        <DialogTitle>Fire Detail</DialogTitle>
        <DialogBody className="mt-4">
          {selectedLog && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-zinc-500 block mb-1">Rule ID</span>
                  <span className="text-zinc-800 dark:text-zinc-200 font-mono">#{selectedLog.rule_id || '—'}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block mb-1">Fired At</span>
                  <span className="text-zinc-800 dark:text-zinc-200">{formatDate(selectedLog.created_at)}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block mb-1">Action</span>
                  <Badge color={actionTypeColor(selectedLog.action_taken)}>
                    {selectedLog.action_taken}
                  </Badge>
                </div>
                <div>
                  <span className="text-zinc-500 block mb-1">Success</span>
                  <span className={selectedLog.action_result?.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                    {selectedLog.action_result?.success ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>

              {selectedLog.trigger_snapshot && (
                <div>
                  <span className="text-zinc-500 block mb-1">Trigger Snapshot</span>
                  <pre className="bg-zinc-100 dark:bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-700 dark:text-zinc-300 overflow-x-auto font-mono">
                    {JSON.stringify(selectedLog.trigger_snapshot, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.action_result && (
                <div>
                  <span className="text-zinc-500 block mb-1">Action Result</span>
                  <pre className="bg-zinc-100 dark:bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-700 dark:text-zinc-300 overflow-x-auto font-mono">
                    {JSON.stringify(selectedLog.action_result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </DialogBody>
        <DialogActions>
          <Button plain onClick={() => setShowLogDetail(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// ─── Rules Tab ─────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════

function RulesTab({
  rules, onToggle, onDelete, onCreate,
}: {
  rules: MonitorRule[];
  onToggle: (r: MonitorRule) => void;
  onDelete: (id: number) => void;
  onCreate: () => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  if (rules.length === 0) {
    return (
      <div className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50 p-12 text-center">
        <div className="flex justify-center mb-4">
          <div className="h-16 w-16 rounded-2xl bg-zinc-200 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 flex items-center justify-center">
            <Shield className="w-8 h-8 text-zinc-400 dark:text-zinc-600" />
          </div>
        </div>
        <h3 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-2">No monitor rules yet</h3>
        <p className="text-sm text-zinc-500 mb-6 max-w-md mx-auto">
          Create rules to automatically watch price levels, indicators, or order statuses and take action when conditions are met.
        </p>
        <Button
          onClick={onCreate}
          className="bg-amber-500 hover:bg-amber-600 text-white shadow-lg shadow-amber-500/20 font-medium"
        >
          <Plus data-slot="icon" className="w-4 h-4" />
          Create Your First Rule
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {rules.map(rule => {
        const isExpanded = expandedId === rule.id;
        const isDeleting = confirmDeleteId === rule.id;

        return (
          <div
            key={rule.id}
            className={`bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border transition-all duration-200 ${
              rule.enabled
                ? 'border-zinc-300 dark:border-zinc-700/50 hover:border-zinc-400 dark:hover:border-zinc-600/50'
                : 'border-zinc-200 dark:border-zinc-800 opacity-60'
            }`}
          >
            {/* Main row */}
            <div className="flex items-center gap-4 px-5 py-4">
              {/* Toggle */}
              <Switch
                checked={rule.enabled}
                onChange={() => onToggle(rule)}
                color={rule.enabled ? 'amber' : 'zinc'}
              />

              {/* Info */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : rule.id)}
                className="flex-1 min-w-0 text-left"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 truncate">
                    {rule.name}
                  </span>
                  {rule.symbol && (
                    <span className="text-xs font-mono text-zinc-500 bg-zinc-200 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
                      {rule.symbol}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge color={triggerTypeColor(rule.trigger_type)}>
                    {rule.trigger_type}
                  </Badge>
                  <span className="text-xs text-zinc-500">{triggerSummary(rule)}</span>
                  <ChevronRight className="w-3 h-3 text-zinc-400 dark:text-zinc-600" />
                  <Badge color={actionTypeColor(rule.action_type)}>
                    {rule.action_type.replace('_', ' ')}
                  </Badge>
                  <span className="text-xs text-zinc-500">{actionSummary(rule)}</span>
                </div>
              </button>

              {/* Fire count + expand */}
              <div className="flex items-center gap-3 flex-shrink-0">
                {rule.fire_count > 0 && (
                  <div className="text-xs text-zinc-500 flex items-center gap-1">
                    <Zap className="w-3 h-3 text-amber-500" />
                    {rule.fire_count}{rule.max_fires ? `/${rule.max_fires}` : ''}
                  </div>
                )}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : rule.id)}
                  className="p-1.5 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-300 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700/50 transition-colors"
                >
                  <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                </button>
              </div>
            </div>

            {/* Expanded details */}
            {isExpanded && (
              <div className="px-5 pb-4 pt-0 border-t border-zinc-300 dark:border-zinc-700/50">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-3 text-sm">
                  <div>
                    <span className="text-zinc-500 block text-xs mb-1">Created</span>
                    <span className="text-zinc-700 dark:text-zinc-300">{formatDate(rule.created_at)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-xs mb-1">Last Fired</span>
                    <span className="text-zinc-700 dark:text-zinc-300">{formatDate(rule.fired_at)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-xs mb-1">Max Fires</span>
                    <span className="text-zinc-700 dark:text-zinc-300">{rule.max_fires ?? 'Unlimited'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-xs mb-1">Expires</span>
                    <span className="text-zinc-700 dark:text-zinc-300">{rule.expires_at ? formatDate(rule.expires_at) : 'Never'}</span>
                  </div>
                </div>

                {/* Trigger + Action configs */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                  <div>
                    <span className="text-zinc-500 block text-xs mb-1">Trigger Config</span>
                    <pre className="bg-zinc-50 dark:bg-zinc-900/50 rounded-lg p-2 text-xs text-zinc-600 dark:text-zinc-400 overflow-x-auto font-mono">
                      {JSON.stringify(rule.trigger_config, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-xs mb-1">Action Config</span>
                    <pre className="bg-zinc-50 dark:bg-zinc-900/50 rounded-lg p-2 text-xs text-zinc-600 dark:text-zinc-400 overflow-x-auto font-mono">
                      {JSON.stringify(rule.action_config, null, 2)}
                    </pre>
                  </div>
                </div>

                {/* Delete button */}
                <div className="flex justify-end">
                  {isDeleting ? (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-red-600 dark:text-red-400">Delete this rule?</span>
                      <Button
                        className="bg-red-600 hover:bg-red-700 text-white text-xs"
                        onClick={() => { onDelete(rule.id); setConfirmDeleteId(null); }}
                      >
                        Yes, delete
                      </Button>
                      <Button plain onClick={() => setConfirmDeleteId(null)} className="text-xs">
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDeleteId(rule.id)}
                      className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-red-600 dark:hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// ─── OCO Builder Tab ──────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════

function OCOTab({
  form, onChange, onSubmit, saving, authToken,
}: {
  form: { symbol: string; qty: number; product: string; side: 'SELL' | 'BUY'; sl: number; target: number; expires_at: string };
  onChange: (f: any) => void;
  onSubmit: () => void;
  saving: boolean;
  authToken: string;
}) {
  const update = (key: string, value: any) => onChange({ ...form, [key]: value });

  const isLong = form.side === 'SELL'; // SELL exits a LONG position
  // Validation: for longs target > sl, for shorts sl > target
  const pricesValid = form.sl > 0 && form.target > 0 && (isLong ? form.target > form.sl : form.sl > form.target);
  const isValid = form.symbol.trim() && form.qty > 0 && pricesValid;

  return (
    <div className="max-w-2xl">
      <div className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 shadow-lg shadow-teal-500/20">
            <Target className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">OCO Pair Builder</h2>
            <p className="text-sm text-zinc-500">Create linked Stop-Loss + Target rules (one cancels the other)</p>
          </div>
        </div>

        <div className="space-y-5">
          {/* Position direction toggle */}
          <div>
            <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-2">Position Type</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onChange({ ...form, side: 'SELL', sl: 0, target: 0 })}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border transition-all ${
                  isLong
                    ? 'bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-700 text-green-700 dark:text-green-300 shadow-sm'
                    : 'bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400 hover:border-zinc-300 dark:hover:border-zinc-600'
                }`}
              >
                <TrendingUp className="w-4 h-4" />
                Long Position
              </button>
              <button
                type="button"
                onClick={() => onChange({ ...form, side: 'BUY', sl: 0, target: 0 })}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border transition-all ${
                  !isLong
                    ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300 shadow-sm'
                    : 'bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400 hover:border-zinc-300 dark:hover:border-zinc-600'
                }`}
              >
                <TrendingDown className="w-4 h-4" />
                Short Position
              </button>
            </div>
            <p className="text-xs text-zinc-500 mt-1.5">
              {isLong
                ? 'Exit side: SELL — SL below entry, target above'
                : 'Exit side: BUY (cover) — SL above entry, target below'}
            </p>
          </div>

          {/* Symbol + Qty row */}
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-1">
              <SymbolSearch
                authToken={authToken}
                value={form.symbol}
                onSelect={(symbol, instrumentKey) => onChange({ ...form, symbol })}
                placeholder="Search symbol..."
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Quantity</label>
              <Input
                type="number"
                min={1}
                value={form.qty}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('qty', parseInt(e.target.value) || 1)}
                className="text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Product</label>
              <select
                value={form.product}
                onChange={e => update('product', e.target.value)}
                className={selectClassName}
              >
                <option value="I">Intraday</option>
                <option value="D">Delivery</option>
              </select>
            </div>
          </div>

          {/* SL + Target */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-red-600 dark:text-red-400 mb-1.5 flex items-center gap-1.5">
                {isLong ? <TrendingDown className="w-3.5 h-3.5" /> : <TrendingUp className="w-3.5 h-3.5" />}
                Stop-Loss Price
              </label>
              <Input
                type="number"
                step="0.05"
                min={0}
                placeholder="0.00"
                value={form.sl || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('sl', parseFloat(e.target.value) || 0)}
                className="text-sm"
              />
              <p className="text-xs text-zinc-500 mt-1">
                {isLong
                  ? 'Exits (SELL) when price drops to this level'
                  : 'Exits (BUY) when price rises to this level'}
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-green-600 dark:text-green-400 mb-1.5 flex items-center gap-1.5">
                {isLong ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                Target Price
              </label>
              <Input
                type="number"
                step="0.05"
                min={0}
                placeholder="0.00"
                value={form.target || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('target', parseFloat(e.target.value) || 0)}
                className="text-sm"
              />
              <p className="text-xs text-zinc-500 mt-1">
                {isLong
                  ? 'Exits (SELL) when price rises to this level'
                  : 'Exits (BUY) when price drops to this level'}
              </p>
            </div>
          </div>

          {/* Visual indicator */}
          {form.sl > 0 && form.target > 0 && (
            <div className="bg-zinc-50 dark:bg-zinc-900/50 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700/30">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-red-600 dark:text-red-400 font-medium">SL: {form.sl}</span>
                <span className="text-zinc-500">Risk / Reward</span>
                <span className="text-green-600 dark:text-green-400 font-medium">Target: {form.target}</span>
              </div>
              <div className="relative h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-red-500 to-zinc-400 dark:to-zinc-600 rounded-full" style={{ width: '50%' }} />
                <div className="absolute inset-y-0 right-0 bg-gradient-to-l from-green-500 to-zinc-400 dark:to-zinc-600 rounded-full" style={{ width: '50%' }} />
              </div>
              {pricesValid && (
                <p className="text-center text-xs text-zinc-500 mt-2">
                  R:R = 1:{(Math.abs(form.target - form.sl) / Math.abs(isLong ? form.sl : form.target) * 100).toFixed(1)}%
                </p>
              )}
            </div>
          )}

          {/* Expires at */}
          <div>
            <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Expires (optional)</label>
            <Input
              type="datetime-local"
              value={form.expires_at}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('expires_at', e.target.value)}
              className="text-sm max-w-xs"
            />
          </div>

          {/* Validation */}
          {form.sl > 0 && form.target > 0 && !pricesValid && (
            <div className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-800/30 rounded-lg px-3 py-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {isLong
                ? 'Target price must be above stop-loss price for long positions'
                : 'Stop-loss price must be above target price for short positions'}
            </div>
          )}

          {/* Submit */}
          <Button
            onClick={onSubmit}
            disabled={saving || !isValid}
            className="w-full bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-600 hover:to-emerald-700 text-white shadow-lg shadow-teal-500/20 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <Loader2 data-slot="icon" className="w-4 h-4 animate-spin" />
                Creating OCO pair...
              </>
            ) : (
              <>
                <Target data-slot="icon" className="w-4 h-4" />
                Create OCO Pair ({isLong ? 'Long' : 'Short'} Exit)
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// ─── Logs Tab ──────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════

function LogsTab({
  logs, rules, onSelectLog,
}: {
  logs: MonitorLog[];
  rules: MonitorRule[];
  onSelectLog: (log: MonitorLog) => void;
}) {
  const ruleMap = new Map(rules.map(r => [r.id, r]));

  if (logs.length === 0) {
    return (
      <div className="bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-300 dark:border-zinc-700/50 p-12 text-center">
        <History className="w-8 h-8 text-zinc-400 dark:text-zinc-600 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-zinc-600 dark:text-zinc-400 mb-2">No fires yet</h3>
        <p className="text-sm text-zinc-500">Rule firings will appear here as they happen</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {logs.map(log => {
        const rule = log.rule_id ? ruleMap.get(log.rule_id) : null;
        const success = log.action_result?.success;

        return (
          <button
            key={log.id}
            onClick={() => onSelectLog(log)}
            className="w-full flex items-center gap-4 px-4 py-3 bg-zinc-100 dark:bg-zinc-800/50 rounded-xl border border-zinc-200 dark:border-zinc-700/30 hover:border-zinc-400 dark:hover:border-zinc-600/50 transition-colors text-left"
          >
            {/* Status dot */}
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
              success === true ? 'bg-green-500' :
              success === false ? 'bg-red-500' :
              'bg-zinc-500'
            }`} />

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300 truncate">
                  {rule?.name || `Rule #${log.rule_id || '?'}`}
                </span>
                <Badge color={actionTypeColor(log.action_taken)}>
                  {log.action_taken.replace('_', ' ')}
                </Badge>
              </div>
              <span className="text-xs text-zinc-500">
                {formatDate(log.created_at)}
              </span>
            </div>

            {/* Result snippet */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {log.action_result?.order_id && (
                <span className="text-xs text-zinc-500 font-mono">
                  #{log.action_result.order_id.slice(-8)}
                </span>
              )}
              <Eye className="w-4 h-4 text-zinc-400 dark:text-zinc-600" />
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// ─── Create Rule Wizard ────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════

function CreateRuleWizard({
  step, setStep, formData, setFormData, updateTriggerType, authToken,
}: {
  step: number;
  setStep: (n: number) => void;
  formData: any;
  setFormData: (f: any) => void;
  updateTriggerType: (t: string) => void;
  authToken: string;
}) {
  const update = (key: string, value: any) => setFormData((prev: any) => ({ ...prev, [key]: value }));
  const updateTC = (key: string, value: any) =>
    setFormData((prev: any) => ({ ...prev, trigger_config: { ...prev.trigger_config, [key]: value } }));
  const updateAC = (key: string, value: any) =>
    setFormData((prev: any) => ({ ...prev, action_config: { ...prev.action_config, [key]: value } }));

  // Step indicators
  const steps = ['Trigger', 'Configure', 'Action', 'Configure', 'Limits'];

  return (
    <div>
      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-6">
        {steps.map((label, i) => (
          <React.Fragment key={i}>
            <button
              onClick={() => setStep(i)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                i === step
                  ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400 ring-1 ring-amber-500/30'
                  : i < step
                    ? 'bg-zinc-300 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300'
                    : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-600'
              }`}
            >
              <span className="w-4 h-4 flex items-center justify-center rounded-full bg-current/20 text-[10px]">
                {i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </button>
            {i < steps.length - 1 && (
              <ChevronRight className="w-3 h-3 text-zinc-400 dark:text-zinc-700 flex-shrink-0" />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Step 0: Choose trigger type */}
      {step === 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">When this happens...</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {TRIGGER_TYPES.map(tt => (
              <button
                key={tt.value}
                onClick={() => { updateTriggerType(tt.value); }}
                className={`flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${
                  formData.trigger_type === tt.value
                    ? 'border-amber-500/50 bg-amber-500/10 ring-1 ring-amber-500/20'
                    : 'border-zinc-300 dark:border-zinc-700/50 bg-zinc-100 dark:bg-zinc-800/50 hover:border-zinc-400 dark:hover:border-zinc-600/50'
                }`}
              >
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                  formData.trigger_type === tt.value ? 'bg-amber-500/20 text-amber-500 dark:text-amber-400' : 'bg-zinc-200 dark:bg-zinc-700/50 text-zinc-500 dark:text-zinc-400'
                }`}>
                  <tt.icon className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200 block">{tt.label}</span>
                  <span className="text-xs text-zinc-500">{tt.desc}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 1: Configure trigger */}
      {step === 1 && (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">
            Configure {formData.trigger_type} trigger
          </h3>

          {/* Symbol search (shared across price/indicator) */}
          {(formData.trigger_type === 'price' || formData.trigger_type === 'indicator') && (
            <SymbolSearch
              authToken={authToken}
              value={formData.symbol}
              onSelect={(symbol, instrumentKey) => {
                setFormData((prev: any) => ({
                  ...prev,
                  symbol,
                  instrument_token: instrumentKey,
                  action_config: { ...prev.action_config, symbol },
                }));
              }}
            />
          )}

          {formData.trigger_type === 'price' && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Condition</label>
                  <select
                    value={formData.trigger_config.condition}
                    onChange={e => updateTC('condition', e.target.value)}
                    className={selectClassName}
                  >
                    {PRICE_CONDITIONS.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Price</label>
                  <Input
                    type="number"
                    step="0.05"
                    placeholder="0.00"
                    value={formData.trigger_config.price || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateTC('price', parseFloat(e.target.value) || 0)}
                    className="text-sm"
                  />
                </div>
              </div>
            </>
          )}

          {formData.trigger_type === 'indicator' && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Indicator</label>
                  <select
                    value={formData.trigger_config.indicator}
                    onChange={e => updateTC('indicator', e.target.value)}
                    className={selectClassName}
                  >
                    {INDICATORS.map(i => (
                      <option key={i.value} value={i.value}>{i.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Timeframe</label>
                  <select
                    value={formData.trigger_config.timeframe}
                    onChange={e => updateTC('timeframe', e.target.value)}
                    className={selectClassName}
                  >
                    {TIMEFRAMES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Period</label>
                  <Input
                    type="number"
                    min={1}
                    value={formData.trigger_config.params?.period || 14}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateTC('params', { ...formData.trigger_config.params, period: parseInt(e.target.value) || 14 })}
                    className="text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Condition</label>
                  <select
                    value={formData.trigger_config.condition}
                    onChange={e => updateTC('condition', e.target.value)}
                    className={selectClassName}
                  >
                    {PRICE_CONDITIONS.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Threshold</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={formData.trigger_config.threshold || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateTC('threshold', parseFloat(e.target.value) || 0)}
                    className="text-sm"
                  />
                </div>
              </div>
            </>
          )}

          {formData.trigger_type === 'time' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Time (IST)</label>
                <Input
                  type="time"
                  value={formData.trigger_config.time || '15:15'}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateTC('time', e.target.value)}
                  className="text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Timezone</label>
                <Input
                  type="text"
                  value={formData.trigger_config.timezone || 'Asia/Kolkata'}
                  readOnly
                  className="text-sm text-zinc-500"
                />
              </div>
            </div>
          )}

          {formData.trigger_type === 'order_status' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Order ID</label>
                <Input
                  type="text"
                  placeholder="e.g. 240218000012345"
                  value={formData.trigger_config.order_id || ''}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateTC('order_id', e.target.value)}
                  className="text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Expected Status</label>
                <select
                  value={formData.trigger_config.expected_status || 'complete'}
                  onChange={e => updateTC('expected_status', e.target.value)}
                  className={selectClassName}
                >
                  <option value="complete">Complete (filled)</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Choose action type */}
      {step === 2 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">...then do this</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {ACTION_TYPES.map(at => (
              <button
                key={at.value}
                onClick={() => {
                  const defaults: Record<string, Record<string, any>> = {
                    place_order: { symbol: formData.symbol || '', transaction_type: 'SELL', quantity: 1, order_type: 'MARKET', product: 'D' },
                    cancel_order: { order_id: '' },
                    cancel_rule: { rule_id: 0 },
                  };
                  setFormData((prev: any) => ({
                    ...prev,
                    action_type: at.value,
                    action_config: defaults[at.value] || {},
                  }));
                }}
                className={`flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${
                  formData.action_type === at.value
                    ? 'border-amber-500/50 bg-amber-500/10 ring-1 ring-amber-500/20'
                    : 'border-zinc-300 dark:border-zinc-700/50 bg-zinc-100 dark:bg-zinc-800/50 hover:border-zinc-400 dark:hover:border-zinc-600/50'
                }`}
              >
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                  formData.action_type === at.value ? 'bg-amber-500/20 text-amber-500 dark:text-amber-400' : 'bg-zinc-200 dark:bg-zinc-700/50 text-zinc-500 dark:text-zinc-400'
                }`}>
                  <at.icon className="w-5 h-5" />
                </div>
                <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{at.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Configure action */}
      {step === 3 && (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">
            Configure {formData.action_type.replace('_', ' ')} action
          </h3>

          {formData.action_type === 'place_order' && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <SymbolSearch
                  authToken={authToken}
                  value={formData.action_config.symbol ? formData.symbol || '' : ''}
                  label="Symbol"
                  onSelect={(symbol, instrumentKey) => {
                    updateAC('symbol', symbol);
                    update('symbol', symbol);
                  }}
                />
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Side</label>
                  <div className="grid grid-cols-2 gap-2">
                    {['BUY', 'SELL'].map(side => (
                      <button
                        key={side}
                        onClick={() => updateAC('transaction_type', side)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                          formData.action_config.transaction_type === side
                            ? side === 'BUY'
                              ? 'bg-green-500/20 text-green-600 dark:text-green-400 ring-1 ring-green-500/30'
                              : 'bg-red-500/20 text-red-600 dark:text-red-400 ring-1 ring-red-500/30'
                            : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
                        }`}
                      >
                        {side}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Quantity</label>
                  <Input
                    type="number"
                    min={1}
                    value={formData.action_config.quantity}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAC('quantity', parseInt(e.target.value) || 1)}
                    className="text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Order Type</label>
                  <select
                    value={formData.action_config.order_type}
                    onChange={e => updateAC('order_type', e.target.value)}
                    className={selectClassName}
                  >
                    <option value="MARKET">Market</option>
                    <option value="LIMIT">Limit</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Product</label>
                  <select
                    value={formData.action_config.product}
                    onChange={e => updateAC('product', e.target.value)}
                    className={selectClassName}
                  >
                    <option value="D">Delivery</option>
                    <option value="I">Intraday</option>
                  </select>
                </div>
              </div>

              {formData.action_config.order_type === 'LIMIT' && (
                <div className="max-w-xs">
                  <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Limit Price</label>
                  <Input
                    type="number"
                    step="0.05"
                    placeholder="0.00"
                    value={formData.action_config.price || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAC('price', parseFloat(e.target.value) || 0)}
                    className="text-sm"
                  />
                </div>
              )}
            </>
          )}

          {formData.action_type === 'cancel_order' && (
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Order ID to cancel</label>
              <Input
                type="text"
                placeholder="e.g. 240218000012345"
                value={formData.action_config.order_id || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAC('order_id', e.target.value)}
                className="text-sm font-mono"
              />
            </div>
          )}

          {formData.action_type === 'cancel_rule' && (
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Rule ID to disable</label>
              <Input
                type="number"
                min={1}
                placeholder="Rule ID"
                value={formData.action_config.rule_id || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAC('rule_id', parseInt(e.target.value) || 0)}
                className="text-sm"
              />
            </div>
          )}
        </div>
      )}

      {/* Step 4: Limits & name */}
      {step === 4 && (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">Name & limits</h3>

          <div>
            <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Rule Name</label>
            <Input
              type="text"
              placeholder="e.g. RELIANCE SL @ 2800"
              value={formData.name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('name', e.target.value)}
              className="text-sm"
            />
            <p className="text-xs text-zinc-500 mt-1">Auto-generated if left empty</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Max Fires</label>
              <Input
                type="number"
                min={1}
                placeholder="1"
                value={formData.max_fires || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('max_fires', e.target.value ? parseInt(e.target.value) : null)}
                className="text-sm"
              />
              <p className="text-xs text-zinc-500 mt-1">Leave empty for unlimited</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">Expires At</label>
              <Input
                type="datetime-local"
                value={formData.expires_at}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update('expires_at', e.target.value)}
                className="text-sm"
              />
            </div>
          </div>

          {/* Summary */}
          <div className="bg-zinc-50 dark:bg-zinc-900/50 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700/30 mt-4">
            <h4 className="text-xs font-medium text-zinc-500 mb-3 uppercase tracking-wider">Rule Summary</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-zinc-500">When:</span>
                <Badge color={triggerTypeColor(formData.trigger_type)}>{formData.trigger_type}</Badge>
                <span className="text-zinc-700 dark:text-zinc-300">
                  {formData.trigger_type === 'price' && `${formData.trigger_config.condition} ${formData.trigger_config.price}`}
                  {formData.trigger_type === 'indicator' && `${formData.trigger_config.indicator} ${formData.trigger_config.condition} ${formData.trigger_config.threshold}`}
                  {formData.trigger_type === 'time' && `at ${formData.trigger_config.time}`}
                  {formData.trigger_type === 'order_status' && `order → ${formData.trigger_config.expected_status}`}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-zinc-500">Then:</span>
                <Badge color={actionTypeColor(formData.action_type)}>{formData.action_type.replace('_', ' ')}</Badge>
                <span className="text-zinc-700 dark:text-zinc-300">
                  {formData.action_type === 'place_order' && `${formData.action_config.transaction_type} ${formData.action_config.quantity} @ ${formData.action_config.order_type}`}
                  {formData.action_type === 'cancel_order' && `order ${formData.action_config.order_id}`}
                  {formData.action_type === 'cancel_rule' && `rule #${formData.action_config.rule_id}`}
                </span>
              </div>
              {formData.max_fires && (
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500">Max fires:</span>
                  <span className="text-zinc-700 dark:text-zinc-300">{formData.max_fires}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
