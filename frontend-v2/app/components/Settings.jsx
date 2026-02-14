import React, { useState, useEffect } from 'react';
import {
  User,
  Moon,
  Sun,
  Check,
  Cpu,
  Zap,
  DollarSign,
  Brain,
  Shield,
  Server,
  Monitor,
  TrendingUp,
  Link as LinkIcon,
  Unlink,
  FileText,
  Loader2,
  AlertTriangle,
  Key,
  X,
} from 'lucide-react';
import { Link, useSearchParams } from 'react-router';
import { Button } from './catalyst/button';
import { Switch } from '@headlessui/react';
import { useTheme } from '../context/ThemeContext';
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogDescription,
  DialogTitle,
} from './catalyst/dialog';

export default function Settings({ authToken, user, setUser }) {
  // Theme context
  const { theme, setTheme, resolvedTheme } = useTheme();

  // URL params (for Upstox callback status)
  const [searchParams] = useSearchParams();

  // State
  const [saveStatus, setSaveStatus] = useState({ show: false, message: '', type: '' });
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('claude-haiku-4.5');
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [hitlEnabled, setHitlEnabled] = useState(true); // Default to approval mode

  // Trading state
  const [tradingMode, setTradingMode] = useState('paper');
  const [upstoxConnected, setUpstoxConnected] = useState(false);
  const [upstoxUserId, setUpstoxUserId] = useState(null);
  const [isLoadingTrading, setIsLoadingTrading] = useState(true);
  const [isSwitchingMode, setIsSwitchingMode] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [showLiveConfirmDialog, setShowLiveConfirmDialog] = useState(false);

  // Upstox API credentials state
  const [hasOwnCredentials, setHasOwnCredentials] = useState(false);
  const [credApiKey, setCredApiKey] = useState('');
  const [credApiSecret, setCredApiSecret] = useState('');
  const [isSavingCreds, setIsSavingCreds] = useState(false);

  // Fetch available models and user preference
  useEffect(() => {
    const fetchModels = async () => {
      try {
        // Fetch available models
        const modelsRes = await fetch('/api/models');
        const modelsData = await modelsRes.json();
        setModels(modelsData.models || []);

        // Fetch user's current preference
        if (authToken) {
          const prefRes = await fetch('/api/user/model-preference', {
            headers: { Authorization: `Bearer ${authToken}` }
          });
          const prefData = await prefRes.json();
          setSelectedModel(prefData.preferred_model || 'claude-haiku-4.5');
        }
      } catch (err) {
        console.error('Failed to fetch models:', err);
      } finally {
        setIsLoadingModels(false);
      }
    };

    fetchModels();
  }, [authToken]);

  // Fetch HITL preference
  useEffect(() => {
    const fetchHITLPreference = async () => {
      if (!authToken) return;

      try {
        const res = await fetch('/api/auth/preferences', {
          headers: { Authorization: `Bearer ${authToken}` }
        });
        const data = await res.json();
        setHitlEnabled(data.hitl_enabled ?? true); // Default to approval mode
      } catch (err) {
        console.error('Failed to fetch HITL preference:', err);
      }
    };

    fetchHITLPreference();
  }, [authToken]);

  // Fetch Upstox/trading status
  useEffect(() => {
    const fetchTradingStatus = async () => {
      if (!authToken) return;

      try {
        const res = await fetch('/api/auth/upstox/status', {
          headers: { Authorization: `Bearer ${authToken}` }
        });
        const data = await res.json();
        setTradingMode(data.trading_mode || 'paper');
        setUpstoxConnected(data.connected);
        setUpstoxUserId(data.upstox_user_id);
        setHasOwnCredentials(data.has_own_credentials || false);
      } catch (err) {
        console.error('Failed to fetch trading status:', err);
      } finally {
        setIsLoadingTrading(false);
      }
    };

    fetchTradingStatus();

    // Show success toast if redirected from Upstox callback
    if (searchParams.get('upstox') === 'connected') {
      showSaveStatus('Upstox connected successfully!', 'success');
      // Clean up URL
      window.history.replaceState({}, '', '/settings');
    }
  }, [authToken, searchParams]);

  // Theme selection handler
  const handleThemeChange = (newTheme) => {
    setTheme(newTheme);
    const themeNames = {
      light: 'Light mode',
      dark: 'Dark mode',
      system: 'System theme'
    };
    showSaveStatus(`${themeNames[newTheme]} enabled`, 'success');
  };

  // HITL toggle handler
  const handleToggleHITL = async () => {
    const newMode = !hitlEnabled;

    try {
      const res = await fetch('/api/auth/preferences/hitl', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ enabled: newMode })
      });

      if (res.ok) {
        setHitlEnabled(newMode);
        showSaveStatus(
          newMode ? 'Approval mode enabled' : 'Auto mode enabled',
          'success'
        );
      } else {
        showSaveStatus('Failed to update approval mode', 'error');
      }
    } catch (err) {
      console.error('Failed to update HITL preference:', err);
      showSaveStatus('Failed to update approval mode', 'error');
    }
  };

  // Trading mode handlers
  const handleTradingModeChange = async (newMode) => {
    if (newMode === 'live' && !upstoxConnected) {
      // Need to connect Upstox first
      window.location.href = '/api/auth/upstox/authorize';
      return;
    }

    if (newMode === 'live' && tradingMode === 'paper') {
      // Show confirmation dialog for switching to live
      setShowLiveConfirmDialog(true);
      return;
    }

    // Direct switch (or switching to paper)
    await switchTradingMode(newMode);
  };

  const switchTradingMode = async (newMode) => {
    setIsSwitchingMode(true);
    try {
      const res = await fetch('/api/auth/upstox/trading-mode', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ mode: newMode })
      });

      if (res.ok) {
        const data = await res.json();
        setTradingMode(data.trading_mode);
        setShowLiveConfirmDialog(false);
        showSaveStatus(
          newMode === 'live' ? 'Switched to Live Trading' : 'Switched to Paper Trading',
          'success'
        );
      } else {
        const error = await res.json();
        showSaveStatus(error.detail || 'Failed to switch trading mode', 'error');
      }
    } catch (err) {
      console.error('Failed to switch trading mode:', err);
      showSaveStatus('Failed to switch trading mode', 'error');
    } finally {
      setIsSwitchingMode(false);
    }
  };

  const handleDisconnectUpstox = async () => {
    if (!confirm('Are you sure you want to disconnect your Upstox account? This will switch you back to paper trading.')) {
      return;
    }

    setIsDisconnecting(true);
    try {
      const res = await fetch('/api/auth/upstox/disconnect', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (res.ok) {
        setUpstoxConnected(false);
        setUpstoxUserId(null);
        setTradingMode('paper');
        showSaveStatus('Upstox disconnected', 'success');
      } else {
        showSaveStatus('Failed to disconnect Upstox', 'error');
      }
    } catch (err) {
      console.error('Failed to disconnect Upstox:', err);
      showSaveStatus('Failed to disconnect Upstox', 'error');
    } finally {
      setIsDisconnecting(false);
    }
  };

  // Upstox credentials handlers
  const handleSaveCredentials = async () => {
    if (!credApiKey.trim() || !credApiSecret.trim()) {
      showSaveStatus('Both API Key and Secret are required', 'error');
      return;
    }
    setIsSavingCreds(true);
    try {
      const res = await fetch('/api/auth/upstox/credentials', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ api_key: credApiKey.trim(), api_secret: credApiSecret.trim() })
      });
      if (res.ok) {
        setHasOwnCredentials(true);
        setCredApiKey('');
        setCredApiSecret('');
        showSaveStatus('Upstox API credentials saved', 'success');
      } else {
        const error = await res.json();
        showSaveStatus(error.detail || 'Failed to save credentials', 'error');
      }
    } catch (err) {
      console.error('Failed to save credentials:', err);
      showSaveStatus('Failed to save credentials', 'error');
    } finally {
      setIsSavingCreds(false);
    }
  };

  const handleClearCredentials = async () => {
    try {
      const res = await fetch('/api/auth/upstox/credentials', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (res.ok) {
        setHasOwnCredentials(false);
        showSaveStatus('Credentials cleared — will use default app credentials', 'success');
      }
    } catch (err) {
      console.error('Failed to clear credentials:', err);
    }
  };

  // Model selection handler
  const handleModelChange = async (modelId) => {
    try {
      const res = await fetch('/api/user/model-preference', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ preferred_model: modelId })
      });

      if (res.ok) {
        setSelectedModel(modelId);
        const modelName = models.find(m => m.id === modelId)?.name || modelId;
        showSaveStatus(`Switched to ${modelName}`, 'success');
      } else {
        showSaveStatus('Failed to update model preference', 'error');
      }
    } catch (err) {
      console.error('Failed to update model:', err);
      showSaveStatus('Failed to update model preference', 'error');
    }
  };

  // Show save status
  const showSaveStatus = (message, type) => {
    setSaveStatus({ show: true, message, type });
    setTimeout(() => setSaveStatus({ show: false, message: '', type: '' }), 3000);
  };

  // Helper to get icon for speed/intelligence indicators
  const getSpeedIcon = (speed) => {
    switch (speed) {
      case 'fast': return <Zap className="w-4 h-4 text-green-600 dark:text-green-400" />;
      case 'medium': return <Zap className="w-4 h-4 text-yellow-600 dark:text-yellow-400" />;
      case 'slow': return <Zap className="w-4 h-4 text-orange-600 dark:text-orange-400" />;
      default: return null;
    }
  };

  const getIntelligenceIcon = (intelligence) => {
    switch (intelligence) {
      case 'frontier': return <Brain className="w-4 h-4 text-purple-600 dark:text-purple-400" />;
      case 'very-high': return <Brain className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
      case 'high': return <Brain className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />;
      default: return null;
    }
  };

  return (
    <div className="h-screen overflow-y-auto bg-white dark:bg-zinc-950">
      <div className="max-w-5xl mx-auto p-6 space-y-8">
        {/* Header */}
        <div className="border-b border-zinc-200 dark:border-zinc-800 pb-6">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            Settings
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400 mt-2">
            Manage your account settings and preferences
          </p>
        </div>

        {/* Save Status Toast */}
        {saveStatus.show && (
          <div
            className={`fixed top-4 right-4 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 transition-all duration-200 ${
              saveStatus.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
                : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
            }`}
          >
            <Check className="w-5 h-5" />
            <span className="text-sm font-medium">{saveStatus.message}</span>
          </div>
        )}

        {/* Appearance Section */}
        <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
              {resolvedTheme === 'dark' ? (
                <Moon className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
              ) : (
                <Sun className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
              )}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Appearance
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Customize the look and feel of the interface
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
              Select your preferred color theme. System will automatically match your device settings.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Light Theme Option */}
              <button
                onClick={() => handleThemeChange('light')}
                className={`relative p-4 rounded-xl border-2 transition-all duration-200 ${
                  theme === 'light'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                    : 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/50'
                }`}
              >
                <div className="flex flex-col items-center gap-3">
                  <div className={`p-3 rounded-xl ${
                    theme === 'light'
                      ? 'bg-blue-100 dark:bg-blue-500/20'
                      : 'bg-zinc-100 dark:bg-zinc-700'
                  }`}>
                    <Sun className={`w-6 h-6 ${
                      theme === 'light'
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-zinc-600 dark:text-zinc-400'
                    }`} />
                  </div>
                  <div className="text-center">
                    <div className={`font-medium ${
                      theme === 'light'
                        ? 'text-blue-900 dark:text-blue-100'
                        : 'text-zinc-900 dark:text-zinc-100'
                    }`}>
                      Light
                    </div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      Always light
                    </div>
                  </div>
                </div>
                {theme === 'light' && (
                  <div className="absolute top-2 right-2">
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </div>
                  </div>
                )}
              </button>

              {/* Dark Theme Option */}
              <button
                onClick={() => handleThemeChange('dark')}
                className={`relative p-4 rounded-xl border-2 transition-all duration-200 ${
                  theme === 'dark'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                    : 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/50'
                }`}
              >
                <div className="flex flex-col items-center gap-3">
                  <div className={`p-3 rounded-xl ${
                    theme === 'dark'
                      ? 'bg-blue-100 dark:bg-blue-500/20'
                      : 'bg-zinc-100 dark:bg-zinc-700'
                  }`}>
                    <Moon className={`w-6 h-6 ${
                      theme === 'dark'
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-zinc-600 dark:text-zinc-400'
                    }`} />
                  </div>
                  <div className="text-center">
                    <div className={`font-medium ${
                      theme === 'dark'
                        ? 'text-blue-900 dark:text-blue-100'
                        : 'text-zinc-900 dark:text-zinc-100'
                    }`}>
                      Dark
                    </div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      Always dark
                    </div>
                  </div>
                </div>
                {theme === 'dark' && (
                  <div className="absolute top-2 right-2">
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </div>
                  </div>
                )}
              </button>

              {/* System Theme Option */}
              <button
                onClick={() => handleThemeChange('system')}
                className={`relative p-4 rounded-xl border-2 transition-all duration-200 ${
                  theme === 'system'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                    : 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/50'
                }`}
              >
                <div className="flex flex-col items-center gap-3">
                  <div className={`p-3 rounded-xl ${
                    theme === 'system'
                      ? 'bg-blue-100 dark:bg-blue-500/20'
                      : 'bg-zinc-100 dark:bg-zinc-700'
                  }`}>
                    <Monitor className={`w-6 h-6 ${
                      theme === 'system'
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-zinc-600 dark:text-zinc-400'
                    }`} />
                  </div>
                  <div className="text-center">
                    <div className={`font-medium ${
                      theme === 'system'
                        ? 'text-blue-900 dark:text-blue-100'
                        : 'text-zinc-900 dark:text-zinc-100'
                    }`}>
                      System
                    </div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      Match device
                    </div>
                  </div>
                </div>
                {theme === 'system' && (
                  <div className="absolute top-2 right-2">
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </div>
                  </div>
                )}
              </button>
            </div>

            {/* Current theme indicator */}
            <div className="mt-4 p-3 rounded-lg bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700">
              <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                <div className={`w-2 h-2 rounded-full ${resolvedTheme === 'dark' ? 'bg-indigo-500' : 'bg-amber-500'}`} />
                <span>
                  Currently using <span className="font-medium text-zinc-900 dark:text-zinc-100">{resolvedTheme}</span> theme
                  {theme === 'system' && <span className="text-zinc-500"> (based on your system preference)</span>}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Human-in-the-Loop Section */}
        <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
              <Shield className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Approval Mode
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Control when the assistant requires your approval
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
            <div className="flex-1 mr-4">
              <div className="font-medium text-zinc-900 dark:text-zinc-100">
                {hitlEnabled ? 'Approval Mode' : 'Auto Mode'}
              </div>
              <div className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                {hitlEnabled
                  ? 'Approve write operations before execution (safer)'
                  : 'Execute all operations automatically (faster)'}
              </div>
              <div className="text-xs text-zinc-500 dark:text-zinc-500 mt-2">
                {hitlEnabled
                  ? 'You\'ll be asked to approve file writes, bash commands, and edits'
                  : 'Operations will run immediately without approval prompts'}
              </div>
            </div>
            <Switch
              checked={hitlEnabled}
              onChange={handleToggleHITL}
              className={`${
                hitlEnabled ? 'bg-blue-600' : 'bg-zinc-200 dark:bg-zinc-600'
              } relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 dark:focus:ring-offset-zinc-900`}
            >
              <span
                className={`${
                  hitlEnabled ? 'translate-x-6' : 'translate-x-1'
                } inline-block h-5 w-5 transform rounded-full bg-white transition-transform shadow-sm`}
              />
            </Switch>
          </div>
        </section>

        {/* Trading & Upstox Section */}
        <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
              <TrendingUp className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Trading Settings
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Manage your broker connection and trading mode
              </p>
            </div>
          </div>

          {isLoadingTrading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
            </div>
          ) : (
            <div className="space-y-4">
              {/* Upstox API Credentials */}
              <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-2 mb-3">
                  <Key className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
                  <div className="font-medium text-zinc-900 dark:text-zinc-100">
                    Upstox API Credentials
                  </div>
                  {hasOwnCredentials && (
                    <span className="ml-auto px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                      Saved
                    </span>
                  )}
                </div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
                  Enter your own Upstox API credentials from the{' '}
                  <a
                    href="https://account.upstox.com/developer/apps"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 underline"
                  >
                    Upstox Developer Console
                  </a>
                  . Required if the default app isn't approved for your account.
                </p>
                {hasOwnCredentials ? (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                    <span className="text-sm text-green-700 dark:text-green-300">
                      Using your own API credentials
                    </span>
                    <Button
                      variant="outline"
                      onClick={handleClearCredentials}
                      className="text-xs"
                    >
                      <X className="w-3 h-3 mr-1" />
                      Clear
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                        API Key
                      </label>
                      <input
                        type="text"
                        value={credApiKey}
                        onChange={(e) => setCredApiKey(e.target.value)}
                        placeholder="Enter your Upstox API Key"
                        className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                        API Secret
                      </label>
                      <input
                        type="password"
                        value={credApiSecret}
                        onChange={(e) => setCredApiSecret(e.target.value)}
                        placeholder="Enter your Upstox API Secret"
                        className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <Button
                      onClick={handleSaveCredentials}
                      disabled={isSavingCreds || !credApiKey.trim() || !credApiSecret.trim()}
                    >
                      {isSavingCreds ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          Saving...
                        </>
                      ) : (
                        'Save Credentials'
                      )}
                    </Button>
                  </div>
                )}
              </div>

              {/* Upstox Connection Status */}
              <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${upstoxConnected ? 'bg-green-100 dark:bg-green-900/30' : 'bg-zinc-100 dark:bg-zinc-700'}`}>
                      {upstoxConnected ? (
                        <LinkIcon className="w-5 h-5 text-green-600 dark:text-green-400" />
                      ) : (
                        <Unlink className="w-5 h-5 text-zinc-500 dark:text-zinc-400" />
                      )}
                    </div>
                    <div>
                      <div className="font-medium text-zinc-900 dark:text-zinc-100">
                        Upstox Account
                      </div>
                      <div className="text-sm text-zinc-600 dark:text-zinc-400">
                        {upstoxConnected ? (
                          <>Connected as <span className="font-mono text-xs">{upstoxUserId}</span></>
                        ) : (
                          'Not connected'
                        )}
                      </div>
                    </div>
                  </div>
                  {upstoxConnected ? (
                    <Button
                      variant="outline"
                      onClick={handleDisconnectUpstox}
                      disabled={isDisconnecting}
                      className="text-red-600 dark:text-red-400 border-red-200 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      {isDisconnecting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        'Disconnect'
                      )}
                    </Button>
                  ) : (
                    <Button
                      onClick={async () => {
                        const res = await fetch('/api/auth/upstox/authorize-url', {
                          headers: { Authorization: `Bearer ${authToken}` }
                        });
                        if (res.ok) {
                          const data = await res.json();
                          window.location.href = data.url;
                        }
                      }}
                    >
                      Connect Upstox
                    </Button>
                  )}
                </div>
              </div>

              {/* Trading Mode Selection */}
              <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div className="font-medium text-zinc-900 dark:text-zinc-100 mb-3">
                  Trading Mode
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {/* Paper Trading Option */}
                  <button
                    onClick={() => handleTradingModeChange('paper')}
                    disabled={isSwitchingMode}
                    className={`relative p-4 rounded-xl border-2 transition-all duration-200 ${
                      tradingMode === 'paper'
                        ? 'border-amber-500 bg-amber-50 dark:bg-amber-500/10'
                        : 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600'
                    }`}
                  >
                    <div className="flex flex-col items-center gap-2">
                      <FileText className={`w-6 h-6 ${tradingMode === 'paper' ? 'text-amber-600 dark:text-amber-400' : 'text-zinc-500 dark:text-zinc-400'}`} />
                      <div className={`font-medium ${tradingMode === 'paper' ? 'text-amber-700 dark:text-amber-300' : 'text-zinc-700 dark:text-zinc-300'}`}>
                        Paper Trading
                      </div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">
                        Simulated orders
                      </div>
                    </div>
                    {tradingMode === 'paper' && (
                      <div className="absolute top-2 right-2">
                        <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center">
                          <Check className="w-3 h-3 text-white" />
                        </div>
                      </div>
                    )}
                  </button>

                  {/* Live Trading Option */}
                  <button
                    onClick={() => handleTradingModeChange('live')}
                    disabled={isSwitchingMode || !upstoxConnected}
                    className={`relative p-4 rounded-xl border-2 transition-all duration-200 ${
                      tradingMode === 'live'
                        ? 'border-red-500 bg-red-50 dark:bg-red-500/10'
                        : upstoxConnected
                          ? 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600'
                          : 'border-zinc-200 dark:border-zinc-700 opacity-50 cursor-not-allowed'
                    }`}
                  >
                    <div className="flex flex-col items-center gap-2">
                      <Zap className={`w-6 h-6 ${tradingMode === 'live' ? 'text-red-600 dark:text-red-400' : 'text-zinc-500 dark:text-zinc-400'}`} />
                      <div className={`font-medium ${tradingMode === 'live' ? 'text-red-700 dark:text-red-300' : 'text-zinc-700 dark:text-zinc-300'}`}>
                        Live Trading
                      </div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">
                        {upstoxConnected ? 'Real money' : 'Connect Upstox first'}
                      </div>
                    </div>
                    {tradingMode === 'live' && (
                      <div className="absolute top-2 right-2">
                        <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center animate-pulse">
                          <Check className="w-3 h-3 text-white" />
                        </div>
                      </div>
                    )}
                  </button>
                </div>

                {tradingMode === 'live' && (
                  <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                    <div className="flex items-center gap-2 text-red-700 dark:text-red-300 text-sm">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Live trading is enabled. All orders will use real money.</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Live Trading Confirmation Dialog */}
        <Dialog open={showLiveConfirmDialog} onClose={() => setShowLiveConfirmDialog(false)}>
          <DialogTitle>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              Switch to Live Trading?
            </div>
          </DialogTitle>
          <DialogDescription>
            <div className="space-y-3">
              <p>
                You're about to enable <strong>live trading</strong> with your Upstox account.
              </p>
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                <p className="text-red-700 dark:text-red-300 text-sm font-medium">
                  All orders will be executed with real money.
                </p>
                <p className="text-red-600 dark:text-red-400 text-sm mt-1">
                  Make sure you understand the risks before proceeding.
                </p>
              </div>
            </div>
          </DialogDescription>
          <DialogActions>
            <Button plain onClick={() => setShowLiveConfirmDialog(false)} disabled={isSwitchingMode}>
              Cancel
            </Button>
            <Button color="red" onClick={() => switchTradingMode('live')} disabled={isSwitchingMode}>
              {isSwitchingMode ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Switching...
                </>
              ) : (
                'Yes, Enable Live Trading'
              )}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Model Preference Section */}
        <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
              <Cpu className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                AI Model Selection
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Choose your preferred orchestrator model for chat
              </p>
            </div>
          </div>

          {isLoadingModels ? (
            <div className="text-center py-8">
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading models...</p>
            </div>
          ) : (
            <div className="space-y-3">
              {models.map((model) => {
                const isSelected = selectedModel === model.id;
                return (
                  <button
                    key={model.id}
                    onClick={() => handleModelChange(model.id)}
                    className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10'
                        : 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className={`font-semibold ${
                            isSelected
                              ? 'text-blue-900 dark:text-blue-100'
                              : 'text-zinc-900 dark:text-zinc-100'
                          }`}>
                            {model.name}
                          </h3>
                          {isSelected && (
                            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-500 text-white">
                              Active
                            </span>
                          )}
                        </div>
                        <p className={`text-sm mb-3 ${
                          isSelected
                            ? 'text-blue-700 dark:text-blue-300'
                            : 'text-zinc-600 dark:text-zinc-400'
                        }`}>
                          {model.description}
                        </p>

                        <div className="flex flex-wrap gap-3 text-xs">
                          <div className="flex items-center gap-1">
                            {getSpeedIcon(model.speed)}
                            <span className="text-zinc-600 dark:text-zinc-400 capitalize">{model.speed}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            {getIntelligenceIcon(model.intelligence)}
                            <span className="text-zinc-600 dark:text-zinc-400 capitalize">{model.intelligence.replace('-', ' ')}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <DollarSign className="w-4 h-4 text-green-600 dark:text-green-400" />
                            <span className="text-zinc-600 dark:text-zinc-400">{model.cost_input}/{model.cost_output}</span>
                          </div>
                        </div>

                        <div className="mt-2 flex flex-wrap gap-2">
                          {model.recommended_for.slice(0, 3).map((use) => (
                            <span
                              key={use}
                              className={`px-2 py-0.5 text-xs rounded-full ${
                                isSelected
                                  ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                                  : 'bg-zinc-100 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300'
                              }`}
                            >
                              {use}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="text-right text-xs text-zinc-500 dark:text-zinc-400">
                        <div>{(model.context_window / 1000).toFixed(0)}K context</div>
                        <div className="mt-1">{(model.max_output / 1000).toFixed(0)}K output</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        {/* MCP Servers Section */}
        <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
              <Server className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                MCP Servers
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Extend orchestrator capabilities with Model Context Protocol servers
              </p>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
              Configure custom MCP servers to add specialized tools and capabilities to your AI assistant. Supports stdio, SSE, and HTTP transports.
            </p>
            <Link to="/settings/mcp">
              <Button variant="outline">
                Manage MCP Servers
              </Button>
            </Link>
          </div>
        </section>

        {/* User Profile Section */}
        <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
              <User className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                User Profile
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Manage your personal information and bio
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Name Preview */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Display Name
              </label>
              <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
                <p className="text-sm text-zinc-900 dark:text-zinc-100">{user?.name || 'Not set'}</p>
              </div>
            </div>

            {/* Email Preview */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Email Address
              </label>
              <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
                <p className="text-sm text-zinc-900 dark:text-zinc-100">{user?.email || 'Not set'}</p>
              </div>
            </div>

            {/* Bio Preview */}
            {user?.bio && (
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Bio
                </label>
                <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap">{user.bio}</p>
                </div>
              </div>
            )}

            {/* Edit Profile Button */}
            <div className="pt-2">
              <Link to="/user/profile">
                <Button variant="outline">
                  Edit Profile & Bio
                </Button>
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
