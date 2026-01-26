import React, { useState, useEffect } from 'react';
import { useOutletContext, useSearchParams } from 'react-router';
import {
  Server,
  Plus,
  Edit,
  Trash2,
  Power,
  CheckCircle,
  XCircle,
  Radio,
  Globe,
  Terminal,
  Key,
  Link,
  Unlink,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Dialog, DialogPanel, DialogTitle } from '@headlessui/react';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
  user?: any;
}

interface OAuthStatus {
  connected: boolean;
  expires_at?: string;
  scopes?: string[];
}

interface OAuthConfig {
  authorization_url: string;
  token_url: string;
  client_id: string;
  client_secret?: string;
  scopes: string[];
}

interface MCPServer {
  id: number;
  name: string;
  description?: string;
  transport_type: 'stdio' | 'sse' | 'http';
  config: any;
  enabled: boolean;
  auth_type: 'none' | 'api_key' | 'oauth';
  oauth_config?: OAuthConfig;
  oauth_status?: OAuthStatus;
  created_at: string;
  updated_at: string;
}

// Known MCP provider presets with pre-configured OAuth settings
// Users only need to provide their client_id (and optionally client_secret)
interface MCPProviderPreset {
  name: string;
  url: string;
  description: string;
  authorization_url: string;
  token_url: string;
  suggested_scopes: string[];
  docs_url: string;
  requires_app_registration: boolean;
  registration_url?: string;
}

// Note: Klaviyo's remote MCP server (mcp.klaviyo.com) uses a proprietary OAuth flow
// that only works with their partner integrations (Claude.ai, ChatGPT, etc.).
// For custom implementations, use the local server with a private API key instead.
const MCP_PROVIDER_PRESETS: Record<string, MCPProviderPreset> = {
  // Klaviyo removed - their remote server doesn't accept standard OAuth tokens
  // Users should configure the local server with: uvx klaviyo-mcp-server@latest
  sentry: {
    name: 'Sentry',
    url: 'https://mcp.sentry.dev/mcp',
    description: 'Error tracking and performance monitoring',
    authorization_url: 'https://sentry.io/oauth/authorize/',
    token_url: 'https://sentry.io/oauth/token/',
    suggested_scopes: ['project:read', 'org:read', 'event:read'],
    docs_url: 'https://docs.sentry.io/product/integrations/mcp/',
    requires_app_registration: true,
    registration_url: 'https://sentry.io/settings/developer-settings/'
  },
  linear: {
    name: 'Linear',
    url: 'https://mcp.linear.app/mcp',
    description: 'Issue tracking and project management',
    authorization_url: 'https://linear.app/oauth/authorize',
    token_url: 'https://api.linear.app/oauth/token',
    suggested_scopes: ['read', 'write', 'issues:create'],
    docs_url: 'https://developers.linear.app/docs/mcp',
    requires_app_registration: true,
    registration_url: 'https://linear.app/settings/api'
  },
  notion: {
    name: 'Notion',
    url: 'https://mcp.notion.so/mcp',
    description: 'Workspace and documentation',
    authorization_url: 'https://api.notion.com/v1/oauth/authorize',
    token_url: 'https://api.notion.com/v1/oauth/token',
    suggested_scopes: [],
    docs_url: 'https://developers.notion.com/',
    requires_app_registration: true,
    registration_url: 'https://www.notion.so/my-integrations'
  }
};

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

export default function MCPServersSettings() {
  const { authToken } = useOutletContext<AuthContext>();
  const [searchParams, setSearchParams] = useSearchParams();

  const [servers, setServers] = useState<MCPServer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServer | null>(null);
  const [saveStatus, setSaveStatus] = useState({ show: false, message: '', type: '' });

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    transport_type: 'stdio' as 'stdio' | 'sse' | 'http',
    auth_type: 'none' as 'none' | 'api_key' | 'oauth',
    config: {
      command: '',
      args: [],
      env: {},
      url: '',
      headers: {}
    },
    oauth_config: {
      authorization_url: '',
      token_url: '',
      client_id: '',
      client_secret: '',
      scopes: [] as string[]
    }
  });
  const [selectedPreset, setSelectedPreset] = useState<string>('');

  // Apply a known provider preset
  const applyPreset = (presetKey: string) => {
    const preset = MCP_PROVIDER_PRESETS[presetKey];
    if (!preset) return;

    setSelectedPreset(presetKey);
    setFormData({
      ...formData,
      name: preset.name,
      description: preset.description,
      transport_type: 'http',
      auth_type: 'oauth',
      config: {
        ...formData.config,
        url: preset.url
      },
      oauth_config: {
        authorization_url: preset.authorization_url,
        token_url: preset.token_url,
        client_id: '', // User must provide
        client_secret: '',
        scopes: preset.suggested_scopes
      }
    });
  };

  // Handle OAuth callback status from URL params
  useEffect(() => {
    const success = searchParams.get('success');
    const error = searchParams.get('error');
    const serverId = searchParams.get('server');

    if (success === 'connected' && serverId) {
      showSaveStatus(`Successfully connected OAuth for server`, 'success');
      // Clear URL params
      setSearchParams({});
      // Refresh servers to get updated OAuth status
      fetchServers();
    } else if (error) {
      const errorMessages: Record<string, string> = {
        invalid_state: 'OAuth failed: Invalid state parameter',
        server_not_found: 'OAuth failed: Server not found',
        token_exchange_failed: 'OAuth failed: Could not exchange authorization code',
        callback_failed: 'OAuth callback failed'
      };
      showSaveStatus(errorMessages[error] || `OAuth error: ${error}`, 'error');
      setSearchParams({});
    }
  }, [searchParams]);

  // Fetch MCP servers
  useEffect(() => {
    fetchServers();
  }, [authToken]);

  const fetchServers = async () => {
    try {
      const res = await fetch('/api/mcp-servers', {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      const data = await res.json();
      setServers(data);
    } catch (err) {
      console.error('Failed to fetch MCP servers:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const showSaveStatus = (message: string, type: 'success' | 'error') => {
    setSaveStatus({ show: true, message, type });
    setTimeout(() => setSaveStatus({ show: false, message: '', type: '' }), 3000);
  };

  const handleOpenDialog = (server?: MCPServer) => {
    setSelectedPreset(''); // Reset preset selection
    if (server) {
      setEditingServer(server);
      setFormData({
        name: server.name,
        description: server.description || '',
        transport_type: server.transport_type,
        auth_type: server.auth_type || 'none',
        config: server.config,
        oauth_config: server.oauth_config || {
          authorization_url: '',
          token_url: '',
          client_id: '',
          client_secret: '',
          scopes: []
        }
      });
    } else {
      setEditingServer(null);
      setFormData({
        name: '',
        description: '',
        transport_type: 'stdio',
        auth_type: 'none',
        config: {
          command: '',
          args: [],
          env: {},
          url: '',
          headers: {}
        },
        oauth_config: {
          authorization_url: '',
          token_url: '',
          client_id: '',
          client_secret: '',
          scopes: []
        }
      });
    }
    setShowDialog(true);
  };

  const handleCloseDialog = () => {
    setShowDialog(false);
    setEditingServer(null);
  };

  const handleSave = async () => {
    try {
      const url = editingServer
        ? `/api/mcp-servers/${editingServer.id}`
        : '/api/mcp-servers';
      const method = editingServer ? 'PUT' : 'POST';

      // Clean up config based on transport type
      let cleanConfig = { ...formData.config };
      if (formData.transport_type === 'stdio') {
        delete cleanConfig.url;
        delete cleanConfig.headers;
        // Parse args if it's a string
        if (typeof cleanConfig.args === 'string') {
          cleanConfig.args = cleanConfig.args.split(',').map((s: string) => s.trim()).filter(Boolean);
        }
        // Clean up empty env entries
        if (cleanConfig.env) {
          cleanConfig.env = Object.fromEntries(
            Object.entries(cleanConfig.env).filter(([k, v]) => k.trim() !== '')
          );
        }
      } else {
        delete cleanConfig.command;
        delete cleanConfig.args;
        delete cleanConfig.env;
      }

      // Prepare OAuth config if needed
      let oauthConfig = null;
      if (formData.auth_type === 'oauth' && formData.oauth_config) {
        oauthConfig = {
          ...formData.oauth_config,
          // Parse scopes if it's a string
          scopes: typeof formData.oauth_config.scopes === 'string'
            ? (formData.oauth_config.scopes as string).split(',').map((s: string) => s.trim()).filter(Boolean)
            : formData.oauth_config.scopes
        };
      }

      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          transport_type: formData.transport_type,
          config: cleanConfig,
          auth_type: formData.auth_type,
          oauth_config: oauthConfig
        })
      });

      if (res.ok) {
        showSaveStatus(
          editingServer ? 'Server updated successfully' : 'Server added successfully',
          'success'
        );
        handleCloseDialog();
        fetchServers();
      } else {
        const error = await res.json();
        showSaveStatus(error.detail || 'Failed to save server', 'error');
      }
    } catch (err) {
      console.error('Failed to save MCP server:', err);
      showSaveStatus('Failed to save server', 'error');
    }
  };

  // OAuth actions
  const handleOAuthConnect = async (serverId: number) => {
    try {
      // Fetch the authorization URL from the backend (which requires auth)
      const res = await fetch(`/api/mcp-servers/${serverId}/oauth/authorize`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          // Redirect to the OAuth provider
          window.location.href = data.auth_url;
          return;
        }
      }

      // Handle error
      const error = await res.json().catch(() => ({ detail: 'Failed to initiate OAuth' }));
      showSaveStatus(error.detail || 'Failed to start OAuth flow', 'error');
    } catch (err) {
      console.error('OAuth connect error:', err);
      showSaveStatus('Failed to connect OAuth', 'error');
    }
  };

  const handleOAuthDisconnect = async (serverId: number) => {
    if (!confirm('Are you sure you want to disconnect OAuth for this server?')) return;

    try {
      const res = await fetch(`/api/mcp-servers/${serverId}/oauth`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (res.ok) {
        showSaveStatus('OAuth disconnected successfully', 'success');
        fetchServers();
      } else {
        showSaveStatus('Failed to disconnect OAuth', 'error');
      }
    } catch (err) {
      console.error('Failed to disconnect OAuth:', err);
      showSaveStatus('Failed to disconnect OAuth', 'error');
    }
  };

  const handleOAuthRefresh = async (serverId: number) => {
    try {
      const res = await fetch(`/api/mcp-servers/${serverId}/oauth/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (res.ok) {
        showSaveStatus('OAuth token refreshed successfully', 'success');
        fetchServers();
      } else {
        const error = await res.json();
        showSaveStatus(error.detail || 'Failed to refresh token', 'error');
      }
    } catch (err) {
      console.error('Failed to refresh OAuth token:', err);
      showSaveStatus('Failed to refresh token', 'error');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this MCP server?')) return;

    try {
      const res = await fetch(`/api/mcp-servers/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (res.ok) {
        showSaveStatus('Server deleted successfully', 'success');
        fetchServers();
      } else {
        showSaveStatus('Failed to delete server', 'error');
      }
    } catch (err) {
      console.error('Failed to delete MCP server:', err);
      showSaveStatus('Failed to delete server', 'error');
    }
  };

  const handleToggle = async (id: number) => {
    try {
      const res = await fetch(`/api/mcp-servers/${id}/toggle`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });

      if (res.ok) {
        const data = await res.json();
        showSaveStatus(data.message, 'success');
        fetchServers();
      } else {
        showSaveStatus('Failed to toggle server', 'error');
      }
    } catch (err) {
      console.error('Failed to toggle MCP server:', err);
      showSaveStatus('Failed to toggle server', 'error');
    }
  };

  const getTransportIcon = (type: string) => {
    switch (type) {
      case 'stdio':
        return <Terminal className="w-4 h-4" />;
      case 'sse':
        return <Radio className="w-4 h-4" />;
      case 'http':
        return <Globe className="w-4 h-4" />;
      default:
        return <Server className="w-4 h-4" />;
    }
  };

  return (
    <div className="h-screen overflow-y-auto bg-white dark:bg-zinc-950">
      <div className="max-w-5xl mx-auto p-6 space-y-8">
        {/* Header */}
        <div className="border-b border-zinc-200 dark:border-zinc-800 pb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
              MCP Servers
            </h1>
            <p className="text-zinc-600 dark:text-zinc-400 mt-2">
              Manage Model Context Protocol servers to extend orchestrator capabilities
            </p>
          </div>
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="w-4 h-4 mr-2" />
            Add Server
          </Button>
        </div>

        {/* Save Status Toast */}
        {saveStatus.show && (
          <div
            className={`fixed top-4 right-4 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 transition-all duration-200 z-50 ${
              saveStatus.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
                : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
            }`}
          >
            {saveStatus.type === 'success' ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <XCircle className="w-5 h-5" />
            )}
            <span className="text-sm font-medium">{saveStatus.message}</span>
          </div>
        )}

        {/* MCP Servers List */}
        {isLoading ? (
          <div className="text-center py-12 text-zinc-600 dark:text-zinc-400">
            Loading MCP servers...
          </div>
        ) : servers.length === 0 ? (
          <div className="text-center py-12 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800">
            <Server className="w-12 h-12 mx-auto text-zinc-400 dark:text-zinc-600 mb-4" />
            <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              No MCP servers configured
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 mb-4">
              Add your first MCP server to extend the orchestrator's capabilities
            </p>
            <Button onClick={() => handleOpenDialog()}>
              <Plus className="w-4 h-4 mr-2" />
              Add Server
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {servers.map((server) => (
              <div
                key={server.id}
                className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800">
                      {getTransportIcon(server.transport_type)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                          {server.name}
                        </h3>
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                          {server.transport_type}
                        </span>
                        {server.enabled ? (
                          <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
                        ) : (
                          <XCircle className="w-4 h-4 text-zinc-400 dark:text-zinc-600" />
                        )}
                      </div>
                      {server.description && (
                        <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                          {server.description}
                        </p>
                      )}
                      <div className="mt-2 text-xs text-zinc-500 dark:text-zinc-500">
                        {server.transport_type === 'stdio' && server.config.command && (
                          <code className="bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded">
                            {server.config.command}
                          </code>
                        )}
                        {(server.transport_type === 'sse' || server.transport_type === 'http') &&
                          server.config.url && (
                            <code className="bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded">
                              {server.config.url}
                            </code>
                          )}
                      </div>
                      {/* OAuth Status */}
                      {server.auth_type === 'oauth' && (
                        <div className="mt-3 flex items-center gap-2">
                          {server.oauth_status?.connected ? (
                            <>
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
                                <Link className="w-3 h-3" />
                                OAuth Connected
                              </span>
                              {server.oauth_status.expires_at && (
                                <span className="text-xs text-zinc-400">
                                  Expires: {new Date(server.oauth_status.expires_at).toLocaleDateString()}
                                </span>
                              )}
                              <button
                                onClick={() => handleOAuthRefresh(server.id)}
                                className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800"
                                title="Refresh Token"
                              >
                                <RefreshCw className="w-3 h-3 text-zinc-500" />
                              </button>
                              <button
                                onClick={() => handleOAuthDisconnect(server.id)}
                                className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                                title="Disconnect"
                              >
                                <Unlink className="w-3 h-3 text-red-500" />
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => handleOAuthConnect(server.id)}
                              className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                            >
                              <Key className="w-3 h-3" />
                              Connect OAuth
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggle(server.id)}
                      className="p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                      title={server.enabled ? 'Disable' : 'Enable'}
                    >
                      <Power
                        className={`w-5 h-5 ${
                          server.enabled
                            ? 'text-green-600 dark:text-green-400'
                            : 'text-zinc-400 dark:text-zinc-600'
                        }`}
                      />
                    </button>
                    <button
                      onClick={() => handleOpenDialog(server)}
                      className="p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                      title="Edit"
                    >
                      <Edit className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
                    </button>
                    <button
                      onClick={() => handleDelete(server.id)}
                      className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-5 h-5 text-red-600 dark:text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add/Edit Dialog */}
        <Dialog open={showDialog} onClose={handleCloseDialog} className="relative z-50">
          <div className="fixed inset-0 bg-black/30" aria-hidden="true" />
          <div className="fixed inset-0 flex items-center justify-center p-4">
            <DialogPanel className="w-full max-w-2xl rounded-xl bg-white dark:bg-zinc-900 p-6 shadow-xl">
              <DialogTitle className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
                {editingServer ? 'Edit MCP Server' : 'Add MCP Server'}
              </DialogTitle>

              {/* Quick Start Presets - Only show when creating new server */}
              {!editingServer && (
                <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <label className="block text-sm font-medium text-blue-800 dark:text-blue-300 mb-2">
                    Quick Start with Known Provider
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(MCP_PROVIDER_PRESETS).map(([key, preset]) => (
                      <button
                        key={key}
                        onClick={() => applyPreset(key)}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                          selectedPreset === key
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-300 dark:border-zinc-600 hover:border-blue-400 dark:hover:border-blue-500'
                        }`}
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>
                  {selectedPreset && MCP_PROVIDER_PRESETS[selectedPreset]?.requires_app_registration && (
                    <div className="mt-3 text-xs text-blue-700 dark:text-blue-400">
                      <span className="font-medium">Note:</span> You'll need to{' '}
                      <a
                        href={MCP_PROVIDER_PRESETS[selectedPreset].registration_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline hover:text-blue-800 dark:hover:text-blue-300"
                      >
                        register an OAuth app
                      </a>{' '}
                      with {MCP_PROVIDER_PRESETS[selectedPreset].name} to get a Client ID.{' '}
                      <a
                        href={MCP_PROVIDER_PRESETS[selectedPreset].docs_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline hover:text-blue-800 dark:hover:text-blue-300"
                      >
                        View docs
                      </a>
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                    placeholder="My MCP Server"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Description
                  </label>
                  <input
                    type="text"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                    placeholder="Optional description"
                  />
                </div>

                {/* Transport Type */}
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Transport Type *
                  </label>
                  <select
                    value={formData.transport_type}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        transport_type: e.target.value as 'stdio' | 'sse' | 'http'
                      })
                    }
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                  >
                    <option value="stdio">stdio (Local Process)</option>
                    <option value="sse">SSE (Server-Sent Events)</option>
                    <option value="http">HTTP</option>
                  </select>
                </div>

                {/* Stdio Config */}
                {formData.transport_type === 'stdio' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Command *
                      </label>
                      <input
                        type="text"
                        value={formData.config.command}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            config: { ...formData.config, command: e.target.value }
                          })
                        }
                        className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono text-sm"
                        placeholder="npx @modelcontextprotocol/server-filesystem"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Arguments (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={
                          Array.isArray(formData.config.args)
                            ? formData.config.args.join(', ')
                            : formData.config.args
                        }
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            config: { ...formData.config, args: e.target.value }
                          })
                        }
                        className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono text-sm"
                        placeholder="--verbose, --port=3000"
                      />
                    </div>

                    {/* Environment Variables */}
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Environment Variables
                      </label>
                      <div className="space-y-2">
                        {Object.entries(formData.config.env || {}).map(([key, value], index) => (
                          <div key={index} className="flex gap-2">
                            <input
                              type="text"
                              value={key}
                              onChange={(e) => {
                                const oldEnv = formData.config.env || {};
                                const entries = Object.entries(oldEnv);
                                const newEntries = entries.map(([k, v], i) =>
                                  i === index ? [e.target.value, v] : [k, v]
                                );
                                setFormData({
                                  ...formData,
                                  config: { ...formData.config, env: Object.fromEntries(newEntries) }
                                });
                              }}
                              className="flex-1 px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono text-sm"
                              placeholder="VARIABLE_NAME"
                            />
                            <input
                              type="text"
                              value={value as string}
                              onChange={(e) => {
                                const newEnv = { ...(formData.config.env || {}) };
                                newEnv[key] = e.target.value;
                                setFormData({
                                  ...formData,
                                  config: { ...formData.config, env: newEnv }
                                });
                              }}
                              className="flex-1 px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono text-sm"
                              placeholder="value"
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const newEnv = { ...(formData.config.env || {}) };
                                delete newEnv[key];
                                setFormData({
                                  ...formData,
                                  config: { ...formData.config, env: newEnv }
                                });
                              }}
                              className="px-3 py-2 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() => {
                            const newEnv = { ...(formData.config.env || {}), '': '' };
                            setFormData({
                              ...formData,
                              config: { ...formData.config, env: newEnv }
                            });
                          }}
                          className="flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
                        >
                          <Plus className="w-4 h-4" />
                          Add Environment Variable
                        </button>
                      </div>
                      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                        e.g., PRIVATE_API_KEY, UV_CACHE_DIR
                      </p>
                    </div>
                  </>
                )}

                {/* HTTP/SSE Config */}
                {(formData.transport_type === 'sse' || formData.transport_type === 'http') && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        URL *
                      </label>
                      <input
                        type="text"
                        value={formData.config.url}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            config: { ...formData.config, url: e.target.value }
                          })
                        }
                        className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono text-sm"
                        placeholder="https://example.com/mcp"
                      />
                    </div>

                    {/* Authentication Type */}
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Authentication
                      </label>
                      <select
                        value={formData.auth_type}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            auth_type: e.target.value as 'none' | 'api_key' | 'oauth'
                          })
                        }
                        className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                      >
                        <option value="none">None</option>
                        <option value="api_key">API Key (in headers)</option>
                        <option value="oauth">OAuth 2.0</option>
                      </select>
                    </div>

                    {/* OAuth Configuration */}
                    {formData.auth_type === 'oauth' && (
                      <div className="space-y-3 p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
                        <div className="flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                          <Key className="w-4 h-4" />
                          OAuth 2.0 Configuration
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                            Authorization URL *
                          </label>
                          <input
                            type="text"
                            value={formData.oauth_config.authorization_url}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                oauth_config: { ...formData.oauth_config, authorization_url: e.target.value }
                              })
                            }
                            className="w-full px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono"
                            placeholder="https://provider.com/oauth/authorize"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                            Token URL *
                          </label>
                          <input
                            type="text"
                            value={formData.oauth_config.token_url}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                oauth_config: { ...formData.oauth_config, token_url: e.target.value }
                              })
                            }
                            className="w-full px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 font-mono"
                            placeholder="https://provider.com/oauth/token"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                              Client ID *
                            </label>
                            <input
                              type="text"
                              value={formData.oauth_config.client_id}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  oauth_config: { ...formData.oauth_config, client_id: e.target.value }
                                })
                              }
                              className="w-full px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                              placeholder="your-client-id"
                            />
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                              Client Secret
                            </label>
                            <input
                              type="password"
                              value={formData.oauth_config.client_secret || ''}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  oauth_config: { ...formData.oauth_config, client_secret: e.target.value }
                                })
                              }
                              className="w-full px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                              placeholder="Optional for public clients"
                            />
                          </div>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                            Scopes (comma-separated)
                          </label>
                          <input
                            type="text"
                            value={
                              Array.isArray(formData.oauth_config.scopes)
                                ? formData.oauth_config.scopes.join(', ')
                                : formData.oauth_config.scopes
                            }
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                oauth_config: { ...formData.oauth_config, scopes: e.target.value as any }
                              })
                            }
                            className="w-full px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                            placeholder="read, write, admin"
                          />
                        </div>

                        <div className="flex items-start gap-2 text-xs text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-700/50 p-2 rounded">
                          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                          <span>
                            After saving, click "Connect OAuth" on the server card to authorize.
                            The OAuth flow uses PKCE for security.
                          </span>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="mt-6 flex justify-end gap-3">
                <Button plain onClick={handleCloseDialog}>
                  Cancel
                </Button>
                <Button onClick={handleSave}>
                  {editingServer ? 'Save Changes' : 'Add Server'}
                </Button>
              </div>
            </DialogPanel>
          </div>
        </Dialog>
      </div>
    </div>
  );
}
