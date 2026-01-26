import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Search,
  Plus,
  Trash2,
  Edit2,
  Tag,
  Filter,
  Clock,
  X,
  Save,
  Star,
  Copy,
  Upload,
  ChevronLeft,
  ChevronRight,
  Percent,
} from 'lucide-react';
import { Input } from './catalyst/input';
import { Button } from './catalyst/button';
import NotesImportDialog from './NotesImportDialog';

export default function NotesManagement({ authToken }) {
  // State
  const [notes, setNotes] = useState([]);
  const [filteredNotes, setFilteredNotes] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedStarred, setSelectedStarred] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  const [totalCount, setTotalCount] = useState(0);
  const [showingCount, setShowingCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [newNote, setNewNote] = useState({
    title: '',
    content: '',
    category: 'personal',
    tags: [],
    is_starred: false,
  });
  const [tagInput, setTagInput] = useState('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(50);

  // Similar notes modal state
  const [showSimilarModal, setShowSimilarModal] = useState(false);
  const [similarNotes, setSimilarNotes] = useState([]);
  const [similarModalLoading, setSimilarModalLoading] = useState(false);
  const [originalNote, setOriginalNote] = useState(null);

  // Sort options
  const sortOptions = [
    { value: 'newest', label: 'Newest First' },
    { value: 'oldest', label: 'Oldest First' },
    { value: 'updated', label: 'Recently Updated' },
    { value: 'accessed', label: 'Recently Accessed' },
  ];

  // Categories
  const categories = [
    { id: 'all', label: 'All Notes', count: notes.length },
    { id: 'personal', label: 'Personal', count: notes.filter(n => n.category === 'personal').length },
    { id: 'work', label: 'Work', count: notes.filter(n => n.category === 'work').length },
    { id: 'ideas', label: 'Ideas', count: notes.filter(n => n.category === 'ideas').length },
    { id: 'reference', label: 'Reference', count: notes.filter(n => n.category === 'reference').length },
  ];

  // Load notes from API
  useEffect(() => {
    loadNotes();
  }, [authToken, currentPage, selectedCategory, selectedStarred, sortBy]);

  const loadNotes = async () => {
    if (!authToken) return;

    try {
      setIsLoading(true);
      const offset = (currentPage - 1) * itemsPerPage;

      // Build query params
      const params = new URLSearchParams({
        limit: itemsPerPage.toString(),
        offset: offset.toString(),
        sort_by: sortBy === 'newest' ? 'created_at' : sortBy === 'oldest' ? 'created_at' : sortBy === 'updated' ? 'updated_at' : 'last_accessed',
        sort_order: (sortBy === 'oldest') ? 'asc' : 'desc',
      });

      if (selectedCategory !== 'all') {
        params.append('category', selectedCategory);
      }

      if (selectedStarred === 'starred') {
        params.append('is_starred', 'true');
      } else if (selectedStarred === 'unstarred') {
        params.append('is_starred', 'false');
      }

      const url = `/api/notes?${params.toString()}`;
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setNotes(data.notes || []);
        setFilteredNotes(data.notes || []);
        setTotalCount(data.total || 0);
        setShowingCount(data.showing || 0);
      } else {
        console.error('Failed to load notes:', response.status);
      }
    } catch (error) {
      console.error('Failed to load notes:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Calculate total pages
  const totalPages = Math.ceil(totalCount / itemsPerPage);

  // Client-side search filter
  useEffect(() => {
    let filtered = [...notes];

    // Apply search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        n =>
          n.title.toLowerCase().includes(term) ||
          n.content.toLowerCase().includes(term) ||
          n.tags.some(tag => tag.toLowerCase().includes(term))
      );
    }

    setFilteredNotes(filtered);
  }, [notes, searchTerm]);

  // Handlers
  const handleCreateNote = async () => {
    if (!authToken) return;
    if (!newNote.title.trim()) {
      alert('Title is required');
      return;
    }

    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: newNote.title,
          content: newNote.content,
          category: newNote.category,
          tags: newNote.tags,
          is_starred: newNote.is_starred,
        })
      });

      if (response.ok) {
        const createdNote = await response.json();
        setShowCreateModal(false);
        setNewNote({ title: '', content: '', category: 'personal', tags: [], is_starred: false });
        loadNotes(); // Reload to get fresh data
      } else {
        const error = await response.json();
        alert(`Failed to create note: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to create note:', error);
      alert('Failed to create note. Please try again.');
    }
  };

  const handleUpdateNote = async () => {
    if (!authToken || !editingNote) return;
    if (!editingNote.title.trim()) {
      alert('Title is required');
      return;
    }

    try {
      const response = await fetch(`/api/notes/${editingNote.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: editingNote.title,
          content: editingNote.content,
          category: editingNote.category,
          tags: editingNote.tags,
          is_starred: editingNote.is_starred,
        })
      });

      if (response.ok) {
        const updatedNote = await response.json();
        setEditingNote(null);
        loadNotes(); // Reload to get fresh data
      } else {
        const error = await response.json();
        alert(`Failed to update note: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to update note:', error);
      alert('Failed to update note. Please try again.');
    }
  };

  const handleDeleteNote = async (id) => {
    if (!confirm('Delete this note? This action cannot be undone.')) return;
    if (!authToken) return;

    try {
      const response = await fetch(`/api/notes/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        loadNotes(); // Reload to get fresh data
      } else {
        console.error('Failed to delete note:', response.status);
        alert('Failed to delete note. Please try again.');
      }
    } catch (error) {
      console.error('Failed to delete note:', error);
      alert('Failed to delete note. Please try again.');
    }
  };

  const handleAddTag = (note) => {
    if (!tagInput.trim()) return;

    if (note) {
      // Adding tag to existing note
      const updated = { ...note, tags: [...note.tags, tagInput.trim()] };
      if (editingNote) {
        setEditingNote(updated);
      }
    } else {
      // Adding tag to new note
      setNewNote({
        ...newNote,
        tags: [...newNote.tags, tagInput.trim()],
      });
    }

    setTagInput('');
  };

  const handleRemoveTag = (note, tagToRemove) => {
    if (note) {
      const updated = { ...note, tags: note.tags.filter(t => t !== tagToRemove) };
      if (editingNote) {
        setEditingNote(updated);
      }
    } else {
      setNewNote({
        ...newNote,
        tags: newNote.tags.filter(t => t !== tagToRemove),
      });
    }
  };

  const handleToggleStar = async (note) => {
    if (!authToken) return;

    try {
      const response = await fetch(`/api/notes/${note.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          is_starred: !note.is_starred,
        })
      });

      if (response.ok) {
        loadNotes(); // Reload to get fresh data
      } else {
        console.error('Failed to toggle star:', response.status);
      }
    } catch (error) {
      console.error('Failed to toggle star:', error);
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

  // Similar notes handlers
  const handleViewSimilar = async (note) => {
    if (!authToken) return;

    setOriginalNote(note);
    setShowSimilarModal(true);
    setSimilarModalLoading(true);
    setSimilarNotes([]);

    try {
      const response = await fetch(`/api/notes/${note.id}/similar?limit=20&threshold=0.5`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSimilarNotes(data.similar_notes || []);
      } else {
        console.error('Failed to fetch similar notes:', response.status);
        alert('Failed to find similar notes. Please try again.');
      }
    } catch (error) {
      console.error('Failed to fetch similar notes:', error);
      alert('Failed to find similar notes. Please try again.');
    } finally {
      setSimilarModalLoading(false);
    }
  };

  const handleDeleteFromSimilar = async (noteId) => {
    if (!confirm('Delete this note? This action cannot be undone.')) return;
    if (!authToken) return;

    try {
      const response = await fetch(`/api/notes/${noteId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        // Remove from similar notes list
        setSimilarNotes(similarNotes.filter(n => n.id !== noteId));
        // Reload main list
        loadNotes();
      } else {
        console.error('Failed to delete note:', response.status);
        alert('Failed to delete note. Please try again.');
      }
    } catch (error) {
      console.error('Failed to delete note:', error);
      alert('Failed to delete note. Please try again.');
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
                <BookOpen className="w-8 h-8 text-zinc-600 dark:text-zinc-400" />
                Notes - Second Brain
              </h1>
              <p className="text-zinc-600 dark:text-zinc-400 mt-2">
                Your personal knowledge base with semantic search
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => setShowImportDialog(true)}
                className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 hover:bg-zinc-300 dark:hover:bg-zinc-600"
              >
                <Upload className="w-4 h-4 mr-2" />
                Import Obsidian
              </Button>
              <Button
                onClick={() => setShowCreateModal(true)}
                className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-200"
              >
                <Plus className="w-4 h-4 mr-2" />
                New Note
              </Button>
            </div>
          </div>

          {/* Count and Page Info */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-zinc-600 dark:text-zinc-400">
              <span className="font-semibold text-zinc-900 dark:text-zinc-100">{totalCount}</span> total notes
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
              placeholder="Search notes by title, content, or tags..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 dark:placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
            />
          </div>

          {/* Category Filters, Starred Filter, and Sort */}
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

              {/* Starred Filter */}
              <button
                onClick={() => setSelectedStarred(selectedStarred === 'starred' ? 'all' : 'starred')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-1 ${
                  selectedStarred === 'starred'
                    ? 'bg-amber-500 text-white'
                    : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                }`}
              >
                <Star className={`w-4 h-4 ${selectedStarred === 'starred' ? 'fill-current' : ''}`} />
                Starred
              </button>
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

        {/* Notes List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100"></div>
          </div>
        ) : filteredNotes.length === 0 ? (
          <div className="text-center py-12 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800">
            <BookOpen className="w-12 h-12 text-zinc-400 mx-auto mb-4" />
            <p className="text-zinc-600 dark:text-zinc-400 text-lg">
              {searchTerm || selectedCategory !== 'all'
                ? 'No notes match your filters'
                : 'No notes yet'}
            </p>
            <p className="text-zinc-500 dark:text-zinc-500 text-sm mt-2">
              Create your first note to build your second brain
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredNotes.map((note) => (
              <div
                key={note.id}
                className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-all duration-200"
              >
                {editingNote?.id === note.id ? (
                  /* Edit Mode */
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                        Title
                      </label>
                      <input
                        type="text"
                        value={editingNote.title}
                        onChange={(e) =>
                          setEditingNote({ ...editingNote, title: e.target.value })
                        }
                        className="w-full px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                        maxLength={500}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                        Content
                      </label>
                      <textarea
                        value={editingNote.content}
                        onChange={(e) =>
                          setEditingNote({ ...editingNote, content: e.target.value })
                        }
                        className="w-full px-4 py-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 resize-none font-mono text-sm"
                        rows={8}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                        Category
                      </label>
                      <select
                        value={editingNote.category}
                        onChange={(e) =>
                          setEditingNote({ ...editingNote, category: e.target.value })
                        }
                        className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                      >
                        <option value="personal">Personal</option>
                        <option value="work">Work</option>
                        <option value="ideas">Ideas</option>
                        <option value="reference">Reference</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                        Tags
                      </label>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {editingNote.tags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                          >
                            {tag}
                            <button
                              onClick={() => handleRemoveTag(editingNote, tag)}
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
                          onKeyPress={(e) => e.key === 'Enter' && handleAddTag(editingNote)}
                          placeholder="Add tag..."
                          className="flex-1 px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
                        />
                        <Button
                          onClick={() => handleAddTag(editingNote)}
                          className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                        >
                          <Plus className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={editingNote.is_starred}
                          onChange={(e) =>
                            setEditingNote({ ...editingNote, is_starred: e.target.checked })
                          }
                          className="w-4 h-4 rounded border-zinc-300 text-amber-500 focus:ring-amber-500"
                        />
                        <span className="text-sm text-zinc-700 dark:text-zinc-300">Starred</span>
                      </label>
                    </div>

                    <div className="flex items-center gap-2 pt-4">
                      <Button
                        onClick={handleUpdateNote}
                        className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
                      >
                        <Save className="w-4 h-4 mr-2" />
                        Save
                      </Button>
                      <Button
                        onClick={() => setEditingNote(null)}
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
                      {/* Star button */}
                      <button
                        onClick={() => handleToggleStar(note)}
                        className={`mt-1 flex-shrink-0 transition-colors ${
                          note.is_starred
                            ? 'text-amber-500 hover:text-amber-600'
                            : 'text-zinc-300 dark:text-zinc-700 hover:text-amber-500'
                        }`}
                      >
                        <Star className={`w-5 h-5 ${note.is_starred ? 'fill-current' : ''}`} />
                      </button>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
                          {note.title}
                        </h3>
                        <p className="text-zinc-700 dark:text-zinc-300 text-sm leading-relaxed whitespace-pre-wrap">
                          {note.content}
                        </p>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => handleViewSimilar(note)}
                          className="p-2 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 text-blue-600 dark:text-blue-400 transition-colors"
                          title="View similar notes"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setEditingNote(note)}
                          className="p-2 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400 transition-colors"
                          title="Edit note"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteNote(note.id)}
                          className="p-2 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 transition-colors"
                          title="Delete note"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium">
                        <Tag className="w-3 h-3" />
                        {note.category}
                      </span>

                      {note.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                        >
                          {tag}
                        </span>
                      ))}

                      <span className="inline-flex items-center gap-1 text-zinc-500 dark:text-zinc-400 ml-auto">
                        <Clock className="w-3 h-3" />
                        {formatDate(note.created_at)}
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

        {/* Create Note Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 max-w-2xl w-full shadow-xl max-h-[90vh] overflow-y-auto">
              <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">
                Create New Note
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Title <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newNote.title}
                    onChange={(e) => setNewNote({ ...newNote, title: e.target.value })}
                    placeholder="Enter note title..."
                    className="w-full px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                    maxLength={500}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Content
                  </label>
                  <textarea
                    value={newNote.content}
                    onChange={(e) => setNewNote({ ...newNote, content: e.target.value })}
                    placeholder="Enter note content (supports markdown)..."
                    className="w-full px-4 py-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 resize-none font-mono text-sm"
                    rows={8}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Category
                  </label>
                  <select
                    value={newNote.category}
                    onChange={(e) => setNewNote({ ...newNote, category: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                  >
                    <option value="personal">Personal</option>
                    <option value="work">Work</option>
                    <option value="ideas">Ideas</option>
                    <option value="reference">Reference</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Tags
                  </label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {newNote.tags.map((tag) => (
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

                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newNote.is_starred}
                      onChange={(e) =>
                        setNewNote({ ...newNote, is_starred: e.target.checked })
                      }
                      className="w-4 h-4 rounded border-zinc-300 text-amber-500 focus:ring-amber-500"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Starred</span>
                  </label>
                </div>

                <div className="flex items-center gap-2 pt-4">
                  <Button
                    onClick={handleCreateNote}
                    disabled={!newNote.title.trim()}
                    className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    Create Note
                  </Button>
                  <Button
                    onClick={() => {
                      setShowCreateModal(false);
                      setNewNote({ title: '', content: '', category: 'personal', tags: [], is_starred: false });
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

        {/* Similar Notes Modal */}
        {showSimilarModal && (
          <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 max-w-4xl w-full max-h-[80vh] overflow-y-auto shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <Copy className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                  Similar Notes
                </h2>
                <button
                  onClick={() => setShowSimilarModal(false)}
                  className="p-2 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Original Note */}
              {originalNote && (
                <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">
                    Original Note:
                  </p>
                  <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-1">
                    {originalNote.title}
                  </h3>
                  <p className="text-zinc-700 dark:text-zinc-300 text-sm">
                    {originalNote.content}
                  </p>
                </div>
              )}

              {/* Loading State */}
              {similarModalLoading && (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 dark:border-blue-400"></div>
                </div>
              )}

              {/* No Similar Notes */}
              {!similarModalLoading && similarNotes.length === 0 && (
                <div className="text-center py-12">
                  <BookOpen className="w-12 h-12 text-zinc-400 mx-auto mb-4" />
                  <p className="text-zinc-600 dark:text-zinc-400 text-lg">
                    No similar notes found
                  </p>
                  <p className="text-zinc-500 dark:text-zinc-500 text-sm mt-2">
                    Try adjusting the similarity threshold or check if other notes have embeddings
                  </p>
                </div>
              )}

              {/* Similar Notes List */}
              {!similarModalLoading && similarNotes.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
                    Found <span className="font-semibold">{similarNotes.length}</span> similar note{similarNotes.length === 1 ? '' : 's'}
                  </p>
                  {similarNotes.map((note) => (
                    <div
                      key={note.id}
                      className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4"
                    >
                      <div className="flex items-start gap-4 mb-3">
                        {/* Similarity Badge */}
                        <div className="flex-shrink-0 px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800">
                          <div className="flex items-center gap-1 text-sm font-semibold text-blue-700 dark:text-blue-300">
                            <Percent className="w-3.5 h-3.5" />
                            {Math.round(note.similarity * 100)}
                          </div>
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <h4 className="text-base font-bold text-zinc-900 dark:text-zinc-100 mb-1">
                            {note.title}
                          </h4>
                          <p className="text-zinc-700 dark:text-zinc-300 text-sm leading-relaxed">
                            {note.content}
                          </p>
                        </div>

                        {/* Delete Button */}
                        <button
                          onClick={() => handleDeleteFromSimilar(note.id)}
                          className="flex-shrink-0 p-2 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 transition-colors"
                          title="Delete this note"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Metadata */}
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300">
                          <Tag className="w-3 h-3" />
                          {note.category}
                        </span>
                        <span className="text-zinc-500 dark:text-zinc-400">
                          {formatDate(note.created_at)}
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

        {/* Import Dialog */}
        {showImportDialog && (
          <NotesImportDialog
            authToken={authToken}
            onClose={() => {
              setShowImportDialog(false);
              loadNotes(); // Reload notes after import
            }}
          />
        )}
      </div>
    </div>
  );
}
