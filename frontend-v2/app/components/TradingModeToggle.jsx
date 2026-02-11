import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  Zap,
  FileText,
  Link as LinkIcon,
  Loader2,
} from 'lucide-react';
import { Button } from './catalyst/button';
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogDescription,
  DialogTitle,
} from './catalyst/dialog';

/**
 * TradingModeToggle - Toggle between paper and live trading
 * Shows in sidebar, handles Upstox connection and confirmation
 */
export default function TradingModeToggle({ authToken, isCollapsed, onModeChange }) {
  const [tradingMode, setTradingMode] = useState('paper');
  const [upstoxConnected, setUpstoxConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);

  // Load trading status on mount
  useEffect(() => {
    loadTradingStatus();
  }, [authToken]);

  const loadTradingStatus = async () => {
    if (!authToken) return;

    try {
      const response = await fetch('/api/auth/upstox/status', {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setTradingMode(data.trading_mode || 'paper');
        setUpstoxConnected(data.connected);
      }
    } catch (error) {
      console.error('Failed to load trading status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleClick = async () => {
    if (tradingMode === 'live') {
      // Switching to paper - no confirmation needed
      switchTradingMode('paper');
    } else {
      // Switching to live - need to check Upstox connection first
      if (!upstoxConnected) {
        // Need to connect Upstox - fetch the authorize URL with auth token
        try {
          const response = await fetch('/api/auth/upstox/authorize-url', {
            headers: {
              'Authorization': `Bearer ${authToken}`,
            },
          });

          if (response.ok) {
            const data = await response.json();
            window.location.href = data.url;
          } else {
            console.error('Failed to get Upstox authorize URL');
            alert('Failed to connect to Upstox. Please try again.');
          }
        } catch (error) {
          console.error('Failed to initiate Upstox OAuth:', error);
          alert('Failed to connect to Upstox. Please try again.');
        }
      } else {
        // Show confirmation dialog
        setShowConfirmDialog(true);
      }
    }
  };

  const switchTradingMode = async (newMode) => {
    setIsSwitching(true);
    try {
      const response = await fetch('/api/auth/upstox/trading-mode', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: newMode }),
      });

      if (response.ok) {
        const data = await response.json();
        setTradingMode(data.trading_mode);
        setShowConfirmDialog(false);
        onModeChange?.(data.trading_mode);
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to switch trading mode');
      }
    } catch (error) {
      console.error('Failed to switch trading mode:', error);
      alert('Failed to switch trading mode');
    } finally {
      setIsSwitching(false);
    }
  };

  const handleConfirmLive = () => {
    switchTradingMode('live');
  };

  if (isLoading) {
    return (
      <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-between px-3'} py-2`}>
        <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
      </div>
    );
  }

  const isLive = tradingMode === 'live';

  // Collapsed view
  if (isCollapsed) {
    return (
      <>
        <div className="relative group px-2 py-1 flex justify-center">
          <button
            onClick={handleToggleClick}
            disabled={isSwitching}
            className={`
              p-2 rounded-xl transition-all duration-200
              ${isLive
                ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 ring-1 ring-red-200 dark:ring-red-800'
                : 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 ring-1 ring-amber-200 dark:ring-amber-800'
              }
              hover:scale-105
            `}
            title={isLive ? 'Live Trading - Click to switch to Paper' : 'Paper Trading - Click to switch to Live'}
          >
            {isSwitching ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : isLive ? (
              <Zap className="w-5 h-5" />
            ) : (
              <FileText className="w-5 h-5" />
            )}
          </button>
          {/* Tooltip */}
          <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1 bg-zinc-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity duration-200">
            {isLive ? 'Live Trading' : 'Paper Trading'}
          </div>
        </div>

        {/* Confirmation Dialog */}
        <ConfirmLiveDialog
          open={showConfirmDialog}
          onClose={() => setShowConfirmDialog(false)}
          onConfirm={handleConfirmLive}
          isSwitching={isSwitching}
        />
      </>
    );
  }

  // Expanded view
  return (
    <>
      <div className="px-3 py-2">
        <button
          onClick={handleToggleClick}
          disabled={isSwitching}
          className={`
            w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200
            ${isLive
              ? 'bg-red-100 dark:bg-red-900/30 ring-1 ring-red-200 dark:ring-red-800'
              : 'bg-amber-100 dark:bg-amber-900/30 ring-1 ring-amber-200 dark:ring-amber-800'
            }
            hover:scale-[1.02] active:scale-[0.98]
          `}
        >
          {/* Icon */}
          <div className={`p-1.5 rounded-lg ${isLive ? 'bg-red-200 dark:bg-red-800' : 'bg-amber-200 dark:bg-amber-800'}`}>
            {isSwitching ? (
              <Loader2 className={`w-4 h-4 animate-spin ${isLive ? 'text-red-600 dark:text-red-300' : 'text-amber-600 dark:text-amber-300'}`} />
            ) : isLive ? (
              <Zap className="w-4 h-4 text-red-600 dark:text-red-300" />
            ) : (
              <FileText className="w-4 h-4 text-amber-600 dark:text-amber-300" />
            )}
          </div>

          {/* Text */}
          <div className="flex-1 text-left">
            <div className={`text-sm font-semibold ${isLive ? 'text-red-700 dark:text-red-300' : 'text-amber-700 dark:text-amber-300'}`}>
              {isLive ? 'Live Trading' : 'Paper Trading'}
            </div>
            <div className={`text-xs ${isLive ? 'text-red-600/70 dark:text-red-400/70' : 'text-amber-600/70 dark:text-amber-400/70'}`}>
              {isLive ? 'Real money at risk' : 'No real money'}
            </div>
          </div>

          {/* Status indicator */}
          <div className={`w-2 h-2 rounded-full ${isLive ? 'bg-red-500 animate-pulse' : 'bg-amber-500'}`} />
        </button>

        {/* Connection status */}
        {!upstoxConnected && (
          <div className="mt-2 flex items-center gap-2 px-3 text-xs text-zinc-500 dark:text-zinc-400">
            <LinkIcon className="w-3 h-3" />
            <span>Connect Upstox for live trading</span>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <ConfirmLiveDialog
        open={showConfirmDialog}
        onClose={() => setShowConfirmDialog(false)}
        onConfirm={handleConfirmLive}
        isSwitching={isSwitching}
      />
    </>
  );
}

/**
 * Confirmation dialog for switching to live trading
 */
function ConfirmLiveDialog({ open, onClose, onConfirm, isSwitching }) {
  return (
    <Dialog open={open} onClose={onClose}>
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
        <Button plain onClick={onClose} disabled={isSwitching}>
          Cancel
        </Button>
        <Button color="red" onClick={onConfirm} disabled={isSwitching}>
          {isSwitching ? (
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
  );
}
