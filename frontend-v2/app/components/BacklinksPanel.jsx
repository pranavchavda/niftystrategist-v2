import React, { useState, useEffect } from 'react';
import { Link2, ChevronRight, Loader2, AlertCircle } from 'lucide-react';

/**
 * Backlinks Panel - Shows notes that link to the current note via [[wikilinks]]
 *
 * Features:
 * - Fetches backlinks from API
 * - Shows context snippets
 * - Clickable to navigate to linking notes
 * - Real-time loading states
 */
export default function BacklinksPanel({ noteId, authToken, onNavigateToNote }) {
  const [backlinks, setBacklinks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!noteId || !authToken) {
      setBacklinks([]);
      return;
    }

    const fetchBacklinks = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/notes/${noteId}/backlinks`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          setBacklinks(data.backlinks || []);
        } else {
          throw new Error('Failed to fetch backlinks');
        }
      } catch (err) {
        console.error('Error fetching backlinks:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBacklinks();
  }, [noteId, authToken]);

  if (!noteId) {
    return null;
  }

  return (
    <div className="border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-3">
          <Link2 className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Backlinks
          </h3>
          {!isLoading && (
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              ({backlinks.length})
            </span>
          )}
        </div>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400 py-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Loading backlinks...</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!isLoading && !error && backlinks.length === 0 && (
          <div className="text-sm text-zinc-500 dark:text-zinc-400 py-4">
            No backlinks yet. Other notes can link to this note using{' '}
            <code className="px-1.5 py-0.5 bg-zinc-200 dark:bg-zinc-800 rounded text-xs">
              [[Note Title]]
            </code>{' '}
            syntax.
          </div>
        )}

        {!isLoading && !error && backlinks.length > 0 && (
          <div className="space-y-2">
            {backlinks.map((backlink) => (
              <button
                key={backlink.id}
                onClick={() => onNavigateToNote(backlink.id)}
                className="w-full text-left p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:border-blue-500 dark:hover:border-blue-500 hover:shadow-sm transition-all group"
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
                  <span className="inline-flex items-center gap-1">
                    📁 {backlink.category}
                  </span>
                  {backlink.created_at && (
                    <span>
                      {new Date(backlink.created_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      })}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
