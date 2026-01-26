import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router';
import {
  BookOpen,
  Search,
  Plus,
  Trash2,
  Tag,
  Star,
  Upload,
  X,
  Clock,
  FileText,
  Sparkles,
  Hash,
  ChevronRight,
  Menu,
  ArrowLeft,
  ChevronLeft,
  CheckSquare,
  Square,
  RefreshCw,
  Loader2,
  AlertTriangle,
  Info,
  CheckCircle2,
  Network,
  Share2,
  Copy,
  Lock,
  Calendar,
  Home,
} from 'lucide-react';
import { Button } from './catalyst/button';
import NotesImportDialog from './NotesImportDialog';
import NoteEditModal from './NoteEditModal';
import TagsBrowser from './TagsBrowser';
import NotesGraph from './NotesGraph';

const PAGE_SIZE_OPTIONS = [10, 20, 50];
const DEFAULT_PAGE_SIZE = 20;

const SORT_OPTIONS = [
  { id: 'created_desc', label: 'Created (newest first)', field: 'created_at', direction: 'DESC' },
  { id: 'created_asc', label: 'Created (oldest first)', field: 'created_at', direction: 'ASC' },
  { id: 'updated_desc', label: 'Updated (newest first)', field: 'updated_at', direction: 'DESC' },
  { id: 'updated_asc', label: 'Updated (oldest first)', field: 'updated_at', direction: 'ASC' },
  { id: 'title_asc', label: 'Title (A → Z)', field: 'title', direction: 'ASC' },
  { id: 'title_desc', label: 'Title (Z → A)', field: 'title', direction: 'DESC' },
];

const SORT_LOOKUP = SORT_OPTIONS.reduce((acc, option) => {
  acc[option.id] = option;
  return acc;
}, {});

const formatNumber = (value) => {
  return new Intl.NumberFormat().format(value);
};

export default function NotesApp({ authToken }) {
  const navigate = useNavigate();

  // State
  const [notes, setNotes] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTag, setSelectedTag] = useState(null);
  const [starredFilter, setStarredFilter] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedNote, setEditedNote] = useState(null);
  const [sortOptionId, setSortOptionId] = useState('created_desc');
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedNoteIds, setSelectedNoteIds] = useState(() => new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [isDeleting, setIsDeleting] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [isReindexing, setIsReindexing] = useState(false);
  const [autocompleteSuggestion, setAutocompleteSuggestion] = useState('');
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [isLoadingAutocomplete, setIsLoadingAutocomplete] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const autocompleteTimeoutRef = useRef(null);
  const textareaRef = useRef(null);
  const [showGraph, setShowGraph] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [publishStatus, setPublishStatus] = useState(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Mobile navigation state
  const [mobileView, setMobileView] = useState('list'); // 'sidebar', 'list', 'viewer'

  // Tags section collapsed state (collapsed by default to reduce clutter)
  const [isTagsSectionCollapsed, setIsTagsSectionCollapsed] = useState(true);

  // All unique tags from notes
  const allTags = useMemo(() => {
    return [...new Set(notes.flatMap(n => (Array.isArray(n.tags) ? n.tags : [])))].sort();
  }, [notes]);

  // Categories with counts
  const categories = useMemo(() => [
    { id: 'all', label: 'All Notes', icon: BookOpen, count: notes.length },
    { id: 'personal', label: 'Personal', icon: FileText, count: notes.filter(n => n.category === 'personal').length },
    { id: 'work', label: 'Work', icon: FileText, count: notes.filter(n => n.category === 'work').length },
    { id: 'ideas', label: 'Ideas', icon: Sparkles, count: notes.filter(n => n.category === 'ideas').length },
    { id: 'reference', label: 'Reference', icon: FileText, count: notes.filter(n => n.category === 'reference').length },
  ], [notes]);

  // Load notes from API
  useEffect(() => {
    loadNotes();
  }, [authToken]);

  const loadNotes = async () => {
    if (!authToken) return;

    try {
      setIsLoading(true);
      // Fetch all notes for client-side filtering/search
      const params = new URLSearchParams({
        limit: '500',
        sort_by: 'created_at',
        sort_order: 'DESC',
      });

      const response = await fetch(`/api/notes?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        const data = await response.json();
        const incomingNotes = data.notes || [];
        setNotes(incomingNotes);
        setSelectedNote((prev) => {
          if (!prev) return null;
          const next = incomingNotes.find(note => note.id === prev.id);
          // Preserve full content if we already have it - only update metadata
          if (next && prev.content && prev.content.length > 200) {
            return {
              ...prev,
              title: next.title,
              category: next.category,
              tags: next.tags,
              is_starred: next.is_starred,
            };
          }
          return next || null;
        });
        setEditedNote((prev) => {
          if (!prev) return null;
          const next = incomingNotes.find(note => note.id === prev.id);
          // Preserve full content - only update metadata from list (which has 200-char previews)
          return next
            ? {
                ...prev, // Keep existing content
                title: next.title,
                category: next.category,
                tags: Array.isArray(next.tags) ? next.tags : [],
                is_starred: next.is_starred,
              }
            : null;
        });
        return incomingNotes;
      } else {
        console.error('Failed to load notes:', response.status);
        setStatusMessage({
          type: 'error',
          text: 'Failed to load notes. Please try again.',
        });
      }
    } catch (error) {
      console.error('Failed to load notes:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to load notes. Please check your connection and try again.',
      });
    } finally {
      setIsLoading(false);
    }
    return [];
  };

  // Filter notes based on selected category, tag, search, and starred
  const sortConfig = SORT_LOOKUP[sortOptionId] || SORT_LOOKUP['created_desc'];

  const filteredNotes = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return notes.filter((note) => {
      const tags = Array.isArray(note.tags) ? note.tags : [];

      if (selectedCategory !== 'all' && note.category !== selectedCategory) return false;
      if (selectedTag && !tags.includes(selectedTag)) return false;
      if (starredFilter && !note.is_starred) return false;

      if (term) {
        const haystack = `${note.title}\n${note.content}`.toLowerCase();
        const tagMatch = tags.some((tag) => tag.toLowerCase().includes(term));
        return haystack.includes(term) || tagMatch;
      }

      return true;
    });
  }, [notes, searchTerm, selectedCategory, selectedTag, starredFilter]);

  const sortedNotes = useMemo(() => {
    const { field, direction } = sortConfig;
    const multiplier = direction === 'ASC' ? 1 : -1;

    return [...filteredNotes].sort((a, b) => {
      if (field === 'title') {
        return a.title.localeCompare(b.title) * multiplier;
      }

      const aValue = a[field];
      const bValue = b[field];
      const aTime = aValue ? new Date(aValue).getTime() : 0;
      const bTime = bValue ? new Date(bValue).getTime() : 0;
      return (aTime - bTime) * multiplier;
    });
  }, [filteredNotes, sortConfig]);

  const totalPages = Math.max(1, Math.ceil(sortedNotes.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageStart = (safeCurrentPage - 1) * pageSize;

  const paginatedNotes = useMemo(() => {
    return sortedNotes.slice(pageStart, pageStart + pageSize);
  }, [sortedNotes, pageStart, pageSize]);

  const showingFrom = sortedNotes.length === 0 ? 0 : pageStart + 1;
  const showingTo = Math.min(pageStart + pageSize, sortedNotes.length);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedCategory, selectedTag, starredFilter, sortOptionId, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  useEffect(() => {
    setSelectedNoteIds((prev) => {
      if (prev.size === 0) return prev;
      const next = new Set();
      const noteIds = new Set(notes.map((n) => n.id));

      prev.forEach((id) => {
        if (noteIds.has(id)) {
          next.add(id);
        }
      });

      if (next.size === prev.size) {
        let identical = true;
        for (const id of prev) {
          if (!next.has(id)) {
            identical = false;
            break;
          }
        }
        if (identical) {
          return prev;
        }
      }

      return next;
    });
  }, [notes]);

  useEffect(() => {
    if (!selectionMode) {
      setSelectedNoteIds((prev) => (prev.size === 0 ? prev : new Set()));
    }
  }, [selectionMode]);

  useEffect(() => {
    if (statusMessage) {
      const timeout = setTimeout(() => setStatusMessage(null), 5000);
      return () => clearTimeout(timeout);
    }
  }, [statusMessage]);

  useEffect(() => {
    if (selectedNote && !sortedNotes.some((note) => note.id === selectedNote.id)) {
      setSelectedNote(null);
      setIsEditing(false);
      setEditedNote(null);
    }
  }, [sortedNotes, selectedNote]);

  // Handlers
  const deleteNotesByIds = async (noteIds, { shouldConfirm = true } = {}) => {
    if (!noteIds || noteIds.length === 0) return;

    if (shouldConfirm) {
      const message = noteIds.length === 1
        ? 'Delete this note? This action cannot be undone.'
        : `Delete ${noteIds.length} notes? This action cannot be undone.`;
      if (!confirmAction(message)) return;
    }

    setIsDeleting(true);
    const failures = [];

    try {
      for (const noteId of noteIds) {
        try {
          const response = await fetch(`/api/notes/${noteId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
          });

          if (!response.ok) {
            failures.push(noteId);
          }
        } catch (error) {
          console.error('Failed to delete note:', error);
          failures.push(noteId);
        }
      }

      if (selectedNote && noteIds.includes(selectedNote.id)) {
        setSelectedNote(null);
        setIsEditing(false);
        setEditedNote(null);
      }

      await loadNotes();
      setSelectedNoteIds(new Set());

      if (failures.length === 0) {
        setStatusMessage({
          type: 'success',
          text: `Deleted ${noteIds.length} note${noteIds.length === 1 ? '' : 's'}.`,
        });
      } else if (failures.length === noteIds.length) {
        setStatusMessage({
          type: 'error',
          text: 'Failed to delete the selected notes. Please try again.',
        });
      } else {
        setStatusMessage({
          type: 'warning',
          text: `Deleted ${noteIds.length - failures.length} note${noteIds.length - failures.length === 1 ? '' : 's'}, but ${failures.length} failed.`,
        });
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleSelectionMode = () => {
    setSelectionMode((prev) => !prev);
  };

  const handleToggleNoteSelection = useCallback((noteId) => {
    setSelectedNoteIds((prev) => {
      const next = new Set(prev);
      if (next.has(noteId)) {
        next.delete(noteId);
      } else {
        next.add(noteId);
      }
      return next;
    });
  }, []);

  const handleSelectAllOnPage = useCallback(() => {
    setSelectedNoteIds((prev) => {
      const next = new Set(prev);
      paginatedNotes.forEach((note) => next.add(note.id));
      return next;
    });
  }, [paginatedNotes]);

  const handleSelectAllFiltered = useCallback(() => {
    setSelectedNoteIds(new Set(sortedNotes.map((note) => note.id)));
  }, [sortedNotes]);

  const handleClearSelection = useCallback(() => {
    setSelectedNoteIds(new Set());
  }, []);

  const handleCreateNote = async () => {
    const newNote = {
      title: 'Untitled Note',
      content: '',
      category: selectedCategory === 'all' ? 'personal' : selectedCategory,
      tags: [],
      is_starred: false,
    };

    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newNote)
      });

      if (response.ok) {
        const result = await response.json();
        const notesAfterCreate = await loadNotes();
        const createdNoteId = result?.note?.id;
        if (createdNoteId && Array.isArray(notesAfterCreate)) {
          const created = notesAfterCreate.find((note) => note.id === createdNoteId);
          if (created) {
            setSelectedNote(created);
            setEditedNote({
              ...created,
              tags: Array.isArray(created.tags) ? created.tags : [],
            });
          } else if (result?.note) {
            setSelectedNote(result.note);
            setEditedNote({
              ...result.note,
              tags: Array.isArray(result.note.tags) ? result.note.tags : [],
            });
          }
        } else if (result?.note) {
          setSelectedNote(result.note);
          setEditedNote({
            ...result.note,
            tags: Array.isArray(result.note.tags) ? result.note.tags : [],
          });
        }
        setCurrentPage(1);
        setSelectionMode(false);
        setSelectedNoteIds(new Set());
        setIsEditing(true);
        setStatusMessage({
          type: 'success',
          text: 'Created a new note.',
        });
        setMobileView('viewer');
      }
    } catch (error) {
      console.error('Failed to create note:', error);
    }
  };

  const handleSaveNote = async (noteToSave) => {
    // Use passed note (from modal) or fall back to editedNote
    const noteData = noteToSave || editedNote;
    if (!noteData) return;

    setIsSaving(true);

    try {
      const payload = {
        title: noteData.title,
        content: noteData.content,
        category: noteData.category,
        tags: noteData.tags,
        is_starred: noteData.is_starred,
      };

      const response = await fetch(`/api/notes/${noteData.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const notesAfterSave = await loadNotes();
        const updated = Array.isArray(notesAfterSave)
          ? notesAfterSave.find((note) => note.id === noteData.id)
          : null;
        if (updated) {
          setSelectedNote(updated);
          setEditedNote({
            ...updated,
            tags: Array.isArray(updated.tags) ? updated.tags : [],
          });
        }
        setIsEditing(false);
        setIsEditModalOpen(false); // Close modal if open
        setStatusMessage({
          type: 'success',
          text: 'Note saved.',
        });
      } else {
        setStatusMessage({
          type: 'error',
          text: 'Failed to save the note. Please try again.',
        });
      }
    } catch (error) {
      console.error('Failed to save note:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to save the note. Please check your connection and try again.',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteNote = async (noteId) => {
    await deleteNotesByIds([noteId]);
  };

  const handleBulkDelete = async () => {
    if (selectedNoteIds.size === 0) return;
    await deleteNotesByIds(Array.from(selectedNoteIds));
  };

  const handleSortChange = (event) => {
    setSortOptionId(event.target.value);
  };

  const handlePageSizeChange = (event) => {
    const value = Number(event.target.value) || DEFAULT_PAGE_SIZE;
    setPageSize(value);
  };

  const handlePageChange = (nextPage) => {
    if (nextPage < 1 || nextPage > totalPages) return;
    setCurrentPage(nextPage);
  };

  const handleNoteLinkNavigation = useCallback(async (targetTitle) => {
    if (!targetTitle || !authToken) return;

    // First check if we have the note locally
    const normalized = targetTitle.trim().toLowerCase();
    const found = notes.find((note) => note.title.trim().toLowerCase() === normalized);

    if (found) {
      // Navigate to the note route
      navigate(`/notes/${found.id}`);
      return;
    }

    // If not found locally, try API lookup
    try {
      const response = await fetch(
        `/api/notes/lookup?title=${encodeURIComponent(targetTitle)}`,
        { headers: { Authorization: `Bearer ${authToken}` } }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.note_id) {
          navigate(`/notes/${data.note_id}`);
        } else {
          setStatusMessage({
            type: 'warning',
            text: `No note titled "${targetTitle}" was found.`,
          });
        }
      } else {
        setStatusMessage({
          type: 'warning',
          text: `No note titled "${targetTitle}" was found.`,
        });
      }
    } catch (err) {
      console.error('Error looking up note:', err);
      setStatusMessage({
        type: 'error',
        text: `Failed to look up note "${targetTitle}".`,
      });
    }
  }, [notes, authToken, navigate]);

  const handleReindexNotes = async () => {
    if (!authToken) return;
    if (!confirmAction('Reindex all notes embeddings? This may take a minute.')) return;

    setIsReindexing(true);
    setStatusMessage({
      type: 'info',
      text: 'Reindexing notes… this may take a minute.',
    });

    try {
      const response = await fetch('/api/notes/reindex', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        let errorMessage = 'Failed to reindex notes. Please try again later.';
        try {
          const errorData = await response.json();
          if (errorData?.message) {
            errorMessage = errorData.message;
          }
        } catch (error) {
          // Ignore JSON parse errors
        }
        setStatusMessage({ type: 'error', text: errorMessage });
        return;
      }

      const data = await response.json().catch(() => null);
      await loadNotes();
      setStatusMessage({
        type: 'success',
        text: data?.message || 'Reindexed notes successfully.',
      });
    } catch (error) {
      console.error('Failed to reindex notes:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to reindex notes. Please try again later.',
      });
    } finally {
      setIsReindexing(false);
    }
  };

  const handleExportPDF = async () => {
    if (!selectedNote || !authToken) return;

    setIsExporting(true);
    try {
      const response = await fetch(`/api/notes/${selectedNote.id}/export/pdf`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to export PDF');
      }

      // Download the PDF
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedNote.title.substring(0, 50)}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setStatusMessage({
        type: 'success',
        text: 'PDF exported successfully!',
      });
    } catch (error) {
      console.error('Failed to export PDF:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to export PDF. Please try again.',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleOpenPublishDialog = async () => {
    if (!selectedNote || !authToken) return;

    // Fetch current publish status
    try {
      const response = await fetch(`/api/notes/${selectedNote.id}/publish-status`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setPublishStatus(data);
      } else {
        setPublishStatus({ is_published: false });
      }
    } catch (error) {
      console.error('Failed to fetch publish status:', error);
      setPublishStatus({ is_published: false });
    }

    setShowPublishDialog(true);
  };

  const handlePublish = async (publishData) => {
    if (!selectedNote || !authToken) return;

    setIsPublishing(true);
    try {
      const response = await fetch(`/api/notes/${selectedNote.id}/publish`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(publishData),
      });

      if (!response.ok) {
        throw new Error('Failed to publish note');
      }

      const data = await response.json();
      // Add is_published flag so the dialog switches to the published view
      setPublishStatus({
        ...data,
        is_published: true,
        view_count: 0,
      });
      // Don't close dialog - let user see the URL and stats

      // Copy public URL to clipboard
      const publicUrl = `${window.location.origin}${data.public_url}`;
      await navigator.clipboard.writeText(publicUrl);

      setStatusMessage({
        type: 'success',
        text: 'Note published successfully! Link copied to clipboard.',
      });
    } catch (error) {
      console.error('Failed to publish note:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to publish note. Please try again.',
      });
    } finally {
      setIsPublishing(false);
    }
  };

  const handleUnpublish = async () => {
    if (!selectedNote || !authToken) return;
    if (!confirmAction('Unpublish this note? The public link will stop working.')) return;

    try {
      const response = await fetch(`/api/notes/${selectedNote.id}/publish`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to unpublish note');
      }

      setPublishStatus({ is_published: false });
      setShowPublishDialog(false);

      setStatusMessage({
        type: 'success',
        text: 'Note unpublished successfully.',
      });
    } catch (error) {
      console.error('Failed to unpublish note:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to unpublish note. Please try again.',
      });
    }
  };

  const dismissStatusMessage = useCallback(() => {
    setStatusMessage(null);
  }, []);

  const statusStyleMap = {
    success: {
      container: 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700 text-emerald-700 dark:text-emerald-200',
      icon: CheckCircle2,
    },
    error: {
      container: 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 text-red-700 dark:text-red-200',
      icon: AlertTriangle,
    },
    warning: {
      container: 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-amber-700 dark:text-amber-200',
      icon: AlertTriangle,
    },
    info: {
      container: 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 text-blue-700 dark:text-blue-200',
      icon: Info,
    },
  };

  const activeStatus = statusMessage ? statusStyleMap[statusMessage.type] || statusStyleMap.info : null;
  const StatusIcon = activeStatus?.icon || null;

  const confirmAction = useCallback((message) => {
    if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
      return window.confirm(message);
    }
    return true;
  }, []);

  const handleToggleStar = async (note, e) => {
    e?.stopPropagation();

    try {
      const response = await fetch(`/api/notes/${note.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_starred: !note.is_starred })
      });

      if (response.ok) {
        const notesAfterToggle = await loadNotes();
        if (selectedNote?.id === note.id && Array.isArray(notesAfterToggle)) {
          const updated = notesAfterToggle.find((item) => item.id === note.id);
          if (updated) {
            setSelectedNote(updated);
          }
        }
        setStatusMessage({
          type: 'success',
          text: !note.is_starred ? 'Note starred.' : 'Note unstarred.',
        });
      } else {
        setStatusMessage({
          type: 'error',
          text: 'Failed to update star status.',
        });
      }
    } catch (error) {
      console.error('Failed to toggle star:', error);
      setStatusMessage({
        type: 'error',
        text: 'Failed to update star status. Please try again.',
      });
    }
  };

  const handleSelectNote = (note) => {
    if (selectionMode) {
      handleToggleNoteSelection(note.id);
      return;
    }

    // Navigate to individual note route
    navigate(`/notes/${note.id}`);
  };

  const handleEditNote = () => {
    setEditedNote({
      ...selectedNote,
      tags: Array.isArray(selectedNote?.tags) ? [...selectedNote.tags] : [],
    });
    // Clear autocomplete state when starting to edit
    setAutocompleteSuggestion('');
    setShowAutocomplete(false);
    setIsLoadingAutocomplete(false);
    setIsEditModalOpen(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedNote(null);
    setIsEditModalOpen(false);
  };

  const handleCloseEditModal = () => {
    setIsEditModalOpen(false);
    setEditedNote(null);
  };

  const handleAddTag = (tag) => {
    if (!editedNote || !tag.trim()) return;
    if (editedNote.tags.includes(tag.trim())) return;

    setEditedNote({
      ...editedNote,
      tags: [...editedNote.tags, tag.trim()]
    });
  };

  const handleRemoveTag = (tag) => {
    if (!editedNote) return;

    setEditedNote({
      ...editedNote,
      tags: editedNote.tags.filter(t => t !== tag)
    });
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // Check if note was edited (updated_at diffeNo backlinks yet. Other notes can link to this note using [[Note Title]] syntax.rs from created_at by more than 1 second)
  const wasEdited = (note) => {
    if (!note.created_at || !note.updated_at) return false;
    const created = new Date(note.created_at).getTime();
    const updated = new Date(note.updated_at).getTime();
    return Math.abs(updated - created) > 1000; // More than 1 second difference
  };

  const truncateContent = (content, maxLength = 120) => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength).trim() + '...';
  };

  const fetchAutocompleteSuggestion = async (text) => {
    if (!text || text.length < 3 || !authToken) return;

    try {
      setIsLoadingAutocomplete(true);
      const response = await fetch('/api/notes/autocomplete', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          current_text: text,
          note_title: editedNote?.title || '',
          note_category: editedNote?.category || 'personal',
          max_tokens: 50,
          mode: 'notes'
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.suggestion && data.confidence > 0.5) {
          setAutocompleteSuggestion(data.suggestion);
          setShowAutocomplete(true);
        } else {
          setAutocompleteSuggestion('');
          setShowAutocomplete(false);
        }
      } else {
        setAutocompleteSuggestion('');
        setShowAutocomplete(false);
      }
    } catch (error) {
      console.error('Error fetching autocomplete suggestion:', error);
      setAutocompleteSuggestion('');
      setShowAutocomplete(false);
    } finally {
      setIsLoadingAutocomplete(false);
    }
  };

  const handleContentKeyDown = (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      
      if (autocompleteSuggestion) {
        // Accept the suggestion - intelligently merge to avoid duplicates
        // Find where the suggestion starts overlapping with existing content
        let newContent = editedNote.content;
        
        // Check if the suggestion starts with text that's already in the content
        // This handles cases like "Espress" + "o Machine" where "o" might be the start
        let overlapLength = 0;
        for (let i = 1; i <= Math.min(autocompleteSuggestion.length, editedNote.content.length); i++) {
          const suggestionStart = autocompleteSuggestion.substring(0, i);
          const contentEnd = editedNote.content.substring(editedNote.content.length - i);
          if (suggestionStart.toLowerCase() === contentEnd.toLowerCase()) {
            overlapLength = i;
          }
        }
        
        // If there's overlap, replace it; otherwise just append
        if (overlapLength > 0) {
          newContent = editedNote.content.substring(0, editedNote.content.length - overlapLength) + autocompleteSuggestion;
        } else {
          newContent = editedNote.content + autocompleteSuggestion;
        }
        
        setEditedNote({
          ...editedNote,
          content: newContent
        });
        setAutocompleteSuggestion('');
        setShowAutocomplete(false);
      } else {
        // Insert tab character if no suggestion
        const textarea = e.target;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const newContent = editedNote.content.substring(0, start) + '\t' + editedNote.content.substring(end);
        setEditedNote({
          ...editedNote,
          content: newContent
        });
      }
    }
  };

  const handleContentChange = (e) => {
    const newContent = e.target.value;
    const cursorPos = e.target.selectionStart;

    setEditedNote({ ...editedNote, content: newContent });
    setCursorPosition(cursorPos);

    // Clear existing timeout
    if (autocompleteTimeoutRef.current) {
      clearTimeout(autocompleteTimeoutRef.current);
    }

    // Hide autocomplete immediately while typing to prevent lag
    setShowAutocomplete(false);

    // Debounce autocomplete requests - wait 1000ms after last keystroke to avoid lag
    if (newContent.length > 2) {
      autocompleteTimeoutRef.current = setTimeout(() => {
        fetchAutocompleteSuggestion(newContent);
      }, 1000);
    } else {
      setAutocompleteSuggestion('');
    }
  };

  return (
    <div className="h-lvh flex bg-zinc-50 dark:bg-zinc-950">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {mobileView !== 'list' && (
              <button
                onClick={() => setMobileView(mobileView === 'viewer' ? 'list' : 'list')}
                className="p-2 -ml-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <ArrowLeft className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
              </button>
            )}
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
              <h1 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                {mobileView === 'viewer' && selectedNote
                  ? selectedNote.title.length > 20
                    ? selectedNote.title.substring(0, 20) + '...'
                    : selectedNote.title
                  : 'Notes'}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {mobileView === 'list' && (
              <>
                <button
                  onClick={() => setMobileView('sidebar')}
                  className="p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"
                >
                  <Menu className="w-5 h-5 text-zinc-700 dark:text-zinc-300" />
                </button>
                <button
                  onClick={handleCreateNote}
                  className="p-2 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-200"
                >
                  <Plus className="w-5 h-5" />
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Left Sidebar - Categories & Tags */}
      <div className={`
        ${mobileView === 'sidebar' ? 'block' : 'hidden'}
        lg:block
        w-full lg:w-64
        ${mobileView === 'sidebar' ? 'pt-4' : ''}
        border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex flex-col min-h-0
      `}>
        {/* Header - Hidden on mobile (using mobile header instead) */}
        <div className="hidden lg:block p-4 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="w-6 h-6 text-zinc-700 dark:text-zinc-300" />
            <h1 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Notes</h1>
          </div>
          <div className="flex flex-col gap-2">
            <Button
              onClick={handleCreateNote}
              className="w-full bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-200"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Note
            </Button>
            <Button
              onClick={() => setShowGraph(true)}
              outline
              className="w-full"
            >
              <Network className="w-4 h-4 mr-2" />
              Graph View
            </Button>
          </div>
        </div>

        {/* Scrollable Categories & Tags */}
        <div className="flex-1 overflow-y-auto min-h-0 p-4 space-y-6 max-h-[68vh]">
          {/* Categories */}
          <div>
            <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-2">
              Categories
            </h3>
            <div className="space-y-1">
              {categories.map((cat) => {
                const Icon = cat.icon;
                return (
                  <button
                    key={cat.id}
                    onClick={() => {
                      setSelectedCategory(cat.id);
                      setSelectedTag(null);
                      setMobileView('list');
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                      selectedCategory === cat.id && !selectedTag
                        ? 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900'
                        : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4" />
                      <span className="font-medium">{cat.label}</span>
                    </div>
                    <span className={`text-xs ${
                      selectedCategory === cat.id && !selectedTag
                        ? 'text-white dark:text-zinc-900'
                        : 'text-zinc-500 dark:text-zinc-400'
                    }`}>
                      {cat.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Starred */}
          <div>
            <button
              onClick={() => {
                setStarredFilter(!starredFilter);
                setMobileView('list');
              }}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                starredFilter
                  ? 'bg-amber-500 text-white'
                  : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              <div className="flex items-center gap-2">
                <Star className={`w-4 h-4 ${starredFilter ? 'fill-current' : ''}`} />
                <span className="font-medium">Starred</span>
              </div>
              <span className={`text-xs ${
                starredFilter ? 'text-white' : 'text-zinc-500 dark:text-zinc-400'
              }`}>
                {notes.filter(n => n.is_starred).length}
              </span>
            </button>
          </div>

          {/* Tags - Hierarchical Browser with Collapse */}
          {allTags.length > 0 && (
            <div>
              <button
                onClick={() => setIsTagsSectionCollapsed(!isTagsSectionCollapsed)}
                className="w-full flex items-center justify-between mb-2 group"
              >
                <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
                  Tags
                </h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {allTags.length}
                  </span>
                  <ChevronRight
                    className={`w-4 h-4 text-zinc-500 dark:text-zinc-400 transition-transform ${
                      isTagsSectionCollapsed ? '' : 'rotate-90'
                    }`}
                  />
                </div>
              </button>
              {!isTagsSectionCollapsed && (
                <TagsBrowser
                  allTags={allTags}
                  selectedTag={selectedTag}
                  onSelectTag={(tag) => {
                    setSelectedTag(tag);
                    setSelectedCategory('all');
                    setMobileView('list');
                  }}
                />
              )}
            </div>
          )}

          {/* Import */}
          <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
            <Button
              outline
              onClick={() => setShowImportDialog(true)}
              // className="w-full bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              <Upload className="w-4 h-4 mr-2" />
              Import
            </Button>
            {/* Back to Home - Visible on mobile */}
            <a href="/" className="lg:hidden block">
              <Button
                outline
                className="w-full"
              >
                <Home className="w-4 h-4 mr-2" />
                Back to Home
              </Button>
            </a>
          </div>
        </div>
      </div>

      {/* Notes List - Full Width */}
      <div className={`
        ${mobileView === 'list' ? 'block' : 'hidden'}
        lg:block
        flex-1 overflow-x-hidden
        ${mobileView === 'list' ? 'pt-4' : ''}
        bg-white dark:bg-zinc-900 flex flex-col min-h-0
      `}>
        {/* Search & Controls */}
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 space-y-3">
          {activeStatus && statusMessage && (
            <div className={`flex items-start justify-between gap-3 rounded-xl px-3 py-2 text-sm ${activeStatus.container}`}>
              <div className="flex items-start gap-2">
                {StatusIcon && <StatusIcon className="mt-0.5 h-4 w-4 flex-shrink-0" />}
                <span className="leading-snug">{statusMessage.text}</span>
              </div>
              <button
                onClick={dismissStatusMessage}
                className="text-xs font-semibold uppercase tracking-wide text-current hover:opacity-80"
              >
                Dismiss
              </button>
            </div>
          )}

          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search notes..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 pl-9 pr-4 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
                />
              </div>
              <button
                onClick={handleToggleSelectionMode}
                className={`inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  selectionMode
                    ? 'border-blue-500 bg-blue-500 text-white hover:bg-blue-600'
                    : 'border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                {selectionMode ? (
                  <CheckSquare className="h-4 w-4" />
                ) : (
                  <Square className="h-4 w-4" />
                )}
                {selectionMode ? 'Exit Select' : 'Multi-select'}
              </button>
            </div>

            <Button
              onClick={handleReindexNotes}
              disabled={isReindexing}
              // className="shrink-0 bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              {isReindexing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              {isReindexing ? 'Reindexing…' : 'Reindex'}
            </Button>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              <label className="tracking-wide">Sort</label>
              <select
                value={sortOptionId}
                onChange={handleSortChange}
                className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              <label className="tracking-wide">Page Size</label>
              <select
                value={pageSize}
                onChange={handlePageSizeChange}
                className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size} / page
                  </option>
                ))}
              </select>
            </div>
            <div className="text-xs text-zinc-500 dark:text-zinc-400">
              {formatNumber(sortedNotes.length)} total notes
            </div>
          </div>

          {selectionMode && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 px-3 py-2 text-xs text-zinc-700 dark:text-zinc-200">
              <div className="font-medium">
                {selectedNoteIds.size > 0
                  ? `${selectedNoteIds.size} selected`
                  : 'Select notes to run bulk actions'}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={handleSelectAllOnPage}
                  className="rounded-md border border-zinc-300 dark:border-zinc-600 px-2 py-1 font-medium hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  Select page
                </button>
                <button
                  onClick={handleSelectAllFiltered}
                  className="rounded-md border border-zinc-300 dark:border-zinc-600 px-2 py-1 font-medium hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  Select all
                </button>
                <button
                  onClick={handleClearSelection}
                  className="rounded-md border border-zinc-300 dark:border-zinc-600 px-2 py-1 font-medium hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  Clear
                </button>
                <button
                  onClick={handleBulkDelete}
                  disabled={selectedNoteIds.size === 0 || isDeleting}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium transition-colors ${
                    selectedNoteIds.size === 0 || isDeleting
                      ? 'cursor-not-allowed bg-red-200/60 text-red-500 dark:bg-red-900/20 dark:text-red-300'
                      : 'bg-red-500 text-white hover:bg-red-600'
                  }`}
                >
                  {isDeleting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  Delete selected
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Notes List */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-b-2 border-zinc-900 dark:border-zinc-100"></div>
            </div>
          ) : sortedNotes.length === 0 ? (
            <div className="p-8 text-center">
              <FileText className="mx-auto mb-3 h-12 w-12 text-zinc-300 dark:text-zinc-700" />
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {searchTerm || selectedTag || selectedCategory !== 'all' || starredFilter
                  ? 'No notes match your filters'
                  : 'No notes yet'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-zinc-200 dark:divide-zinc-800 overflow-y-auto md:max-h-[68vh]">
              {paginatedNotes.map((note) => {
                const isActive = selectedNote?.id === note.id;
                const isSelected = selectedNoteIds.has(note.id);
                const tags = Array.isArray(note.tags) ? note.tags : [];

                return (
                  <div
                    key={note.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSelectNote(note)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        handleSelectNote(note);
                      }
                    }}
                    className={`w-full cursor-pointer p-4 text-left transition-colors ${
                      isActive
                        ? 'bg-zinc-100 dark:bg-zinc-800'
                        : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
                    } ${
                      selectionMode && isSelected
                        ? 'ring-2 ring-blue-400 dark:ring-blue-600'
                        : ''
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {selectionMode && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleToggleNoteSelection(note.id);
                          }}
                          className={`mt-0.5 rounded-md border p-1 transition-colors ${
                            isSelected
                              ? 'border-blue-500 bg-blue-500 text-white'
                              : 'border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                          }`}
                        >
                          {isSelected ? (
                            <CheckSquare className="h-3.5 w-3.5" />
                          ) : (
                            <Square className="h-3.5 w-3.5" />
                          )}
                        </button>
                      )}

                      <div className="flex-1">
                        <div className="mb-2 flex items-start justify-between gap-2">
                          <h3 className="line-clamp-1 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                            {note.title || 'Untitled note'}
                          </h3>
                          <button
                            type="button"
                            onClick={(e) => handleToggleStar(note, e)}
                            className={`flex-shrink-0 transition-colors ${
                              note.is_starred
                                ? 'text-amber-500'
                                : 'text-zinc-300 dark:text-zinc-700 hover:text-amber-500'
                            }`}
                          >
                            <Star className={`h-3.5 w-3.5 ${note.is_starred ? 'fill-current' : ''}`} />
                          </button>
                        </div>

                        <p className="mb-2 line-clamp-2 text-xs text-zinc-600 dark:text-zinc-400">
                          {truncateContent(note.content || '')}
                        </p>

                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {wasEdited(note) ? `Edited ${formatDate(note.updated_at)}` : `Created ${formatDate(note.created_at)}`}
                          </span>
                        </div>

                        {tags.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                className="inline-flex items-center gap-1 rounded-full bg-blue-100 dark:bg-blue-900/30 px-2 py-0.5 text-xs text-blue-700 dark:text-blue-300"
                              >
                                <Hash className="h-3 w-3" />
                                {tag}
                              </span>
                            ))}
                            {tags.length > 3 && (
                              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                +{tags.length - 3} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer - Pagination */}
        <div className="border-t border-zinc-200 dark:border-zinc-800 px-4 py-3 text-xs text-zinc-500 dark:text-zinc-400">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Showing {sortedNotes.length === 0 ? 0 : showingFrom}–{sortedNotes.length === 0 ? 0 : showingTo} of {formatNumber(sortedNotes.length)} note{sortedNotes.length === 1 ? '' : 's'}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handlePageChange(safeCurrentPage - 1)}
                disabled={safeCurrentPage === 1}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 font-medium transition-colors ${
                  safeCurrentPage === 1
                    ? 'cursor-not-allowed border-zinc-200 text-zinc-400 dark:border-zinc-700 dark:text-zinc-600'
                    : 'border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Prev
              </button>
              <span className="rounded-md border border-zinc-200 bg-white px-3 py-1 font-medium dark:border-zinc-700 dark:bg-zinc-900">
                Page {safeCurrentPage} / {totalPages}
              </span>
              <button
                onClick={() => handlePageChange(safeCurrentPage + 1)}
                disabled={safeCurrentPage === totalPages}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 font-medium transition-colors ${
                  safeCurrentPage === totalPages
                    ? 'cursor-not-allowed border-zinc-200 text-zinc-400 dark:border-zinc-700 dark:text-zinc-600'
                    : 'border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Notes Graph Modal */}
      {showGraph && (
        <NotesGraph
          notes={notes}
          onSelectNote={(noteId) => {
            navigate(`/notes/${noteId}`);
          }}
          onClose={() => setShowGraph(false)}
        />
      )}

      {/* Import Dialog */}
      {showImportDialog && (
        <NotesImportDialog
          authToken={authToken}
          onClose={() => {
            setShowImportDialog(false);
            loadNotes();
          }}
        />
      )}

      {/* Publish Dialog */}
      {showPublishDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-4">
              {publishStatus?.is_published ? 'Manage Published Note' : 'Publish Note'}
            </h3>

            {publishStatus?.is_published ? (
              <div className="space-y-4">
                <div className="p-4 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700">
                  <p className="text-sm text-emerald-700 dark:text-emerald-200 mb-2">
                    This note is currently published
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={`${window.location.origin}/public/notes/${publishStatus.public_id}`}
                      className="flex-1 px-3 py-2 text-sm rounded border border-emerald-200 dark:border-emerald-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    />
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(`${window.location.origin}/public/notes/${publishStatus.public_id}`);
                        setStatusMessage({ type: 'success', text: 'Link copied!' });
                      }}
                      className="p-2 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/40"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="mt-3 text-xs text-emerald-600 dark:text-emerald-300 space-y-1">
                    <p>Views: {publishStatus.view_count || 0}</p>
                    {publishStatus.has_password && <p className="flex items-center gap-1"><Lock className="w-3 h-3" /> Password protected</p>}
                    {publishStatus.expires_at && <p className="flex items-center gap-1"><Calendar className="w-3 h-3" /> Expires: {new Date(publishStatus.expires_at).toLocaleDateString()}</p>}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => setShowPublishDialog(false)} outline className="flex-1">
                    Close
                  </Button>
                  <Button onClick={handleUnpublish} color="red" className="flex-1">
                    Unpublish
                  </Button>
                </div>
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.target);
                  const publishData = {
                    password: formData.get('password') || undefined,
                    expires_at: formData.get('expires_at') || undefined,
                  };
                  handlePublish(publishData);
                }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Password Protection (Optional)
                  </label>
                  <input
                    type="password"
                    name="password"
                    placeholder="Leave empty for public access"
                    className="w-full px-3 py-2 rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    Expiration Date (Optional)
                  </label>
                  <input
                    type="datetime-local"
                    name="expires_at"
                    className="w-full px-3 py-2 rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    onClick={() => setShowPublishDialog(false)}
                    outline
                    className="flex-1"
                    disabled={isPublishing}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    color="blue"
                    className="flex-1"
                    disabled={isPublishing}
                  >
                    {isPublishing ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Publishing...
                      </>
                    ) : (
                      <>
                        <Share2 className="w-4 h-4 mr-2" />
                        Publish
                      </>
                    )}
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Edit Modal */}
      <NoteEditModal
        note={editedNote}
        isOpen={isEditModalOpen}
        onClose={handleCloseEditModal}
        onSave={handleSaveNote}
        onDelete={handleDeleteNote}
        autocompleteSuggestion={autocompleteSuggestion}
        showAutocomplete={showAutocomplete}
        isLoadingAutocomplete={isLoadingAutocomplete}
        onContentChange={handleContentChange}
        onKeyDown={handleContentKeyDown}
        isSaving={isSaving}
      />
    </div>
  );
}
