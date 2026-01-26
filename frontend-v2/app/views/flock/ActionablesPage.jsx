import React, { useState, useEffect } from 'react';
import {
  FunnelIcon,
  XMarkIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  PlusCircleIcon,
} from '@heroicons/react/20/solid';
import ActionableCard from './ActionableCard';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const ACTIONABLE_TYPES = [
  { value: 'task', label: 'Task', icon: '📋', color: 'blue' },
  { value: 'decision', label: 'Decision', icon: '🎯', color: 'purple' },
  { value: 'question', label: 'Question', icon: '❓', color: 'yellow' },
  { value: 'reminder', label: 'Reminder', icon: '⏰', color: 'green' },
  { value: 'deadline', label: 'Deadline', icon: '📅', color: 'red' },
  { value: 'followup', label: 'Follow-up', icon: '🔄', color: 'indigo' },
  { value: 'info', label: 'Info', icon: 'ℹ️', color: 'gray' },
];

const PRIORITIES = [
  { value: 'urgent', label: 'Urgent', color: 'red' },
  { value: 'high', label: 'High', color: 'orange' },
  { value: 'medium', label: 'Medium', color: 'yellow' },
  { value: 'low', label: 'Low', color: 'gray' },
];

const STATUSES = [
  { value: 'pending', label: 'Pending', icon: ClockIcon, color: 'yellow' },
  { value: 'in_progress', label: 'In Progress', icon: ClipboardDocumentListIcon, color: 'blue' },
  { value: 'completed', label: 'Completed', icon: CheckCircleIcon, color: 'green' },
  { value: 'added_to_tasks', label: 'In Google Tasks', icon: PlusCircleIcon, color: 'purple' },
];

export default function ActionablesPage({ authToken }) {
  const [actionables, setActionables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showFilters, setShowFilters] = useState(false);

  // Filter states
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [selectedPriorities, setSelectedPriorities] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState(['pending', 'in_progress']);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchActionables();
  }, [selectedTypes, selectedPriorities, selectedStatuses]);

  const fetchActionables = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();

      if (selectedTypes.length > 0) {
        selectedTypes.forEach(type => params.append('type', type));
      }
      if (selectedPriorities.length > 0) {
        selectedPriorities.forEach(priority => params.append('priority', priority));
      }
      if (selectedStatuses.length > 0) {
        selectedStatuses.forEach(status => params.append('status', status));
      }

      const response = await fetch(`${API_BASE_URL}/api/flock/actionables?${params}`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch actionables');

      const data = await response.json();
      setActionables(data.actionables || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddToGoogleTasks = async (actionableIds) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/flock/actionables/create-tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ actionable_ids: actionableIds }),
      });

      if (!response.ok) throw new Error('Failed to add to Google Tasks');

      const data = await response.json();

      // Refresh actionables to show updated status
      fetchActionables();

      return data;
    } catch (err) {
      console.error('Error adding to Google Tasks:', err);
      throw err;
    }
  };

  const toggleType = (type) => {
    setSelectedTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

  const togglePriority = (priority) => {
    setSelectedPriorities(prev =>
      prev.includes(priority) ? prev.filter(p => p !== priority) : [...prev, priority]
    );
  };

  const toggleStatus = (status) => {
    setSelectedStatuses(prev =>
      prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]
    );
  };

  const clearFilters = () => {
    setSelectedTypes([]);
    setSelectedPriorities([]);
    setSelectedStatuses(['pending', 'in_progress']);
    setSearchQuery('');
  };

  const filteredActionables = actionables.filter(actionable => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      actionable.title?.toLowerCase().includes(query) ||
      actionable.description?.toLowerCase().includes(query) ||
      actionable.context?.toLowerCase().includes(query)
    );
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-sm text-zinc-500">Loading actionables...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <ExclamationCircleIcon className="h-12 w-12 text-red-500 mx-auto" />
          <p className="mt-4 text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex-shrink-0 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 p-4">
        <div className="flex items-center gap-4">
          {/* Search */}
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search actionables..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors
              ${
                showFilters
                  ? 'bg-purple-600 text-white'
                  : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
              }
            `}
          >
            <FunnelIcon className="h-5 w-5" />
            <span>Filters</span>
            {(selectedTypes.length > 0 || selectedPriorities.length > 0) && (
              <span className="px-2 py-0.5 text-xs bg-white/20 rounded-full">
                {selectedTypes.length + selectedPriorities.length}
              </span>
            )}
          </button>

          {/* Results Count */}
          <div className="text-sm text-zinc-600 dark:text-zinc-400">
            {filteredActionables.length} {filteredActionables.length === 1 ? 'item' : 'items'}
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mt-4 p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Filters</h3>
              <button
                onClick={clearFilters}
                className="text-xs text-purple-600 hover:text-purple-700 font-medium"
              >
                Clear all
              </button>
            </div>

            <div className="space-y-4">
              {/* Type Filter */}
              <div>
                <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">
                  Type
                </label>
                <div className="flex flex-wrap gap-2">
                  {ACTIONABLE_TYPES.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => toggleType(type.value)}
                      className={`
                        px-3 py-1.5 text-xs font-medium rounded-full transition-colors
                        ${
                          selectedTypes.includes(type.value)
                            ? `bg-${type.color}-600 text-white`
                            : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-300 dark:hover:bg-zinc-600'
                        }
                      `}
                    >
                      <span className="mr-1">{type.icon}</span>
                      {type.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Priority Filter */}
              <div>
                <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">
                  Priority
                </label>
                <div className="flex flex-wrap gap-2">
                  {PRIORITIES.map((priority) => (
                    <button
                      key={priority.value}
                      onClick={() => togglePriority(priority.value)}
                      className={`
                        px-3 py-1.5 text-xs font-medium rounded-full transition-colors
                        ${
                          selectedPriorities.includes(priority.value)
                            ? `bg-${priority.color}-600 text-white`
                            : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-300 dark:hover:bg-zinc-600'
                        }
                      `}
                    >
                      {priority.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status Filter */}
              <div>
                <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">
                  Status
                </label>
                <div className="flex flex-wrap gap-2">
                  {STATUSES.map((status) => {
                    const Icon = status.icon;
                    return (
                      <button
                        key={status.value}
                        onClick={() => toggleStatus(status.value)}
                        className={`
                          flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full transition-colors
                          ${
                            selectedStatuses.includes(status.value)
                              ? `bg-${status.color}-600 text-white`
                              : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-300 dark:hover:bg-zinc-600'
                          }
                        `}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        {status.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Actionables List */}
      <div className="flex-1 overflow-auto p-6">
        {filteredActionables.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <ClipboardDocumentListIcon className="h-16 w-16 text-zinc-300 dark:text-zinc-700 mb-4" />
            <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              No actionables found
            </h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
              {searchQuery || selectedTypes.length > 0 || selectedPriorities.length > 0
                ? 'Try adjusting your filters or search query'
                : 'Actionables from your Flock messages will appear here'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredActionables.map((actionable) => (
              <ActionableCard
                key={actionable.id}
                actionable={actionable}
                onAddToGoogleTasks={handleAddToGoogleTasks}
                authToken={authToken}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
