import { useState, useEffect } from "react";
import {
  ExclamationTriangleIcon,
  ArrowPathRoundedSquareIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from "@heroicons/react/24/outline";

/**
 * TokenUsageBanner - Displays token usage and fork recommendations
 *
 * Shows a banner when token usage approaches the warning threshold (100k)
 * Provides quick access to fork functionality to start fresh with context
 */
function TokenUsageBanner({
  tokenUsage,
  onFork,
  isForkingConversation,
  isLoading,
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!tokenUsage) return null;

  const {
    total_input_tokens = 0,
    total_output_tokens = 0,
    total_tokens = 0,
    warning_threshold = 100000,
    should_fork = false,
    warning_message = null,
  } = tokenUsage;

  // Calculate percentage for visual indicator
  const usagePercentage = Math.min(
    (total_input_tokens / warning_threshold) * 100,
    100
  );

  // Determine severity level
  const getSeverity = () => {
    if (usagePercentage >= 90) return "critical";
    if (usagePercentage >= 75) return "warning";
    if (usagePercentage >= 50) return "notice";
    return "normal";
  };

  const severity = getSeverity();

  // Format token count for display
  const formatTokens = (count) => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M`;
    }
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}k`;
    }
    return count.toString();
  };

  // Color scheme based on severity
  const colors = {
    normal: {
      bg: "bg-zinc-100 dark:bg-zinc-800",
      text: "text-zinc-600 dark:text-zinc-400",
      border: "border-zinc-200 dark:border-zinc-700",
      bar: "bg-zinc-400 dark:bg-zinc-500",
    },
    notice: {
      bg: "bg-blue-50 dark:bg-blue-900/20",
      text: "text-blue-700 dark:text-blue-300",
      border: "border-blue-200 dark:border-blue-700",
      bar: "bg-blue-500 dark:bg-blue-400",
    },
    warning: {
      bg: "bg-amber-50 dark:bg-amber-900/20",
      text: "text-amber-700 dark:text-amber-300",
      border: "border-amber-200 dark:border-amber-700",
      bar: "bg-amber-500 dark:bg-amber-400",
    },
    critical: {
      bg: "bg-red-50 dark:bg-red-900/20",
      text: "text-red-700 dark:text-red-300",
      border: "border-red-200 dark:border-red-700",
      bar: "bg-red-500 dark:bg-red-400",
    },
  };

  const style = colors[severity];

  // Only show banner if there's meaningful usage or a warning
  if (total_tokens === 0 && !should_fork) return null;

  // Compact view for normal usage
  if (severity === "normal" && !isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="flex items-center gap-2 px-3 py-1.5 text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
      >
        <span>{formatTokens(total_tokens)} tokens</span>
        <ChevronUpIcon className="w-3 h-3" />
      </button>
    );
  }

  return (
    <div
      className={`rounded-lg border ${style.border} ${style.bg} p-3 mb-3 animate-fade-in`}
    >
      {/* Header with toggle */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {severity !== "normal" && (
            <ExclamationTriangleIcon className={`w-4 h-4 ${style.text}`} />
          )}
          <span className={`text-sm font-medium ${style.text}`}>
            {severity === "critical"
              ? "Context Limit Approaching"
              : severity === "warning"
                ? "High Token Usage"
                : "Token Usage"}
          </span>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`p-1 rounded hover:bg-white/50 dark:hover:bg-black/20 transition-colors ${style.text}`}
        >
          {isExpanded ? (
            <ChevronDownIcon className="w-4 h-4" />
          ) : (
            <ChevronUpIcon className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-white/50 dark:bg-black/20 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full ${style.bar} transition-all duration-500`}
          style={{ width: `${usagePercentage}%` }}
        />
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs">
        <div className={style.text}>
          <span className="font-semibold">{formatTokens(total_tokens)}</span>
          <span className="opacity-70"> context tokens</span>
          {total_output_tokens > 0 && (
            <>
              <span className="mx-1 opacity-50">|</span>
              <span className="opacity-70">{formatTokens(total_output_tokens)} from assistant</span>
            </>
          )}
        </div>
        <div className={`${style.text} opacity-70`}>
          {usagePercentage.toFixed(0)}% of {formatTokens(warning_threshold)} limit
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-current/10">
          {/* Warning message */}
          {warning_message && (
            <p className={`text-xs ${style.text} mb-3`}>{warning_message}</p>
          )}

          {/* Fork recommendation */}
          {should_fork && (
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
              <p className={`text-xs ${style.text} flex-1`}>
                Consider forking to start fresh with a compressed summary of this
                conversation. This preserves context while reducing tokens.
              </p>
              <button
                onClick={onFork}
                disabled={isForkingConversation || isLoading}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all
                  ${isForkingConversation || isLoading
                    ? "opacity-50 cursor-not-allowed"
                    : "hover:opacity-90"
                  }
                  ${severity === "critical"
                    ? "bg-red-600 text-white"
                    : "bg-amber-600 text-white"
                  }
                `}
              >
                <ArrowPathRoundedSquareIcon className="w-3.5 h-3.5" />
                {isForkingConversation ? "Forking..." : "Fork Now"}
              </button>
            </div>
          )}

          {/* Info text for non-critical usage */}
          {!should_fork && (
            <p className={`text-xs ${style.text} opacity-70`}>
              Token usage is tracked to help you manage conversation length.
              Consider forking when approaching the limit for optimal performance.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default TokenUsageBanner;
