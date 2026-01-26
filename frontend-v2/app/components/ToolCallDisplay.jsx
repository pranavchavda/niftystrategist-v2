import React, { useState, useRef, useEffect } from 'react';
import {
  Search,
  Plus,
  Edit,
  Trash2,
  ChartBar,
  Wrench,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Terminal
} from 'lucide-react';

function ToolCallDisplay({ toolCall, isActive = false, status = 'pending' }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [startTime] = useState(Date.now());
  const [elapsedTime, setElapsedTime] = useState(0);
  const contentRef = useRef(null);
  const [contentHeight, setContentHeight] = useState(0);

  // Update elapsed time for running tools
  useEffect(() => {
    if (status === 'running' || isActive) {
      const interval = setInterval(() => {
        setElapsedTime(Date.now() - startTime);
      }, 100);
      return () => clearInterval(interval);
    }
  }, [status, isActive, startTime]);

  // Measure content height for smooth animation
  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(isExpanded ? contentRef.current.scrollHeight : 0);
    }
  }, [isExpanded, toolCall.arguments, toolCall.result]);

  const getToolIcon = (toolName) => {
    const iconClass = "w-4 h-4";
    const lowerName = toolName.toLowerCase();

    if (lowerName.includes('search') || lowerName.includes('find')) {
      return <Search className={iconClass} />;
    }
    if (lowerName.includes('create') || lowerName.includes('add')) {
      return <Plus className={iconClass} />;
    }
    if (lowerName.includes('update') || lowerName.includes('edit') || lowerName.includes('modify')) {
      return <Edit className={iconClass} />;
    }
    if (lowerName.includes('delete') || lowerName.includes('remove')) {
      return <Trash2 className={iconClass} />;
    }
    if (lowerName.includes('analyze') || lowerName.includes('report') || lowerName.includes('stats')) {
      return <ChartBar className={iconClass} />;
    }

    return <Wrench className={iconClass} />;
  };

  const getStatusIcon = () => {
    const iconClass = "w-4 h-4";

    if (status === 'success' || (toolCall.result && !isActive)) {
      return <CheckCircle2 className={`${iconClass} text-green-600 dark:text-green-500`} />;
    }
    if (status === 'error') {
      return <XCircle className={`${iconClass} text-red-600 dark:text-red-500`} />;
    }
    if (status === 'running' || isActive) {
      return <Clock className={`${iconClass} text-blue-600 dark:text-blue-500 animate-pulse`} />;
    }

    return <Clock className={`${iconClass} text-zinc-400 dark:text-zinc-600`} />;
  };

  const getStatusStyles = () => {
    if (status === 'success' || (toolCall.result && !isActive)) {
      return {
        border: 'border-green-200 dark:border-green-900/50',
        bg: 'bg-green-50/50 dark:bg-green-950/20',
        iconBg: 'bg-green-100 dark:bg-green-900/30',
        iconText: 'text-green-600 dark:text-green-400'
      };
    }
    if (status === 'error') {
      return {
        border: 'border-red-200 dark:border-red-900/50',
        bg: 'bg-red-50/50 dark:bg-red-950/20',
        iconBg: 'bg-red-100 dark:bg-red-900/30',
        iconText: 'text-red-600 dark:text-red-400'
      };
    }
    if (status === 'running' || isActive) {
      return {
        border: 'border-blue-200 dark:border-blue-900/50',
        bg: 'bg-blue-50/50 dark:bg-blue-950/20',
        iconBg: 'bg-blue-100 dark:bg-blue-900/30',
        iconText: 'text-blue-600 dark:text-blue-400'
      };
    }

    return {
      border: 'border-zinc-200 dark:border-zinc-800',
      bg: 'bg-zinc-50/50 dark:bg-zinc-900/20',
      iconBg: 'bg-zinc-100 dark:bg-zinc-800/50',
      iconText: 'text-zinc-600 dark:text-zinc-400'
    };
  };

  const formatTime = (ms) => {
    const seconds = Math.floor(ms / 1000);
    const deciseconds = Math.floor((ms % 1000) / 100);
    return `${seconds}.${deciseconds}s`;
  };

  const getStatusText = () => {
    if (status === 'success' || (toolCall.result && !isActive)) {
      return toolCall.duration ? `Completed in ${formatTime(toolCall.duration)}` : 'Completed';
    }
    if (status === 'error') {
      return 'Failed';
    }
    if (status === 'running' || isActive) {
      return `Running ${formatTime(elapsedTime)}`;
    }

    return 'Pending';
  };

  const formatToolName = (name) => {
    return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getCompactArgs = () => {
    if (!toolCall.arguments) return '';

    try {
      const args = typeof toolCall.arguments === 'string'
        ? JSON.parse(toolCall.arguments)
        : toolCall.arguments;

      const entries = Object.entries(args).slice(0, 2);
      return entries.map(([key, value]) => {
        const stringValue = typeof value === 'string' ? value : JSON.stringify(value);
        const truncated = stringValue.length > 30 ? stringValue.substring(0, 30) + '...' : stringValue;
        return `${key}: ${truncated}`;
      }).join(', ');
    } catch {
      return '';
    }
  };

  const copyToClipboard = async () => {
    const result = typeof toolCall.result === 'string'
      ? toolCall.result
      : JSON.stringify(toolCall.result, null, 2);

    await navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const syntaxHighlight = (json) => {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, null, 2);
    }

    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'text-zinc-700 dark:text-zinc-300';
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'text-blue-600 dark:text-blue-400 font-medium';
        } else {
          cls = 'text-green-600 dark:text-green-400';
        }
      } else if (/true|false/.test(match)) {
        cls = 'text-purple-600 dark:text-purple-400';
      } else if (/null/.test(match)) {
        cls = 'text-red-600 dark:text-red-400';
      } else {
        cls = 'text-orange-600 dark:text-orange-400';
      }
      return `<span class="${cls}">${match}</span>`;
    });
  };

  const styles = getStatusStyles();

  return (
    <div className={`my-2 shadow-sm  max-w-full rounded-lg border ${styles.border} ${styles.bg} overflow-hidden transition-all duration-200 animate-slide-in-bottom`}>
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/50 transition-colors duration-150"
      >
        {/* Icon */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-lg ${styles.iconBg} ${styles.iconText} flex items-center justify-center`}>
          {getToolIcon(toolCall.name)}
        </div>

        {/* Tool info */}
        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              {formatToolName(toolCall.name)}
            </span>
            {!isExpanded && toolCall.arguments && (
              <span className="text-xs text-zinc-500 dark:text-zinc-500 truncate max-w-xs">
                {getCompactArgs()}
              </span>
            )}
          </div>
        </div>

        {/* Status */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {getStatusIcon()}
          <span className="text-xs text-zinc-600 dark:text-zinc-400">
            {getStatusText()}
          </span>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-zinc-400 dark:text-zinc-600" />
          ) : (
            <ChevronRight className="w-4 h-4 text-zinc-400 dark:text-zinc-600" />
          )}
        </div>
      </button>

      {/* Expandable content */}
      <div
        style={{ height: `${contentHeight}px` }}
        className="overflow-hidden transition-[height] duration-200 ease-in-out"
      >
        <div ref={contentRef} className="px-4 pb-4 space-y-3">
          {/* Arguments */}
          {toolCall.arguments && (
            <div>
              <div className="text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Arguments
              </div>
              <div className="bg-white dark:bg-zinc-950 rounded-md border border-zinc-200 dark:border-zinc-800 p-3 overflow-x-auto">
                <pre className="text-xs font-mono break-words whitespace-pre-wrap">
                  <code
                    dangerouslySetInnerHTML={{
                      __html: syntaxHighlight(toolCall.arguments)
                    }}
                  />
                </pre>
              </div>
            </div>
          )}

          {/* Bash Terminal Output (for execute_bash tool) */}
          {(toolCall.name === 'execute_bash' || toolCall.name.includes('bash')) && toolCall.result && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Terminal className="w-4 h-4 text-zinc-700 dark:text-zinc-300" />
                <div className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  Terminal Output
                </div>
              </div>

              {/* Extract command from arguments */}
              {(() => {
                try {
                  const args = typeof toolCall.arguments === 'string'
                    ? JSON.parse(toolCall.arguments)
                    : toolCall.arguments;
                  const command = args?.command || args?.cmd;

                  if (command) {
                    return (
                      <div className="mb-2">
                        <div className="bg-zinc-900 dark:bg-zinc-950 rounded-t-md border border-zinc-700 dark:border-zinc-800 px-3 py-2 font-mono text-xs">
                          <span className="text-green-400">$</span>{' '}
                          <span className="text-zinc-100">{command}</span>
                        </div>
                      </div>
                    );
                  }
                } catch (e) {
                  return null;
                }
              })()}

              {/* Output - show the tool result as terminal output */}
              <div className="bg-zinc-950 dark:bg-black rounded-md border border-zinc-700 dark:border-zinc-800 p-3 overflow-x-auto max-h-96 overflow-y-auto font-mono text-xs">
                <pre className="text-zinc-100 whitespace-pre-wrap m-0">
                  {typeof toolCall.result === 'string' ? toolCall.result : JSON.stringify(toolCall.result, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Result */}
          {toolCall.result && !isActive && status !== 'running' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  Result
                </div>
                <button
                  onClick={copyToClipboard}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200 rounded transition-colors duration-150"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <div className="bg-white dark:bg-zinc-950 rounded-md border border-zinc-200 dark:border-zinc-800 p-3 overflow-x-auto max-h-96 overflow-y-auto">
                <pre className="text-xs font-mono break-words whitespace-pre-wrap">
                  <code
                    dangerouslySetInnerHTML={{
                      __html: syntaxHighlight(toolCall.result)
                    }}
                  />
                </pre>
              </div>
            </div>
          )}

          {/* Running indicator */}
          {(status === 'running' || isActive) && (
            <div className="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-600 dark:bg-blue-400 animate-pulse" />
              <span>Executing tool...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ToolCallDisplay;