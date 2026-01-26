import { useState, useEffect } from 'react';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';

/**
 * HITL (Human-in-the-Loop) Toggle Component
 *
 * Allows users to enable/disable approval mode for tool executions
 */
export default function HITLToggle({ authToken, compact = false }) {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load HITL preference on mount
  useEffect(() => {
    loadPreference();
  }, [authToken]);

  const loadPreference = async () => {
    try {
      const response = await fetch('/api/auth/preferences', {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setEnabled(data.hitl_enabled || false);
      } else {
        console.error('Failed to load HITL preference:', response.status);
      }
    } catch (err) {
      console.error('Error loading HITL preference:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleHITL = async () => {
    const newValue = !enabled;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/auth/preferences/hitl', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ enabled: newValue })
      });

      if (response.ok) {
        setEnabled(newValue);
      } else {
        setError('Failed to update preference');
        console.error('Failed to update HITL preference:', response.status);
      }
    } catch (err) {
      setError('Network error');
      console.error('Error updating HITL preference:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading && enabled === false) {
    return null; // Hide during initial load
  }

  // Compact mode: just the toggle switch
  if (compact) {
    return (
      <button
        onClick={toggleHITL}
        disabled={loading}
        className={`${enabled ? 'bg-blue-600' : 'bg-zinc-300 dark:bg-zinc-700'
          } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 dark:focus:ring-offset-zinc-900 ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        aria-label={enabled ? 'Disable approval mode' : 'Enable approval mode'}
      >
        <span
          className={`${enabled ? 'translate-x-6' : 'translate-x-1'
            } inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm`}
        />
      </button>
    );
  }

  // Full mode: toggle with labels
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={toggleHITL}
        disabled={loading}
        className={`${enabled ? 'bg-blue-600' : 'bg-zinc-300 dark:bg-zinc-700'
          } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 dark:focus:ring-offset-zinc-900 ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        aria-label={enabled ? 'Disable approval mode' : 'Enable approval mode'}
      >
        <span
          className={`${enabled ? 'translate-x-6' : 'translate-x-1'
            } inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm`}
        />
      </button>

      <span className="text-xs sm:text-sm text-zinc-700 dark:text-zinc-300">
        {enabled ? (
          <span className="flex items-center gap-1.5">
            <CheckCircleIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            Approval Mode
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            <XCircleIcon className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
            Auto Mode
          </span>
        )}
      </span>

      {error && (
        <span className="text-xs text-red-400 dark:text-red-500">{error}</span>
      )}
    </div>
  );
}

