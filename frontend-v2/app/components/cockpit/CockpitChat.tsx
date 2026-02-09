import { useState, useRef, useEffect } from 'react';
import {
  SendIcon,
  SparklesIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  MessageSquareIcon,
  Loader2Icon,
} from 'lucide-react';
import { Badge } from '../catalyst/badge';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface CockpitChatProps {
  messages: ChatMessage[];
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  contextPrefix?: string;
  onClearContext?: () => void;
  isDrawer?: boolean;
  onClose?: () => void;
}

const QUICK_PROMPTS = [
  'Analyze my positions',
  "What's moving?",
  "Review today's trades",
  'Market outlook',
];

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
        isUser
          ? 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300'
          : 'bg-gradient-to-br from-amber-400 to-amber-600 text-white'
      }`}>
        {isUser ? 'P' : 'N'}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block text-left max-w-full rounded-xl px-3 py-2 text-xs leading-relaxed ${
          isUser
            ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200'
            : 'bg-white/60 dark:bg-zinc-800/60 text-zinc-700 dark:text-zinc-300 border border-zinc-200/30 dark:border-zinc-700/30'
        }`}>
          {/* Simple markdown-like rendering */}
          {message.content.split('\n').map((line, i) => {
            if (line.startsWith('## ')) return <h3 key={i} className="text-xs font-bold text-zinc-800 dark:text-zinc-200 mt-2 mb-1">{line.slice(3)}</h3>;
            if (line.startsWith('### ')) return <h4 key={i} className="text-[11px] font-bold text-zinc-700 dark:text-zinc-300 mt-1.5 mb-0.5">{line.slice(4)}</h4>;
            if (line.startsWith('- **')) {
              const match = line.match(/- \*\*(.+?)\*\*(.+)/);
              if (match) return <div key={i} className="flex gap-1 mt-0.5"><span className="font-bold text-zinc-800 dark:text-zinc-200">{match[1]}</span><span>{match[2]}</span></div>;
            }
            if (line.startsWith('- ')) return <div key={i} className="flex gap-1 mt-0.5 ml-2"><span className="text-amber-500">-</span><span>{line.slice(2)}</span></div>;
            if (line.match(/^\d+\./)) return <div key={i} className="mt-0.5 ml-2">{line}</div>;
            if (line.startsWith('**') && line.endsWith('**')) return <div key={i} className="font-bold text-zinc-800 dark:text-zinc-200 mt-1">{line.slice(2, -2)}</div>;
            if (line === '') return <div key={i} className="h-1.5" />;
            // Bold within line
            const boldProcessed = line.split(/\*\*(.+?)\*\*/g).map((part, j) =>
              j % 2 === 1 ? <strong key={j} className="font-bold text-zinc-800 dark:text-zinc-200">{part}</strong> : part
            );
            return <div key={i} className="mt-0.5">{boldProcessed}</div>;
          })}
        </div>
        <div className={`text-[10px] text-zinc-400 mt-0.5 ${isUser ? 'text-right' : ''}`}>
          {message.timestamp}
        </div>
      </div>
    </div>
  );
}

export default function CockpitChat({ messages, isCollapsed, onToggleCollapse, contextPrefix, onClearContext, isDrawer, onClose }: CockpitChatProps) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Prepend context to input when set
  useEffect(() => {
    if (contextPrefix) {
      setInput(contextPrefix);
    }
  }, [contextPrefix]);

  const handleSend = () => {
    if (!input.trim()) return;
    // In Phase 1, just simulate
    setIsStreaming(true);
    setTimeout(() => setIsStreaming(false), 1500);
    setInput('');
    if (onClearContext) onClearContext();
  };

  // Collapsed State (skip when used as drawer)
  if (isCollapsed && !isDrawer) {
    return (
      <div className="flex flex-col items-center py-3 gap-2">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors"
          title="Open Cockpit Chat"
        >
          <MessageSquareIcon className="h-4 w-4" />
        </button>
        <span className="text-[9px] font-bold text-zinc-400 tracking-wider" style={{ writingMode: 'vertical-rl' }}>
          COCKPIT CHAT
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
            <SparklesIcon className="h-3 w-3 text-white" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-zinc-800 dark:text-zinc-200">Cockpit Chat</h3>
            <span className="text-[9px] text-zinc-400">Trading Day - Feb 7, 2026</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Badge color="amber" className="text-[9px]">Daily Thread</Badge>
          <button
            onClick={isDrawer ? onClose : onToggleCollapse}
            className="p-1 rounded text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <ChevronRightIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Quick Prompts */}
      <div className="flex flex-wrap gap-1 px-3 py-2 border-b border-zinc-200/30 dark:border-zinc-800/30 flex-shrink-0">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => setInput(prompt)}
            className="px-2 py-0.5 text-[10px] font-medium rounded-full border border-zinc-200/60 dark:border-zinc-700/60 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-3 space-y-3 min-h-0">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && (
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <Loader2Icon className="h-3 w-3 text-white animate-spin" />
            </div>
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-typing" />
              <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-typing animation-delay-200" />
              <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-typing animation-delay-400" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Context Banner */}
      {contextPrefix && (
        <div className="mx-3 mb-1 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 border border-amber-200/50 dark:border-amber-800/50 rounded-md flex items-center justify-between">
          <span className="text-[10px] text-amber-700 dark:text-amber-400 font-medium truncate">
            Context loaded from dashboard
          </span>
          <button
            onClick={onClearContext}
            className="text-[10px] text-amber-500 hover:text-amber-700 font-medium ml-2"
          >
            Clear
          </button>
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-2 border-t border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask about your positions..."
            rows={1}
            className="flex-1 text-xs bg-zinc-100/80 dark:bg-zinc-800/80 border border-zinc-200/50 dark:border-zinc-700/50 rounded-lg px-3 py-2 text-zinc-700 dark:text-zinc-300 placeholder:text-zinc-400 focus:outline-none focus:ring-1 focus:ring-amber-500/50 resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="p-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            <SendIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
