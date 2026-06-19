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
  Server,
  Monitor,
  TrendingUp,
  Link as LinkIcon,
  Unlink,
  Loader2,
  AlertTriangle,
  Key,
  X,
  Smartphone,
  RefreshCw,
  Fingerprint,
  Trash2,
  Plus,
  Send,
  Bell,
} from 'lucide-react';
import { Link, useSearchParams } from 'react-router';
import { Button } from './catalyst/button';
import { useTheme } from '../context/ThemeContext';
import { bufferToBase64url, base64urlToBuffer } from '../utils/webauthn';

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

  // Trading state
  const [upstoxConnected, setUpstoxConnected] = useState(false);
  const [upstoxUserId, setUpstoxUserId] = useState(null);
  const [isLoadingTrading, setIsLoadingTrading] = useState(true);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  // Upstox API credentials state
  const [hasOwnCredentials, setHasOwnCredentials] = useState(false);
  const [credApiKey, setCredApiKey] = useState('');
  const [credApiSecret, setCredApiSecret] = useState('');
  const [isSavingCreds, setIsSavingCreds] = useState(false);

  // TOTP auto-login state
  const [hasTotpCredentials, setHasTotpCredentials] = useState(false);
  const [totpMobile, setTotpMobile] = useState('');
  const [totpPin, setTotpPin] = useState('');
  const [totpSecret, setTotpSecret] = useState('');
  const [isSavingTotp, setIsSavingTotp] = useState(false);
  const [isTestingTotp, setIsTestingTotp] = useState(false);

  // Telegram state
  const TELEGRAM_CATEGORIES = [
    { key: 'monitor_fire', label: 'Monitor rule fires', desc: 'Triggers, SL/target hits, OCO completions' },
    { key: 'monitor_failure', label: 'Monitor failures', desc: 'Order rejections, stream auth issues' },
    { key: 'awakening', label: 'Scheduled awakenings', desc: 'Summary of each autonomous awakening' },
    { key: 'order_fill', label: 'Order fills', desc: 'When Upstox confirms an order fill (Phase 1.5)' },
    { key: 'system', label: 'System alerts', desc: 'TOTP failures, daemon issues, deploy notices' },
  ];
  const [telegram, setTelegram] = useState({
    configured: false,
    paired: false,
    bot_username: null,
    chat_id: null,
    notification_prefs: {},
  });
  const [telegramToken, setTelegramToken] = useState('');
  const [isSavingTelegram, setIsSavingTelegram] = useState(false);
  const [isClearingTelegram, setIsClearingTelegram] = useState(false);

  // Web Push state (native PWA notifications)
  const [push, setPush] = useState({
    enabled: false,
    device_count: 0,
    vapid_public_key: null,
    notification_prefs: {},
  });
  const [isPushBusy, setIsPushBusy] = useState(false);
  const pushSupported =
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window;

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

  // Passkey state
  const [passkeys, setPasskeys] = useState([]);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [passkeySupported, setPasskeySupported] = useState(false);

  useEffect(() => {
    setPasskeySupported(
      typeof window !== 'undefined' && !!window.PublicKeyCredential
    );
  }, []);

  useEffect(() => {
    const fetchPasskeys = async () => {
      if (!authToken) return;
      try {
        const res = await fetch('/api/auth/passkeys', {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          setPasskeys(data.passkeys || []);
        }
      } catch (err) {
        console.error('Failed to fetch passkeys:', err);
      }
    };
    fetchPasskeys();
  }, [authToken]);

  const handleRegisterPasskey = async () => {
    setPasskeyLoading(true);
    try {
      const optionsRes = await fetch('/api/auth/passkey/register/options', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (!optionsRes.ok) throw new Error('Failed to get registration options');
      const { options } = await optionsRes.json();

      const publicKeyOptions = {
        challenge: base64urlToBuffer(options.challenge),
        rp: options.rp,
        user: {
          ...options.user,
          id: base64urlToBuffer(options.user.id),
        },
        pubKeyCredParams: options.pubKeyCredParams,
        timeout: options.timeout || 60000,
        attestation: options.attestation || 'none',
        authenticatorSelection: options.authenticatorSelection,
        excludeCredentials: (options.excludeCredentials || []).map((c) => ({
          id: base64urlToBuffer(c.id),
          type: c.type,
          transports: c.transports,
        })),
      };

      const credential = await navigator.credentials.create({
        publicKey: publicKeyOptions,
      });
      if (!credential) throw new Error('No credential created');

      const response = credential.response;

      const deviceName =
        prompt(
          'Name this passkey (e.g. "MacBook Touch ID", "YubiKey"):',
          'My Passkey'
        ) || 'Passkey';

      const verifyRes = await fetch('/api/auth/passkey/register/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          credential: {
            id: credential.id,
            rawId: bufferToBase64url(credential.rawId),
            type: credential.type,
            response: {
              attestationObject: bufferToBase64url(response.attestationObject),
              clientDataJSON: bufferToBase64url(response.clientDataJSON),
              transports: response.getTransports ? response.getTransports() : [],
            },
          },
          device_name: deviceName,
        }),
      });

      if (!verifyRes.ok) {
        const errData = await verifyRes.json();
        throw new Error(errData.detail || 'Registration failed');
      }

      showSaveStatus('Passkey registered successfully', 'success');

      const listRes = await fetch('/api/auth/passkeys', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (listRes.ok) {
        const data = await listRes.json();
        setPasskeys(data.passkeys || []);
      }
    } catch (err) {
      if (err.name === 'NotAllowedError') {
        // user cancelled
      } else {
        showSaveStatus(err.message || 'Failed to register passkey', 'error');
      }
    } finally {
      setPasskeyLoading(false);
    }
  };

  const handleDeletePasskey = async (passkeyId, deviceName) => {
    if (
      !confirm(
        `Remove passkey "${deviceName}"? You won't be able to sign in with it anymore.`
      )
    )
      return;

    try {
      const res = await fetch(`/api/auth/passkeys/${passkeyId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        setPasskeys(passkeys.filter((p) => p.id !== passkeyId));
        showSaveStatus('Passkey removed', 'success');
      } else {
        showSaveStatus('Failed to remove passkey', 'error');
      }
    } catch {
      showSaveStatus('Failed to remove passkey', 'error');
    }
  };

  // Fetch Upstox/trading status
  useEffect(() => {
    const fetchTradingStatus = async () => {
      if (!authToken) return;

      try {
        const res = await fetch('/api/auth/upstox/status', {
          headers: { Authorization: `Bearer ${authToken}` }
        });
        const data = await res.json();
        setUpstoxConnected(data.connected);
        setUpstoxUserId(data.upstox_user_id);
        setHasOwnCredentials(data.has_own_credentials || false);
        setHasTotpCredentials(data.has_totp_credentials || false);
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

  // Trading mode handlers
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

  // TOTP credential handlers
  const handleSaveTotpCredentials = async () => {
    if (!totpMobile.trim() || !totpPin.trim() || !totpSecret.trim()) {
      showSaveStatus('All TOTP fields are required', 'error');
      return;
    }
    setIsSavingTotp(true);
    try {
      const res = await fetch('/api/auth/upstox/totp-credentials', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({
          mobile: totpMobile.trim(),
          pin: totpPin.trim(),
          totp_secret: totpSecret.trim(),
        })
      });
      if (res.ok) {
        setHasTotpCredentials(true);
        setTotpMobile('');
        setTotpPin('');
        setTotpSecret('');
        showSaveStatus('TOTP auto-login credentials saved', 'success');
      } else {
        const error = await res.json();
        showSaveStatus(error.detail || 'Failed to save TOTP credentials', 'error');
      }
    } catch (err) {
      console.error('Failed to save TOTP credentials:', err);
      showSaveStatus('Failed to save TOTP credentials', 'error');
    } finally {
      setIsSavingTotp(false);
    }
  };

  const handleClearTotpCredentials = async () => {
    try {
      const res = await fetch('/api/auth/upstox/totp-credentials', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (res.ok) {
        setHasTotpCredentials(false);
        showSaveStatus('TOTP credentials cleared', 'success');
      }
    } catch (err) {
      console.error('Failed to clear TOTP credentials:', err);
    }
  };

  const handleTestTotp = async () => {
    setIsTestingTotp(true);
    try {
      const res = await fetch('/api/auth/upstox/totp-test', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (data.status === 'success') {
        setUpstoxConnected(true);
        showSaveStatus('TOTP auto-login successful! Token refreshed.', 'success');
      } else {
        showSaveStatus(data.message || 'TOTP test failed', 'error');
      }
    } catch (err) {
      console.error('Failed to test TOTP:', err);
      showSaveStatus('Failed to test TOTP auto-login', 'error');
    } finally {
      setIsTestingTotp(false);
    }
  };

  // Telegram fetch + handlers
  const fetchTelegramStatus = async () => {
    if (!authToken) return;
    try {
      const res = await fetch('/api/telegram/status', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTelegram(data);
      }
    } catch (err) {
      console.error('Failed to fetch telegram status:', err);
    }
  };

  useEffect(() => {
    fetchTelegramStatus();
    // Poll while waiting for the user to /confirm pairing so the UI reflects
    // the chat_id binding without a manual refresh.
    const interval = setInterval(() => {
      // Only poll if a token is configured but pairing isn't complete yet.
      // We don't have telegram.* available in this closure, so we poll
      // unconditionally and the endpoint is cheap (single indexed lookup).
      fetchTelegramStatus();
    }, 8000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  const handleSaveTelegramToken = async () => {
    const token = telegramToken.trim();
    if (!token) {
      showSaveStatus('Bot token is required', 'error');
      return;
    }
    setIsSavingTelegram(true);
    try {
      const res = await fetch('/api/telegram/bot-token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (res.ok) {
        showSaveStatus(`Bot @${data.bot_username} configured. Now DM it /start.`, 'success');
        setTelegramToken('');
        await fetchTelegramStatus();
      } else {
        showSaveStatus(data.detail || 'Failed to save bot token', 'error');
      }
    } catch (err) {
      console.error('Failed to save telegram token:', err);
      showSaveStatus('Failed to save bot token', 'error');
    } finally {
      setIsSavingTelegram(false);
    }
  };

  const handleClearTelegramToken = async () => {
    if (!confirm('Disconnect Telegram bot? Notifications will stop.')) return;
    setIsClearingTelegram(true);
    try {
      const res = await fetch('/api/telegram/bot-token', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        showSaveStatus('Telegram disconnected', 'success');
        await fetchTelegramStatus();
      } else {
        showSaveStatus('Failed to disconnect', 'error');
      }
    } catch (err) {
      console.error('Failed to clear telegram:', err);
      showSaveStatus('Failed to disconnect', 'error');
    } finally {
      setIsClearingTelegram(false);
    }
  };

  const handleToggleCategory = async (categoryKey) => {
    // Missing key defaults to enabled (server-side opt-out), so we flip
    // current effective state — undefined → false on first toggle.
    const current = telegram.notification_prefs?.[categoryKey];
    const next = current === false ? true : false;
    const newPrefs = { ...(telegram.notification_prefs || {}), [categoryKey]: next };
    // Optimistic update
    setTelegram((t) => ({ ...t, notification_prefs: newPrefs }));
    try {
      const res = await fetch('/api/telegram/notification-prefs', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ prefs: newPrefs }),
      });
      if (!res.ok) {
        showSaveStatus('Failed to update preferences', 'error');
        // Revert
        setTelegram((t) => ({ ...t, notification_prefs: telegram.notification_prefs }));
      }
    } catch (err) {
      console.error('Failed to update prefs:', err);
      setTelegram((t) => ({ ...t, notification_prefs: telegram.notification_prefs }));
    }
  };

  // Web Push fetch + handlers
  // Notification category prefs are shared with Telegram (same server column),
  // so the category toggles below reuse `telegram.notification_prefs` +
  // `handleToggleCategory`. /api/push/status is only for device/enable state.
  const urlBase64ToUint8Array = (base64String) => {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  };

  const fetchPushStatus = async () => {
    if (!authToken) return;
    try {
      const res = await fetch('/api/push/status', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) setPush(await res.json());
    } catch (err) {
      console.error('Failed to fetch push status:', err);
    }
  };

  useEffect(() => {
    fetchPushStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  const handleEnablePush = async () => {
    if (!pushSupported) {
      showSaveStatus('Push notifications are not supported in this browser', 'error');
      return;
    }
    setIsPushBusy(true);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        showSaveStatus('Notification permission denied', 'error');
        return;
      }

      // Fetch the app VAPID public key (so we don't bake it into the build).
      const keyRes = await fetch('/api/push/vapid-public-key', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!keyRes.ok) {
        showSaveStatus('Web Push is not configured on the server', 'error');
        return;
      }
      const { key } = await keyRes.json();

      const registration = await navigator.serviceWorker.ready;
      // Reuse an existing subscription if present, else create one.
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(key),
        });
      }

      const json = subscription.toJSON();
      const res = await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          endpoint: json.endpoint,
          keys: json.keys,
          user_agent: navigator.userAgent,
        }),
      });
      if (res.ok) {
        showSaveStatus('Push notifications enabled on this device', 'success');
        await fetchPushStatus();
      } else {
        showSaveStatus('Failed to register device', 'error');
      }
    } catch (err) {
      console.error('Failed to enable push:', err);
      showSaveStatus('Failed to enable push notifications', 'error');
    } finally {
      setIsPushBusy(false);
    }
  };

  const handleDisablePush = async () => {
    setIsPushBusy(true);
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      const endpoint = subscription?.endpoint;
      if (subscription) await subscription.unsubscribe();

      if (endpoint) {
        await fetch('/api/push/subscribe', {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({ endpoint }),
        });
      }
      showSaveStatus('Push notifications disabled on this device', 'success');
      await fetchPushStatus();
    } catch (err) {
      console.error('Failed to disable push:', err);
      showSaveStatus('Failed to disable push notifications', 'error');
    } finally {
      setIsPushBusy(false);
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

              {/* TOTP Auto-Login Credentials */}
              <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-2 mb-3">
                  <Smartphone className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
                  <div className="font-medium text-zinc-900 dark:text-zinc-100">
                    TOTP Auto-Login
                  </div>
                  {hasTotpCredentials && (
                    <span className="ml-auto px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                      Configured
                    </span>
                  )}
                </div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
                  Enable automatic token refresh when your Upstox session expires (daily ~3:30 AM).
                  Requires your Upstox mobile number, password, PIN, and TOTP secret from your authenticator app.
                </p>
                {hasTotpCredentials ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                      <span className="text-sm text-green-700 dark:text-green-300">
                        TOTP auto-login configured
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          onClick={handleTestTotp}
                          disabled={isTestingTotp}
                          className="text-xs"
                        >
                          {isTestingTotp ? (
                            <Loader2 className="w-3 h-3 animate-spin mr-1" />
                          ) : (
                            <RefreshCw className="w-3 h-3 mr-1" />
                          )}
                          Test
                        </Button>
                        <Button
                          variant="outline"
                          onClick={handleClearTotpCredentials}
                          className="text-xs"
                        >
                          <X className="w-3 h-3 mr-1" />
                          Clear
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                        Mobile Number
                      </label>
                      <input
                        type="text"
                        value={totpMobile}
                        onChange={(e) => setTotpMobile(e.target.value)}
                        placeholder="Your registered mobile number"
                        className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                          PIN
                        </label>
                        <input
                          type="password"
                          value={totpPin}
                          onChange={(e) => setTotpPin(e.target.value)}
                          placeholder="6-digit PIN"
                          className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                          TOTP Secret
                        </label>
                        <input
                          type="password"
                          value={totpSecret}
                          onChange={(e) => setTotpSecret(e.target.value)}
                          placeholder="Base32 secret key"
                          className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                        />
                      </div>
                    </div>
                    <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                      <div className="flex items-start gap-2 text-amber-700 dark:text-amber-300 text-xs">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                        <span>
                          These credentials are stored encrypted on the server. Your TOTP secret and PIN enable automatic login without manual OAuth each morning.
                        </span>
                      </div>
                    </div>
                    <Button
                      onClick={handleSaveTotpCredentials}
                      disabled={isSavingTotp || !totpMobile.trim() || !totpPin.trim() || !totpSecret.trim()}
                    >
                      {isSavingTotp ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          Saving...
                        </>
                      ) : (
                        'Save TOTP Credentials'
                      )}
                    </Button>
                  </div>
                )}
              </div>

              {/* Web Push (PWA) Notifications */}
              <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-2 mb-3">
                  <Smartphone className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
                  <div className="font-medium text-zinc-900 dark:text-zinc-100">
                    Push Notifications
                  </div>
                  {push.enabled && (
                    <span className="ml-auto px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                      {push.device_count} device{push.device_count === 1 ? '' : 's'}
                    </span>
                  )}
                </div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
                  Get monitor fires, awakening digests, and system alerts as
                  notifications on this device — no third-party app needed.
                  Enable per device you want notified.
                </p>

                {!pushSupported ? (
                  <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-xs text-amber-700 dark:text-amber-300">
                    This browser doesn't support web push. On iOS, add Nifty
                    Strategist to your Home Screen first, then enable here.
                  </div>
                ) : (
                  <div className="space-y-3">
                    <Button
                      onClick={push.enabled ? handleDisablePush : handleEnablePush}
                      disabled={isPushBusy}
                      variant={push.enabled ? 'outline' : undefined}
                    >
                      {isPushBusy ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      ) : push.enabled ? (
                        <X className="w-4 h-4 mr-2" />
                      ) : (
                        <Bell className="w-4 h-4 mr-2" />
                      )}
                      {push.enabled ? 'Disable on this device' : 'Enable on this device'}
                    </Button>

                    <div>
                      <div className="flex items-center gap-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-2">
                        <Bell className="w-3.5 h-3.5" />
                        Notification categories
                        <span className="text-zinc-400 dark:text-zinc-500 font-normal">
                          (shared with Telegram)
                        </span>
                      </div>
                      <div className="space-y-2">
                        {TELEGRAM_CATEGORIES.map((cat) => {
                          const enabled = telegram.notification_prefs?.[cat.key] !== false;
                          return (
                            <label
                              key={cat.key}
                              className="flex items-start gap-3 p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={enabled}
                                onChange={() => handleToggleCategory(cat.key)}
                                className="mt-0.5"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="text-sm text-zinc-900 dark:text-zinc-100">
                                  {cat.label}
                                </div>
                                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                  {cat.desc}
                                </div>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Telegram Notifications */}
              <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-2 mb-3">
                  <Send className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
                  <div className="font-medium text-zinc-900 dark:text-zinc-100">
                    Telegram Notifications
                  </div>
                  {telegram.configured && telegram.paired && (
                    <span className="ml-auto px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                      Paired
                    </span>
                  )}
                  {telegram.configured && !telegram.paired && (
                    <span className="ml-auto px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
                      Pairing pending
                    </span>
                  )}
                </div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
                  Use your own Telegram bot for outbound notifications. The bot
                  token is encrypted; only your account can DM it.
                </p>

                {!telegram.configured ? (
                  <div className="space-y-3">
                    <ol className="text-xs text-zinc-600 dark:text-zinc-400 list-decimal list-inside space-y-1">
                      <li>Open Telegram, DM <code className="px-1 rounded bg-zinc-200 dark:bg-zinc-700">@BotFather</code></li>
                      <li>Send <code className="px-1 rounded bg-zinc-200 dark:bg-zinc-700">/newbot</code>, pick a name + username</li>
                      <li>Copy the HTTP API token BotFather gives you and paste it below</li>
                    </ol>
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                        Bot Token
                      </label>
                      <input
                        type="password"
                        value={telegramToken}
                        onChange={(e) => setTelegramToken(e.target.value)}
                        placeholder="123456:ABC-DEF..."
                        className="w-full px-3 py-2 text-sm font-mono rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                      <div className="flex items-start gap-2 text-amber-700 dark:text-amber-300 text-xs">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                        <span>
                          Telegram is NOT end-to-end encrypted. Trade activity sent through
                          this channel is visible to Telegram and to anyone who has the bot token.
                          Rotate the token via BotFather if it ever leaks.
                        </span>
                      </div>
                    </div>
                    <Button
                      onClick={handleSaveTelegramToken}
                      disabled={isSavingTelegram || !telegramToken.trim()}
                    >
                      {isSavingTelegram ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          Validating...
                        </>
                      ) : (
                        'Save Bot Token'
                      )}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                      <div className="text-sm text-green-700 dark:text-green-300">
                        Bot: <code className="font-mono">@{telegram.bot_username}</code>
                        {telegram.paired ? (
                          <span className="ml-2 text-xs">— chat #{telegram.chat_id}</span>
                        ) : (
                          <span className="ml-2 text-xs">
                            — DM <a
                              href={`https://t.me/${telegram.bot_username}`}
                              target="_blank"
                              rel="noreferrer"
                              className="underline"
                            >@{telegram.bot_username}</a> with <code>/start</code> then <code>/confirm</code>
                          </span>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        onClick={handleClearTelegramToken}
                        disabled={isClearingTelegram}
                        className="text-xs"
                      >
                        {isClearingTelegram ? (
                          <Loader2 className="w-3 h-3 animate-spin mr-1" />
                        ) : (
                          <X className="w-3 h-3 mr-1" />
                        )}
                        Disconnect
                      </Button>
                    </div>

                    {telegram.paired && (
                      <div>
                        <div className="flex items-center gap-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-2">
                          <Bell className="w-3.5 h-3.5" />
                          Notification categories
                        </div>
                        <div className="space-y-2">
                          {TELEGRAM_CATEGORIES.map((cat) => {
                            const enabled = telegram.notification_prefs?.[cat.key] !== false;
                            return (
                              <label
                                key={cat.key}
                                className="flex items-start gap-3 p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={enabled}
                                  onChange={() => handleToggleCategory(cat.key)}
                                  className="mt-0.5"
                                />
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm text-zinc-900 dark:text-zinc-100">
                                    {cat.label}
                                  </div>
                                  <div className="text-xs text-zinc-500 dark:text-zinc-400">
                                    {cat.desc}
                                  </div>
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    )}
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

              {/* Trading Mode - Live by default */}
              {upstoxConnected && (
                <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                  <div className="flex items-center gap-2 text-green-700 dark:text-green-300 text-sm">
                    <Zap className="w-4 h-4" />
                    <span>Live trading is active. All orders use real money via Upstox.</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>


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

        {/* Passkeys Section */}
        {passkeySupported && (
          <section className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
                <Fingerprint className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                  Passkeys
                </h2>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  Sign in with biometrics or security keys instead of passwords
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {passkeys.length > 0 ? (
                passkeys.map((pk) => (
                  <div
                    key={pk.id}
                    className="flex items-center justify-between p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700"
                  >
                    <div className="flex items-center gap-3">
                      <Fingerprint className="w-5 h-5 text-indigo-500" />
                      <div>
                        <div className="font-medium text-sm text-zinc-900 dark:text-zinc-100">
                          {pk.device_name || 'Passkey'}
                        </div>
                        <div className="text-xs text-zinc-500 dark:text-zinc-400">
                          Added {pk.created_at ? new Date(pk.created_at).toLocaleDateString() : 'unknown'}
                          {pk.last_used_at && ` \u00b7 Last used ${new Date(pk.last_used_at).toLocaleDateString()}`}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeletePasskey(pk.id, pk.device_name)}
                      className="p-2 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      title="Remove passkey"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              ) : (
                <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    No passkeys registered yet. Add one to enable passwordless sign-in.
                  </p>
                </div>
              )}

              <Button
                onClick={handleRegisterPasskey}
                disabled={passkeyLoading}
                variant="outline"
                className="mt-2"
              >
                <Plus className="w-4 h-4 mr-2" />
                {passkeyLoading ? 'Registering...' : 'Add Passkey'}
              </Button>
            </div>
          </section>
        )}

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
