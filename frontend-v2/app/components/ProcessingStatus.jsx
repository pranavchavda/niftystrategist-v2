import React, { useState, useEffect } from 'react';
import {
  MapIcon,
  SparklesIcon,
  CpuChipIcon,
  WrenchScrewdriverIcon,
  MagnifyingGlassIcon,
  ChartBarIcon,
  PencilIcon,
  ClockIcon,
  BoltIcon,
  ExclamationTriangleIcon,
  LightBulbIcon
} from '@heroicons/react/24/outline';

function ProcessingStatus({ status, details, startTime }) {
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (!startTime) return;

    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 100);

    return () => clearInterval(interval);
  }, [startTime]);

  const getStatusIcon = () => {
    const iconClass = "w-5 h-5 text-zinc-400 dark:text-zinc-500";
    switch (status) {
      case 'routing':
        return <MapIcon className={iconClass} />;
      case 'thinking':
        return <SparklesIcon className={iconClass} />;
      case 'calling_agent':
        return <CpuChipIcon className={iconClass} />;
      case 'executing_tool':
        return <WrenchScrewdriverIcon className={iconClass} />;
      case 'searching':
        return <MagnifyingGlassIcon className={iconClass} />;
      case 'analyzing':
        return <ChartBarIcon className={iconClass} />;
      case 'writing':
        return <PencilIcon className={iconClass} />;
      case 'waiting':
        return <ClockIcon className={iconClass} />;
      default:
        return <BoltIcon className={iconClass} />;
    }
  };

  const getStatusMessage = () => {
    switch (status) {
      case 'routing':
        return 'Determining the best agent for your request...';
      case 'thinking':
        return 'Analyzing your request...';
      case 'calling_agent':
        return `Delegating to ${details?.agentName || 'specialized agent'}...`;
      case 'executing_tool':
        return `Running ${details?.toolName || 'tool'}...`;
      case 'searching':
        return 'Searching for information...';
      case 'analyzing':
        return 'Analyzing results...';
      case 'writing':
        return 'Composing response...';
      case 'waiting':
        return 'Waiting for backend...';
      default:
        return 'Processing...';
    }
  };

  const getSubMessage = () => {
    if (details?.subMessage) return details.subMessage;

    switch (status) {
      case 'routing':
        return 'Analyzing your request';
      case 'calling_agent':
        if (details?.agentName === 'market_data') {
          return 'Fetching market data from Upstox';
        } else if (details?.agentName === 'analysis') {
          return 'Running technical analysis';
        } else if (details?.agentName === 'portfolio') {
          return 'Checking portfolio and positions';
        }
        return 'Connecting to trading systems';
      case 'executing_tool':
        if (details?.toolName?.includes('quote')) {
          return 'Fetching live stock quotes';
        } else if (details?.toolName?.includes('analyze')) {
          return 'Computing technical indicators';
        } else if (details?.toolName?.includes('order')) {
          return 'Processing order request';
        }
        return 'Executing operation';
      default:
        return null;
    }
  };

  return (
    <div className="py-6 px-4 bg-zinc-50/50 dark:bg-zinc-900/50 animate-slide-in-bottom">
      <div className="max-w-3xl mx-auto">
        <div className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mb-2 px-1">
          Nifty Strategist
        </div>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            {getStatusIcon()}
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-zinc-700 dark:text-zinc-300">
                {getStatusMessage()}
              </span>
              {elapsedTime > 0 && (
                <span className="text-xs text-zinc-500 dark:text-zinc-400 tabular-nums">
                  {elapsedTime}s
                </span>
              )}
            </div>
            {getSubMessage() && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                {getSubMessage()}
              </p>
            )}
            {details?.steps && (
              <div className="mt-2">
                <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400 mb-1">
                  <span>Step {details.currentStep} of {details.totalSteps}</span>
                </div>
                <div className="w-full bg-zinc-200 dark:bg-zinc-800 rounded-full h-1">
                  <div
                    className="bg-zinc-900 dark:bg-zinc-100 h-1 rounded-full transition-all"
                    style={{ width: `${Math.min((details.currentStep / details.totalSteps) * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProcessingStatus;