import { useState, useEffect } from 'react';
import { useNavigate, useOutletContext } from 'react-router';
import {
  Cpu,
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
  Zap,
  Brain,
  DollarSign,
  Star,
  Eye,
  EyeOff
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { requirePermission } from '../utils/route-permissions';

export async function clientLoader() {
  await requirePermission('admin.manage_users');
  return null;
}

interface AIModel {
  id: number;
  model_id: string;
  name: string;
  slug: string;
  provider: string;
  description: string;
  context_window: number;
  max_output: number;
  cost_input: string;
  cost_output: string;
  supports_thinking: boolean;
  speed: string;
  intelligence: string;
  recommended_for: string[];
  is_enabled: boolean;
  is_default: boolean;
}

interface ModelFormData {
  model_id: string;
  name: string;
  slug: string;
  provider: string;
  description: string;
  context_window: number;
  max_output: number;
  cost_input: string;
  cost_output: string;
  supports_thinking: boolean;
  speed: string;
  intelligence: string;
  recommended_for: string[];
  is_enabled: boolean;
  is_default: boolean;
}

export default function AdminModels() {
  const navigate = useNavigate();
  const { authToken }: any = useOutletContext();

  const [models, setModels] = useState<AIModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingModel, setEditingModel] = useState<AIModel | null>(null);
  const [formData, setFormData] = useState<ModelFormData>({
    model_id: '',
    name: '',
    slug: '',
    provider: 'openrouter',
    description: '',
    context_window: 128000,
    max_output: 16000,
    cost_input: '',
    cost_output: '',
    supports_thinking: false,
    speed: 'fast',
    intelligence: 'high',
    recommended_for: [],
    is_enabled: true,
    is_default: false,
  });

  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      setIsLoading(true);
      const res = await fetch('/api/admin/models', {
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to fetch models');

      const data = await res.json();
      setModels(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      const res = await fetch('/api/admin/models', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(formData)
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to create model');
      }

      await fetchModels();
      setShowForm(false);
      resetForm();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleUpdate = async () => {
    if (!editingModel) return;

    try {
      const res = await fetch(`/api/admin/models/${editingModel.model_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(formData)
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to update model');
      }

      await fetchModels();
      setShowForm(false);
      setEditingModel(null);
      resetForm();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleDelete = async (modelId: string) => {
    if (!confirm(`Are you sure you want to delete model ${modelId}?`)) return;

    try {
      const res = await fetch(`/api/admin/models/${modelId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to delete model');
      }

      await fetchModels();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleClearCache = async () => {
    if (!confirm('Clear the orchestrator cache? This will reload all model configurations.')) return;

    try {
      const res = await fetch('/api/admin/clear-model-cache', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to clear cache');
      }

      const data = await res.json();
      alert(`Success: ${data.message}\nCleared: ${data.cleared_models.join(', ')}`);
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const openEditForm = (model: AIModel) => {
    setEditingModel(model);
    setFormData({
      model_id: model.model_id,
      name: model.name,
      slug: model.slug,
      provider: model.provider,
      description: model.description,
      context_window: model.context_window,
      max_output: model.max_output,
      cost_input: model.cost_input,
      cost_output: model.cost_output,
      supports_thinking: model.supports_thinking,
      speed: model.speed,
      intelligence: model.intelligence,
      recommended_for: model.recommended_for,
      is_enabled: model.is_enabled,
      is_default: model.is_default,
    });
    setShowForm(true);
  };

  const resetForm = () => {
    setFormData({
      model_id: '',
      name: '',
      slug: '',
      provider: 'openrouter',
      description: '',
      context_window: 128000,
      max_output: 16000,
      cost_input: '',
      cost_output: '',
      supports_thinking: false,
      speed: 'fast',
      intelligence: 'high',
      recommended_for: [],
      is_enabled: true,
      is_default: false,
    });
    setEditingModel(null);
  };

  const getSpeedIcon = (speed: string) => {
    return <Zap className={`w-4 h-4 ${
      speed === 'fast' ? 'text-green-600 dark:text-green-400' :
      speed === 'medium' ? 'text-yellow-600 dark:text-yellow-400' :
      'text-orange-600 dark:text-orange-400'
    }`} />;
  };

  const getIntelligenceIcon = (intelligence: string) => {
    return <Brain className={`w-4 h-4 ${
      intelligence === 'frontier' ? 'text-purple-600 dark:text-purple-400' :
      intelligence === 'very-high' ? 'text-blue-600 dark:text-blue-400' :
      'text-zinc-600 dark:text-zinc-400'
    }`} />;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-white dark:bg-zinc-950">
        <p className="text-zinc-600 dark:text-zinc-400">Loading models...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-3">
              <Cpu className="w-8 h-8" />
              AI Model Management
            </h1>
            <p className="text-zinc-600 dark:text-zinc-400 mt-2">
              Manage available orchestrator models for the platform
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleClearCache}
            >
              Clear Cache
            </Button>
            <Button
              onClick={() => {
                resetForm();
                setShowForm(true);
              }}
            >
              <Plus className="w-4 h-4" />
              Add Model
            </Button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        {/* Model List */}
        <div className="grid gap-4">
          {models.map((model) => (
            <div
              key={model.id}
              className={`border-2 rounded-lg p-5 transition-all ${
                model.is_enabled
                  ? 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900'
                  : 'border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 opacity-60'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                      {model.name}
                    </h3>
                    {model.is_default && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 flex items-center gap-1">
                        <Star className="w-3 h-3" />
                        Default
                      </span>
                    )}
                    {model.is_enabled ? (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        Enabled
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 flex items-center gap-1">
                        <EyeOff className="w-3 h-3" />
                        Disabled
                      </span>
                    )}
                  </div>

                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
                    {model.description}
                  </p>

                  <div className="flex flex-wrap gap-3 text-xs mb-3">
                    <div className="flex items-center gap-1">
                      {getSpeedIcon(model.speed)}
                      <span className="text-zinc-600 dark:text-zinc-400 capitalize">{model.speed}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      {getIntelligenceIcon(model.intelligence)}
                      <span className="text-zinc-600 dark:text-zinc-400 capitalize">
                        {model.intelligence.replace('-', ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <DollarSign className="w-4 h-4 text-green-600 dark:text-green-400" />
                      <span className="text-zinc-600 dark:text-zinc-400">
                        {model.cost_input}/{model.cost_output}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      {model.provider}
                    </span>
                    <span className="px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      {(model.context_window / 1000).toFixed(0)}K context
                    </span>
                    <span className="px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      {(model.max_output / 1000).toFixed(0)}K output
                    </span>
                    {model.supports_thinking && (
                      <span className="px-2 py-1 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
                        Extended Thinking
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => openEditForm(model)}
                    className="p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(model.model_id)}
                    disabled={model.is_default}
                    className="p-2 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6">
              <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-6">
                {editingModel ? 'Edit Model' : 'Add New Model'}
              </h2>

              <div className="space-y-4">
                {/* Model ID */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Model ID
                  </label>
                  <input
                    type="text"
                    value={formData.model_id}
                    onChange={(e) => setFormData({ ...formData, model_id: e.target.value })}
                    disabled={!!editingModel}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 disabled:opacity-50"
                    placeholder="e.g., claude-haiku-4.5"
                  />
                </div>

                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    placeholder="e.g., Claude Haiku 4.5"
                  />
                </div>

                {/* Slug */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    API Slug
                  </label>
                  <input
                    type="text"
                    value={formData.slug}
                    onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    placeholder="e.g., claude-haiku-4-5-20251001"
                  />
                </div>

                {/* Provider */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Provider
                  </label>
                  <select
                    value={formData.provider}
                    onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                  >
                    <option value="anthropic">Anthropic (Direct API)</option>
                    <option value="openai">OpenAI (Direct API)</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="gateway">Gateway (Pydantic AI)</option>
                  </select>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    placeholder="Brief description of model capabilities"
                  />
                </div>

                {/* Technical Specs - Row */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Context Window
                    </label>
                    <input
                      type="number"
                      value={formData.context_window}
                      onChange={(e) => setFormData({ ...formData, context_window: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Max Output
                    </label>
                    <input
                      type="number"
                      value={formData.max_output}
                      onChange={(e) => setFormData({ ...formData, max_output: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    />
                  </div>
                </div>

                {/* Pricing - Row */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Cost (Input)
                    </label>
                    <input
                      type="text"
                      value={formData.cost_input}
                      onChange={(e) => setFormData({ ...formData, cost_input: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                      placeholder="$1/1M tokens"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Cost (Output)
                    </label>
                    <input
                      type="text"
                      value={formData.cost_output}
                      onChange={(e) => setFormData({ ...formData, cost_output: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                      placeholder="$5/1M tokens"
                    />
                  </div>
                </div>

                {/* Speed & Intelligence - Row */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Speed
                    </label>
                    <select
                      value={formData.speed}
                      onChange={(e) => setFormData({ ...formData, speed: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    >
                      <option value="fast">Fast</option>
                      <option value="medium">Medium</option>
                      <option value="slow">Slow</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Intelligence
                    </label>
                    <select
                      value={formData.intelligence}
                      onChange={(e) => setFormData({ ...formData, intelligence: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    >
                      <option value="high">High</option>
                      <option value="very-high">Very High</option>
                      <option value="frontier">Frontier</option>
                    </select>
                  </div>
                </div>

                {/* Checkboxes */}
                <div className="flex gap-6">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.supports_thinking}
                      onChange={(e) => setFormData({ ...formData, supports_thinking: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Supports Extended Thinking</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.is_enabled}
                      onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Enabled</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.is_default}
                      onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Set as Default</span>
                  </label>
                </div>

                {/* Actions */}
                <div className="flex gap-3 pt-4 border-t border-zinc-200 dark:border-zinc-800">
                  <Button
                    style={{ variant: 'plain' }}
                    onClick={editingModel ? handleUpdate : handleCreate}
                    className="flex-1"
                  >
                    <Check className="w-4 h-4" />
                    {editingModel ? 'Update' : 'Create'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowForm(false);
                      setEditingModel(null);
                      resetForm();
                    }}
                    className="flex-1"
                  >
                    <X className="w-4 h-4" />
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
