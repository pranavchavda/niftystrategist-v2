import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router';
import { Subheading } from './catalyst/heading';
import { Textarea } from './catalyst/textarea';
import { Button } from './catalyst/button';
import { Badge } from './catalyst/badge';
import { Field, Label, ErrorMessage } from './catalyst/fieldset';
import { Text } from './catalyst/text';
import { PlusIcon, ExclamationCircleIcon, PencilIcon, TrashIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline';

/**
 * ScratchpadPanel - Live notes/scratchpad component using Catalyst UI
 *
 * Displays entries with timestamps, authors, and content.
 * Fetches data from /api/scratchpad/{thread_id} and allows adding new entries.
 *
 * Features:
 * - Live data fetching from backend API
 * - Add new entries with POST request
 * - Auto-refresh after adding entry
 * - Loading states
 * - Error handling with user feedback
 * - Full dark mode support
 */
export default function ScratchpadPanel() {
  const { threadId } = useParams();
  const [entries, setEntries] = useState([]);
  const [newEntry, setNewEntry] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState(null);
  const [editingIndex, setEditingIndex] = useState(null);
  const [editContent, setEditContent] = useState('');

  // Get auth token from localStorage
  const authToken = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

  // Fetch entries from API
  const fetchEntries = useCallback(async () => {
    if (!threadId || !authToken) {
      setEntries([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/scratchpad/${threadId}`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to load scratchpad: ${response.status}`);
      }

      const data = await response.json();
      setEntries(data || []);
    } catch (err) {
      console.error('Error fetching scratchpad entries:', err);
      setError(err.message);
      setEntries([]);
    } finally {
      setIsLoading(false);
    }
  }, [threadId, authToken]);

  // Fetch entries on mount and when threadId changes
  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  // Listen for scratchpad updates from SSE events
  useEffect(() => {
    const handleScratchpadUpdate = (event) => {
      const { threadId: updatedThreadId } = event.detail;
      // Only refetch if the update is for the current thread
      if (updatedThreadId === threadId) {
        console.log('[Scratchpad] Received update event, refetching entries');
        fetchEntries();
      }
    };

    window.addEventListener('scratchpadUpdate', handleScratchpadUpdate);
    return () => {
      window.removeEventListener('scratchpadUpdate', handleScratchpadUpdate);
    };
  }, [threadId, fetchEntries]);

  // Add new entry
  const handleAddEntry = async () => {
    if (!newEntry.trim() || isAdding || !threadId || !authToken) return;

    setIsAdding(true);
    setError(null);

    try {
      const response = await fetch(`/api/scratchpad/${threadId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: newEntry.trim() })
      });

      if (!response.ok) {
        throw new Error(`Failed to add entry: ${response.status}`);
      }

      // Clear input and refresh entries
      setNewEntry('');
      await fetchEntries();
    } catch (err) {
      console.error('Error adding scratchpad entry:', err);
      setError(err.message);
    } finally {
      setIsAdding(false);
    }
  };

  // Update entry
  const handleUpdateEntry = async (index) => {
    if (!editContent.trim() || !threadId || !authToken) return;

    try {
      const response = await fetch(`/api/scratchpad/${threadId}/${index}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: editContent.trim() })
      });

      if (!response.ok) {
        throw new Error(`Failed to update entry: ${response.status}`);
      }

      // Cancel edit mode and refresh
      setEditingIndex(null);
      setEditContent('');
      await fetchEntries();
    } catch (err) {
      console.error('Error updating scratchpad entry:', err);
      setError(err.message);
    }
  };

  // Delete entry
  const handleDeleteEntry = async (index) => {
    if (!window.confirm('Are you sure you want to delete this note?')) return;
    if (!threadId || !authToken) return;

    try {
      const response = await fetch(`/api/scratchpad/${threadId}/${index}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to delete entry: ${response.status}`);
      }

      // Refresh entries
      await fetchEntries();
    } catch (err) {
      console.error('Error deleting scratchpad entry:', err);
      setError(err.message);
    }
  };

  // Start editing
  const startEdit = (index, content) => {
    setEditingIndex(index);
    setEditContent(content);
  };

  // Cancel editing
  const cancelEdit = () => {
    setEditingIndex(null);
    setEditContent('');
  };

  // Handle Enter key (Shift+Enter for newline)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAddEntry();
    }
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  // Get author badge color
  const getAuthorColor = (author) => {
    if (author === 'agent' || author.includes('@') === false) return 'blue';
    return 'green';
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-800">
      {/* Header */}
      <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
        <Subheading level={3}>Scratchpad</Subheading>
        {threadId ? (
          <Text className="mt-1">
            Notes for this conversation
          </Text>
        ) : (
          <Text className="mt-1">
            Select a conversation to view notes
          </Text>
        )}
      </div>

      {/* Entries List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
        {/* Loading State */}
        {isLoading && entries.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
              <div className="w-2 h-2 bg-zinc-400 dark:bg-zinc-600 rounded-full animate-pulse"></div>
              <div className="w-2 h-2 bg-zinc-400 dark:bg-zinc-600 rounded-full animate-pulse animation-delay-150"></div>
              <div className="w-2 h-2 bg-zinc-400 dark:bg-zinc-600 rounded-full animate-pulse animation-delay-300"></div>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <div className="flex items-start gap-2">
              <ExclamationCircleIcon className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-900 dark:text-red-100">
                  Error loading scratchpad
                </p>
                <p className="text-xs text-red-700 dark:text-red-300 mt-1">
                  {error}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && entries.length === 0 && !error && threadId && (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              No notes yet. Add your first note below.
            </p>
          </div>
        )}

        {/* No Thread Selected */}
        {!threadId && (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Start or select a conversation to use the scratchpad.
            </p>
          </div>
        )}

        {/* Entries */}
        <div className="space-y-3">
          {entries.map((entry, index) => (
            <div
              key={index}
              className="group relative p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
            >
              {/* Header: Author + Timestamp */}
              <div className="flex items-center justify-between mb-2">
                <Badge color={getAuthorColor(entry.author)}>
                  {entry.author === 'agent' ? 'Agent' : entry.author.split('@')[0] || entry.author}
                </Badge>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {formatTimestamp(entry.timestamp)}
                  </span>
                  {/* Edit/Delete buttons - only show for human entries and when not editing */}
                  {entry.author !== 'agent' && editingIndex !== index && (
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => startEdit(index, entry.content)}
                        className="p-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        title="Edit"
                      >
                        <PencilIcon className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteEntry(index)}
                        className="p-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                        title="Delete"
                      >
                        <TrashIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Content or Edit Mode */}
              {editingIndex === index ? (
                <div className="space-y-2">
                  <Textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="text-sm"
                    rows={3}
                    autoFocus
                  />
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleUpdateEntry(index)}
                      variant="solid"
                      className="flex-1"
                    >
                      <CheckIcon data-slot="icon" className="w-4 h-4" />
                      Save
                    </Button>
                    <Button
                      onClick={cancelEdit}
                      variant="outline"
                      className="flex-1"
                    >
                      <XMarkIcon data-slot="icon" className="w-4 h-4" />
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-zinc-900 dark:text-zinc-100 whitespace-pre-wrap">
                  {entry.content}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Add Entry Form */}
      {threadId && (
        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800">
          <Field>
            <Label>Add Note</Label>
            <Textarea
              value={newEntry}
              onChange={(e) => setNewEntry(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add a note... (Shift+Enter for newline)"
              rows={3}
              disabled={isAdding}
              className="mb-3"
            />
            <Button
              onClick={handleAddEntry}
              disabled={!newEntry.trim() || isAdding}
              variant="solid"
              className="w-full"
            >
              <PlusIcon data-slot="icon" />
              {isAdding ? 'Adding...' : 'Add Note'}
            </Button>
          </Field>
        </div>
      )}
    </div>
  );
}
