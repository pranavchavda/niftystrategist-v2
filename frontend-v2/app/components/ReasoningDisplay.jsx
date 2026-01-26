import React, { useState, useEffect } from 'react';
import { ChevronDownIcon, ChevronRightIcon, SparklesIcon, CpuChipIcon } from '@heroicons/react/24/outline';

function ReasoningDisplay({ reasoning, isStreaming }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [displayedReasoning, setDisplayedReasoning] = useState('');
  const [animationPhase, setAnimationPhase] = useState(0);

  // Animate the reasoning text when streaming
  useEffect(() => {
    if (isStreaming && reasoning) {
      setDisplayedReasoning(reasoning);
    } else if (!isStreaming && reasoning) {
      setDisplayedReasoning(reasoning);
    }
  }, [reasoning, isStreaming]);

  // Thinking animation
  useEffect(() => {
    if (isStreaming && !reasoning) {
      const interval = setInterval(() => {
        setAnimationPhase(prev => (prev + 1) % 4);
      }, 500);
      return () => clearInterval(interval);
    }
  }, [isStreaming, reasoning]);

  if (!isStreaming && !reasoning) {
    return null;
  }

  const getThinkingText = () => {
    const dots = '.'.repeat(animationPhase);
    return `Thinking${dots}`;
  };

  return (
    <div className="py-6 px-4 bg-purple-50/50 dark:bg-purple-950/20 border-y border-purple-200/50 dark:border-purple-800/30 animate-slide-in-bottom">
      <div className="max-w-3xl mx-auto">
        <div className="relative overflow-hidden rounded-lg bg-white dark:bg-zinc-900 border border-purple-200 dark:border-purple-800/50">


          {/* Header */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-6 h-6 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                {isStreaming ? (
                  <SparklesIcon className="w-4 h-4 animate-pulse" />
                ) : (
                  <CpuChipIcon className="w-4 h-4" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    Reasoning
                  </span>
                  {isStreaming && (
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      {getThinkingText()}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="text-zinc-400 dark:text-zinc-500">
              {isExpanded ? (
                <ChevronDownIcon className="w-4 h-4" />
              ) : (
                <ChevronRightIcon className="w-4 h-4" />
              )}
            </div>
          </button>

          {/* Content */}
          {isExpanded && (
            <div className="border-t border-zinc-200 dark:border-zinc-800 px-4 py-4">
              {displayedReasoning ? (
                <div className="text-sm text-zinc-700 dark:text-zinc-300 font-mono leading-relaxed whitespace-pre-wrap bg-zinc-50 dark:bg-zinc-950 rounded-lg p-4 border border-zinc-200 dark:border-zinc-800">
                  {displayedReasoning}
                  {isStreaming && (
                    <span className="inline-block w-1 h-4 bg-purple-500 ml-1 animate-pulse"></span>
                  )}
                </div>
              ) : isStreaming ? (
                <div className="flex items-center gap-2 py-4">
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse"></div>
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse animation-delay-150"></div>
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse animation-delay-300"></div>
                  <span className="text-sm text-zinc-600 dark:text-zinc-400 ml-2">
                    Thinking...
                  </span>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ReasoningDisplay;