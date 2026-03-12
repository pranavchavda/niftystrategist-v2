import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  Layers, Rocket, Trash2, ChevronDown, ChevronRight,
  Loader2, RefreshCw, Eye, AlertTriangle, CheckCircle2,
  TrendingUp, BarChart3, Zap, Target, Shield, Info,
} from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../components/catalyst/dialog';
import { Button } from '../components/catalyst/button';
import { Badge } from '../components/catalyst/badge';
import { Input } from '../components/catalyst/input';

interface AuthContext {
  authToken: string;
  user?: any;
}

interface StrategyTemplate {
  name: string;
  description: string;
  category: string;
  required_params: string[];
  optional_params: Record<string, any>;
}

interface ActiveStrategy {
  group_id: string;
  template_name: string;
  symbol: string;
  rules: Array<{
    id: number;
    name: string;
    enabled: boolean;
    trigger_type: string;
    action_type: string;
    fire_count: number;
  }>;
  total_fires: number;
}

interface PreviewRule {
  name: string;
  trigger_type: string;
  action_type: string;
  trigger_config: Record<string, any>;
  action_config: Record<string, any>;
}

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

// Param tooltips (shared with backtest page)
const PARAM_TOOLTIPS: Record<string, string> = {
  capital: 'Total money allocated for this strategy.',
  risk_percent: 'Max % of capital risked per trade.',
  rr_ratio: 'Reward-to-Risk ratio. Target = risk x RR.',
  trail_percent: 'Trailing stop distance as % from peak.',
  squareoff_time: 'Auto-close time (HH:MM). Usually 15:15.',
  entry_time: 'Entry time (HH:MM). Common: 09:20.',
  product: '"I" = Intraday, "D" = Delivery.',
  side: '"both", "long" (buy only), or "short" (sell only).',
  underlying: 'Index or stock. E.g. NIFTY, BANKNIFTY.',
  expiry: 'Option expiry date (YYYY-MM-DD).',
  strike: 'Strike price of the option.',
  lots: 'Number of lots to trade.',
  direction: '"sell" = collect premium, "buy" = pay premium.',
  sl_percent: 'SL trigger as % premium change from entry.',
  call_strike: 'Strike for the Call (CE) leg.',
  put_strike: 'Strike for the Put (PE) leg.',
  buy_strike: 'Strike of the option you BUY.',
  sell_strike: 'Strike of the option you SELL.',
  call_sell_strike: 'Strike of the Call you SELL (OTM).',
  call_buy_strike: 'Strike of the Call you BUY (protection).',
  put_sell_strike: 'Strike of the Put you SELL (OTM).',
  put_buy_strike: 'Strike of the Put you BUY (protection).',
};

function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex ml-1 align-middle">
      <Info className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 cursor-help" />
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs text-zinc-200 bg-zinc-800 dark:bg-zinc-700 rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none w-52 text-left leading-relaxed z-50 whitespace-normal">
        {text}
      </span>
    </span>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────

const TEMPLATE_DISPLAY_NAMES: Record<string, string> = {
  'orb': 'Opening Range Breakout',
  'breakout': 'Level Breakout',
  'mean-reversion': 'Mean Reversion',
  'vwap-bounce': 'VWAP Bounce',
  'scalp': 'Scalp',
  'straddle': 'Straddle',
  'strangle': 'Strangle',
  'bull-call-spread': 'Bull Call Spread',
  'bear-put-spread': 'Bear Put Spread',
  'iron-condor': 'Iron Condor',
};

function formatTemplateName(name: string): string {
  if (TEMPLATE_DISPLAY_NAMES[name]) return TEMPLATE_DISPLAY_NAMES[name];
  return name
    .split(/[-_]/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function categoryColor(cat: string): string {
  if (cat === 'equity') return 'emerald';
  if (cat === 'fno' || cat === 'options') return 'purple';
  return 'zinc';
}

function categoryLabel(cat: string): string {
  if (cat === 'equity') return 'Equity';
  if (cat === 'fno' || cat === 'options') return 'F&O Options';
  return cat;
}

const selectClassName = "w-full rounded-lg bg-white dark:bg-zinc-900/50 border border-zinc-300 dark:border-zinc-700 text-sm text-zinc-800 dark:text-zinc-200 px-3 py-2 focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30";

const FNO_UNDERLYINGS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'];

// ─── Deploy Dialog ───────────────────────────────────────────────────

function DeployDialog({
  template,
  isOpen,
  onClose,
  authToken,
}: {
  template: StrategyTemplate | null;
  isOpen: boolean;
  onClose: () => void;
  authToken: string;
}) {
  const [params, setParams] = useState<Record<string, any>>({});
  const [previewRules, setPreviewRules] = useState<PreviewRule[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [result, setResult] = useState<{ group_id: string; count: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reset state when template changes
  useEffect(() => {
    if (template) {
      const defaults: Record<string, any> = {};
      if (template.optional_params) {
        Object.entries(template.optional_params).forEach(([k, v]) => {
          defaults[k] = v;
        });
      }
      setParams(defaults);
      setPreviewRules(null);
      setResult(null);
      setError(null);
    }
  }, [template]);

  const isFnO = template?.category === 'fno' || template?.category === 'options';

  const updateParam = (key: string, value: any) => {
    setParams(prev => ({ ...prev, [key]: value }));
  };

  const deploy = async (dryRun: boolean) => {
    if (!template) return;
    const setter = dryRun ? setPreviewLoading : setLoading;
    setter(true);
    setError(null);
    if (!dryRun) setResult(null);

    try {
      const res = await fetch('/api/strategies/deploy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          template: template.name,
          params,
          dry_run: dryRun,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Deployment failed');
        return;
      }
      if (dryRun) {
        setPreviewRules(data.rules || []);
      } else {
        setResult({ group_id: data.group_id, count: data.rules_created || 0 });
        setPreviewRules(null);
      }
    } catch (e: any) {
      setError(e.message || 'Network error');
    } finally {
      setter(false);
    }
  };

  const renderParamInput = (paramName: string, isRequired: boolean) => {
    const value = params[paramName] ?? '';

    // Special handling for known param types
    if (paramName === 'underlying' && isFnO) {
      return (
        <div key={paramName}>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            {paramName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          <select
            className={selectClassName}
            value={value}
            onChange={e => updateParam(paramName, e.target.value)}
          >
            <option value="">Select underlying</option>
            {FNO_UNDERLYINGS.map(u => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
      );
    }

    if (paramName === 'product') {
      return (
        <div key={paramName}>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            Product Type
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          <select
            className={selectClassName}
            value={value}
            onChange={e => updateParam(paramName, e.target.value)}
          >
            <option value="">Select</option>
            <option value="D">Delivery (CNC)</option>
            <option value="I">Intraday (MIS)</option>
          </select>
        </div>
      );
    }

    if (paramName === 'side' || paramName === 'direction') {
      const options = paramName === 'direction'
        ? [['buy', 'Buy'], ['sell', 'Sell']]
        : [['long', 'Long'], ['short', 'Short'], ['both', 'Both']];
      return (
        <div key={paramName}>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            {paramName === 'direction' ? 'Direction' : 'Side'}
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          <select
            className={selectClassName}
            value={value}
            onChange={e => updateParam(paramName, e.target.value)}
          >
            <option value="">Select</option>
            {options.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
      );
    }

    if (paramName === 'option_type') {
      return (
        <div key={paramName}>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            Option Type
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          <select
            className={selectClassName}
            value={value}
            onChange={e => updateParam(paramName, e.target.value)}
          >
            <option value="">Select</option>
            <option value="CE">Call (CE)</option>
            <option value="PE">Put (PE)</option>
          </select>
        </div>
      );
    }

    if (paramName === 'expiry') {
      return (
        <div key={paramName}>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
            Expiry Date
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          <Input
            type="date"
            value={value}
            onChange={e => updateParam(paramName, e.target.value)}
          />
        </div>
      );
    }

    // Number fields
    const numberFields = ['capital', 'entry', 'sl', 'target', 'strike', 'strikes', 'lots', 'quantity', 'trail_percent', 'entry_price', 'sl_price', 'target_price'];
    const isNumber = numberFields.some(f => paramName.toLowerCase().includes(f));

    return (
      <div key={paramName}>
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
          {paramName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          {isRequired && <span className="text-red-400 ml-1">*</span>}
          {PARAM_TOOLTIPS[paramName] && <InfoTip text={PARAM_TOOLTIPS[paramName]} />}
        </label>
        <Input
          type={isNumber ? 'number' : 'text'}
          value={value}
          onChange={e => updateParam(paramName, isNumber ? parseFloat(e.target.value) || '' : e.target.value)}
          placeholder={isRequired ? 'Required' : `Default: ${template?.optional_params?.[paramName] ?? ''}`}
        />
      </div>
    );
  };

  if (!template) return null;

  return (
    <Dialog open={isOpen} onClose={onClose} size="2xl">
      <DialogTitle>
        <div className="flex items-center gap-3">
          <Rocket className="w-5 h-5 text-amber-500" />
          Deploy: {formatTemplateName(template.name)}
        </div>
      </DialogTitle>
      <DialogBody>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">{template.description}</p>

        {/* Parameter Form */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          {template.required_params.map(p => renderParamInput(p, true))}
          {template.optional_params && Object.keys(template.optional_params).map(p => renderParamInput(p, false))}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Success */}
        {result && (
          <div className="mb-4 p-4 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-sm text-emerald-700 dark:text-emerald-300">
            <div className="flex items-center gap-2 font-medium mb-1">
              <CheckCircle2 className="w-4 h-4" />
              Strategy deployed successfully
            </div>
            <div className="text-xs mt-1">
              Group ID: <code className="px-1.5 py-0.5 bg-emerald-100 dark:bg-emerald-900/40 rounded">{result.group_id}</code>
              {' '} | {result.count} rules created
            </div>
          </div>
        )}

        {/* Preview Table */}
        {previewRules && previewRules.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-2 flex items-center gap-2">
              <Eye className="w-4 h-4" />
              Preview: {previewRules.length} rules will be created
            </h4>
            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-zinc-50 dark:bg-zinc-800/50">
                    <th className="text-left px-3 py-2 text-zinc-600 dark:text-zinc-400 font-medium">Rule Name</th>
                    <th className="text-left px-3 py-2 text-zinc-600 dark:text-zinc-400 font-medium">Trigger</th>
                    <th className="text-left px-3 py-2 text-zinc-600 dark:text-zinc-400 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRules.map((rule, i) => (
                    <tr key={i} className="border-t border-zinc-200 dark:border-zinc-700/50">
                      <td className="px-3 py-2 text-zinc-800 dark:text-zinc-200">{rule.name}</td>
                      <td className="px-3 py-2">
                        <Badge color="blue">{rule.trigger_type}</Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge color="emerald">{rule.action_type}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </DialogBody>
      <DialogActions>
        <Button plain onClick={onClose}>Cancel</Button>
        <Button
          color="zinc"
          onClick={() => deploy(true)}
          disabled={previewLoading}
        >
          {previewLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
          <span className="ml-1.5">Preview (Dry Run)</span>
        </Button>
        <Button
          color="amber"
          onClick={() => deploy(false)}
          disabled={loading}
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
          <span className="ml-1.5">Deploy</span>
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Teardown Confirm Dialog ─────────────────────────────────────────

function TeardownDialog({
  groupId,
  templateName,
  isOpen,
  onClose,
  onConfirm,
  loading,
}: {
  groupId: string;
  templateName: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  return (
    <Dialog open={isOpen} onClose={onClose}>
      <DialogTitle>
        <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
          <AlertTriangle className="w-5 h-5" />
          Teardown Strategy
        </div>
      </DialogTitle>
      <DialogBody>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          This will permanently delete all monitor rules for the{' '}
          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{formatTemplateName(templateName)}</span>{' '}
          strategy (group: <code className="text-xs px-1 py-0.5 bg-zinc-100 dark:bg-zinc-800 rounded">{groupId}</code>).
        </p>
        <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-2">This action cannot be undone.</p>
      </DialogBody>
      <DialogActions>
        <Button plain onClick={onClose}>Cancel</Button>
        <Button color="red" onClick={onConfirm} disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          <span className="ml-1.5">Teardown</span>
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Active Strategy Card ────────────────────────────────────────────

function ActiveStrategyCard({
  strategy,
  onTeardown,
}: {
  strategy: ActiveStrategy;
  onTeardown: (groupId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const activeCount = strategy.rules.filter(r => r.enabled).length;

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 overflow-hidden transition-all duration-200 hover:border-zinc-300 dark:hover:border-zinc-600">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
      >
        <div className={`transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}>
          <ChevronRight className="w-4 h-4 text-zinc-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-zinc-800 dark:text-zinc-200">
              {formatTemplateName(strategy.template_name)}
            </span>
            <Badge color="zinc">{strategy.symbol}</Badge>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            <span>{activeCount}/{strategy.rules.length} rules active</span>
            <span>{strategy.total_fires} total fires</span>
          </div>
        </div>
        <Button
          color="red"
          className="text-xs"
          onClick={e => { e.stopPropagation(); onTeardown(strategy.group_id); }}
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span className="ml-1">Teardown</span>
        </Button>
      </button>

      {/* Expanded Rules */}
      {expanded && (
        <div className="border-t border-zinc-200 dark:border-zinc-700/50">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-zinc-50 dark:bg-zinc-800/30">
                <th className="text-left px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400 font-medium">Rule</th>
                <th className="text-left px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400 font-medium">Trigger</th>
                <th className="text-left px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400 font-medium">Action</th>
                <th className="text-left px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400 font-medium">Fires</th>
                <th className="text-left px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {strategy.rules.map(rule => (
                <tr key={rule.id} className="border-t border-zinc-100 dark:border-zinc-800/50">
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{rule.name}</td>
                  <td className="px-4 py-2"><Badge color="blue">{rule.trigger_type}</Badge></td>
                  <td className="px-4 py-2"><Badge color="emerald">{rule.action_type}</Badge></td>
                  <td className="px-4 py-2 text-zinc-500">{rule.fire_count}</td>
                  <td className="px-4 py-2">
                    <Badge color={rule.enabled ? 'emerald' : 'zinc'}>
                      {rule.enabled ? 'Active' : 'Disabled'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

export default function StrategiesPage() {
  const { authToken } = useOutletContext<AuthContext>();
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [activeStrategies, setActiveStrategies] = useState<ActiveStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeLoading, setActiveLoading] = useState(true);
  const [deployTemplate, setDeployTemplate] = useState<StrategyTemplate | null>(null);
  const [teardownTarget, setTeardownTarget] = useState<{ groupId: string; templateName: string } | null>(null);
  const [teardownLoading, setTeardownLoading] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/strategies/list', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || data || []);
      }
    } catch (e) {
      console.error('Failed to fetch templates:', e);
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  const fetchActive = useCallback(async () => {
    setActiveLoading(true);
    try {
      const res = await fetch('/api/strategies/active', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setActiveStrategies(data.strategies || data || []);
      }
    } catch (e) {
      console.error('Failed to fetch active strategies:', e);
    } finally {
      setActiveLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    fetchTemplates();
    fetchActive();
  }, [fetchTemplates, fetchActive]);

  const handleTeardown = async () => {
    if (!teardownTarget) return;
    setTeardownLoading(true);
    try {
      const res = await fetch(`/api/strategies/${teardownTarget.groupId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        setTeardownTarget(null);
        fetchActive();
      }
    } catch (e) {
      console.error('Teardown failed:', e);
    } finally {
      setTeardownLoading(false);
    }
  };

  // Group templates by category
  const equityTemplates = templates.filter(t => t.category === 'equity');
  const fnoTemplates = templates.filter(t => t.category !== 'equity');

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/30">
              <Layers className="w-6 h-6 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Strategy Templates</h1>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Deploy pre-built trading strategies as monitor rules</p>
            </div>
          </div>
        </div>

        {/* Templates Gallery */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
            <span className="ml-2 text-sm text-zinc-500">Loading templates...</span>
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-20">
            <Layers className="w-12 h-12 mx-auto mb-4 text-zinc-300 dark:text-zinc-700" />
            <p className="text-zinc-500 dark:text-zinc-400">No strategy templates available.</p>
            <p className="text-sm text-zinc-400 dark:text-zinc-500 mt-1">
              Templates are created via the <code className="px-1.5 py-0.5 bg-zinc-100 dark:bg-zinc-800 rounded text-xs">nf-strategy</code> CLI.
            </p>
          </div>
        ) : (
          <div className="space-y-8 mb-12">
            {/* Equity Strategies */}
            {equityTemplates.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200 mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-emerald-500" />
                  Equity Strategies
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {equityTemplates.map(t => (
                    <TemplateCard key={t.name} template={t} onDeploy={() => setDeployTemplate(t)} />
                  ))}
                </div>
              </div>
            )}

            {/* F&O Strategies */}
            {fnoTemplates.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200 mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-purple-500" />
                  F&O Options Strategies
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {fnoTemplates.map(t => (
                    <TemplateCard key={t.name} template={t} onDeploy={() => setDeployTemplate(t)} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Active Strategies */}
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              Active Strategies
            </h2>
            <Button plain onClick={fetchActive} disabled={activeLoading}>
              <RefreshCw className={`w-4 h-4 ${activeLoading ? 'animate-spin' : ''}`} />
              <span className="ml-1.5 text-sm">Refresh</span>
            </Button>
          </div>

          {activeLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
            </div>
          ) : activeStrategies.length === 0 ? (
            <div className="text-center py-12 rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700">
              <Target className="w-10 h-10 mx-auto mb-3 text-zinc-300 dark:text-zinc-700" />
              <p className="text-sm text-zinc-500 dark:text-zinc-400">No active strategies deployed.</p>
              <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">Deploy a template above to get started.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {activeStrategies.map(s => (
                <ActiveStrategyCard
                  key={s.group_id}
                  strategy={s}
                  onTeardown={gid => setTeardownTarget({ groupId: gid, templateName: s.template_name })}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <DeployDialog
        template={deployTemplate}
        isOpen={!!deployTemplate}
        onClose={() => { setDeployTemplate(null); fetchActive(); }}
        authToken={authToken}
      />
      {teardownTarget && (
        <TeardownDialog
          groupId={teardownTarget.groupId}
          templateName={teardownTarget.templateName}
          isOpen={!!teardownTarget}
          onClose={() => setTeardownTarget(null)}
          onConfirm={handleTeardown}
          loading={teardownLoading}
        />
      )}
    </div>
  );
}

// ─── Template Card ───────────────────────────────────────────────────

function TemplateCard({
  template,
  onDeploy,
}: {
  template: StrategyTemplate;
  onDeploy: () => void;
}) {
  return (
    <div className="group rounded-xl border border-zinc-200 dark:border-zinc-700/50 bg-white dark:bg-zinc-900/50 p-5 hover:border-amber-300 dark:hover:border-amber-700 hover:shadow-md hover:shadow-amber-500/5 transition-all duration-200">
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-semibold text-zinc-800 dark:text-zinc-200 text-sm">
          {formatTemplateName(template.name)}
        </h3>
        <Badge color={categoryColor(template.category)}>
          {categoryLabel(template.category)}
        </Badge>
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4 leading-relaxed line-clamp-2">
        {template.description}
      </p>
      <div className="flex flex-wrap gap-1.5 mb-4">
        {template.required_params.map(p => (
          <span
            key={p}
            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
          >
            {p.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
      <Button
        color="amber"
        className="w-full justify-center text-sm"
        onClick={onDeploy}
      >
        <Rocket className="w-4 h-4" />
        <span className="ml-1.5">Deploy</span>
      </Button>
    </div>
  );
}
