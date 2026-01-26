import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Lock, Calendar, Eye, AlertCircle, PenBoxIcon } from 'lucide-react';

interface PublicNoteData {
  title: string;
  content: string;
  content_html: string;
  category: string;
  tags: string[];
  created_at: string;
  view_count: number;
  has_password: boolean;
}

interface ErrorState {
  type: 'not_found' | 'expired' | 'unauthorized' | 'server_error';
  message: string;
}

export default function PublicNote() {
  const { publicId } = useParams<{ publicId: string }>();
  const [note, setNote] = useState<PublicNoteData | null>(null);
  const [error, setError] = useState<ErrorState | null>(null);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState('');
  const [showPasswordInput, setShowPasswordInput] = useState(false);
  const [passwordError, setPasswordError] = useState('');

  const logo = new URL('../assets/eblogo-notext.webp', import.meta.url).href;


  const markdownComponents = useMemo(() => ({
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-([\w-]+)/.exec(className || '');
      const language = match ? match[1] : '';

      if (inline) {
        return (
          <code className="bg-zinc-100 dark:bg-zinc-800 rounded px-1.5 py-0.5 text-sm font-mono text-pink-600 dark:text-pink-400">
            {children}
          </code>
        );
      }

      return (
        <div className="my-4 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-black">
          {language && (
            <div className="flex items-center justify-between px-4 py-2 bg-zinc-100 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
              <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wide">
                {language}
              </span>
            </div>
          )}
          <pre className="overflow-x-auto p-4 bg-transparent">
            <code className={`${className || ''} font-mono text-sm leading-relaxed text-zinc-900 dark:text-zinc-100`} {...props}>
              {children}
            </code>
          </pre>
        </div>
      );
    },
    h1({ node, children, ...props }: any) {
      return (
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-6 mb-4 pb-2 border-b border-zinc-200 dark:border-zinc-800" {...props}>
          {children}
        </h1>
      );
    },
    h2({ node, children, ...props }: any) {
      return (
        <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-5 mb-3" {...props}>
          {children}
        </h2>
      );
    },
    h3({ node, children, ...props }: any) {
      return (
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-4 mb-2" {...props}>
          {children}
        </h3>
      );
    },
    ul({ node, children, ...props }: any) {
      return (
        <ul className="list-disc list-outside ml-6 my-3 space-y-1.5" {...props}>
          {children}
        </ul>
      );
    },
    ol({ node, children, ...props }: any) {
      return (
        <ol className="list-decimal list-outside ml-6 my-3 space-y-1.5" {...props}>
          {children}
        </ol>
      );
    },
    li({ node, children, ...props }: any) {
      return (
        <li className="text-zinc-700 dark:text-zinc-300 leading-relaxed" {...props}>
          {children}
        </li>
      );
    },
    blockquote({ node, children, ...props }: any) {
      return (
        <blockquote className="border-l-4 border-zinc-300 dark:border-zinc-700 pl-4 my-4 italic text-zinc-600 dark:text-zinc-400" {...props}>
          {children}
        </blockquote>
      );
    },
    table({ node, children, ...props }: any) {
      return (
        <div className="my-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg" {...props}>
            {children}
          </table>
        </div>
      );
    },
    thead({ node, children, ...props }: any) {
      return (
        <thead className="bg-zinc-50 dark:bg-zinc-900/50" {...props}>
          {children}
        </thead>
      );
    },
    th({ node, children, ...props }: any) {
      return (
        <th className="px-4 py-2 text-left text-xs font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider" {...props}>
          {children}
        </th>
      );
    },
    td({ node, children, ...props }: any) {
      return (
        <td className="px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 border-t border-zinc-200 dark:border-zinc-800" {...props}>
          {children}
        </td>
      );
    },
    a({ node, href, children, ...props }: any) {
      return (
        <a
          href={href}
          className="text-blue-600 dark:text-blue-400 hover:underline"
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        >
          {children}
        </a>
      );
    },
  }), []);

  const fetchNote = async (passwordAttempt?: string) => {
    setLoading(true);
    setPasswordError('');

    try {
      const url = passwordAttempt
        ? `/api/public/notes/${publicId}?password=${encodeURIComponent(passwordAttempt)}`
        : `/api/public/notes/${publicId}`;

      const response = await fetch(url);

      if (response.ok) {
        const data = await response.json();
        setNote(data);
        setError(null);
        setShowPasswordInput(false);
      } else if (response.status === 401) {
        const errorData = await response.json();
        if (errorData.detail === 'This note is password protected') {
          setShowPasswordInput(true);
          setError(null);
        } else {
          setPasswordError('Incorrect password. Please try again.');
        }
      } else if (response.status === 404) {
        setError({
          type: 'not_found',
          message: 'This note does not exist or is no longer public.'
        });
      } else if (response.status === 410) {
        setError({
          type: 'expired',
          message: 'This note has expired and is no longer available.'
        });
      } else {
        setError({
          type: 'server_error',
          message: 'An error occurred while loading this note. Please try again later.'
        });
      }
    } catch (err) {
      console.error('Error fetching public note:', err);
      setError({
        type: 'server_error',
        message: 'Failed to connect to the server. Please check your internet connection.'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (publicId) {
      fetchNote();
    }
  }, [publicId]);

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password.trim()) {
      fetchNote(password);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-950 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-zinc-600 dark:text-zinc-400">Loading note...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    const errorIcons = {
      not_found: AlertCircle,
      expired: Calendar,
      unauthorized: Lock,
      server_error: AlertCircle,
    };
    const ErrorIcon = errorIcons[error.type];

    return (
      <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-800 rounded-xl shadow-lg p-8 text-center">
          <ErrorIcon className="w-16 h-16 text-red-500 dark:text-red-400 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mb-2">
            {error.type === 'not_found' && 'Note Not Found'}
            {error.type === 'expired' && 'Note Expired'}
            {error.type === 'unauthorized' && 'Access Denied'}
            {error.type === 'server_error' && 'Server Error'}
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">{error.message}</p>
        </div>
      </div>
    );
  }

  // Password input state
  if (showPasswordInput) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-800 rounded-xl shadow-lg p-8">
          <div className="text-center mb-6">
            <Lock className="w-12 h-12 text-blue-600 dark:text-blue-400 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mb-2">
              Password Protected
            </h1>
            <p className="text-zinc-600 dark:text-zinc-400">
              This note is password protected. Enter the password to view it.
            </p>
          </div>

          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full px-4 py-3 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white placeholder-zinc-400 dark:placeholder-zinc-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
              {passwordError && (
                <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                  {passwordError}
                </p>
              )}
            </div>

            <button
              type="submit"
              className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
            >
              View Note
            </button>
          </form>
        </div>
      </div>
    );
  }

  // Note display state
  if (!note) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-950">
      {/* Header */}
      <header className="border-b border-zinc-200 dark:border-zinc-700 sticky top-0 z-10 backdrop-blur-sm bg-white/80 dark:bg-zinc-800/80">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Logo */}
              <img src={logo} alt="EspressoBot" className="w-10" />
              <PenBoxIcon className="w-6 h-6 text-zinc-600 dark:text-zinc-400" />
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-white">
                {note.title}
              </h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-zinc-600 dark:text-zinc-400">
              {note.has_password && (
                <div className="flex items-center gap-1">
                  <Lock className="w-4 h-4" />
                  <span>Protected</span>
                </div>
              )}
              <div className="flex items-center gap-1">
                <Eye className="w-4 h-4" />
                <span>{note.view_count} {note.view_count === 1 ? 'view' : 'views'}</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Note Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <article className="bg-white dark:bg-zinc-800 rounded-xl shadow-lg overflow-hidden">
          {/* Note Header */}
          <div className="border-b border-zinc-200 dark:border-zinc-700 px-6 sm:px-8 py-6">
            <h1 className="text-3xl sm:text-4xl font-bold text-zinc-900 dark:text-white mb-4">
              {note.title}
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-sm text-zinc-600 dark:text-zinc-400">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                <span>{new Date(note.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })}</span>
              </div>

              {note.category && (
                <span className="px-2.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium">
                  {note.category}
                </span>
              )}

              {note.tags && note.tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {note.tags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 text-xs"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Note Body */}
          <div className="px-6 sm:px-8 py-8">
            <div className="prose prose-zinc dark:prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {note.content}
              </ReactMarkdown>
            </div>
          </div>
        </article>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Powered by{' '}
            <a
              href="/"
              className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
            >
              EspressoBot
            </a>
          </p>
        </div>
      </main>
    </div>
  );
}
