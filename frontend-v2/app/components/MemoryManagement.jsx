import React, { useState, useEffect } from 'react';
import {
  Brain,
  Search,
  Plus,
  Trash2,
  Edit2,
  Tag,
  Filter,
  Calendar,
  Clock,
  X,
  Save,
  AlertCircle,
  CheckSquare,
  Square,
  ChevronLeft,
  ChevronRight,
  Copy,
  Percent,
} from 'lucide-react';
import { Input } from './catalyst/input';
import { Button } from './catalyst/button';

export default function MemoryManagement({ authToken }) {
  // State
  const [memories, setMemories] = useState([]);
  const [filteredMemories, setFilteredMemories] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  const [totalCount, setTotalCount] = useState(0);
  const [showingCount, setShowingCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingMemory, setEditingMemory] = useState(null);
  const [newMemory, setNewMemory] = useState({
    content: '',
    category: 'fact',
    tags: [],
  });
  const [tagInput, setTagInput] = useState('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(50);

  // Multi-select state
  const [selectedMemoryIds, setSelectedMemoryIds] = useState(new Set());

  // Similar memories modal state
  const [showSimilarModal, setShowSimilarModal] = useState(false);
  const [similarMemories, setSimilarMemories] = useState([]);
  const [similarModalLoading, setSimilarModalLoading] = useState(false);
  const [originalMemory, setOriginalMemory] = useState(null);

  // Sort options
  const sortOptions = [
    { value: 'newest', label: 'Most Recent' },
    { value: 'oldest', label: 'Oldest First' },
    { value: 'confidence_high', label: 'Highest Confidence' },
    { value: 'confidence_low', label: 'Lowest Confidence' },
  ];

  // Categories
  const categories = [
    { id: 'all', label: 'All Memories', count: memories.length },
    { id: 'fact', label: 'Facts', count: memories.filter(m => m.category === 'fact').length },
    { id: 'preference', label: 'Preferences', count: memories.filter(m => m.category === 'preference').length },
    { id: 'context', label: 'Context', count: memories.filter(m => m.category === 'context').length },
    { id: 'task', label: 'Tasks', count: memories.filter(m => m.category === 'task').length },
  ];

  // Load memories from API
  useEffect(() => {
    loadMemories();
  }, [authToken, currentPage]);

  const loadMemories = async () => {
    if (!authToken) return;

    try {
      setIsLoading(true);
      const offset = (currentPage - 1) * itemsPerPage;
      const url = `/api/memories?limit=${itemsPerPage}&offset=${offset}`;
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setMemories(data.memories || []);
        setFilteredMemories(data.memories || []);
        setTotalCount(data.total || 0);
        setShowingCount(data.showing || 0);
        // Clear selection when page changes
        setSelectedMemoryIds(new Set());
      } else {
        console.error('Failed to load memories:', response.status);
      }
    } catch (error) {
      console.error('Failed to load memories:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Calculate total pages
  const totalPages = Math.ceil(totalCount / itemsPerPage);

  // Filter and sort memories
  useEffect(() => {
    let filtered = [...memories];

    // Apply category filter
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(m => m.category === selectedCategory);
    }

    // Apply search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        m =>
          m.content.toLowerCase().includes(term) ||
          m.tags.some(tag => tag.toLowerCase().includes(term))
      );
    }

    // Apply sorting
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return new Date(b.updated_at) - new Date(a.updated_at);
        case 'oldest':
          return new Date(a.updated_at) - new Date(b.updated_at);
        case 'confidence_high':
          return (b.confidence || 0) - (a.confidence || 0);
        case 'confidence_low':
          return (a.confidence || 0) - (b.confidence || 0);
        default:
          return 0;
      }
    });

    setFilteredMemories(filtered);
  }, [memories, searchTerm, selectedCategory, sortBy]);

  // Handlers
  const handleCreateMemory = async () => {
    if (!authToken) return;

    try {
      const response = await fetch('/api/memories', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: newMemory.content,
          category: newMemory.category,
          tags: newMemory.tags
        })
      });

      if (response.ok) {
        const createdMemory = await response.json();
        setMemories([createdMemory, ...memories]);
        setShowCreateModal(false);
        setNewMemory({ content: '', category: 'fact', tags: [] });
      } else {
        console.error('Failed to create memory:', response.status);
      }
    } catch (error) {
      console.error('Failed to create memory:', error);
    }
  };

  const handleUpdateMemory = async () => {
    if (!authToken || !editingMemory) return;

    try {
      const response = await fetch(`/api/memories/${editingMemory.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: editingMemory.content,
          category: editingMemory.category,
          tags: editingMemory.tags
        })
      });

      if (response.ok) {
        setMemories(
          memories.map(m => (m.id === editingMemory.id ? editingMemory : m))
        );
        setEditingMemory(null);
      } else {
        console.error('Failed to update memory:', response.status);
      }
    } catch (error) {
      console.error('Failed to update memory:', error);
    }
  };

  const handleDeleteMemory = async (id) => {
    if (!confirm('Delete this memory? This action cannot be undone.')) return;
    if (!authToken) return;

    try {
      const response = await fetch(`/api/memories/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        setMemories(memories.filter(m => m.id !== id));
      } else {
        console.error('Failed to delete memory:', response.status);
      }
    } catch (error) {
      console.error('Failed to delete memory:', error);
    }
  };

  const handleAddTag = (memory) => {
    if (!tagInput.trim()) return;

    if (memory) {
      // Adding tag to existing memory
      const updated = { ...memory, tags: [...memory.tags, tagInput.trim()] };
      if (editingMemory) {
        setEditingMemory(updated);
      } else {
        setMemories(memories.map(m => (m.id === memory.id ? updated : m)));
      }
    } else {
      // Adding tag to new memory
      setNewMemory({
        ...newMemory,
        tags: [...newMemory.tags, tagInput.trim()],
      });
    }

    setTagInput('');
  };

  const handleRemoveTag = (memory, tagToRemove) => {
    if (memory) {
      const updated = { ...memory, tags: memory.tags.filter(t => t !== tagToRemove) };
      if (editingMemory) {
        setEditingMemory(updated);
      } else {
        setMemories(memories.map(m => (m.id === memory.id ? updated : m)));
      }
    } else {
      setNewMemory({
        ...newMemory,
        tags: newMemory.tags.filter(t => t !== tagToRemove),
      });
    }
  };

  // Multi-select handlers
  const handleToggleSelect = (memoryId) => {
    setSelectedMemoryIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(memoryId)) {
        newSet.delete(memoryId);
      } else {
        newSet.add(memoryId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (selectedMemoryIds.size === filteredMemories.length) {
      setSelectedMemoryIds(new Set());
    } else {
      setSelectedMemoryIds(new Set(filteredMemories.map(m => m.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedMemoryIds.size === 0) return;

    const count = selectedMemoryIds.size;
    if (!confirm(`Delete ${count} selected memor${count === 1 ? 'y' : 'ies'}? This action cannot be undone.`)) {
      return;
    }

    if (!authToken) return;

    try {
      const response = await fetch('/api/memories/bulk-delete', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          memory_ids: Array.from(selectedMemoryIds)
        })
      });

      if (response.ok) {
        // Remove deleted memories from state
        setMemories(memories.filter(m => !selectedMemoryIds.has(m.id)));
        setSelectedMemoryIds(new Set());
        // Reload to get fresh data and update counts
        loadMemories();
      } else {
        console.error('Failed to bulk delete memories:', response.status);
        alert('Failed to delete memories. Please try again.');
      }
    } catch (error) {
      console.error('Failed to bulk delete memories:', error);
      alert('Failed to delete memories. Please try again.');
    }
  };

  // Pagination handlers
  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handleGoToPage = (page) => {
    setCurrentPage(page);
  };

  // Similar memories handlers
  const handleViewSimilar = async (memory) => {
    if (!authToken) return;

    setOriginalMemory(memory);
    setShowSimilarModal(true);
    setSimilarModalLoading(true);
    setSimilarMemories([]);

    try {
      const response = await fetch(`/api/memories/${memory.id}/similar?limit=20&threshold=0.5`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSimilarMemories(data.similar_memories || []);
      } else {
        console.error('Failed to fetch similar memories:', response.status);
        alert('Failed to find similar memories. Please try again.');
      }
    } catch (error) {
      console.error('Failed to fetch similar memories:', error);
      alert('Failed to find similar memories. Please try again.');
    } finally {
      setSimilarModalLoading(false);
    }
  };

  const handleDeleteFromSimilar = async (memoryId) => {
    if (!confirm('Delete this memory? This action cannot be undone.')) return;
    if (!authToken) return;

    try {
      const response = await fetch(`/api/memories/${memoryId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        // Remove from similar memories list
        setSimilarMemories(similarMemories.filter(m => m.id !== memoryId));
        // Also remove from main memories list if present
        setMemories(memories.filter(m => m.id !== memoryId));
        // Reload to update counts
        loadMemories();
      } else {
        console.error('Failed to delete memory:', response.status);
        alert('Failed to delete memory. Please try again.');
      }
    } catch (error) {
      console.error('Failed to delete memory:', error);
      alert('Failed to delete memory. Please try again.');
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-screen overflow-y-auto bg-white dark:bg-zinc-950">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="border-b border-zinc-200 dark:border-zinc-800 pb-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-3">
                <Brain className="w-8 h-8 text-zinc-600 dark:text-zinc-400" />
                Memory Management
              </h1>
              <p className="text-zinc-600 dark:text-zinc-400 mt-2">
                View and manage stored memories, facts, and preferences
              </p>
            </div>
            <Button
              onClick={() => setShowCreateModal(true)}
              className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-200"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Memory
            </Button>
          </div>

          {/* Count and Page Info */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-zinc-600 dark:text-zinc-400">
              <span className="font-semibold text-zinc-900 dark:text-zinc-100">{totalCount}</span> total memories
              {totalPages > 1 && (
                <span className="ml-2">
                  • Page <span className="font-semibold text-zinc-900 dark:text-zinc-100">{currentPage}</span> of{' '}
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100">{totalPages}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="mb-6 space-y-4">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
            <input
              type="text"
              placeholder="Search memories by content or tags..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 dark:placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
            />
          </div>

          {/* Category Filters and Sort */}
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              <Filter className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    selectedCategory === cat.id
                      ? 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                  }`}
                >
                  {cat.label} ({cat.count})
                </button>
              ))}
            </div>

            {/* Sort Dropdown */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-zinc-600 dark:text-zinc-400">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
              >
                {sortOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Bulk Actions Bar */}
        {selectedMemoryIds.size > 0 && (
          <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={handleSelectAll}
                className="p-1 hover:bg-blue-100 dark:hover:bg-blue-800 rounded transition-colors"
              >
                {selectedMemoryIds.size === filteredMemories.length ? (
                  <CheckSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                ) : (
                  <Square className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                )}
              </button>
              <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                {selectedMemoryIds.size} selected
              </span>
            </div>
            <Button
              onClick={handleBulkDelete}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete Selected
            </Button>
          </div>
        )}

        {/* Select All Checkbox (when not in selection mode) */}
        {!isLoading && filteredMemories.length > 0 && selectedMemoryIds.size === 0 && (
          <div className="mb-4 flex items-center gap-2">
            <button
              onClick={handleSelectAll}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-sm text-zinc-600 dark:text-zinc-400 transition-colors"
            >
              <Square className="w-4 h-4" />
              Select All
            </button>
          </div>
        )}

        {/* Memory List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100"></div>
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="text-center py-12 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800">
            <Brain className="w-12 h-12 text-zinc-400 mx-auto mb-4" />
            <p className="text-zinc-600 dark:text-zinc-400 text-lg">
              {searchTerm || selectedCategory !== 'all'
                ? 'No memories match your filters'
                : 'No memories stored yet'}
            </p>
            <p className="text-zinc-500 dark:text-zinc-500 text-sm mt-2">
              Create your first memory to get started
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredMemories.map((memory) => (
              <div
                key={memory.id}
                className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-all duration-200"
              >
                {editingMemory?.id === memory.id ? (
                  /* Edit Mode */
                  <div className="space-y-4">
                    <textarea
                      value={editingMemory.content}
                      onChange={(e) =>
                        setEditingMemory({ ...editingMemory, content: e.target.value })
                      }
                      className="w-full px-4 py-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 resize-none"
                      rows={3}
                    />

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                        Category
                      </label>
                      <select
                        value={editingMemory.category}
                        onChange={(e) =>
                          setEditingMemory({ ...editingMemory, category: e.target.value })
                        }
                        className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                      >
                        <option value="fact">Fact</option>
                        <option value="preference">Preference</option>
                        <option value="context">Context</option>
                        <option value="task">Task</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                        Tags
                      </label>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {editingMemory.tags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                          >
                            {tag}
                            <button
                              onClick={() => handleRemoveTag(editingMemory, tag)}
                              className="hover:text-red-600 dark:hover:text-red-400"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={tagInput}
                          onChange={(e) => setTagInput(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && handleAddTag(editingMemory)}
                          placeholder="Add tag..."
                          className="flex-1 px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
                        />
                        <Button
                          onClick={() => handleAddTag(editingMemory)}
                          className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                        >
                          <Plus className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        onClick={handleUpdateMemory}
                        className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
                      >
                        <Save className="w-4 h-4 mr-2" />
                        Save
                      </Button>
                      <Button
                        onClick={() => setEditingMemory(null)}
                        className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* View Mode */
                  <div>
                    <div className="flex items-start gap-4 mb-3">
                      {/* Checkbox */}
                      <button
                        onClick={() => handleToggleSelect(memory.id)}
                        className="mt-1 p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors flex-shrink-0"
                      >
                        {selectedMemoryIds.has(memory.id) ? (
                          <CheckSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                        ) : (
                          <Square className="w-5 h-5 text-zinc-400 dark:text-zinc-600" />
                        )}
                      </button>

                      {/* Content */}
                      <p className="text-zinc-900 dark:text-zinc-100 text-base leading-relaxed flex-1">
                        {memory.content}
                      </p>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => handleViewSimilar(memory)}
                          className="p-2 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 text-blue-600 dark:text-blue-400 transition-colors"
                          title="View similar memories"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setEditingMemory(memory)}
                          className="p-2 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400 transition-colors"
                          title="Edit memory"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteMemory(memory.id)}
                          className="p-2 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 transition-colors"
                          title="Delete memory"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium">
                        <Tag className="w-3 h-3" />
                        {memory.category}
                      </span>

                      {memory.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                        >
                          {tag}
                        </span>
                      ))}

                      <span className="inline-flex items-center gap-1 text-zinc-500 dark:text-zinc-400 ml-auto">
                        <Clock className="w-3 h-3" />
                        {formatDate(memory.created_at)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Pagination Controls */}
        {!isLoading && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <button
              onClick={handlePreviousPage}
              disabled={currentPage === 1}
              className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            {/* Page Numbers */}
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                // Show first page, last page, current page, and pages around current
                let pageNum;
                if (totalPages <= 7) {
                  pageNum = i + 1;
                } else if (currentPage <= 4) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 3) {
                  pageNum = totalPages - 6 + i;
                } else {
                  pageNum = currentPage - 3 + i;
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => handleGoToPage(pageNum)}
                    className={`min-w-[40px] px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      currentPage === pageNum
                        ? 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900'
                        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>

            <button
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
              className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Create Memory Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 max-w-2xl w-full shadow-xl">
              <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">
                Create New Memory
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Content
                  </label>
                  <textarea
                    value={newMemory.content}
                    onChange={(e) => setNewMemory({ ...newMemory, content: e.target.value })}
                    placeholder="Enter memory content..."
                    className="w-full px-4 py-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 resize-none"
                    rows={4}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Category
                  </label>
                  <select
                    value={newMemory.category}
                    onChange={(e) => setNewMemory({ ...newMemory, category: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                  >
                    <option value="fact">Fact</option>
                    <option value="preference">Preference</option>
                    <option value="context">Context</option>
                    <option value="task">Task</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Tags
                  </label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {newMemory.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                      >
                        {tag}
                        <button
                          onClick={() => handleRemoveTag(null, tag)}
                          className="hover:text-red-600 dark:hover:text-red-400"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleAddTag(null)}
                      placeholder="Add tag..."
                      className="flex-1 px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
                    />
                    <Button
                      onClick={() => handleAddTag(null)}
                      className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-4">
                  <Button
                    onClick={handleCreateMemory}
                    disabled={!newMemory.content.trim()}
                    className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    Create Memory
                  </Button>
                  <Button
                    onClick={() => {
                      setShowCreateModal(false);
                      setNewMemory({ content: '', category: 'fact', tags: [] });
                    }}
                    className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Similar Memories Modal */}
        {showSimilarModal && (
          <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 max-w-4xl w-full max-h-[80vh] overflow-y-auto shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <Copy className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                  Similar Memories
                </h2>
                <button
                  onClick={() => setShowSimilarModal(false)}
                  className="p-2 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Original Memory */}
              {originalMemory && (
                <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">
                    Original Memory:
                  </p>
                  <p className="text-zinc-900 dark:text-zinc-100">
                    {originalMemory.content}
                  </p>
                </div>
              )}

              {/* Loading State */}
              {similarModalLoading && (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 dark:border-blue-400"></div>
                </div>
              )}

              {/* No Similar Memories */}
              {!similarModalLoading && similarMemories.length === 0 && (
                <div className="text-center py-12">
                  <Brain className="w-12 h-12 text-zinc-400 mx-auto mb-4" />
                  <p className="text-zinc-600 dark:text-zinc-400 text-lg">
                    No similar memories found
                  </p>
                  <p className="text-zinc-500 dark:text-zinc-500 text-sm mt-2">
                    Try adjusting the similarity threshold or check if other memories have embeddings
                  </p>
                </div>
              )}

              {/* Similar Memories List */}
              {!similarModalLoading && similarMemories.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
                    Found <span className="font-semibold">{similarMemories.length}</span> similar memor{similarMemories.length === 1 ? 'y' : 'ies'}
                  </p>
                  {similarMemories.map((memory) => (
                    <div
                      key={memory.id}
                      className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4"
                    >
                      <div className="flex items-start gap-4 mb-3">
                        {/* Similarity Badge */}
                        <div className="flex-shrink-0 px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800">
                          <div className="flex items-center gap-1 text-sm font-semibold text-blue-700 dark:text-blue-300">
                            <Percent className="w-3.5 h-3.5" />
                            {Math.round(memory.similarity * 100)}
                          </div>
                        </div>

                        {/* Content */}
                        <p className="flex-1 text-zinc-900 dark:text-zinc-100 text-sm leading-relaxed">
                          {memory.content}
                        </p>

                        {/* Delete Button */}
                        <button
                          onClick={() => handleDeleteFromSimilar(memory.id)}
                          className="flex-shrink-0 p-2 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 transition-colors"
                          title="Delete this memory"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Metadata */}
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300">
                          <Tag className="w-3 h-3" />
                          {memory.category}
                        </span>
                        <span className="text-zinc-500 dark:text-zinc-400">
                          {formatDate(memory.created_at)}
                        </span>
                        <span className="text-zinc-500 dark:text-zinc-400">
                          • Confidence: {Math.round(memory.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Close Button */}
              <div className="mt-6 flex justify-end">
                <Button
                  onClick={() => setShowSimilarModal(false)}
                  className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
