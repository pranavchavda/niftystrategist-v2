import React, { useState } from 'react';
import {
  ClockIcon,
  CheckCircleIcon,
  CalendarIcon,
  UserIcon,
  ChatBubbleLeftRightIcon,
  PlusCircleIcon,
  CheckIcon,
} from '@heroicons/react/20/solid';

const ACTIONABLE_TYPES = {
  task: { icon: '📋', color: 'blue' },
  decision: { icon: '🎯', color: 'purple' },
  question: { icon: '❓', color: 'yellow' },
  reminder: { icon: '⏰', color: 'green' },
  deadline: { icon: '📅', color: 'red' },
  followup: { icon: '🔄', color: 'indigo' },
  info: { icon: 'ℹ️', color: 'gray' },
};

const PRIORITIES = {
  urgent: { label: 'Urgent', color: 'red', bgColor: 'bg-red-50', textColor: 'text-red-700' },
  high: { label: 'High', color: 'orange', bgColor: 'bg-orange-50', textColor: 'text-orange-700' },
  medium: { label: 'Medium', color: 'yellow', bgColor: 'bg-yellow-50', textColor: 'text-yellow-700' },
  low: { label: 'Low', color: 'gray', bgColor: 'bg-gray-50', textColor: 'text-gray-700' },
};

const STATUSES = {
  pending: { label: 'Pending', icon: ClockIcon, color: 'yellow' },
  in_progress: { label: 'In Progress', icon: ClockIcon, color: 'blue' },
  completed: { label: 'Completed', icon: CheckCircleIcon, color: 'green' },
  added_to_tasks: { label: 'In Google Tasks', icon: PlusCircleIcon, color: 'purple' },
};

export default function ActionableCard({ actionable, onAddToGoogleTasks, authToken }) {
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(null);

  const typeInfo = ACTIONABLE_TYPES[actionable.type] || ACTIONABLE_TYPES.info;
  const priorityInfo = PRIORITIES[actionable.priority] || PRIORITIES.low;
  const statusInfo = STATUSES[actionable.status] || STATUSES.pending;
  const StatusIcon = statusInfo.icon;

  const handleAddToGoogleTasks = async () => {
    try {
      setAdding(true);
      setError(null);
      await onAddToGoogleTasks([actionable.id]);
    } catch (err) {
      setError('Failed to add to Google Tasks');
    } finally {
      setAdding(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return null;
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const canAddToTasks = actionable.status === 'pending' || actionable.status === 'in_progress';

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden hover:shadow-lg transition-shadow">
      {/* Header */}
      <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{typeInfo.icon}</span>
            <div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${priorityInfo.bgColor} ${priorityInfo.textColor}`}>
                {priorityInfo.label}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-600 dark:text-zinc-400">
            <StatusIcon className={`h-4 w-4 text-${statusInfo.color}-600`} />
            <span>{statusInfo.label}</span>
          </div>
        </div>

        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
          {actionable.title}
        </h3>

        {actionable.description && (
          <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2">
            {actionable.description}
          </p>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Context */}
        {actionable.context && (
          <div className="flex items-start gap-2 text-sm">
            <ChatBubbleLeftRightIcon className="h-4 w-4 text-zinc-400 mt-0.5 flex-shrink-0" />
            <p className="text-zinc-600 dark:text-zinc-400 line-clamp-2">{actionable.context}</p>
          </div>
        )}

        {/* Assigned To */}
        {actionable.assigned_to && (
          <div className="flex items-center gap-2 text-sm">
            <UserIcon className="h-4 w-4 text-zinc-400" />
            <span className="text-zinc-600 dark:text-zinc-400">
              Assigned to: <span className="font-medium text-zinc-900 dark:text-zinc-100">{actionable.assigned_to}</span>
            </span>
          </div>
        )}

        {/* Due Date */}
        {actionable.due_date && (
          <div className="flex items-center gap-2 text-sm">
            <CalendarIcon className="h-4 w-4 text-zinc-400" />
            <span className="text-zinc-600 dark:text-zinc-400">
              Due: <span className="font-medium text-zinc-900 dark:text-zinc-100">{formatDate(actionable.due_date)}</span>
            </span>
          </div>
        )}

        {/* Confidence Score */}
        {actionable.confidence_score && (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  actionable.confidence_score >= 0.8
                    ? 'bg-green-500'
                    : actionable.confidence_score >= 0.6
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
                style={{ width: `${actionable.confidence_score * 100}%` }}
              />
            </div>
            <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">
              {Math.round(actionable.confidence_score * 100)}%
            </span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 bg-zinc-50 dark:bg-zinc-800/50 border-t border-zinc-200 dark:border-zinc-800">
        {actionable.status === 'added_to_tasks' ? (
          <div className="flex items-center justify-center gap-2 text-sm text-green-600 dark:text-green-400">
            <CheckCircleIcon className="h-5 w-5" />
            <span className="font-medium">Added to Google Tasks</span>
          </div>
        ) : canAddToTasks ? (
          <button
            onClick={handleAddToGoogleTasks}
            disabled={adding}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white rounded-lg font-medium transition-colors"
          >
            {adding ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Adding...</span>
              </>
            ) : (
              <>
                <PlusCircleIcon className="h-5 w-5" />
                <span>Add to Google Tasks</span>
              </>
            )}
          </button>
        ) : (
          <div className="flex items-center justify-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <CheckCircleIcon className="h-5 w-5" />
            <span className="font-medium">Completed</span>
          </div>
        )}

        {error && (
          <div className="mt-2 text-xs text-red-600 dark:text-red-400 text-center">{error}</div>
        )}
      </div>

      {/* Metadata Footer */}
      <div className="px-4 py-2 bg-zinc-100 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400 flex items-center justify-between">
        <span>Extracted: {formatDate(actionable.extracted_at)}</span>
        {actionable.message_id && (
          <span className="font-mono">#{actionable.message_id.slice(0, 8)}</span>
        )}
      </div>
    </div>
  );
}
