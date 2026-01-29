import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';

/**
 * Upstox OAuth Callback Handler
 *
 * This route receives the OAuth callback from Upstox after user authorization.
 * It forwards the authorization code to the backend for token exchange.
 */
export default function UpstoxCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Connecting to Upstox...');

  // Guard against double-execution in React StrictMode
  const hasCalledRef = useRef(false);

  useEffect(() => {
    // Prevent double-execution (React 18 StrictMode runs effects twice)
    if (hasCalledRef.current) {
      return;
    }

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');

    if (error) {
      setStatus('error');
      setMessage(errorDescription || error || 'Authorization failed');
      return;
    }

    if (!code || !state) {
      setStatus('error');
      setMessage('Missing authorization code or state parameter');
      return;
    }

    // Mark as called before making the request
    hasCalledRef.current = true;

    // Forward to backend callback endpoint
    handleCallback(code, state);
  }, [searchParams]);

  const handleCallback = async (code: string, state: string) => {
    try {
      // Call backend callback endpoint
      const response = await fetch(`/api/auth/upstox/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        },
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.status === 'success') {
        setStatus('success');
        setMessage('Upstox connected successfully!');

        // Redirect to settings after a short delay
        setTimeout(() => {
          navigate('/settings?upstox=connected');
        }, 1500);
      } else {
        throw new Error(data.detail || data.message || 'Failed to connect Upstox');
      }
    } catch (error) {
      console.error('Upstox callback error:', error);
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Failed to connect Upstox');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-md w-full mx-4">
        <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-xl p-8 text-center">
          {/* Status Icon */}
          <div className="mb-6">
            {status === 'loading' && (
              <div className="w-16 h-16 mx-auto bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
              </div>
            )}
            {status === 'success' && (
              <div className="w-16 h-16 mx-auto bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
            )}
            {status === 'error' && (
              <div className="w-16 h-16 mx-auto bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                <XCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
              </div>
            )}
          </div>

          {/* Title */}
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
            {status === 'loading' && 'Connecting Upstox'}
            {status === 'success' && 'Connected!'}
            {status === 'error' && 'Connection Failed'}
          </h1>

          {/* Message */}
          <p className="text-zinc-600 dark:text-zinc-400 mb-6">
            {message}
          </p>

          {/* Actions */}
          {status === 'error' && (
            <div className="space-y-3">
              <button
                onClick={() => window.location.href = '/api/auth/upstox/authorize'}
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={() => navigate('/settings')}
                className="w-full px-4 py-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 rounded-lg font-medium transition-colors"
              >
                Back to Settings
              </button>
            </div>
          )}

          {status === 'success' && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Redirecting to settings...
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
