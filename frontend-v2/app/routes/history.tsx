import { useNavigate, useOutletContext } from 'react-router';
import { useEffect, useState } from 'react';
import {
  ChatBubbleLeftRightIcon,
  MagnifyingGlassIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';

interface AuthContext {
  authToken: string;
}

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
  created_at: string;
  is_starred: boolean;
  summary: string | null;
}

function timeAgo(dateStr: string) {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function ChatHistory() {
  const navigate = useNavigate();
  const { authToken } = useOutletContext<AuthContext>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!authToken) return;
    fetch('/api/conversations/?limit=100', {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((res) => res.json())
      .then((data) => setConversations(data.conversations || []))
      .catch((err) => console.error('Failed to load conversations:', err))
      .finally(() => setLoading(false));
  }, [authToken]);

  const filtered = conversations.filter(
    (c) => !search || c.title?.toLowerCase().includes(search.toLowerCase())
  );

  const handleDelete = async (convId: string) => {
    if (!confirm('Delete this conversation?')) return;
    const res = await fetch(`/api/conversations/${convId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${authToken}` },
    });
    if (res.ok) {
      setConversations((prev) => prev.filter((c) => c.id !== convId));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Chat History</h1>
            <p className="text-sm text-zinc-500 mt-1">
              {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
          />
        </div>

        {/* List */}
        {loading ? (
          <div className="text-center py-20 text-zinc-400">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-zinc-400">
            {search ? 'No matching conversations.' : 'No conversations yet.'}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {filtered.map((conv) => (
              <div
                key={conv.id}
                className="group flex items-center gap-3 p-4 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 hover:shadow-sm transition-all cursor-pointer"
                onClick={() => navigate(`/chat/${conv.id}`)}
              >
                <ChatBubbleLeftRightIcon className="w-5 h-5 text-zinc-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {conv.title || 'Untitled'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {timeAgo(conv.updated_at)}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(conv.id);
                  }}
                  className="p-1.5 text-zinc-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                  title="Delete"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function meta() {
  return [{ title: 'Chat History - Nifty Strategist' }];
}
