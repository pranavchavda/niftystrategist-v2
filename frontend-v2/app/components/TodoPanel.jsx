import React, { useState } from 'react';
import { CheckCircleIcon, ClockIcon, CircleStackIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';

/**
 * TodoPanel - Displays real-time task progress (Claude Code style)
 *
 * Shows tasks the agent is working on with 3 states:
 * - pending: Not started yet (gray)
 * - in_progress: Currently working on (blue, animated)
 * - completed: Finished (green, checkmark)
 *
 * Features:
 * - Collapsible on mobile to avoid covering streamed text
 * - Shows progress bar and task count
 */
export default function TodoPanel({ todos = [] }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!todos || todos.length === 0) {
    return null; // Don't show panel if no todos
  }

  const completed = todos.filter(t => t.status === 'completed').length;
  const total = todos.length;
  const progress = total > 0 ? (completed / total) * 100 : 0;

  return (
    <div className="bg-white dark:bg-zinc-800 rounded-lg shadow-sm border border-zinc-200 dark:border-zinc-700 overflow-hidden">
      {/* Header with progress - clickable to toggle collapse on mobile */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer lg:cursor-default"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
          Task Progress
          {/* Collapse button - only visible on mobile */}
          <button
            className="lg:hidden p-1 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setIsCollapsed(!isCollapsed);
            }}
          >
            {isCollapsed ? (
              <ChevronDownIcon className="h-4 w-4" />
            ) : (
              <ChevronUpIcon className="h-4 w-4" />
            )}
          </button>
        </h3>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {completed}/{total} completed
        </span>
      </div>

      {/* Progress bar - always visible */}
      <div className="px-3 pb-3">
        <div className="w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-1.5">
          <div
            className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Task list - collapsible on mobile */}
      {!isCollapsed && (
        <div className="px-3 pb-3 space-y-1.5">
        {todos.map((todo, index) => (
          <div
            key={todo.id || index}
            className="flex items-start gap-2 text-sm"
          >
            {/* Status icon */}
            <div className="flex-shrink-0 mt-0.5">
              {todo.status === 'completed' && (
                <CheckCircleIcon className="h-4 w-4 text-green-500" />
              )}
              {todo.status === 'in_progress' && (
                <ClockIcon className="h-4 w-4 text-blue-500 animate-pulse" />
              )}
              {todo.status === 'pending' && (
                <CircleStackIcon className="h-4 w-4 text-zinc-400" />
              )}
            </div>

            {/* Task text */}
            <span
              className={`flex-1 ${
                todo.status === 'completed'
                  ? 'text-zinc-500 dark:text-zinc-400 line-through'
                  : todo.status === 'in_progress'
                  ? 'text-blue-600 dark:text-blue-400 font-medium'
                  : 'text-zinc-700 dark:text-zinc-300'
              }`}
            >
              {todo.status === 'in_progress' ? todo.activeForm : todo.content}
            </span>
          </div>
        ))}
        </div>
      )}
    </div>
  );
}
