import { useParams, useOutletContext, useNavigate, Link } from 'react-router';
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  ArrowLeft,
  Edit2,
  Trash2,
  Star,
  Save,
  X,
  Clock,
  Tag,
  Hash,
  Loader2,
  Download,
  Share2,
  Globe,
  AlertCircle,
  Link2,
  ChevronRight,
  Sparkles,
  Copy,
  Lock,
  Calendar,
  Brain,
} from 'lucide-react';
import { Button } from '../components/catalyst/button';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark as syntaxTheme } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

interface Note {
  id: number;
  title: string;
  content: string;
  category: string;
  tags: string[];
  is_starred: boolean;
  created_at: string;
  updated_at: string;
}

interface PublishStatus {
  is_published: boolean;
  public_id?: string;
  published_at?: string;
}

interface Backlink {
  id: number;
  title: string;
  snippet?: string;
  category: string;
  created_at: string;
}

interface SimilarNote {
  id: number;
  title: string;
  content: string;
  category: string;
  tags: string[];
  similarity: number;
  created_at: string;
}

export function clientLoader() {
  requirePermission('notes.access');
  return null;
}

// Pre-process content to convert [[wikilinks]] to standard markdown links
function preprocessWikilinks(content: string): string {
  if (!content) return '';
  // Convert [[Title]] or [[Title|Display]] to [Display](#wikilink:Title)
  // Using hash-based URL to avoid ReactMarkdown URL sanitization
  return content.replace(/\[\[([^\]|]+)(\|([^\]]+))?\]\]/g, (_, target, __, alias) => {
    const title = target.trim();
    const display = (alias || title).trim();
    return `[${display}](#wikilink:${encodeURIComponent(title)})`;
  });
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function wasEdited(note: Note): boolean {
  if (!note.updated_at || !note.created_at) return false;
  const created = new Date(note.created_at).getTime();
  const updated = new Date(note.updated_at).getTime();
  return updated - created > 60000; // More than 1 minute difference
}

export default function NoteDetailRoute() {
  const { noteId } = useParams();
  const navigate = useNavigate();
  const { authToken } = useOutletContext<AuthContext>();

  // State
  const [note, setNote] = useState<Note | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedNote, setEditedNote] = useState<Note | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [publishStatus, setPublishStatus] = useState<PublishStatus | null>(null);
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [backlinks, setBacklinks] = useState<Backlink[]>([]);
  const [isLoadingBacklinks, setIsLoadingBacklinks] = useState(false);
  const [similarNotes, setSimilarNotes] = useState<SimilarNote[]>([]);
  const [isLoadingSimilar, setIsLoadingSimilar] = useState(false);

  // Autocomplete state
  const [autocompleteSuggestion, setAutocompleteSuggestion] = useState('');
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [isLoadingAutocomplete, setIsLoadingAutocomplete] = useState(false);
  const autocompleteTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch note data
  useEffect(() => {
    if (!noteId || !authToken) return;

    const fetchNote = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/notes/${noteId}`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });

        if (response.ok) {
          const data = await response.json();
          setNote(data.note);
          setPublishStatus(data.note?.publish_status || null);
        } else if (response.status === 404) {
          setError('Note not found');
        } else {
          setError('Failed to load note');
        }
      } catch (err) {
        console.error('Error fetching note:', err);
        setError('Failed to load note. Please check your connection.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchNote();
  }, [noteId, authToken]);

  // Fetch backlinks
  useEffect(() => {
    if (!noteId || !authToken) return;

    const fetchBacklinks = async () => {
      setIsLoadingBacklinks(true);
      try {
        const response = await fetch(`/api/notes/${noteId}/backlinks`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (response.ok) {
          const data = await response.json();
          setBacklinks(data.backlinks || []);
        }
      } catch (err) {
        console.error('Error fetching backlinks:', err);
      } finally {
        setIsLoadingBacklinks(false);
      }
    };

    fetchBacklinks();
  }, [noteId, authToken]);

  // Fetch similar notes (semantic)
  useEffect(() => {
    if (!noteId || !authToken) return;

    const fetchSimilarNotes = async () => {
      setIsLoadingSimilar(true);
      try {
        const response = await fetch(`/api/notes/${noteId}/similar?limit=5`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (response.ok) {
          const data = await response.json();
          setSimilarNotes(data.similar_notes || []);
        }
      } catch (err) {
        console.error('Error fetching similar notes:', err);
      } finally {
        setIsLoadingSimilar(false);
      }
    };

    fetchSimilarNotes();
  }, [noteId, authToken]);

  // Handle wikilink navigation - lookup note by title and navigate
  const handleWikilinkNavigation = useCallback(
    async (targetTitle: string) => {
      if (!targetTitle || !authToken) return;

      try {
        // Search for note by title
        const response = await fetch(
          `/api/notes/lookup?title=${encodeURIComponent(targetTitle)}`,
          { headers: { Authorization: `Bearer ${authToken}` } }
        );

        if (response.ok) {
          const data = await response.json();
          if (data.note_id) {
            navigate(`/notes/${data.note_id}`);
          } else {
            // Note not found - could prompt to create
            alert(`Note "${targetTitle}" not found. Would you like to create it?`);
          }
        }
      } catch (err) {
        console.error('Error looking up note:', err);
      }
    },
    [authToken, navigate]
  );

  // Edit handlers
  const handleStartEdit = () => {
    if (note) {
      setEditedNote({ ...note });
      setIsEditing(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedNote(null);
  };

  const handleSaveNote = async () => {
    if (!editedNote || !authToken) return;

    setIsSaving(true);
    try {
      const response = await fetch(`/api/notes/${editedNote.id}`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: editedNote.title,
          content: editedNote.content,
          category: editedNote.category,
          tags: editedNote.tags,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setNote(data.note || data);
        setIsEditing(false);
        setEditedNote(null);
      } else {
        throw new Error('Failed to save note');
      }
    } catch (err) {
      console.error('Error saving note:', err);
      alert('Failed to save note. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleStar = async () => {
    if (!note || !authToken) return;

    try {
      const response = await fetch(`/api/notes/${note.id}`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_starred: !note.is_starred }),
      });

      if (response.ok) {
        setNote({ ...note, is_starred: !note.is_starred });
      }
    } catch (err) {
      console.error('Error toggling star:', err);
    }
  };

  const handleDeleteNote = async () => {
    if (!note || !authToken) return;

    if (!confirm('Are you sure you want to delete this note? This cannot be undone.')) {
      return;
    }

    try {
      const response = await fetch(`/api/notes/${note.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });

      if (response.ok) {
        navigate('/notes');
      } else {
        throw new Error('Failed to delete note');
      }
    } catch (err) {
      console.error('Error deleting note:', err);
      alert('Failed to delete note. Please try again.');
    }
  };

  const handleExportPDF = async () => {
    if (!note || !authToken) return;

    setIsExporting(true);
    try {
      const response = await fetch(`/api/notes/${note.id}/export/pdf`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${note.title.replace(/[^a-z0-9]/gi, '_')}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Error exporting PDF:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleOpenPublishDialog = async () => {
    if (!note || !authToken) return;

    // Fetch current publish status
    try {
      const response = await fetch(`/api/notes/${note.id}/publish-status`, {
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

  const handlePublish = async (publishData: any) => {
    if (!note || !authToken) return;

    setIsPublishing(true);
    try {
      const response = await fetch(`/api/notes/${note.id}/publish`, {
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
      const publicUrl = `${window.location.origin}/public/notes/${data.public_id}`;
      await navigator.clipboard.writeText(publicUrl);

      alert('Note published successfully! Link copied to clipboard.');
    } catch (error) {
      console.error('Failed to publish note:', error);
      alert('Failed to publish note. Please try again.');
    } finally {
      setIsPublishing(false);
    }
  };

  const handleUnpublish = async () => {
    if (!note || !authToken) return;
    if (!confirm('Unpublish this note? The public link will stop working.')) return;

    try {
      const response = await fetch(`/api/notes/${note.id}/publish`, {
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

      alert('Note unpublished successfully.');
    } catch (error) {
      console.error('Failed to unpublish note:', error);
      alert('Failed to unpublish note. Please try again.');
    }
  };

  const handleAddTag = (tag: string) => {
    if (!editedNote || !tag.trim()) return;
    const normalizedTag = tag.trim().toLowerCase();
    if (!editedNote.tags.includes(normalizedTag)) {
      setEditedNote({
        ...editedNote,
        tags: [...editedNote.tags, normalizedTag],
      });
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    if (!editedNote) return;
    setEditedNote({
      ...editedNote,
      tags: editedNote.tags.filter((tag) => tag !== tagToRemove),
    });
  };

  // Autocomplete functions
  const fetchAutocompleteSuggestion = async (text: string) => {
    if (!text || text.length < 3 || !authToken) return;

    try {
      setIsLoadingAutocomplete(true);
      const response = await fetch('/api/notes/autocomplete', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          current_text: text,
          note_title: editedNote?.title || '',
          note_category: editedNote?.category || 'personal',
          max_tokens: 50,
          mode: 'notes',
        }),
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
    } catch (err) {
      console.error('Error fetching autocomplete suggestion:', err);
      setAutocompleteSuggestion('');
      setShowAutocomplete(false);
    } finally {
      setIsLoadingAutocomplete(false);
    }
  };

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setEditedNote((prev) => (prev ? { ...prev, content: newContent } : null));

    // Clear existing timeout
    if (autocompleteTimeoutRef.current) {
      clearTimeout(autocompleteTimeoutRef.current);
    }

    // Hide autocomplete immediately while typing
    setShowAutocomplete(false);

    // Debounce autocomplete requests - wait 1000ms after last keystroke
    if (newContent.length > 2) {
      autocompleteTimeoutRef.current = setTimeout(() => {
        fetchAutocompleteSuggestion(newContent);
      }, 1000);
    } else {
      setAutocompleteSuggestion('');
    }
  };

  const handleContentKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();

      if (autocompleteSuggestion && editedNote) {
        // Accept the suggestion - intelligently merge to avoid duplicates
        let newContent = editedNote.content;

        // Check for overlap between content end and suggestion start
        let overlapLength = 0;
        for (
          let i = 1;
          i <= Math.min(autocompleteSuggestion.length, editedNote.content.length);
          i++
        ) {
          const suggestionStart = autocompleteSuggestion.substring(0, i);
          const contentEnd = editedNote.content.substring(editedNote.content.length - i);
          if (suggestionStart.toLowerCase() === contentEnd.toLowerCase()) {
            overlapLength = i;
          }
        }

        // If there's overlap, replace it; otherwise just append
        if (overlapLength > 0) {
          newContent =
            editedNote.content.substring(0, editedNote.content.length - overlapLength) +
            autocompleteSuggestion;
        } else {
          newContent = editedNote.content + autocompleteSuggestion;
        }

        setEditedNote({ ...editedNote, content: newContent });
        setAutocompleteSuggestion('');
        setShowAutocomplete(false);
      } else {
        // Insert tab character if no suggestion
        const textarea = e.currentTarget;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        if (editedNote) {
          const newContent =
            editedNote.content.substring(0, start) + '\t' + editedNote.content.substring(end);
          setEditedNote({ ...editedNote, content: newContent });
          // Move cursor after the tab
          setTimeout(() => {
            textarea.selectionStart = textarea.selectionEnd = start + 1;
          }, 0);
        }
      }
    }
  };

  // Markdown components with wikilink handling
  const markdownComponents = useMemo(
    () => ({
      code({ node, inline, className, children, ...props }: any) {
        const match = /language-(\w+)/.exec(className || '');
        return !inline && match ? (
          <SyntaxHighlighter
            style={syntaxTheme}
            language={match[1]}
            PreTag="div"
            className="rounded-lg !bg-zinc-900 !my-4"
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        ) : (
          <code
            className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 text-sm font-mono"
            {...props}
          >
            {children}
          </code>
        );
      },
      a({ node, href, children, ...props }: any) {
        // Check for wikilink format: #wikilink:Title
        const isWikilink = href && href.startsWith('#wikilink:');
        const targetTitle = isWikilink
          ? decodeURIComponent(href.replace('#wikilink:', ''))
          : '';

        if (isWikilink) {
          return (
            <button
              type="button"
              onClick={() => handleWikilinkNavigation(targetTitle)}
              className="inline-flex items-center gap-1 rounded-md bg-blue-50 dark:bg-blue-900/30 px-2 py-1 text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40"
            >
              <Hash className="h-3.5 w-3.5" />
              <span>{children}</span>
            </button>
          );
        }

        const isExternal = href && /^https?:/i.test(href);
        return (
          <a
            href={href}
            className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 underline underline-offset-2"
            target={isExternal ? '_blank' : undefined}
            rel={isExternal ? 'noopener noreferrer' : undefined}
            {...props}
          >
            {children}
          </a>
        );
      },
      p({ children, ...props }: any) {
        return (
          <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed my-3" {...props}>
            {children}
          </p>
        );
      },
      h1({ children, ...props }: any) {
        return (
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-6 mb-4" {...props}>
            {children}
          </h1>
        );
      },
      h2({ children, ...props }: any) {
        return (
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mt-5 mb-3" {...props}>
            {children}
          </h2>
        );
      },
      h3({ children, ...props }: any) {
        return (
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-4 mb-2" {...props}>
            {children}
          </h3>
        );
      },
      ul({ children, ...props }: any) {
        return (
          <ul className="list-disc list-inside my-3 space-y-1 text-zinc-700 dark:text-zinc-300" {...props}>
            {children}
          </ul>
        );
      },
      ol({ children, ...props }: any) {
        return (
          <ol className="list-decimal list-inside my-3 space-y-1 text-zinc-700 dark:text-zinc-300" {...props}>
            {children}
          </ol>
        );
      },
      blockquote({ children, ...props }: any) {
        return (
          <blockquote
            className="border-l-4 border-zinc-300 dark:border-zinc-600 pl-4 my-4 italic text-zinc-600 dark:text-zinc-400"
            {...props}
          >
            {children}
          </blockquote>
        );
      },
    }),
    [handleWikilinkNavigation]
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-zinc-500">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading note...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !note) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
          <AlertCircle className="w-6 h-6" />
          <span>{error || 'Note not found'}</span>
        </div>
        <Button onClick={() => navigate('/notes')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Notes
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white dark:bg-zinc-900">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-zinc-200 dark:border-zinc-800 p-4 lg:p-6">
        <div className="flex items-start justify-between gap-4">
          {/* Back button and title */}
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <Link
              to="/notes"
              className="flex-shrink-0 p-2 rounded-lg text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>

            {isEditing ? (
              <input
                type="text"
                value={editedNote?.title || ''}
                onChange={(e) =>
                  setEditedNote((prev) => (prev ? { ...prev, title: e.target.value } : null))
                }
                className="flex-1 text-xl lg:text-2xl font-bold text-zinc-900 dark:text-zinc-100 bg-transparent border-none outline-none focus:ring-0"
                placeholder="Note title..."
              />
            ) : (
              <h1 className="flex-1 text-xl lg:text-2xl font-bold text-zinc-900 dark:text-zinc-100 truncate">
                {note.title}
              </h1>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {isEditing ? (
              <>
                <Button onClick={handleSaveNote} disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      Save
                    </>
                  )}
                </Button>
                <Button plain onClick={handleCancelEdit}>
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <button
                  onClick={handleToggleStar}
                  className={`p-2 rounded-lg transition-colors ${note.is_starred
                      ? 'text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-900/20'
                      : 'text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                    }`}
                >
                  <Star className={`w-5 h-5 ${note.is_starred ? 'fill-current' : ''}`} />
                </button>
                <Button plain color="zinc" onClick={handleExportPDF} disabled={isExporting}>
                  {isExporting ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  PDF
                </Button>
                <Button plain color="zinc" onClick={handleOpenPublishDialog}>
                  <Share2 className="w-4 h-4 mr-2" />
                  Share
                </Button>
                {publishStatus?.is_published && (
                  <Link
                    to={`/public/notes/${publishStatus.public_id}`}
                    target="_blank"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/30 hover:bg-emerald-100 dark:hover:bg-emerald-900/50"
                  >
                    <Globe className="w-4 h-4" />
                    Published
                  </Link>
                )}
                <Button plain color="blue" onClick={handleStartEdit}>
                  <Edit2 className="w-4 h-4 mr-2" />
                  Edit
                </Button>
                <button
                  onClick={handleDeleteNote}
                  className="p-2 rounded-lg text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-4 mt-4 ml-11 text-sm text-zinc-600 dark:text-zinc-400">
          {isEditing ? (
            <select
              value={editedNote?.category || 'personal'}
              onChange={(e) =>
                setEditedNote((prev) => (prev ? { ...prev, category: e.target.value } : null))
              }
              className="px-3 py-1 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
            >
              <option value="personal">Personal</option>
              <option value="work">Work</option>
              <option value="ideas">Ideas</option>
              <option value="reference">Reference</option>
            </select>
          ) : (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              <Tag className="w-3 h-3" />
              {note.category}
            </span>
          )}

          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {wasEdited(note)
              ? `Edited ${formatDate(note.updated_at)}`
              : `Created ${formatDate(note.created_at)}`}
          </span>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap items-center gap-2 mt-3 ml-11">
          {isEditing ? (
            <>
              {(editedNote?.tags || []).map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                >
                  {tag}
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="hover:text-red-600 dark:hover:text-red-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              <input
                type="text"
                placeholder="Add tag..."
                onKeyPress={(e: React.KeyboardEvent<HTMLInputElement>) => {
                  if (e.key === 'Enter') {
                    handleAddTag((e.target as HTMLInputElement).value);
                    (e.target as HTMLInputElement).value = '';
                  }
                }}
                className="px-3 py-1 rounded-full border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
              />
            </>
          ) : (
            (note.tags || []).map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
              >
                <Hash className="w-3 h-3" />
                {tag}
              </span>
            ))
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isEditing ? (
          <div className="relative h-full">
            {/* Autocomplete indicator */}
            {(isLoadingAutocomplete || showAutocomplete) && (
              <div className="absolute top-4 right-4 lg:top-6 lg:right-6 flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400 z-10">
                {isLoadingAutocomplete ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Thinking...</span>
                  </>
                ) : showAutocomplete ? (
                  <>
                    <Sparkles className="w-3 h-3 text-amber-500" />
                    <span className="text-amber-600 dark:text-amber-400">
                      Press Tab to accept
                    </span>
                  </>
                ) : null}
              </div>
            )}

            {/* Editor with ghost text */}
            <div className="relative h-full">
              <textarea
                ref={textareaRef}
                value={editedNote?.content || ''}
                onChange={handleContentChange}
                onKeyDown={handleContentKeyDown}
                className="w-full h-full min-h-[600px] p-4 lg:p-6 resize-none bg-transparent text-zinc-900 dark:text-zinc-100 font-mono text-sm leading-relaxed focus:outline-none"
                placeholder="Start writing..."
              />

              {/* Ghost text suggestion overlay */}
              {showAutocomplete && autocompleteSuggestion && (
                <div
                  className="absolute inset-0 pointer-events-none p-4 lg:p-6 font-mono text-sm leading-relaxed whitespace-pre-wrap overflow-hidden"
                  aria-hidden="true"
                >
                  <span className="invisible">{editedNote?.content || ''}</span>
                  <span className="text-zinc-400 dark:text-zinc-500">{autocompleteSuggestion}</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-4 lg:p-6">
            <div className="prose prose-zinc max-w-none dark:prose-invert">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {preprocessWikilinks(note.content || '')}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {/* Backlinks Panel */}
        {!isEditing && (
          <div className="border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
            <div className="px-4 lg:px-6 py-4">
              <div className="flex items-center gap-2 mb-3">
                <Link2 className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Backlinks</h3>
                {!isLoadingBacklinks && (
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">({backlinks.length})</span>
                )}
              </div>

              {isLoadingBacklinks && (
                <div className="flex items-center gap-2 text-sm text-zinc-500 py-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Loading backlinks...</span>
                </div>
              )}

              {!isLoadingBacklinks && backlinks.length === 0 && (
                <div className="text-sm text-zinc-500 dark:text-zinc-400 py-4">
                  No backlinks yet. Other notes can link to this note using{' '}
                  <code className="px-1.5 py-0.5 bg-zinc-200 dark:bg-zinc-800 rounded text-xs">
                    [[{note.title}]]
                  </code>{' '}
                  syntax.
                </div>
              )}

              {!isLoadingBacklinks && backlinks.length > 0 && (
                <div className="space-y-2">
                  {backlinks.map((backlink) => (
                    <Link
                      key={backlink.id}
                      to={`/notes/${backlink.id}`}
                      className="block w-full text-left p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:border-blue-500 dark:hover:border-blue-500 hover:shadow-sm transition-all group"
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <h4 className="font-medium text-sm text-zinc-900 dark:text-zinc-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                          {backlink.title}
                        </h4>
                        <ChevronRight className="w-4 h-4 text-zinc-400 group-hover:text-blue-500 flex-shrink-0 mt-0.5" />
                      </div>

                      {backlink.snippet && (
                        <p className="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-2">
                          {backlink.snippet}
                        </p>
                      )}

                      <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                        <span>{backlink.category}</span>
                        {backlink.created_at && (
                          <span>{formatDate(backlink.created_at)}</span>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Similar Notes Panel (Semantic) */}
        {!isEditing && (
          <div className="border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
            <div className="px-4 lg:px-6 py-4">
              <div className="flex items-center gap-2 mb-3">
                <Brain className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Similar Notes</h3>
                {!isLoadingSimilar && (
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">({similarNotes.length})</span>
                )}
                <span className="text-xs text-purple-600 dark:text-purple-400 ml-auto">semantic</span>
              </div>

              {isLoadingSimilar && (
                <div className="flex items-center gap-2 text-sm text-zinc-500 py-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Finding similar notes...</span>
                </div>
              )}

              {!isLoadingSimilar && similarNotes.length === 0 && (
                <div className="text-sm text-zinc-500 dark:text-zinc-400 py-4">
                  No semantically similar notes found. As you add more notes, connections will appear here based on content similarity.
                </div>
              )}

              {!isLoadingSimilar && similarNotes.length > 0 && (
                <div className="space-y-2">
                  {similarNotes.map((similar) => (
                    <Link
                      key={similar.id}
                      to={`/notes/${similar.id}`}
                      className="block w-full text-left p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:border-purple-500 dark:hover:border-purple-500 hover:shadow-sm transition-all group"
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <h4 className="font-medium text-sm text-zinc-900 dark:text-zinc-100 group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                          {similar.title}
                        </h4>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
                            {Math.round(similar.similarity * 100)}%
                          </span>
                          <ChevronRight className="w-4 h-4 text-zinc-400 group-hover:text-purple-500" />
                        </div>
                      </div>

                      {similar.content && (
                        <p className="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-2">
                          {similar.content.substring(0, 150)}...
                        </p>
                      )}

                      <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                        <span>{similar.category}</span>
                        {similar.tags && similar.tags.length > 0 && (
                          <span className="flex items-center gap-1">
                            <Hash className="w-3 h-3" />
                            {similar.tags.slice(0, 2).join(', ')}
                            {similar.tags.length > 2 && ` +${similar.tags.length - 2}`}
                          </span>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

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
                        navigator.clipboard.writeText(
                          `${window.location.origin}/public/notes/${publishStatus.public_id}`
                        );
                        alert('Link copied to clipboard!');
                      }}
                      className="p-2 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/40"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="mt-3 text-xs text-emerald-600 dark:text-emerald-300 space-y-1">
                    {publishStatus.public_id && <p>ID: {publishStatus.public_id}</p>}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => setShowPublishDialog(false)}
                    outline
                    className="flex-1"
                  >
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
                  const formData = new FormData(e.currentTarget);
                  const publishData = {
                    password: formData.get('password')?.toString() || undefined,
                    expires_at: formData.get('expires_at')?.toString() || undefined,
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
    </div>
  );
}
