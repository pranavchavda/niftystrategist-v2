import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  CheckCircle2,
  Circle,
  Plus,
  Trash2,
  RefreshCw,
  Loader2,
  AlertCircle,
  Calendar,
  Clock,
  ChevronDown,
  ChevronRight,
  Sparkles,
  X,
  ArrowLeft,
  Save,
  FileText,
  FolderOpen,
} from 'lucide-react';
import { Button } from './catalyst/button';

// Format relative date for display
function formatDueDate(dueString) {
  if (!dueString) return null;

  try {
    const due = new Date(dueString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const nextWeek = new Date(today);
    nextWeek.setDate(nextWeek.getDate() + 7);

    const dueDate = new Date(due.getFullYear(), due.getMonth(), due.getDate());

    // Check if it's today
    if (dueDate.getTime() === today.getTime()) {
      // Show time if available
      if (due.getHours() !== 0 || due.getMinutes() !== 0) {
        return due.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      }
      return 'Today';
    }

    // Check if it's tomorrow
    if (dueDate.getTime() === tomorrow.getTime()) {
      return 'Tomorrow';
    }

    // Check if it's within a week
    if (dueDate > today && dueDate < nextWeek) {
      return due.toLocaleDateString([], { weekday: 'short' });
    }

    // Otherwise show the date
    return due.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

// Calculate how overdue a task is
function getOverdueText(dueString) {
  if (!dueString) return '';

  try {
    const due = new Date(dueString);
    const now = new Date();
    const diffMs = now - due;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Due today';
    if (diffDays === 1) return '1 day late';
    return `${diffDays} days late`;
  } catch {
    return '';
  }
}

// Build task hierarchy from flat list (separates parent tasks and subtasks)
function buildHierarchy(flatTasks) {
  const parentTasks = [];
  const subtasksByParent = {};

  for (const task of flatTasks) {
    if (task.parent) {
      // This is a subtask
      if (!subtasksByParent[task.parent]) {
        subtasksByParent[task.parent] = [];
      }
      subtasksByParent[task.parent].push(task);
    } else {
      // This is a parent/top-level task
      parentTasks.push(task);
    }
  }

  return { parentTasks, subtasksByParent };
}

// Task Item Component - supports subtasks with expand/collapse
function TaskItem({
  task,
  subtasks = [],
  isExpanded = false,
  onToggleExpand,
  onAddSubtask,
  onComplete,
  onUncomplete,
  onDelete,
  onSelect,
  isSubtask = false,
  addingSubtaskTo,
  subtaskInput,
  setSubtaskInput,
  onCreateSubtask,
  isCreatingSubtask,
  setAddingSubtaskTo
}) {
  const isCompleted = task.status === 'completed';
  const isOverdue = !isCompleted && task.due && new Date(task.due) < new Date();
  const hasSubtasks = subtasks.length > 0;

  return (
    <div className={isSubtask ? 'ml-8' : ''}>
      <div
        className={`group flex items-start gap-2 p-3 rounded-lg transition-colors cursor-pointer
          ${isCompleted ? 'opacity-60' : ''}
          hover:bg-zinc-50 dark:hover:bg-zinc-800/50`}
        onClick={() => onSelect(task)}
      >
        {/* Expand/Collapse toggle for parent tasks */}
        {!isSubtask && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleExpand?.(task.id);
            }}
            className="mt-0.5 flex-shrink-0 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 w-5 h-5 flex items-center justify-center"
          >
            {hasSubtasks ? (
              isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
            ) : (
              <span className="w-4" /> // Spacer for alignment
            )}
          </button>
        )}

        {/* Checkbox */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            isCompleted ? onUncomplete(task.id) : onComplete(task.id);
          }}
          className={`mt-0.5 flex-shrink-0 transition-colors
            ${isCompleted
              ? 'text-green-500 hover:text-green-600'
              : 'text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300'
            }`}
        >
          {isCompleted ? (
            <CheckCircle2 className="w-5 h-5" />
          ) : (
            <Circle className="w-5 h-5" />
          )}
        </button>

        {/* Task Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className={`text-sm font-medium ${isCompleted ? 'line-through text-zinc-500' : 'text-zinc-900 dark:text-zinc-100'}`}>
              {task.title}
            </p>
            {/* Show task list name if not default */}
            {task.tasklist_title && task.tasklist_title !== 'My Tasks' && (
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full whitespace-nowrap">
                {task.tasklist_title}
              </span>
            )}
          </div>
          {task.notes && (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 line-clamp-1">
              {task.notes}
            </p>
          )}
          {/* Show subtask count when collapsed */}
          {hasSubtasks && !isExpanded && (
            <p className="mt-1 text-xs text-zinc-400">
              {subtasks.length} subtask{subtasks.length > 1 ? 's' : ''}
            </p>
          )}
        </div>

        {/* Due Date & Actions */}
        <div className="flex items-center gap-1">
          {task.due && (
            <span className={`text-xs mr-1 ${isOverdue ? 'text-red-500 font-medium' : 'text-zinc-500'}`}>
              {isOverdue ? getOverdueText(task.due) : formatDueDate(task.due)}
            </span>
          )}
          {/* Add subtask button - only for parent tasks (not subtasks) */}
          {!isSubtask && !isCompleted && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAddSubtask?.(task.id);
              }}
              className="p-1 text-zinc-400 hover:text-blue-500 transition-colors"
              title="Add subtask"
            >
              <Plus className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(task.id);
            }}
            className="opacity-0 group-hover:opacity-100 p-1 text-zinc-400 hover:text-red-500 transition-opacity"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Render subtasks when expanded */}
      {isExpanded && subtasks.map(subtask => (
        <TaskItem
          key={subtask.id}
          task={subtask}
          isSubtask={true}
          onComplete={onComplete}
          onUncomplete={onUncomplete}
          onDelete={onDelete}
          onSelect={onSelect}
        />
      ))}

      {/* Inline subtask creation input */}
      {addingSubtaskTo === task.id && (
        <div className="ml-8 mt-2 flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
          <Circle className="w-4 h-4 text-zinc-300 flex-shrink-0" />
          <input
            type="text"
            value={subtaskInput}
            onChange={(e) => setSubtaskInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && onCreateSubtask()}
            placeholder="Add subtask..."
            className="flex-1 bg-transparent text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none"
            autoFocus
          />
          <Button onClick={onCreateSubtask} disabled={isCreatingSubtask || !subtaskInput.trim()} color="blue" className="text-xs py-1 px-2">
            {isCreatingSubtask ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Add'}
          </Button>
          <button
            onClick={() => setAddingSubtaskTo(null)}
            className="p-1 text-zinc-400 hover:text-zinc-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

// Task Group Component - now with subtask hierarchy support
function TaskGroup({
  title,
  icon: Icon,
  tasks,
  color,
  defaultOpen = true,
  onComplete,
  onUncomplete,
  onDelete,
  onSelect,
  expandedTasks,
  onToggleExpand,
  onAddSubtask,
  addingSubtaskTo,
  subtaskInput,
  setSubtaskInput,
  onCreateSubtask,
  isCreatingSubtask,
  setAddingSubtaskTo,
  globalSubtasksByParent = {}  // Global map of subtasks by parent ID
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // Filter to only parent tasks (no parent field) - subtasks are fetched from globalSubtasksByParent
  const parentTasks = useMemo(
    () => tasks.filter(task => !task.parent),
    [tasks]
  );

  // Show nothing if no parent tasks
  if (parentTasks.length === 0) return null;

  return (
    <div className="mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 w-full px-2 py-1.5 text-sm font-semibold ${color} hover:bg-zinc-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors`}
      >
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        <Icon className="w-4 h-4" />
        <span>{title}</span>
        <span className="ml-auto text-xs font-normal text-zinc-500">({tasks.length})</span>
      </button>

      {isOpen && (
        <div className="mt-1 space-y-1">
          {parentTasks.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              subtasks={globalSubtasksByParent[task.id] || []}
              isExpanded={expandedTasks?.has(task.id)}
              onToggleExpand={onToggleExpand}
              onAddSubtask={onAddSubtask}
              onComplete={onComplete}
              onUncomplete={onUncomplete}
              onDelete={onDelete}
              onSelect={onSelect}
              addingSubtaskTo={addingSubtaskTo}
              subtaskInput={subtaskInput}
              setSubtaskInput={setSubtaskInput}
              onCreateSubtask={onCreateSubtask}
              isCreatingSubtask={isCreatingSubtask}
              setAddingSubtaskTo={setAddingSubtaskTo}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Task Detail Panel - Editable
function TaskDetail({
  task,
  onClose,
  onComplete,
  onUncomplete,
  onDelete,
  onUpdate,
  authToken,
  onPromote,
  subtasks = [],
  onAddSubtask,
  onSelect
}) {
  const [editedTitle, setEditedTitle] = useState(task?.title || '');
  const [editedNotes, setEditedNotes] = useState(task?.notes || '');
  const [editedDueDate, setEditedDueDate] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Task list state for move functionality
  const [taskLists, setTaskLists] = useState([]);
  const [selectedListId, setSelectedListId] = useState('');
  const [isMoving, setIsMoving] = useState(false);
  const [isLoadingLists, setIsLoadingLists] = useState(false);

  // Subtask creation state
  const [showSubtaskInput, setShowSubtaskInput] = useState(false);
  const [subtaskInputValue, setSubtaskInputValue] = useState('');
  const [isCreatingSubtask, setIsCreatingSubtask] = useState(false);

  // Update local state when task changes
  useEffect(() => {
    if (task) {
      setEditedTitle(task.title || '');
      setEditedNotes(task.notes || '');
      // Convert ISO date to YYYY-MM-DD for input
      if (task.due) {
        const dueDate = new Date(task.due);
        setEditedDueDate(dueDate.toISOString().split('T')[0]);
      } else {
        setEditedDueDate('');
      }
      setHasChanges(false);
      // Set current list
      setSelectedListId(task.tasklist_id || '@default');
    }
  }, [task]);

  // Fetch available task lists
  useEffect(() => {
    const fetchTaskLists = async () => {
      if (!authToken) return;
      setIsLoadingLists(true);
      try {
        const response = await fetch('/api/tasks/lists', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (response.ok) {
          const lists = await response.json();
          setTaskLists(lists);
        }
      } catch (err) {
        console.error('Failed to fetch task lists:', err);
      } finally {
        setIsLoadingLists(false);
      }
    };
    fetchTaskLists();
  }, [authToken]);

  // Track changes
  useEffect(() => {
    if (!task) return;
    const titleChanged = editedTitle !== (task.title || '');
    const notesChanged = editedNotes !== (task.notes || '');
    const originalDate = task.due ? new Date(task.due).toISOString().split('T')[0] : '';
    const dateChanged = editedDueDate !== originalDate;
    setHasChanges(titleChanged || notesChanged || dateChanged);
  }, [editedTitle, editedNotes, editedDueDate, task]);

  if (!task) return null;

  const isCompleted = task.status === 'completed';

  const handleSave = async () => {
    if (!hasChanges || isSaving) return;

    try {
      setIsSaving(true);

      const updateData = {};
      if (editedTitle !== task.title) updateData.title = editedTitle;
      if (editedNotes !== (task.notes || '')) updateData.notes = editedNotes;
      if (editedDueDate) {
        // Convert to RFC3339 format
        updateData.due_date = editedDueDate + 'T00:00:00.000Z';
      } else if (task.due && !editedDueDate) {
        // Clear due date
        updateData.due_date = null;
      }

      const tasklistParam = task.tasklist_id ? `?tasklist_id=${task.tasklist_id}` : '';
      const response = await fetch(`/api/tasks/${task.id}${tasklistParam}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updateData)
      });

      if (!response.ok) {
        throw new Error('Failed to update task');
      }

      // Trigger refresh
      if (onUpdate) onUpdate();
      setHasChanges(false);
    } catch (err) {
      console.error('Failed to save task:', err);
      alert('Failed to save changes: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  // Handle moving task to another list
  const handleMoveTask = async (newListId) => {
    if (!task || isMoving || newListId === (task.tasklist_id || '@default')) return;

    const currentListId = task.tasklist_id || '@default';

    try {
      setIsMoving(true);

      const response = await fetch(`/api/tasks/${task.id}/move`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          source_tasklist_id: currentListId,
          destination_tasklist_id: newListId
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to move task');
      }

      // Refresh tasks and close panel
      if (onUpdate) onUpdate();
      onClose();
    } catch (err) {
      console.error('Failed to move task:', err);
      alert('Failed to move task: ' + err.message);
    } finally {
      setIsMoving(false);
    }
  };

  // Create subtask from within the detail panel
  const handleCreateSubtask = async () => {
    if (!subtaskInputValue.trim() || isCreatingSubtask || !task) return;

    setIsCreatingSubtask(true);
    try {
      const tasklistId = task.tasklist_id || '@default';

      const response = await fetch(`/api/tasks/${task.id}/subtasks?tasklist_id=${tasklistId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: subtaskInputValue,
          parse_natural_language: true
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create subtask');
      }

      // Success - clear input and refresh
      setSubtaskInputValue('');
      setShowSubtaskInput(false);
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Failed to create subtask:', err);
      alert('Failed to create subtask: ' + err.message);
    } finally {
      setIsCreatingSubtask(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white dark:bg-zinc-900 shadow-xl border-l border-zinc-200 dark:border-zinc-700 z-50 overflow-auto">
      <div className="sticky top-0 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-700 px-4 py-3 flex items-center justify-between">
        <button
          onClick={onClose}
          className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>
        <div className="flex items-center gap-2">
          {hasChanges && (
            <Button
              onClick={handleSave}
              disabled={isSaving}
              color="blue"
              className="text-sm"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span className="ml-1.5">Save</span>
            </Button>
          )}
          <button
            onClick={() => onDelete(task.id)}
            className="p-2 text-zinc-400 hover:text-red-500"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Title - Editable */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            Title
          </label>
          <input
            type="text"
            value={editedTitle}
            onChange={(e) => setEditedTitle(e.target.value)}
            className={`w-full px-3 py-2 text-lg font-semibold bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors
              ${isCompleted ? 'line-through text-zinc-500' : 'text-zinc-900 dark:text-zinc-100'}`}
            placeholder="Task title"
          />
        </div>

        {/* Due Date - Editable */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            <Calendar className="w-4 h-4 inline mr-2" />
            Due Date
          </label>
          <input
            type="date"
            value={editedDueDate}
            onChange={(e) => setEditedDueDate(e.target.value)}
            className="w-full px-3 py-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-zinc-900 dark:text-zinc-100"
          />
          {editedDueDate && (
            <button
              onClick={() => setEditedDueDate('')}
              className="mt-2 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            >
              Clear due date
            </button>
          )}
        </div>

        {/* Notes - Editable */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            <FileText className="w-4 h-4 inline mr-2" />
            Notes
          </label>
          <textarea
            value={editedNotes}
            onChange={(e) => setEditedNotes(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm text-zinc-900 dark:text-zinc-100 resize-none"
            placeholder="Add notes..."
          />
        </div>

        {/* Move to List */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            <FolderOpen className="w-4 h-4 inline mr-2" />
            List
          </label>
          <div className="flex items-center gap-2">
            <select
              value={selectedListId}
              onChange={(e) => {
                setSelectedListId(e.target.value);
                handleMoveTask(e.target.value);
              }}
              disabled={isMoving || isLoadingLists}
              className="flex-1 px-3 py-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm text-zinc-900 dark:text-zinc-100"
            >
              {isLoadingLists ? (
                <option>Loading lists...</option>
              ) : taskLists.length === 0 ? (
                <option value="@default">My Tasks</option>
              ) : (
                taskLists.map((list) => (
                  <option key={list.id} value={list.id}>
                    {list.title}
                  </option>
                ))
              )}
            </select>
            {isMoving && (
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
            )}
          </div>
          {task.tasklist_title && task.tasklist_title !== 'My Tasks' && (
            <p className="mt-1 text-xs text-zinc-500">
              Currently in: {task.tasklist_title}
            </p>
          )}
        </div>

        {/* Subtasks section - only show for parent tasks (not subtasks) */}
        {!task.parent && (
          <div className="pt-4 border-t border-zinc-200 dark:border-zinc-700">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Subtasks ({subtasks.length})
              </label>
              {!showSubtaskInput && (
                <button
                  onClick={() => setShowSubtaskInput(true)}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                >
                  <Plus className="w-3 h-3" />
                  Add subtask
                </button>
              )}
            </div>

            {/* Inline subtask creation input */}
            {showSubtaskInput && (
              <div className="mb-3 flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
                <Circle className="w-4 h-4 text-zinc-300 flex-shrink-0" />
                <input
                  type="text"
                  value={subtaskInputValue}
                  onChange={(e) => setSubtaskInputValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleCreateSubtask()}
                  placeholder="Add subtask..."
                  className="flex-1 bg-transparent text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none"
                  autoFocus
                />
                <Button
                  onClick={handleCreateSubtask}
                  disabled={isCreatingSubtask || !subtaskInputValue.trim()}
                  color="blue"
                  className="text-xs py-1 px-2"
                >
                  {isCreatingSubtask ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Add'}
                </Button>
                <button
                  onClick={() => {
                    setShowSubtaskInput(false);
                    setSubtaskInputValue('');
                  }}
                  className="p-1 text-zinc-400 hover:text-zinc-600"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
            {subtasks.length > 0 ? (
              <div className="space-y-2">
                {subtasks.map(subtask => (
                  <div
                    key={subtask.id}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800/50 cursor-pointer group"
                    onClick={() => onSelect?.(subtask)}
                  >
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        subtask.status === 'completed'
                          ? onUncomplete(subtask.id)
                          : onComplete(subtask.id);
                      }}
                      className={`flex-shrink-0 ${
                        subtask.status === 'completed'
                          ? 'text-green-500 hover:text-green-600'
                          : 'text-zinc-400 hover:text-zinc-600'
                      }`}
                    >
                      {subtask.status === 'completed' ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : (
                        <Circle className="w-4 h-4" />
                      )}
                    </button>
                    <span className={`flex-1 text-sm ${
                      subtask.status === 'completed'
                        ? 'line-through text-zinc-500'
                        : 'text-zinc-900 dark:text-zinc-100'
                    }`}>
                      {subtask.title}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(subtask.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-zinc-400 hover:text-red-500"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-400 dark:text-zinc-500 italic">
                No subtasks yet
              </p>
            )}
          </div>
        )}

        {/* Subtask indicator */}
        {task.parent && (
          <div className="pt-4 border-t border-zinc-200 dark:border-zinc-700">
            <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <div className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-500" />
                <span className="text-sm text-blue-700 dark:text-blue-300">This is a subtask</span>
              </div>
              <Button
                onClick={() => {
                  onPromote?.(task.id);
                  onClose();
                }}
                color="zinc"
                outline
                className="text-xs"
              >
                Promote to task
              </Button>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="pt-4 border-t border-zinc-200 dark:border-zinc-700 flex gap-3">
          <Button
            onClick={() => isCompleted ? onUncomplete(task.id) : onComplete(task.id)}
            color={isCompleted ? 'zinc' : 'green'}
            className="flex-1"
          >
            {isCompleted ? 'Reopen Task' : 'Mark Complete'}
          </Button>
        </div>

        {/* Change indicator */}
        {hasChanges && (
          <p className="text-xs text-amber-600 dark:text-amber-400 text-center">
            You have unsaved changes
          </p>
        )}
      </div>
    </div>
  );
}

// Main TasksApp Component
export default function TasksApp({ authToken }) {
  // State
  const [tasks, setTasks] = useState({
    overdue: [],
    today: [],
    this_week: [],
    someday: [],
    completed_today: []
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [showCompleted, setShowCompleted] = useState(false);
  const [parsedPreview, setParsedPreview] = useState(null);

  // Task list state for creation
  const [availableLists, setAvailableLists] = useState([]);
  const [createInList, setCreateInList] = useState('@default');
  const [isCreatingList, setIsCreatingList] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [isSubmittingList, setIsSubmittingList] = useState(false);
  const [showManageLists, setShowManageLists] = useState(false);
  const [isDeletingList, setIsDeletingList] = useState(false);

  // Subtask state
  const [expandedTasks, setExpandedTasks] = useState(new Set());
  const [addingSubtaskTo, setAddingSubtaskTo] = useState(null);  // Parent task ID when adding subtask
  const [subtaskInput, setSubtaskInput] = useState('');
  const [isCreatingSubtask, setIsCreatingSubtask] = useState(false);

  const inputRef = useRef(null);

  // Load tasks on mount
  useEffect(() => {
    loadTasks();
    loadAvailableLists();
  }, [authToken]);

  // Load available task lists
  const loadAvailableLists = async () => {
    if (!authToken) return;
    try {
      const response = await fetch('/api/tasks/lists', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const lists = await response.json();
        setAvailableLists(lists);
      }
    } catch (err) {
      console.error('Failed to fetch task lists:', err);
    }
  };

  // Load tasks from API
  const loadTasks = async () => {
    if (!authToken) return;

    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch('/api/tasks?include_completed=true', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to load tasks');
      }

      const data = await response.json();
      console.log('[Tasks] API response:', JSON.stringify(data, null, 2));
      console.log('[Tasks] Sample task:', data.today?.[0] || data.someday?.[0] || data.overdue?.[0]);
      setTasks(data);
    } catch (err) {
      console.error('Failed to load tasks:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Sync (refresh) tasks
  const syncTasks = async () => {
    setIsSyncing(true);
    await loadTasks();
    setIsSyncing(false);
  };

  // Create task - uses direct endpoint with list support
  const createTask = async () => {
    if (!inputValue.trim() || isCreating) return;

    try {
      setIsCreating(true);
      setError(null);

      // Use direct POST endpoint which supports tasklist_id
      const response = await fetch('/api/tasks', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: inputValue,
          tasklist_id: createInList !== '@default' ? createInList : null,
          parse_natural_language: true
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create task');
      }

      const data = await response.json();
      console.log('Task created:', data);

      if (!data.success) {
        throw new Error('Task creation failed');
      }

      // Clear input and reload tasks
      setInputValue('');
      setParsedPreview(null);
      await loadTasks();

      // Focus input for next task
      inputRef.current?.focus();
    } catch (err) {
      console.error('Failed to create task:', err);
      setError(err.message);
    } finally {
      setIsCreating(false);
    }
  };

  // Create new task list
  const handleCreateList = async () => {
    if (!newListName.trim() || isSubmittingList) return;

    try {
      setIsSubmittingList(true);
      const response = await fetch('/api/tasks/lists', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: newListName })
      });

      if (!response.ok) throw new Error('Failed to create list');

      const newList = await response.json();

      // Update available lists and select the new one
      setAvailableLists(prev => [...prev, newList]);
      setCreateInList(newList.id);

      // Reset creation state
      setIsCreatingList(false);
      setNewListName('');
    } catch (err) {
      console.error('Failed to create list:', err);
      setError(err.message);
    } finally {
      setIsSubmittingList(false);
    }
  };

  // Delete task list
  const handleDeleteList = async (listId) => {
    if (listId === '@default' || isDeletingList) return;
    if (!confirm('Are you sure you want to delete this list? All tasks in it will be deleted permanently.')) return;

    try {
      setIsDeletingList(true);
      const response = await fetch(`/api/tasks/lists/${listId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (!response.ok) throw new Error('Failed to delete list');

      // Update available lists
      setAvailableLists(prev => prev.filter(l => l.id !== listId));

      // If we were creating in this list, reset to default
      if (createInList === listId) {
        setCreateInList('@default');
      }

    } catch (err) {
      console.error('Failed to delete list:', err);
      alert('Failed to delete list: ' + err.message);
    } finally {
      setIsDeletingList(false);
    }
  };

  // Toggle expand/collapse for parent task
  const toggleExpand = useCallback((taskId) => {
    setExpandedTasks(prev => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  }, []);

  // Handle add subtask button click
  const handleAddSubtask = useCallback((parentTaskId) => {
    setAddingSubtaskTo(parentTaskId);
    setSubtaskInput('');
    // Expand the parent to show the input
    setExpandedTasks(prev => new Set([...prev, parentTaskId]));
  }, []);

  // Create subtask
  const createSubtask = async () => {
    if (!subtaskInput.trim() || !addingSubtaskTo || isCreatingSubtask) return;

    setIsCreatingSubtask(true);
    try {
      const parentTask = findTask(addingSubtaskTo);
      const tasklistId = parentTask?.tasklist_id || '@default';

      const response = await fetch(`/api/tasks/${addingSubtaskTo}/subtasks?tasklist_id=${tasklistId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: subtaskInput,
          parse_natural_language: true
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create subtask');
      }

      // Success - clear input and reload
      setSubtaskInput('');
      setAddingSubtaskTo(null);
      await loadTasks();
    } catch (err) {
      console.error('Failed to create subtask:', err);
      setError(err.message);
    } finally {
      setIsCreatingSubtask(false);
    }
  };

  // Promote subtask to top-level task
  const promoteSubtask = async (taskId) => {
    try {
      const task = findTask(taskId);
      const tasklistId = task?.tasklist_id || '@default';

      const response = await fetch(`/api/tasks/${taskId}/promote?tasklist_id=${tasklistId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!response.ok) {
        throw new Error('Failed to promote subtask');
      }

      await loadTasks();
    } catch (err) {
      console.error('Failed to promote subtask:', err);
      setError(err.message);
    }
  };

  // Helper to find task and its tasklist_id
  const findTask = (taskId) => {
    for (const group of ['overdue', 'today', 'this_week', 'someday', 'completed_today']) {
      const task = tasks[group].find(t => t.id === taskId);
      if (task) return task;
    }
    return null;
  };

  // Complete task
  const completeTask = async (taskId) => {
    try {
      const task = findTask(taskId);
      const tasklistParam = task?.tasklist_id ? `?tasklist_id=${task.tasklist_id}` : '';

      const response = await fetch(`/api/tasks/${taskId}/complete${tasklistParam}`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!response.ok) {
        throw new Error('Failed to complete task');
      }

      // Optimistic update - move to completed
      setTasks(prev => {
        const updated = { ...prev };
        let foundTask = null;

        // Find and remove from current group
        for (const group of ['overdue', 'today', 'this_week', 'someday']) {
          const idx = updated[group].findIndex(t => t.id === taskId);
          if (idx !== -1) {
            foundTask = { ...updated[group][idx], status: 'completed' };
            updated[group] = updated[group].filter(t => t.id !== taskId);
            break;
          }
        }

        // Add to completed_today
        if (foundTask) {
          updated.completed_today = [foundTask, ...updated.completed_today];
        }

        return updated;
      });

      // Close detail panel if this task was selected
      if (selectedTask?.id === taskId) {
        setSelectedTask(prev => prev ? { ...prev, status: 'completed' } : null);
      }
    } catch (err) {
      console.error('Failed to complete task:', err);
      setError(err.message);
      // Reload on error to get correct state
      await loadTasks();
    }
  };

  // Uncomplete task
  const uncompleteTask = async (taskId) => {
    try {
      const task = findTask(taskId);
      const tasklistParam = task?.tasklist_id ? `?tasklist_id=${task.tasklist_id}` : '';

      const response = await fetch(`/api/tasks/${taskId}/uncomplete${tasklistParam}`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!response.ok) {
        throw new Error('Failed to reopen task');
      }

      // Reload to get correct grouping
      await loadTasks();

      // Update selected task if needed
      if (selectedTask?.id === taskId) {
        setSelectedTask(prev => prev ? { ...prev, status: 'needsAction' } : null);
      }
    } catch (err) {
      console.error('Failed to uncomplete task:', err);
      setError(err.message);
    }
  };

  // Delete task
  const deleteTask = async (taskId) => {
    if (!confirm('Delete this task?')) return;

    try {
      const task = findTask(taskId);
      const tasklistParam = task?.tasklist_id ? `?tasklist_id=${task.tasklist_id}` : '';

      const response = await fetch(`/api/tasks/${taskId}${tasklistParam}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!response.ok) {
        throw new Error('Failed to delete task');
      }

      // Close detail panel if this task was selected
      if (selectedTask?.id === taskId) {
        setSelectedTask(null);
      }

      // Remove from state
      setTasks(prev => {
        const updated = { ...prev };
        for (const group of Object.keys(updated)) {
          updated[group] = updated[group].filter(t => t.id !== taskId);
        }
        return updated;
      });
    } catch (err) {
      console.error('Failed to delete task:', err);
      setError(err.message);
    }
  };

  // Handle input key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      createTask();
    }
  };

  // Total task count
  const totalActive = tasks.overdue.length + tasks.today.length + tasks.this_week.length + tasks.someday.length;

  // Build global subtask map from ALL tasks (subtasks may be in different time groups than parents)
  const globalSubtasksByParent = useMemo(() => {
    const allTasks = [
      ...tasks.overdue,
      ...tasks.today,
      ...tasks.this_week,
      ...tasks.someday,
      ...tasks.completed_today
    ];
    const subtaskMap = {};
    for (const task of allTasks) {
      if (task.parent) {
        if (!subtaskMap[task.parent]) {
          subtaskMap[task.parent] = [];
        }
        subtaskMap[task.parent].push(task);
      }
    }
    return subtaskMap;
  }, [tasks]);

  return (
    <div className="h-full flex flex-col bg-white dark:bg-zinc-950">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Tasks</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {totalActive} active task{totalActive !== 1 ? 's' : ''}
            </p>
          </div>
          <Button
            onClick={syncTasks}
            disabled={isSyncing}
            color="zinc"
            outline
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
            Sync
          </Button>
          <Button
            onClick={() => setShowManageLists(true)}
            color="zinc"
            outline
            className="ml-2"
          >
            <FolderOpen className="w-4 h-4 mr-2" />
            Lists
          </Button>
        </div>
      </div>

      {/* Smart Input */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
        <div className="relative">
          <div className="flex items-center gap-3 p-3 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500">
            <Sparkles className="w-5 h-5 text-blue-500 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="What do you need to do? (e.g., Call John tomorrow at 2pm)"
              className="flex-1 bg-transparent text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 focus:outline-none"
              disabled={isCreating}
            />
            {inputValue && (
              <button
                onClick={() => setInputValue('')}
                className="text-zinc-400 hover:text-zinc-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <Button
              onClick={createTask}
              disabled={!inputValue.trim() || isCreating}
              color="blue"
              className="flex-shrink-0"
            >
              {isCreating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              <span className="ml-1.5 hidden sm:inline">Add</span>
            </Button>
          </div>
          <p className="mt-2 text-xs text-zinc-500">
            Type naturally - powered by the same AI as chat (e.g., "Call John tomorrow at 2pm")
          </p>
          {/* List selector for new tasks */}
          {availableLists.length >= 1 && (
            <div className="mt-3 flex items-center gap-2 text-xs">
              <span className="text-zinc-500">Add to:</span>

              {isCreatingList ? (
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={newListName}
                    onChange={(e) => setNewListName(e.target.value)}
                    placeholder="List name..."
                    className="px-2 py-1 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded text-zinc-900 dark:text-zinc-100 text-xs w-32 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    onKeyPress={(e) => e.key === 'Enter' && handleCreateList()}
                    autoFocus
                  />
                  <button
                    onClick={handleCreateList}
                    disabled={!newListName.trim() || isSubmittingList}
                    className="p-1 text-green-600 hover:text-green-700"
                  >
                    {isSubmittingList ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Save className="w-3 h-3" />
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setIsCreatingList(false);
                      setNewListName('');
                      setCreateInList('@default');
                    }}
                    className="p-1 text-zinc-400 hover:text-zinc-600"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <select
                  value={createInList}
                  onChange={(e) => {
                    if (e.target.value === 'NEW_LIST') {
                      setIsCreatingList(true);
                    } else {
                      setCreateInList(e.target.value);
                    }
                  }}
                  disabled={isCreating}
                  className="px-2 py-1 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded text-zinc-900 dark:text-zinc-100 text-xs cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-700"
                >
                  {availableLists.map((list) => (
                    <option key={list.id} value={list.id}>
                      {list.title}
                    </option>
                  ))}
                  <option disabled>──────────</option>
                  <option value="NEW_LIST">+ Create new list...</option>
                </select>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex-shrink-0 px-6 py-3 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
          <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Task List */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
          </div>
        ) : totalActive === 0 && tasks.completed_today.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <CheckCircle2 className="w-12 h-12 text-zinc-300 dark:text-zinc-600 mb-4" />
            <p className="text-zinc-500 dark:text-zinc-400 mb-2">No tasks yet</p>
            <p className="text-sm text-zinc-400 dark:text-zinc-500">
              Type a task above to get started
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Overdue */}
            <TaskGroup
              title="Overdue"
              icon={AlertCircle}
              tasks={tasks.overdue}
              color="text-red-600 dark:text-red-400"
              defaultOpen={true}
              onComplete={completeTask}
              onUncomplete={uncompleteTask}
              onDelete={deleteTask}
              onSelect={setSelectedTask}
              expandedTasks={expandedTasks}
              onToggleExpand={toggleExpand}
              onAddSubtask={handleAddSubtask}
              addingSubtaskTo={addingSubtaskTo}
              subtaskInput={subtaskInput}
              setSubtaskInput={setSubtaskInput}
              onCreateSubtask={createSubtask}
              isCreatingSubtask={isCreatingSubtask}
              setAddingSubtaskTo={setAddingSubtaskTo}
              globalSubtasksByParent={globalSubtasksByParent}
            />

            {/* Today */}
            <TaskGroup
              title="Today"
              icon={Clock}
              tasks={tasks.today}
              color="text-blue-600 dark:text-blue-400"
              defaultOpen={true}
              onComplete={completeTask}
              onUncomplete={uncompleteTask}
              onDelete={deleteTask}
              onSelect={setSelectedTask}
              expandedTasks={expandedTasks}
              onToggleExpand={toggleExpand}
              onAddSubtask={handleAddSubtask}
              addingSubtaskTo={addingSubtaskTo}
              subtaskInput={subtaskInput}
              setSubtaskInput={setSubtaskInput}
              onCreateSubtask={createSubtask}
              isCreatingSubtask={isCreatingSubtask}
              setAddingSubtaskTo={setAddingSubtaskTo}
              globalSubtasksByParent={globalSubtasksByParent}
            />

            {/* This Week */}
            <TaskGroup
              title="This Week"
              icon={Calendar}
              tasks={tasks.this_week}
              color="text-amber-600 dark:text-amber-400"
              defaultOpen={true}
              onComplete={completeTask}
              onUncomplete={uncompleteTask}
              onDelete={deleteTask}
              onSelect={setSelectedTask}
              expandedTasks={expandedTasks}
              onToggleExpand={toggleExpand}
              onAddSubtask={handleAddSubtask}
              addingSubtaskTo={addingSubtaskTo}
              subtaskInput={subtaskInput}
              setSubtaskInput={setSubtaskInput}
              onCreateSubtask={createSubtask}
              isCreatingSubtask={isCreatingSubtask}
              setAddingSubtaskTo={setAddingSubtaskTo}
              globalSubtasksByParent={globalSubtasksByParent}
            />

            {/* Someday */}
            <TaskGroup
              title="Someday"
              icon={Sparkles}
              tasks={tasks.someday}
              color="text-zinc-600 dark:text-zinc-400"
              defaultOpen={tasks.overdue.length === 0 && tasks.today.length === 0}
              onComplete={completeTask}
              onUncomplete={uncompleteTask}
              onDelete={deleteTask}
              onSelect={setSelectedTask}
              expandedTasks={expandedTasks}
              onToggleExpand={toggleExpand}
              onAddSubtask={handleAddSubtask}
              addingSubtaskTo={addingSubtaskTo}
              subtaskInput={subtaskInput}
              setSubtaskInput={setSubtaskInput}
              onCreateSubtask={createSubtask}
              isCreatingSubtask={isCreatingSubtask}
              setAddingSubtaskTo={setAddingSubtaskTo}
              globalSubtasksByParent={globalSubtasksByParent}
            />

            {/* Completed Today */}
            {tasks.completed_today.length > 0 && (
              <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  onClick={() => setShowCompleted(!showCompleted)}
                  className="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                >
                  {showCompleted ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Completed Today ({tasks.completed_today.length})</span>
                </button>

                {showCompleted && (
                  <div className="mt-2 space-y-1">
                    {tasks.completed_today.map((task) => (
                      <TaskItem
                        key={task.id}
                        task={task}
                        onComplete={completeTask}
                        onUncomplete={uncompleteTask}
                        onDelete={deleteTask}
                        onSelect={setSelectedTask}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Task Detail Panel */}
      {selectedTask && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/20 z-40"
            onClick={() => setSelectedTask(null)}
          />
          <TaskDetail
            task={selectedTask}
            onClose={() => setSelectedTask(null)}
            onComplete={completeTask}
            onUncomplete={uncompleteTask}
            onDelete={deleteTask}
            onUpdate={loadTasks}
            authToken={authToken}
            onPromote={promoteSubtask}
            subtasks={globalSubtasksByParent[selectedTask?.id] || []}
            onAddSubtask={handleAddSubtask}
            onSelect={setSelectedTask}
          />
        </>
      )}

      {/* Manage Lists Modal */}
      {showManageLists && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl max-w-md w-full overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
              <h3 className="font-semibold text-lg text-zinc-900 dark:text-zinc-100">Manage Lists</h3>
              <button
                onClick={() => setShowManageLists(false)}
                className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 max-h-[60vh] overflow-y-auto">
              {availableLists.length === 0 ? (
                <p className="text-zinc-500 text-center py-4">No lists found</p>
              ) : (
                <div className="space-y-2">
                  {availableLists.map(list => (
                    <div
                      key={list.id}
                      className="flex items-center justify-between p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg"
                    >
                      <span className="font-medium text-zinc-900 dark:text-zinc-100">
                        {list.title}
                      </span>
                      {list.id !== '@default' && list.title !== 'My Tasks' && (
                        <button
                          onClick={() => handleDeleteList(list.id)}
                          className="p-2 text-zinc-400 hover:text-red-500 transition-colors"
                          title="Delete list"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                      {/* Default list cannot be deleted */}
                      {(list.id === '@default' || list.title === 'My Tasks') && (
                        <span className="text-xs text-zinc-400 italic px-2">Default</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="px-4 py-3 bg-zinc-50 dark:bg-zinc-800/50 border-t border-zinc-200 dark:border-zinc-700 text-right">
              <Button onClick={() => setShowManageLists(false)} color="white">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
