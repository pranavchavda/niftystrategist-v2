import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext, useNavigate } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import {
  Clock, Plus, Trash2, Play, Loader2, Shield, Power, PowerOff,
  ChevronDown, ChevronUp, Pencil, Save, X, AlertTriangle, CalendarClock,
  Sunrise, Sun, SunDim, Moon,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../components/catalyst/dialog';
import { Badge } from '../components/catalyst/badge';
import { Input } from '../components/catalyst/input';
import { Switch } from '../components/catalyst/switch';

interface AuthContext {
  authToken: string;
  user?: any;
}

interface Schedule {
  id: number;
  name: string;
  enabled: boolean;
  cron_hour: number;
  cron_minute: number;
  weekdays_only: boolean;
  prompt: string;
  timeout_seconds: number;
  model_override: string | null;
  last_run_at: string | null;
  last_error: string | null;
  run_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface Mandate {
  risk_per_trade?: string;
  daily_loss_cap?: string;
  allowed_instruments?: string;
  cutoff_time?: string;
  auto_squareoff_time?: string;
  custom_instructions?: string;
  approved_at?: string;
}

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

const WINDOW_ICONS: Record<string, React.ReactNode> = {
  'Morning Scan': <Sunrise className="w-4 h-4" />,
  'Mid-Day Check': <Sun className="w-4 h-4" />,
  'Pre-Close Positioning': <SunDim className="w-4 h-4" />,
  'Post-Close Review': <Moon className="w-4 h-4" />,
};

function formatTime(hour: number, minute: number): string {
  const h = hour % 12 || 12;
  const ampm = hour >= 12 ? 'PM' : 'AM';
  return `${h}:${minute.toString().padStart(2, '0')} ${ampm}`;
}

function timeAgo(isoString: string): string {
  const d = new Date(isoString + 'Z'); // Treat as UTC
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}d ago`;
}

export default function MandatesRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  const navigate = useNavigate();

  // Schedules state
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Mandate state
  const [mandate, setMandate] = useState<Mandate | null>(null);
  const [mandateLoading, setMandateLoading] = useState(true);
  const [editingMandate, setEditingMandate] = useState(false);
  const [mandateForm, setMandateForm] = useState<Mandate>({});

  // Create/edit dialog
  const [showCreate, setShowCreate] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    cron_hour: 9,
    cron_minute: 20,
    prompt: '',
    enabled: true,
    weekdays_only: true,
    timeout_seconds: 600,
  });

  // Expanded schedule (to show prompt)
  const [expanded, setExpanded] = useState<number | null>(null);

  // Running a schedule manually
  const [runningId, setRunningId] = useState<number | null>(null);

  // Daily thread
  const [dailyThreadId, setDailyThreadId] = useState<string | null>(null);

  // Action feedback
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Fetch schedules
  const fetchSchedules = useCallback(async () => {
    try {
      const res = await fetch('/api/awakenings/schedules', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to fetch schedules');
      const data = await res.json();
      setSchedules(data.schedules || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load schedules');
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  // Fetch mandate
  const fetchMandate = useCallback(async () => {
    try {
      const res = await fetch('/api/awakenings/mandate', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to fetch mandate');
      const data = await res.json();
      setMandate(data.mandate);
      if (data.mandate) setMandateForm(data.mandate);
    } catch (err) {
      // non-fatal
    } finally {
      setMandateLoading(false);
    }
  }, [authToken]);

  // Fetch daily thread
  const fetchDailyThread = useCallback(async () => {
    try {
      const res = await fetch('/api/awakenings/daily-thread', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setDailyThreadId(data.thread_id);
      }
    } catch { /* non-fatal */ }
  }, [authToken]);

  useEffect(() => {
    fetchSchedules();
    fetchMandate();
    fetchDailyThread();
  }, [fetchSchedules, fetchMandate, fetchDailyThread]);

  // Toggle schedule enabled
  const toggleSchedule = async (schedule: Schedule) => {
    try {
      const res = await fetch(`/api/awakenings/schedules/${schedule.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ enabled: !schedule.enabled }),
      });
      if (!res.ok) throw new Error('Failed to toggle schedule');
      setSchedules(prev =>
        prev.map(s => s.id === schedule.id ? { ...s, enabled: !s.enabled } : s)
      );
      showAction(`${schedule.name} ${!schedule.enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle');
    }
  };

  // Create or update schedule
  const saveSchedule = async () => {
    try {
      const url = editingSchedule
        ? `/api/awakenings/schedules/${editingSchedule.id}`
        : '/api/awakenings/schedules';
      const method = editingSchedule ? 'PATCH' : 'POST';

      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(formData),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save schedule');
      }

      setShowCreate(false);
      setEditingSchedule(null);
      await fetchSchedules();
      showAction(editingSchedule ? 'Schedule updated' : 'Schedule created');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    }
  };

  // Delete schedule
  const deleteSchedule = async (id: number) => {
    try {
      const res = await fetch(`/api/awakenings/schedules/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to delete');
      setSchedules(prev => prev.filter(s => s.id !== id));
      showAction('Schedule deleted');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  // Run schedule now
  const runNow = async (schedule: Schedule) => {
    setRunningId(schedule.id);
    try {
      const res = await fetch(`/api/awakenings/schedules/${schedule.id}/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to run');
      const data = await res.json();
      if (data.success) {
        showAction(`${schedule.name} completed`);
        await fetchSchedules();
        await fetchDailyThread();
      } else {
        setError(data.error || 'Awakening failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run');
    } finally {
      setRunningId(null);
    }
  };

  // Seed defaults
  const seedDefaults = async () => {
    try {
      const res = await fetch('/api/awakenings/schedules/seed', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to seed');
      const data = await res.json();
      await fetchSchedules();
      showAction(`Seeded ${data.seeded} default schedules`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to seed defaults');
    }
  };

  // Save mandate
  const saveMandate = async () => {
    try {
      const res = await fetch('/api/awakenings/mandate', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(mandateForm),
      });
      if (!res.ok) throw new Error('Failed to save mandate');
      const data = await res.json();
      setMandate(data.mandate);
      setEditingMandate(false);
      showAction('Mandate saved');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save mandate');
    }
  };

  // Clear mandate
  const clearMandate = async () => {
    try {
      const res = await fetch('/api/awakenings/mandate', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Failed to clear mandate');
      setMandate(null);
      setMandateForm({});
      showAction('Mandate cleared');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear');
    }
  };

  // Open create dialog
  const openCreate = () => {
    setEditingSchedule(null);
    setFormData({
      name: '',
      cron_hour: 9,
      cron_minute: 20,
      prompt: '',
      enabled: true,
      weekdays_only: true,
      timeout_seconds: 600,
    });
    setShowCreate(true);
  };

  // Open edit dialog
  const openEdit = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    setFormData({
      name: schedule.name,
      cron_hour: schedule.cron_hour,
      cron_minute: schedule.cron_minute,
      prompt: schedule.prompt,
      enabled: schedule.enabled,
      weekdays_only: schedule.weekdays_only,
      timeout_seconds: schedule.timeout_seconds,
    });
    setShowCreate(true);
  };

  const showAction = (msg: string) => {
    setActionMessage(msg);
    setTimeout(() => setActionMessage(null), 3000);
  };

  // Count active schedules
  const activeCount = schedules.filter(s => s.enabled).length;

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="p-4 sm:p-6 max-w-4xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <Shield className="w-6 h-6 text-amber-500" />
              Mandates
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              Configure autonomous trading rules and recurring awakening schedules
            </p>
          </div>
          {dailyThreadId && (
            <button
              onClick={() => navigate(`/chat/${dailyThreadId}`)}
              className="text-sm text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 flex items-center gap-1.5 bg-amber-50 dark:bg-amber-900/20 px-3 py-1.5 rounded-lg border border-amber-200 dark:border-amber-800 transition-colors"
            >
              <CalendarClock className="w-3.5 h-3.5" />
              Today's Thread
            </button>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Action feedback */}
        {actionMessage && (
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-sm text-emerald-700 dark:text-emerald-300">
            {actionMessage}
          </div>
        )}

        {/* ================================================================ */}
        {/* TRADING MANDATE CARD */}
        {/* ================================================================ */}
        <div className="rounded-xl bg-white dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-700/60 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-500" />
              <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">Trading Mandate</h2>
              {mandate && (
                <Badge color="emerald" className="ml-2">Active</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {mandate && !editingMandate && (
                <>
                  <Button variant="plain" onClick={() => { setMandateForm(mandate); setEditingMandate(true); }}>
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                  <Button variant="plain" onClick={clearMandate} className="text-red-500 hover:text-red-600">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </>
              )}
            </div>
          </div>

          <div className="px-5 py-4">
            {mandateLoading ? (
              <div className="flex items-center gap-2 text-zinc-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading...
              </div>
            ) : editingMandate || !mandate ? (
              <div className="space-y-4">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Define risk boundaries for autonomous trading. Awakenings will operate within these limits.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Risk per trade
                    </label>
                    <Input
                      type="text"
                      placeholder="e.g., ₹5,000"
                      value={mandateForm.risk_per_trade || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMandateForm({ ...mandateForm, risk_per_trade: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Daily loss cap
                    </label>
                    <Input
                      type="text"
                      placeholder="e.g., ₹10,000"
                      value={mandateForm.daily_loss_cap || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMandateForm({ ...mandateForm, daily_loss_cap: e.target.value })}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Allowed instruments
                    </label>
                    <Input
                      type="text"
                      placeholder="e.g., NIFTY, BANKNIFTY options + Nifty 500 equity"
                      value={mandateForm.allowed_instruments || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMandateForm({ ...mandateForm, allowed_instruments: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Cutoff time
                    </label>
                    <Input
                      type="text"
                      placeholder="e.g., 3:00 PM IST"
                      value={mandateForm.cutoff_time || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMandateForm({ ...mandateForm, cutoff_time: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Auto-squareoff time
                    </label>
                    <Input
                      type="text"
                      placeholder="e.g., 3:15 PM IST"
                      value={mandateForm.auto_squareoff_time || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMandateForm({ ...mandateForm, auto_squareoff_time: e.target.value })}
                    />
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Custom instructions
                  </label>
                  <textarea
                    className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-sm text-zinc-900 dark:text-zinc-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[80px] resize-y"
                    placeholder="e.g., Only use ORB and breakout strategies. Prefer NIFTY 50 stocks. Avoid F&O before lunch."
                    value={mandateForm.custom_instructions || ''}
                    onChange={e => setMandateForm({ ...mandateForm, custom_instructions: e.target.value })}
                    rows={3}
                  />
                  <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
                    Free-form preferences injected into every awakening's context.
                  </p>
                </div>
                <div className="flex items-center gap-2 pt-2">
                  <Button onClick={saveMandate}>
                    <Save className="w-4 h-4 mr-1" />
                    {mandate ? 'Update Mandate' : 'Save Mandate'}
                  </Button>
                  {editingMandate && (
                    <Button variant="plain" onClick={() => setEditingMandate(false)}>
                      Cancel
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {[
                    { label: 'Risk/Trade', value: mandate.risk_per_trade },
                    { label: 'Daily Loss Cap', value: mandate.daily_loss_cap },
                    { label: 'Instruments', value: mandate.allowed_instruments },
                    { label: 'Cutoff', value: mandate.cutoff_time },
                    { label: 'Auto-Squareoff', value: mandate.auto_squareoff_time },
                    { label: 'Approved', value: mandate.approved_at ? new Date(mandate.approved_at).toLocaleDateString() : undefined },
                  ].filter(item => item.value).map(item => (
                    <div key={item.label} className="p-2.5 rounded-lg bg-zinc-50 dark:bg-zinc-800/50">
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">{item.label}</div>
                      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mt-0.5">{item.value}</div>
                    </div>
                  ))}
                </div>
                {mandate.custom_instructions && (
                  <div className="mt-3 p-3 rounded-lg bg-amber-50/50 dark:bg-amber-900/10 border border-amber-200/50 dark:border-amber-800/30">
                    <div className="text-xs text-amber-600 dark:text-amber-400 font-medium mb-1">Custom Instructions</div>
                    <div className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">{mandate.custom_instructions}</div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* AWAKENING SCHEDULES */}
        {/* ================================================================ */}
        <div className="rounded-xl bg-white dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-700/60 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CalendarClock className="w-4 h-4 text-blue-500" />
              <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">Awakening Schedules</h2>
              {activeCount > 0 && (
                <Badge color="blue" className="ml-2">{activeCount} active</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {schedules.length === 0 && (
                <Button variant="outline" onClick={seedDefaults}>
                  Seed Defaults
                </Button>
              )}
              <Button onClick={openCreate}>
                <Plus className="w-4 h-4 mr-1" />
                Add
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="px-5 py-8 flex items-center justify-center text-zinc-400">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              Loading schedules...
            </div>
          ) : schedules.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <CalendarClock className="w-10 h-10 text-zinc-300 dark:text-zinc-600 mx-auto mb-3" />
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
                No awakening schedules configured yet.
              </p>
              <Button variant="outline" onClick={seedDefaults}>
                Seed Default Schedules
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {schedules.map(schedule => (
                <div key={schedule.id} className="group">
                  {/* Schedule row */}
                  <div className="px-5 py-3 flex items-center gap-3">
                    {/* Icon */}
                    <div className={`flex-shrink-0 p-2 rounded-lg ${
                      schedule.enabled
                        ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-500'
                    }`}>
                      {WINDOW_ICONS[schedule.name] || <Clock className="w-4 h-4" />}
                    </div>

                    {/* Name + time */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${
                          schedule.enabled
                            ? 'text-zinc-900 dark:text-zinc-100'
                            : 'text-zinc-500 dark:text-zinc-400'
                        }`}>
                          {schedule.name}
                        </span>
                        <span className="text-xs text-zinc-400 dark:text-zinc-500">
                          {formatTime(schedule.cron_hour, schedule.cron_minute)} IST
                        </span>
                        {schedule.weekdays_only && (
                          <span className="text-xs text-zinc-400 dark:text-zinc-500">Mon-Fri</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        {schedule.last_run_at && (
                          <span className="text-xs text-zinc-400 dark:text-zinc-500">
                            Last run: {timeAgo(schedule.last_run_at)}
                          </span>
                        )}
                        {schedule.run_count > 0 && (
                          <span className="text-xs text-zinc-400 dark:text-zinc-500">
                            {schedule.run_count} runs
                          </span>
                        )}
                        {schedule.last_error && (
                          <span className="text-xs text-red-500" title={schedule.last_error}>
                            Last error
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => openEdit(schedule)}
                        className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                        title="Edit"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => runNow(schedule)}
                        disabled={runningId === schedule.id}
                        className="p-1.5 rounded-md text-zinc-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 disabled:opacity-50"
                        title="Run now"
                      >
                        {runningId === schedule.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Play className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => deleteSchedule(schedule.id)}
                        className="p-1.5 rounded-md text-zinc-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Toggle */}
                    <Switch
                      checked={schedule.enabled}
                      onChange={() => toggleSchedule(schedule)}
                      className="flex-shrink-0"
                    />

                    {/* Expand */}
                    <button
                      onClick={() => setExpanded(expanded === schedule.id ? null : schedule.id)}
                      className="p-1 rounded text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                    >
                      {expanded === schedule.id ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>

                  {/* Expanded prompt */}
                  {expanded === schedule.id && (
                    <div className="px-5 pb-4 pl-16">
                      <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 text-sm text-zinc-700 dark:text-zinc-300 font-mono whitespace-pre-wrap">
                        {schedule.prompt}
                      </div>
                      {schedule.last_error && (
                        <div className="mt-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 text-xs text-red-600 dark:text-red-400">
                          <strong>Last error:</strong> {schedule.last_error}
                        </div>
                      )}
                      <div className="mt-2 flex items-center gap-4 text-xs text-zinc-400">
                        <span>Timeout: {schedule.timeout_seconds}s</span>
                        {schedule.model_override && (
                          <span>Model: {schedule.model_override}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ================================================================ */}
        {/* HOW IT WORKS */}
        {/* ================================================================ */}
        <div className="rounded-xl bg-zinc-50 dark:bg-zinc-800/30 border border-zinc-200/60 dark:border-zinc-700/40 px-5 py-4">
          <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">How it works</h3>
          <ol className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1.5 list-decimal list-inside">
            <li>Each schedule fires at its configured IST time on trading days (Mon-Fri, non-holidays)</li>
            <li>All awakenings for one day write to a single "daily thread" — each one sees what previous awakenings did</li>
            <li>The trading mandate sets risk boundaries — awakenings operate within these limits autonomously</li>
            <li>Results appear in the daily thread (linked above) and in your conversation history</li>
          </ol>
        </div>
      </div>

      {/* ================================================================ */}
      {/* CREATE / EDIT DIALOG */}
      {/* ================================================================ */}
      <Dialog open={showCreate} onClose={() => { setShowCreate(false); setEditingSchedule(null); }}>
        <DialogTitle>{editingSchedule ? 'Edit Schedule' : 'New Awakening Schedule'}</DialogTitle>
        <DialogBody>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Name</label>
              <Input
                type="text"
                placeholder="e.g., Morning Scan"
                value={formData.name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Hour (IST)</label>
                <Input
                  type="number"
                  min={0}
                  max={23}
                  value={formData.cron_hour}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, cron_hour: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Minute</label>
                <Input
                  type="number"
                  min={0}
                  max={59}
                  value={formData.cron_minute}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, cron_minute: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Prompt</label>
              <textarea
                className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-sm text-zinc-900 dark:text-zinc-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[120px] resize-y"
                placeholder="What should the awakening do? The agent has access to all CLI tools."
                value={formData.prompt}
                onChange={e => setFormData({ ...formData, prompt: e.target.value })}
                rows={5}
              />
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                <Switch
                  checked={formData.weekdays_only}
                  onChange={(checked: boolean) => setFormData({ ...formData, weekdays_only: checked })}
                />
                Weekdays only
              </label>
              <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                <Switch
                  checked={formData.enabled}
                  onChange={(checked: boolean) => setFormData({ ...formData, enabled: checked })}
                />
                Enabled
              </label>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Timeout (seconds)</label>
              <Input
                type="number"
                min={60}
                max={1800}
                value={formData.timeout_seconds}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, timeout_seconds: parseInt(e.target.value) || 600 })}
              />
            </div>
          </div>
        </DialogBody>
        <DialogActions>
          <Button variant="plain" onClick={() => { setShowCreate(false); setEditingSchedule(null); }}>
            Cancel
          </Button>
          <Button onClick={saveSchedule} disabled={!formData.name || !formData.prompt}>
            <Save className="w-4 h-4 mr-1" />
            {editingSchedule ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}
