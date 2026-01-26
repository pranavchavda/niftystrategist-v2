import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router';
import { requirePermission } from '../utils/route-permissions';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface AuthContext {
  authToken: string;
  user?: any;
}

interface WorkflowConfig {
  id: number;
  workflow_type: string;
  enabled: boolean;
  frequency: string;
  config: Record<string, any>;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

interface WorkflowType {
  type: string;
  name: string;
  description: string;
  default_config: Record<string, any>;
  config_schema: Record<string, any>;
}

interface WorkflowRun {
  id: number;
  workflow_type: string;
  status: string;
  trigger_type: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  result: Record<string, any> | null;
  error_message: string | null;
}

interface CustomWorkflow {
  id: number;
  name: string;
  description: string | null;
  icon: string;
  prompt: string;
  agent_hint: string | null;
  enabled: boolean;
  frequency: string;
  cron_expression: string | null;
  scheduled_at: string | null;  // For one-time scheduled runs
  timeout_seconds: number;
  notify_on_complete: boolean;
  notify_on_failure: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  created_at: string;
  updated_at: string;
}

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

// Available icons for custom workflows
const WORKFLOW_ICONS = ['🤖', '📧', '📊', '🔍', '📝', '⚡', '🎯', '📈', '🛒', '💼', '🔔', '📱'];

export default function AutomationsRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  const [workflowTypes, setWorkflowTypes] = useState<WorkflowType[]>([]);
  const [configs, setConfigs] = useState<WorkflowConfig[]>([]);
  const [history, setHistory] = useState<Record<string, WorkflowRun[]>>({});
  const [customWorkflows, setCustomWorkflows] = useState<CustomWorkflow[]>([]);
  const [customHistory, setCustomHistory] = useState<Record<number, WorkflowRun[]>>({});
  const [loading, setLoading] = useState(true);
  const [runningWorkflows, setRunningWorkflows] = useState<Set<string>>(new Set());
  const [runningCustomWorkflows, setRunningCustomWorkflows] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingWorkflow, setEditingWorkflow] = useState<CustomWorkflow | null>(null);
  const [modalData, setModalData] = useState({
    name: '',
    description: '',
    icon: '🤖',
    prompt: '',
    frequency: 'daily',
    scheduled_at: '',  // For one-time scheduled runs (ISO datetime string)
    enabled: false,
    notify_on_complete: true,  // Default to true
    notify_on_failure: true,
    timeout_seconds: 120
  });
  const [saving, setSaving] = useState(false);

  // Run result viewer modal state
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  // Fetch workflow types and configs
  useEffect(() => {
    async function fetchData() {
      try {
        const [typesRes, configsRes, customRes] = await Promise.all([
          fetch('/api/workflows/types', {
            headers: { Authorization: `Bearer ${authToken}` }
          }),
          fetch('/api/workflows/configs', {
            headers: { Authorization: `Bearer ${authToken}` }
          }),
          fetch('/api/workflows/custom', {
            headers: { Authorization: `Bearer ${authToken}` }
          })
        ]);

        if (!typesRes.ok || !configsRes.ok) {
          throw new Error('Failed to fetch workflow data');
        }

        const types = await typesRes.json();
        const cfgs = await configsRes.json();
        const customs = customRes.ok ? await customRes.json() : [];

        setWorkflowTypes(types);
        setConfigs(cfgs);
        setCustomWorkflows(customs);

        // Fetch history for each workflow type
        const historyPromises = types.map(async (t: WorkflowType) => {
          const res = await fetch(`/api/workflows/${t.type}/history?limit=5`, {
            headers: { Authorization: `Bearer ${authToken}` }
          });
          if (res.ok) {
            return { type: t.type, runs: await res.json() };
          }
          return { type: t.type, runs: [] };
        });

        const historyResults = await Promise.all(historyPromises);
        const historyMap: Record<string, WorkflowRun[]> = {};
        historyResults.forEach(h => {
          historyMap[h.type] = h.runs;
        });
        setHistory(historyMap);

        // Fetch history for custom workflows
        const customHistoryPromises = customs.map(async (w: CustomWorkflow) => {
          const res = await fetch(`/api/workflows/custom/${w.id}/history?limit=5`, {
            headers: { Authorization: `Bearer ${authToken}` }
          });
          if (res.ok) {
            return { id: w.id, runs: await res.json() };
          }
          return { id: w.id, runs: [] };
        });

        const customHistoryResults = await Promise.all(customHistoryPromises);
        const customHistoryMap: Record<number, WorkflowRun[]> = {};
        customHistoryResults.forEach(h => {
          customHistoryMap[h.id] = h.runs;
        });
        setCustomHistory(customHistoryMap);

      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load workflows');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [authToken]);

  // Get config for a workflow type
  const getConfig = (type: string): WorkflowConfig | undefined => {
    return configs.find(c => c.workflow_type === type);
  };

  // Update workflow config
  const updateConfig = async (type: string, updates: Partial<WorkflowConfig>) => {
    try {
      const res = await fetch(`/api/workflows/${type}/config`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(updates)
      });

      if (!res.ok) {
        throw new Error('Failed to update configuration');
      }

      const updated = await res.json();

      // Update local state
      setConfigs(prev => {
        const existing = prev.findIndex(c => c.workflow_type === type);
        if (existing >= 0) {
          const newConfigs = [...prev];
          newConfigs[existing] = updated;
          return newConfigs;
        }
        return [...prev, updated];
      });

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update');
    }
  };

  // Run workflow manually
  const runWorkflow = async (type: string) => {
    setRunningWorkflows(prev => new Set(prev).add(type));
    setError(null);

    try {
      const res = await fetch(`/api/workflows/${type}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({})
      });

      const result = await res.json();

      if (!res.ok) {
        throw new Error(result.detail || 'Failed to run workflow');
      }

      // Refresh history for this workflow
      const historyRes = await fetch(`/api/workflows/${type}/history?limit=5`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (historyRes.ok) {
        const runs = await historyRes.json();
        setHistory(prev => ({ ...prev, [type]: runs }));
      }

      // Refresh config to get updated last_run_at
      const configRes = await fetch(`/api/workflows/${type}/config`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (configRes.ok) {
        const updated = await configRes.json();
        setConfigs(prev => {
          const idx = prev.findIndex(c => c.workflow_type === type);
          if (idx >= 0) {
            const newConfigs = [...prev];
            newConfigs[idx] = updated;
            return newConfigs;
          }
          return prev;
        });
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run workflow');
    } finally {
      setRunningWorkflows(prev => {
        const next = new Set(prev);
        next.delete(type);
        return next;
      });
    }
  };

  // Run custom workflow manually
  const runCustomWorkflow = async (workflowId: number) => {
    setRunningCustomWorkflows(prev => new Set(prev).add(workflowId));
    setError(null);

    try {
      const res = await fetch(`/api/workflows/custom/${workflowId}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        }
      });

      const result = await res.json();

      if (!res.ok) {
        throw new Error(result.detail || 'Failed to run workflow');
      }

      // Refresh history for this workflow
      const historyRes = await fetch(`/api/workflows/custom/${workflowId}/history?limit=5`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (historyRes.ok) {
        const runs = await historyRes.json();
        setCustomHistory(prev => ({ ...prev, [workflowId]: runs }));
      }

      // Refresh custom workflow to get updated last_run_at
      const workflowRes = await fetch(`/api/workflows/custom/${workflowId}`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (workflowRes.ok) {
        const updated = await workflowRes.json();
        setCustomWorkflows(prev =>
          prev.map(w => w.id === workflowId ? updated : w)
        );
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run workflow');
    } finally {
      setRunningCustomWorkflows(prev => {
        const next = new Set(prev);
        next.delete(workflowId);
        return next;
      });
    }
  };

  // Open modal for creating new workflow
  const openCreateModal = () => {
    setEditingWorkflow(null);
    setModalData({
      name: '',
      description: '',
      icon: '🤖',
      prompt: '',
      frequency: 'daily',
      scheduled_at: '',
      enabled: false,
      notify_on_complete: false,
      notify_on_failure: true,
      timeout_seconds: 120
    });
    setShowModal(true);
  };

  // Open modal for editing workflow
  const openEditModal = (workflow: CustomWorkflow) => {
    setEditingWorkflow(workflow);
    // Convert ISO datetime to datetime-local format (YYYY-MM-DDTHH:mm)
    let scheduledAtLocal = '';
    if (workflow.scheduled_at) {
      const dt = new Date(workflow.scheduled_at);
      scheduledAtLocal = dt.toISOString().slice(0, 16);
    }
    setModalData({
      name: workflow.name,
      description: workflow.description || '',
      icon: workflow.icon,
      prompt: workflow.prompt,
      frequency: workflow.frequency,
      scheduled_at: scheduledAtLocal,
      enabled: workflow.enabled,
      notify_on_complete: workflow.notify_on_complete,
      notify_on_failure: workflow.notify_on_failure,
      timeout_seconds: workflow.timeout_seconds
    });
    setShowModal(true);
  };

  // Save workflow (create or update)
  const saveWorkflow = async () => {
    if (!modalData.name.trim() || !modalData.prompt.trim()) {
      setError('Name and prompt are required');
      return;
    }

    // Validate scheduled_at is required for 'once' frequency
    if (modalData.frequency === 'once' && !modalData.scheduled_at) {
      setError('Please select a date and time for the one-time run');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const url = editingWorkflow
        ? `/api/workflows/custom/${editingWorkflow.id}`
        : '/api/workflows/custom';

      // Prepare request body - convert scheduled_at to ISO string if present
      const requestBody = {
        ...modalData,
        scheduled_at: modalData.frequency === 'once' && modalData.scheduled_at
          ? new Date(modalData.scheduled_at).toISOString()
          : null
      };

      const res = await fetch(url, {
        method: editingWorkflow ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save workflow');
      }

      const saved = await res.json();

      if (editingWorkflow) {
        setCustomWorkflows(prev =>
          prev.map(w => w.id === saved.id ? saved : w)
        );
      } else {
        setCustomWorkflows(prev => [saved, ...prev]);
      }

      setShowModal(false);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save workflow');
    } finally {
      setSaving(false);
    }
  };

  // Delete workflow
  const deleteWorkflow = async (workflowId: number) => {
    if (!confirm('Are you sure you want to delete this workflow?')) {
      return;
    }

    try {
      const res = await fetch(`/api/workflows/custom/${workflowId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (!res.ok) {
        throw new Error('Failed to delete workflow');
      }

      setCustomWorkflows(prev => prev.filter(w => w.id !== workflowId));

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete workflow');
    }
  };

  // Toggle workflow enabled state
  const toggleCustomWorkflow = async (workflow: CustomWorkflow) => {
    try {
      const res = await fetch(`/api/workflows/custom/${workflow.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ enabled: !workflow.enabled })
      });

      if (!res.ok) {
        throw new Error('Failed to update workflow');
      }

      const updated = await res.json();
      setCustomWorkflows(prev =>
        prev.map(w => w.id === updated.id ? updated : w)
      );

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update workflow');
    }
  };

  // Format date for display
  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  // Format duration
  const formatDuration = (ms: number | null): string => {
    if (!ms) return '';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-900 text-white p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold mb-8">Automations</h1>
          <div className="animate-pulse space-y-4">
            <div className="h-48 bg-zinc-800 rounded-lg"></div>
            <div className="h-48 bg-zinc-800 rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Automations</h1>
            <p className="text-zinc-400 mt-1">
              Configure automated workflows that run on a schedule or on-demand
            </p>
          </div>
          <button
            onClick={openCreateModal}
            className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Workflow
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-4 text-red-400 hover:text-red-300"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Built-in Workflows Section */}
        {workflowTypes.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-zinc-300 mb-4">Built-in Workflows</h2>
            <div className="space-y-6">
              {workflowTypes.map(wfType => {
                const config = getConfig(wfType.type);
                const runs = history[wfType.type] || [];
                const isRunning = runningWorkflows.has(wfType.type);

                return (
                  <div
                    key={wfType.type}
                    className="bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden"
                  >
                    {/* Header */}
                    <div className="p-6 border-b border-zinc-700">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-2xl">
                            {wfType.type === 'email_autolabel' ? '📧' : '📊'}
                          </div>
                          <div>
                            <h2 className="text-lg font-semibold">{wfType.name}</h2>
                            <p className="text-sm text-zinc-400">{wfType.description}</p>
                          </div>
                        </div>

                        {/* Enable Toggle */}
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={config?.enabled || false}
                            onChange={(e) => updateConfig(wfType.type, { enabled: e.target.checked })}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-zinc-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-500"></div>
                          <span className="ms-3 text-sm font-medium text-zinc-400">
                            {config?.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </label>
                      </div>
                    </div>

                    {/* Configuration */}
                    <div className="p-6 border-b border-zinc-700 bg-zinc-800/50">
                      <div className="flex flex-wrap gap-4 items-center">
                        {/* Frequency */}
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">Schedule</label>
                          <select
                            value={config?.frequency || 'daily'}
                            onChange={(e) => updateConfig(wfType.type, { frequency: e.target.value })}
                            className="bg-zinc-700 border border-zinc-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-orange-500"
                          >
                            <option value="manual">Manual only</option>
                            <option value="hourly">Every hour</option>
                            <option value="6hours">Every 6 hours</option>
                            <option value="daily">Daily (8 AM)</option>
                            <option value="weekly">Weekly (Monday)</option>
                          </select>
                        </div>

                        {/* Workflow-specific config */}
                        {wfType.type === 'email_autolabel' && (
                          <>
                            <div>
                              <label className="block text-xs text-zinc-500 mb-1">Emails</label>
                              <select
                                value={config?.config?.email_count || 50}
                                onChange={(e) => updateConfig(wfType.type, {
                                  config: { ...config?.config, email_count: parseInt(e.target.value) }
                                })}
                                className="bg-zinc-700 border border-zinc-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-orange-500"
                              >
                                <option value={25}>25 emails</option>
                                <option value={50}>50 emails</option>
                                <option value={100}>100 emails</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-xs text-zinc-500 mb-1">Age limit</label>
                              <select
                                value={config?.config?.max_age_days || 7}
                                onChange={(e) => updateConfig(wfType.type, {
                                  config: { ...config?.config, max_age_days: parseInt(e.target.value) }
                                })}
                                className="bg-zinc-700 border border-zinc-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-orange-500"
                              >
                                <option value={1}>Last 24 hours</option>
                                <option value={3}>Last 3 days</option>
                                <option value={7}>Last 7 days</option>
                                <option value={14}>Last 14 days</option>
                                <option value={30}>Last 30 days</option>
                              </select>
                            </div>
                          </>
                        )}

                        {/* Run Now Button */}
                        <div className="ml-auto">
                          <button
                            onClick={() => runWorkflow(wfType.type)}
                            disabled={isRunning}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                              isRunning
                                ? 'bg-zinc-600 text-zinc-400 cursor-not-allowed'
                                : 'bg-orange-500 hover:bg-orange-600 text-white'
                            }`}
                          >
                            {isRunning ? (
                              <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Running...
                              </>
                            ) : (
                              <>
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                Run Now
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Last run info */}
                      {config?.last_run_at && (
                        <div className="mt-4 text-sm text-zinc-400">
                          Last run: {formatDate(config.last_run_at)}
                          {config.next_run_at && config.enabled && (
                            <span className="ml-4">
                              Next run: {formatDate(config.next_run_at)}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Recent Runs */}
                    {runs.length > 0 && (
                      <div className="p-6">
                        <h3 className="text-sm font-medium text-zinc-400 mb-3">Recent Runs</h3>
                        <div className="space-y-2">
                          {runs.slice(0, 5).map(run => (
                            <button
                              key={run.id}
                              onClick={() => {
                                setSelectedRun(run);
                                setShowRunModal(true);
                              }}
                              className="w-full flex items-center justify-between text-sm py-2 px-2 -mx-2 border-b border-zinc-700/50 last:border-0 rounded hover:bg-zinc-700/50 transition-colors text-left"
                            >
                              <div className="flex items-center gap-3">
                                <span className={`w-2 h-2 rounded-full ${
                                  run.status === 'completed' ? 'bg-green-500' :
                                  run.status === 'failed' ? 'bg-red-500' :
                                  run.status === 'running' ? 'bg-yellow-500 animate-pulse' :
                                  'bg-zinc-500'
                                }`} />
                                <span className="text-zinc-300">
                                  {formatDate(run.started_at)}
                                </span>
                                <span className="text-zinc-500">
                                  ({run.trigger_type})
                                </span>
                              </div>

                              <div className="flex items-center gap-4">
                                {run.result && (
                                  <span className="text-zinc-400">
                                    {run.result.emails_processed !== undefined && (
                                      <>{run.result.emails_processed} emails</>
                                    )}
                                    {run.result.labels_applied && Object.keys(run.result.labels_applied).length > 0 && (
                                      <span className="text-green-400 ml-2">
                                        {Object.values(run.result.labels_applied as Record<string, number>).reduce((a, b) => a + b, 0)} labeled
                                      </span>
                                    )}
                                  </span>
                                )}
                                {run.duration_ms && (
                                  <span className="text-zinc-500 text-xs">
                                    {formatDuration(run.duration_ms)}
                                  </span>
                                )}
                                <span className={`text-xs px-2 py-0.5 rounded ${
                                  run.status === 'completed' ? 'bg-green-900/50 text-green-400' :
                                  run.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                                  'bg-zinc-700 text-zinc-400'
                                }`}>
                                  {run.status}
                                </span>
                                <span className="text-zinc-500 text-xs">→</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Custom Workflows Section */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-zinc-300 mb-4">Custom Workflows</h2>

          {customWorkflows.length === 0 ? (
            <div className="bg-zinc-800 rounded-lg border border-zinc-700 p-8 text-center">
              <div className="text-4xl mb-4">🤖</div>
              <h3 className="text-lg font-medium mb-2">No custom workflows yet</h3>
              <p className="text-zinc-400 mb-4">
                Create a custom workflow to automate any task with natural language prompts
              </p>
              <button
                onClick={openCreateModal}
                className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Create Your First Workflow
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {customWorkflows.map(workflow => {
                const runs = customHistory[workflow.id] || [];
                const isRunning = runningCustomWorkflows.has(workflow.id);

                return (
                  <div
                    key={workflow.id}
                    className="bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden"
                  >
                    {/* Header */}
                    <div className="p-6 border-b border-zinc-700">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-2xl">{workflow.icon}</div>
                          <div>
                            <h2 className="text-lg font-semibold">{workflow.name}</h2>
                            {workflow.description && (
                              <p className="text-sm text-zinc-400">{workflow.description}</p>
                            )}
                          </div>
                        </div>

                        {/* Enable Toggle */}
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={workflow.enabled}
                            onChange={() => toggleCustomWorkflow(workflow)}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-zinc-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-500"></div>
                          <span className="ms-3 text-sm font-medium text-zinc-400">
                            {workflow.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </label>
                      </div>
                    </div>

                    {/* Prompt Preview */}
                    <div className="p-6 border-b border-zinc-700 bg-zinc-800/50">
                      <div className="mb-4">
                        <label className="block text-xs text-zinc-500 mb-1">Prompt</label>
                        <p className="text-sm text-zinc-300 bg-zinc-700/50 rounded-lg p-3 font-mono">
                          {workflow.prompt.length > 200
                            ? workflow.prompt.substring(0, 200) + '...'
                            : workflow.prompt}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-4 items-center">
                        <div className="text-sm text-zinc-400">
                          <span className="text-zinc-500">Schedule:</span>{' '}
                          {workflow.frequency === 'manual' ? 'Manual only' :
                           workflow.frequency === 'once' ? (
                             workflow.scheduled_at
                               ? `One-time: ${new Date(workflow.scheduled_at).toLocaleString()}`
                               : 'One-time (completed)'
                           ) :
                           workflow.frequency === 'hourly' ? 'Every hour' :
                           workflow.frequency === '6hours' ? 'Every 6 hours' :
                           workflow.frequency === 'daily' ? 'Daily (8 AM)' :
                           workflow.frequency === 'weekly' ? 'Weekly (Monday)' :
                           workflow.frequency}
                        </div>

                        {workflow.run_count > 0 && (
                          <div className="text-sm text-zinc-400">
                            <span className="text-zinc-500">Runs:</span> {workflow.run_count}
                          </div>
                        )}

                        {/* Action Buttons */}
                        <div className="ml-auto flex items-center gap-2">
                          <button
                            onClick={() => openEditModal(workflow)}
                            className="px-3 py-1.5 text-sm bg-zinc-700 hover:bg-zinc-600 rounded-lg transition-colors"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deleteWorkflow(workflow.id)}
                            className="px-3 py-1.5 text-sm bg-zinc-700 hover:bg-red-600 rounded-lg transition-colors"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => runCustomWorkflow(workflow.id)}
                            disabled={isRunning}
                            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg font-medium transition-colors ${
                              isRunning
                                ? 'bg-zinc-600 text-zinc-400 cursor-not-allowed'
                                : 'bg-orange-500 hover:bg-orange-600 text-white'
                            }`}
                          >
                            {isRunning ? (
                              <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Running...
                              </>
                            ) : (
                              <>
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                </svg>
                                Run Now
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Last run info */}
                      {workflow.last_run_at && (
                        <div className="mt-4 text-sm text-zinc-400">
                          Last run: {formatDate(workflow.last_run_at)}
                          {workflow.next_run_at && workflow.enabled && (
                            <span className="ml-4">
                              Next run: {formatDate(workflow.next_run_at)}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Recent Runs */}
                    {runs.length > 0 && (
                      <div className="p-6">
                        <h3 className="text-sm font-medium text-zinc-400 mb-3">Recent Runs</h3>
                        <div className="space-y-2">
                          {runs.slice(0, 5).map(run => (
                            <button
                              key={run.id}
                              onClick={() => {
                                setSelectedRun(run);
                                setShowRunModal(true);
                              }}
                              className="w-full flex items-center justify-between text-sm py-2 px-2 -mx-2 border-b border-zinc-700/50 last:border-0 rounded hover:bg-zinc-700/50 transition-colors text-left"
                            >
                              <div className="flex items-center gap-3">
                                <span className={`w-2 h-2 rounded-full ${
                                  run.status === 'completed' ? 'bg-green-500' :
                                  run.status === 'failed' ? 'bg-red-500' :
                                  run.status === 'running' ? 'bg-yellow-500 animate-pulse' :
                                  'bg-zinc-500'
                                }`} />
                                <span className="text-zinc-300">
                                  {formatDate(run.started_at)}
                                </span>
                                <span className="text-zinc-500">
                                  ({run.trigger_type})
                                </span>
                              </div>

                              <div className="flex items-center gap-4">
                                {run.duration_ms && (
                                  <span className="text-zinc-500 text-xs">
                                    {formatDuration(run.duration_ms)}
                                  </span>
                                )}
                                <span className={`text-xs px-2 py-0.5 rounded ${
                                  run.status === 'completed' ? 'bg-green-900/50 text-green-400' :
                                  run.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                                  'bg-zinc-700 text-zinc-400'
                                }`}>
                                  {run.status}
                                </span>
                                <span className="text-zinc-500 text-xs">→</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-800 rounded-lg border border-zinc-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-zinc-700">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold">
                  {editingWorkflow ? 'Edit Workflow' : 'Create Custom Workflow'}
                </h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-zinc-400 hover:text-white"
                >
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Name</label>
                <input
                  type="text"
                  value={modalData.name}
                  onChange={(e) => setModalData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Daily Inbox Summary"
                  className="w-full bg-zinc-700 border border-zinc-600 rounded-lg px-4 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500"
                />
              </div>

              {/* Icon */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Icon</label>
                <div className="flex flex-wrap gap-2">
                  {WORKFLOW_ICONS.map(icon => (
                    <button
                      key={icon}
                      onClick={() => setModalData(prev => ({ ...prev, icon }))}
                      className={`text-2xl p-2 rounded-lg transition-colors ${
                        modalData.icon === icon
                          ? 'bg-orange-500'
                          : 'bg-zinc-700 hover:bg-zinc-600'
                      }`}
                    >
                      {icon}
                    </button>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Description (optional)</label>
                <input
                  type="text"
                  value={modalData.description}
                  onChange={(e) => setModalData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of what this workflow does"
                  className="w-full bg-zinc-700 border border-zinc-600 rounded-lg px-4 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500"
                />
              </div>

              {/* Prompt */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">What should this workflow do?</label>
                <textarea
                  value={modalData.prompt}
                  onChange={(e) => setModalData(prev => ({ ...prev, prompt: e.target.value }))}
                  placeholder="e.g., Check my last 20 unread emails and give me a summary of what needs my attention. Prioritize emails from customers and internal team over marketing emails."
                  rows={4}
                  className="w-full bg-zinc-700 border border-zinc-600 rounded-lg px-4 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500 resize-none"
                />
                <p className="mt-1 text-xs text-zinc-500">
                  Tip: Write like you're chatting with EspressoBot
                </p>
              </div>

              {/* Schedule */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Schedule</label>
                <div className="flex flex-wrap gap-3 items-start">
                  <select
                    value={modalData.frequency}
                    onChange={(e) => setModalData(prev => ({ ...prev, frequency: e.target.value }))}
                    className="bg-zinc-700 border border-zinc-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-orange-500"
                  >
                    <option value="manual">Manual only</option>
                    <option value="once">One-time (scheduled)</option>
                    <option value="hourly">Every hour</option>
                    <option value="6hours">Every 6 hours</option>
                    <option value="daily">Daily (8 AM)</option>
                    <option value="weekly">Weekly (Monday)</option>
                  </select>

                  {/* DateTime picker for one-time scheduled runs */}
                  {modalData.frequency === 'once' && (
                    <div className="flex-1 min-w-[200px]">
                      <input
                        type="datetime-local"
                        value={modalData.scheduled_at}
                        onChange={(e) => setModalData(prev => ({ ...prev, scheduled_at: e.target.value }))}
                        min={new Date().toISOString().slice(0, 16)}
                        className="w-full bg-zinc-700 border border-zinc-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-orange-500"
                      />
                      <p className="mt-1 text-xs text-zinc-500">
                        Select when to run this workflow
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Notifications */}
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={modalData.notify_on_complete}
                    onChange={(e) => setModalData(prev => ({ ...prev, notify_on_complete: e.target.checked }))}
                    className="w-4 h-4 accent-orange-500"
                  />
                  <span className="text-sm text-zinc-300">Notify me when complete</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={modalData.notify_on_failure}
                    onChange={(e) => setModalData(prev => ({ ...prev, notify_on_failure: e.target.checked }))}
                    className="w-4 h-4 accent-orange-500"
                  />
                  <span className="text-sm text-zinc-300">Notify me on failure</span>
                </label>
              </div>
            </div>

            <div className="p-6 border-t border-zinc-700 flex justify-end gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveWorkflow}
                disabled={saving || !modalData.name.trim() || !modalData.prompt.trim()}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  saving || !modalData.name.trim() || !modalData.prompt.trim()
                    ? 'bg-zinc-600 text-zinc-400 cursor-not-allowed'
                    : 'bg-orange-500 hover:bg-orange-600 text-white'
                }`}
              >
                {saving ? 'Saving...' : (editingWorkflow ? 'Save Changes' : 'Create Workflow')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Run Result Modal */}
      {showRunModal && selectedRun && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-800 rounded-lg border border-zinc-700 w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-6 border-b border-zinc-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full ${
                    selectedRun.status === 'completed' ? 'bg-green-500' :
                    selectedRun.status === 'failed' ? 'bg-red-500' :
                    'bg-zinc-500'
                  }`} />
                  <h2 className="text-xl font-bold">
                    Run Details
                  </h2>
                  <span className={`text-sm px-2 py-0.5 rounded ${
                    selectedRun.status === 'completed' ? 'bg-green-900/50 text-green-400' :
                    selectedRun.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                    'bg-zinc-700 text-zinc-400'
                  }`}>
                    {selectedRun.status}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setShowRunModal(false);
                    setSelectedRun(null);
                  }}
                  className="text-zinc-400 hover:text-white transition-colors text-2xl leading-none"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              {/* Run Metadata */}
              <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
                <div>
                  <span className="text-zinc-500">Started:</span>
                  <span className="text-zinc-300 ml-2">{formatDate(selectedRun.started_at)}</span>
                </div>
                {selectedRun.completed_at && (
                  <div>
                    <span className="text-zinc-500">Completed:</span>
                    <span className="text-zinc-300 ml-2">{formatDate(selectedRun.completed_at)}</span>
                  </div>
                )}
                <div>
                  <span className="text-zinc-500">Trigger:</span>
                  <span className="text-zinc-300 ml-2">{selectedRun.trigger_type}</span>
                </div>
                {selectedRun.duration_ms && (
                  <div>
                    <span className="text-zinc-500">Duration:</span>
                    <span className="text-zinc-300 ml-2">{formatDuration(selectedRun.duration_ms)}</span>
                  </div>
                )}
              </div>

              {/* Error Message */}
              {selectedRun.error_message && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-red-400 mb-2">Error</h3>
                  <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-4 text-red-300 text-sm font-mono whitespace-pre-wrap">
                    {selectedRun.error_message}
                  </div>
                </div>
              )}

              {/* Result/Response */}
              {selectedRun.result && (
                <div>
                  <h3 className="text-sm font-medium text-zinc-400 mb-2">Result</h3>

                  {/* Show response text for custom workflows with markdown rendering */}
                  {selectedRun.result.response && (
                    <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4 text-zinc-300 text-sm max-h-[500px] overflow-y-auto prose prose-invert prose-sm max-w-none
                      prose-headings:text-zinc-200 prose-headings:font-semibold
                      prose-h1:text-xl prose-h1:border-b prose-h1:border-zinc-700 prose-h1:pb-2
                      prose-h2:text-lg prose-h2:mt-4
                      prose-h3:text-base prose-h3:mt-3
                      prose-p:text-zinc-300 prose-p:leading-relaxed
                      prose-strong:text-zinc-200
                      prose-code:bg-zinc-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-orange-300
                      prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-700
                      prose-ul:list-disc prose-ul:ml-4
                      prose-ol:list-decimal prose-ol:ml-4
                      prose-li:text-zinc-300
                      prose-a:text-orange-400 prose-a:no-underline hover:prose-a:underline
                      prose-table:border-collapse prose-th:bg-zinc-800 prose-th:px-3 prose-th:py-2 prose-th:border prose-th:border-zinc-700
                      prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-zinc-700
                    ">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {selectedRun.result.response}
                      </ReactMarkdown>
                    </div>
                  )}

                  {/* Show structured data for built-in workflows */}
                  {!selectedRun.result.response && (
                    <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
                      {selectedRun.result.emails_processed !== undefined && (
                        <div className="text-zinc-300 mb-2">
                          <span className="text-zinc-500">Emails processed:</span> {selectedRun.result.emails_processed}
                        </div>
                      )}
                      {selectedRun.result.skipped !== undefined && (
                        <div className="text-zinc-300 mb-2">
                          <span className="text-zinc-500">Skipped:</span> {selectedRun.result.skipped}
                        </div>
                      )}
                      {selectedRun.result.labels_applied && Object.keys(selectedRun.result.labels_applied).length > 0 && (
                        <div className="text-zinc-300 mb-2">
                          <span className="text-zinc-500">Labels applied:</span>
                          <div className="mt-1 flex flex-wrap gap-2">
                            {Object.entries(selectedRun.result.labels_applied as Record<string, number>).map(([label, count]) => (
                              <span key={label} className="px-2 py-1 bg-zinc-800 rounded text-xs">
                                {label}: <span className="text-green-400">{count}</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedRun.result.message && (
                        <div className="text-zinc-400 text-sm">
                          {selectedRun.result.message}
                        </div>
                      )}
                      {/* Fallback: show raw JSON for any other result structure */}
                      {!selectedRun.result.emails_processed && !selectedRun.result.labels_applied && !selectedRun.result.message && (
                        <pre className="text-zinc-300 text-sm font-mono whitespace-pre-wrap overflow-x-auto">
                          {JSON.stringify(selectedRun.result, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* No result */}
              {!selectedRun.result && !selectedRun.error_message && (
                <div className="text-zinc-500 text-center py-8">
                  No result data available for this run.
                </div>
              )}
            </div>

            <div className="p-6 border-t border-zinc-700 flex justify-end">
              <button
                onClick={() => {
                  setShowRunModal(false);
                  setSelectedRun(null);
                }}
                className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
