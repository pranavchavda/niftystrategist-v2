import React, { useState, useEffect } from 'react';
import {
  StarIcon,
  TrashIcon,
  PlusIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  Bars3Icon
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';

function ConversationSidebar({
  currentThreadId,
  onSelectConversation,
  onNewConversation,
  authToken,
  refreshTrigger
}) {
  const [conversations, setConversations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showStarred, setShowStarred] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Load conversations on mount and when refreshTrigger changes
  useEffect(() => {
    loadConversations();
  }, [authToken, refreshTrigger]);

  const loadConversations = async () => {
    if (!authToken) return;

    try {
      const response = await fetch('/api/conversations/?limit=50', {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Loaded conversations:', data);
        setConversations(data.conversations || []);
      } else {
        console.error('Failed to load conversations:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (convId, e) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    try {
      const response = await fetch(`/api/conversations/${convId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        setConversations(prev => prev.filter(c => c.id !== convId));
        if (currentThreadId === convId) {
          onNewConversation();
        }
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleStar = async (convId, isStarred, e) => {
    e.stopPropagation();

    try {
      const endpoint = isStarred ? 'unstar' : 'star';
      const response = await fetch(`/api/conversations/${convId}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        setConversations(prev => prev.map(c =>
          c.id === convId ? { ...c, is_starred: !isStarred } : c
        ));
      }
    } catch (error) {
      console.error('Failed to star conversation:', error);
    }
  };

  // Filter conversations (with safety check)
  const filteredConversations = (conversations || []).filter(conv => {
    const matchesSearch = !searchTerm ||
      conv.title?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStarred = !showStarred || conv.is_starred;
    return matchesSearch && matchesStarred && !conv.is_archived;
  });

  // Group by date
  const groupConversations = (convs) => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);

    const groups = {
      today: [],
      yesterday: [],
      lastWeek: [],
      older: []
    };

    convs.forEach(conv => {
      const convDate = new Date(conv.updated_at);
      if (convDate.toDateString() === today.toDateString()) {
        groups.today.push(conv);
      } else if (convDate.toDateString() === yesterday.toDateString()) {
        groups.yesterday.push(conv);
      } else if (convDate > lastWeek) {
        groups.lastWeek.push(conv);
      } else {
        groups.older.push(conv);
      }
    });

    return groups;
  };

  const groups = groupConversations(filteredConversations);

  if (isCollapsed) {
    return (
      <div className="w-12 bg-gray-50 border-r flex flex-col items-center py-4">
        <button
          onClick={() => setIsCollapsed(false)}
          className="p-2 hover:bg-gray-200 rounded-lg"
          title="Expand sidebar"
        >
          <ChevronRightIcon className="w-5 h-5" />
        </button>
        <button
          onClick={onNewConversation}
          className="p-2 hover:bg-gray-200 rounded-lg mt-4"
          title="New conversation"
        >
          <PlusIcon className="w-5 h-5" />
        </button>
      </div>
    );
  }

  return (
    <div className="w-80 bg-gray-50 border-r flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b bg-white">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-800">Conversations</h2>
          <div className="flex space-x-1">
            <button
              onClick={() => setShowStarred(!showStarred)}
              className={`p-1.5 rounded ${showStarred ? 'bg-yellow-100 text-yellow-600' : 'text-gray-500 hover:bg-gray-100'}`}
              title="Show starred"
            >
              <StarIcon className="w-5 h-5" />
            </button>
            <button
              onClick={() => setIsCollapsed(true)}
              className="p-1.5 text-gray-500 hover:bg-gray-100 rounded"
              title="Collapse sidebar"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        {/* New Conversation Button */}
        <button
          onClick={onNewConversation}
          className="w-full mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center justify-center space-x-2"
        >
          <PlusIcon className="w-4 h-4" />
          <span>New Conversation</span>
        </button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-gray-500">
            Loading conversations...
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            {searchTerm ? 'No conversations found' : 'No conversations yet'}
          </div>
        ) : (
          <>
            {groups.today.length > 0 && (
              <ConversationGroup
                title="Today"
                conversations={groups.today}
                currentThreadId={currentThreadId}
                onSelect={onSelectConversation}
                onDelete={handleDelete}
                onStar={handleStar}
              />
            )}
            {groups.yesterday.length > 0 && (
              <ConversationGroup
                title="Yesterday"
                conversations={groups.yesterday}
                currentThreadId={currentThreadId}
                onSelect={onSelectConversation}
                onDelete={handleDelete}
                onStar={handleStar}
              />
            )}
            {groups.lastWeek.length > 0 && (
              <ConversationGroup
                title="Previous 7 Days"
                conversations={groups.lastWeek}
                currentThreadId={currentThreadId}
                onSelect={onSelectConversation}
                onDelete={handleDelete}
                onStar={handleStar}
              />
            )}
            {groups.older.length > 0 && (
              <ConversationGroup
                title="Older"
                conversations={groups.older}
                currentThreadId={currentThreadId}
                onSelect={onSelectConversation}
                onDelete={handleDelete}
                onStar={handleStar}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ConversationGroup({
  title,
  conversations,
  currentThreadId,
  onSelect,
  onDelete,
  onStar
}) {
  return (
    <div className="mb-4">
      <h3 className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase">
        {title}
      </h3>
      {conversations.map(conv => (
        <ConversationItem
          key={conv.id}
          conversation={conv}
          isActive={conv.id === currentThreadId}
          onSelect={onSelect}
          onDelete={onDelete}
          onStar={onStar}
        />
      ))}
    </div>
  );
}

function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
  onStar
}) {
  const [showActions, setShowActions] = useState(false);

  return (
    <div
      className={`px-4 py-3 cursor-pointer transition-colors ${
        isActive
          ? 'bg-blue-50 border-l-4 border-blue-600'
          : 'hover:bg-gray-100'
      }`}
      onClick={() => onSelect(conversation.id)}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-gray-900 truncate">
            {conversation.title}
          </h4>
          {conversation.summary && (
            <p className="text-xs text-gray-500 truncate mt-1">
              {conversation.summary}
            </p>
          )}
          <p className="text-xs text-gray-400 mt-1">
            {new Date(conversation.updated_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit'
            })}
          </p>
        </div>

        {(showActions || conversation.is_starred) && (
          <div className="flex items-center space-x-1 ml-2">
            <button
              onClick={(e) => onStar(conversation.id, conversation.is_starred, e)}
              className={`p-1 rounded ${
                conversation.is_starred
                  ? 'text-yellow-500'
                  : 'text-gray-400 hover:text-yellow-500'
              }`}
            >
              {conversation.is_starred ? <StarIconSolid className="w-4 h-4" /> : <StarIcon className="w-4 h-4" />}
            </button>
            {showActions && (
              <button
                onClick={(e) => onDelete(conversation.id, e)}
                className="p-1 text-gray-400 hover:text-red-600 rounded"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConversationSidebar;