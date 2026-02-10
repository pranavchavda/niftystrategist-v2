import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  SendIcon,
  SparklesIcon,
  XIcon,
  Loader2Icon,
  SquareIcon,
  WrenchIcon,
  CheckCircle2Icon,
  SearchIcon,
  BarChart3Icon,
  TerminalIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CopyIcon,
  CheckIcon,
  BrainCircuitIcon,
} from 'lucide-react';
import { Badge } from '../catalyst/badge';

// ─── Types ──────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isError?: boolean;
  toolCalls?: ToolCall[];
  reasoning?: string;
}

interface ToolCall {
  id: string;
  name: string;
  arguments: string;
  result?: string;
  isComplete: boolean;
  startTime: number;
}

interface CockpitChatProps {
  authToken?: string;
  contextPrefix?: string;
  onClearContext?: () => void;
  onClose?: () => void;
  // Legacy props (kept for backward compat, not used)
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isDrawer?: boolean;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const QUICK_PROMPTS = [
  'Analyze my positions',
  "What's moving?",
  "Review today's trades",
  'Market outlook',
];

// ─── Compact Markdown Components ────────────────────────────────────────────

const markdownComponents = {
  code({ node, inline, className, children, ...props }: any) {
    const [copied, setCopied] = useState(false);
    const match = /language-(\w+)/.exec(className || '');
    const codeContent = String(children).replace(/\n$/, '');

    if (!inline && match) {
      return (
        <div className="relative group/code my-2 not-prose">
          <div className="flex items-center justify-between px-2.5 py-1 bg-zinc-800 dark:bg-zinc-900 border-b border-zinc-700 rounded-t-md">
            <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wide">{match[1]}</span>
            <button
              onClick={() => { navigator.clipboard.writeText(codeContent); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
              className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              {copied ? <><CheckIcon className="w-3 h-3" /> Copied</> : <><CopyIcon className="w-3 h-3" /> Copy</>}
            </button>
          </div>
          <pre className="bg-zinc-900 dark:bg-zinc-950 rounded-b-md overflow-x-auto p-2.5 border border-zinc-700 border-t-0">
            <code className={`${className} text-[11px] leading-relaxed text-zinc-100`} {...props}>{children}</code>
          </pre>
        </div>
      );
    }
    return <code className="bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 px-1 py-0.5 rounded font-mono text-[0.85em]" {...props}>{children}</code>;
  },
  pre({ children }: any) { return <>{children}</>; },
  h1({ children, ...props }: any) { return <h1 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 mt-3 mb-1.5" {...props}>{children}</h1>; },
  h2({ children, ...props }: any) { return <h2 className="text-[13px] font-bold text-zinc-900 dark:text-zinc-100 mt-2.5 mb-1" {...props}>{children}</h2>; },
  h3({ children, ...props }: any) { return <h3 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mt-2 mb-1" {...props}>{children}</h3>; },
  p({ children, ...props }: any) { return <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed my-1.5" {...props}>{children}</p>; },
  ul({ children, ...props }: any) { return <ul className="list-disc list-outside ml-3.5 my-1.5 space-y-0.5" {...props}>{children}</ul>; },
  ol({ children, ...props }: any) { return <ol className="list-decimal list-outside ml-3.5 my-1.5 space-y-0.5" {...props}>{children}</ol>; },
  li({ children, ...props }: any) { return <li className="text-zinc-700 dark:text-zinc-300 leading-relaxed" {...props}>{children}</li>; },
  strong({ children, ...props }: any) { return <strong className="font-semibold text-zinc-900 dark:text-zinc-100" {...props}>{children}</strong>; },
  blockquote({ children, ...props }: any) { return <blockquote className="border-l-2 border-zinc-300 dark:border-zinc-700 pl-2.5 my-2 italic text-zinc-500 dark:text-zinc-400 text-[11px]" {...props}>{children}</blockquote>; },
  table({ children, ...props }: any) {
    return (
      <div className="my-2 overflow-x-auto">
        <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800 border border-zinc-200 dark:border-zinc-800 rounded text-[11px]" {...props}>{children}</table>
      </div>
    );
  },
  thead({ children, ...props }: any) { return <thead className="bg-zinc-50 dark:bg-zinc-900" {...props}>{children}</thead>; },
  th({ children, ...props }: any) { return <th className="px-2 py-1 text-left text-[10px] font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider" {...props}>{children}</th>; },
  td({ children, ...props }: any) { return <td className="px-2 py-1 text-zinc-700 dark:text-zinc-300 border-t border-zinc-200 dark:border-zinc-800" {...props}>{children}</td>; },
  a({ children, href, ...props }: any) { return <a href={href} className="text-amber-600 dark:text-amber-400 hover:underline" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>; },
  hr({ ...props }: any) { return <hr className="my-3 border-zinc-200 dark:border-zinc-800" {...props} />; },
};

// ─── Compact Tool Call Pill ─────────────────────────────────────────────────

function ToolCallPill({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = !toolCall.isComplete;

  const getIcon = () => {
    const cls = 'w-3 h-3';
    const name = toolCall.name.toLowerCase();
    if (name.includes('search') || name.includes('find')) return <SearchIcon className={cls} />;
    if (name.includes('analyz') || name.includes('report')) return <BarChart3Icon className={cls} />;
    if (name.includes('bash') || name.includes('execute')) return <TerminalIcon className={cls} />;
    return <WrenchIcon className={cls} />;
  };

  const formatName = (name: string) => name.replace(/^execute_/, '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  const getCompactArgs = () => {
    if (!toolCall.arguments) return '';
    try {
      const args = typeof toolCall.arguments === 'string' ? JSON.parse(toolCall.arguments) : toolCall.arguments;
      // For bash commands, show the command
      if (args.command || args.cmd) return args.command || args.cmd;
      const entries = Object.entries(args).slice(0, 2);
      return entries.map(([k, v]) => {
        const s = typeof v === 'string' ? v : JSON.stringify(v);
        return s.length > 40 ? s.slice(0, 40) + '...' : s;
      }).join(', ');
    } catch { return ''; }
  };

  return (
    <div className={`my-1.5 rounded-md border text-[11px] overflow-hidden transition-colors ${
      isRunning
        ? 'border-blue-200 dark:border-blue-900/50 bg-blue-50/50 dark:bg-blue-950/20'
        : 'border-green-200 dark:border-green-900/50 bg-green-50/30 dark:bg-green-950/10'
    }`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-2.5 py-1.5 flex items-center gap-2 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 transition-colors"
      >
        <span className={isRunning ? 'text-blue-500 animate-pulse' : 'text-green-500'}>{getIcon()}</span>
        <span className="font-medium text-zinc-700 dark:text-zinc-300 truncate">{formatName(toolCall.name)}</span>
        {!expanded && getCompactArgs() && (
          <span className="text-zinc-400 truncate flex-1 text-left">{getCompactArgs()}</span>
        )}
        <span className="flex items-center gap-1 flex-shrink-0">
          {isRunning ? (
            <Loader2Icon className="w-3 h-3 text-blue-500 animate-spin" />
          ) : (
            <CheckCircle2Icon className="w-3 h-3 text-green-500" />
          )}
          {expanded ? <ChevronDownIcon className="w-3 h-3 text-zinc-400" /> : <ChevronRightIcon className="w-3 h-3 text-zinc-400" />}
        </span>
      </button>
      {expanded && (
        <div className="px-2.5 pb-2 space-y-1.5 border-t border-zinc-200/50 dark:border-zinc-800/50">
          {toolCall.arguments && (
            <div className="mt-1.5">
              <div className="text-[10px] font-medium text-zinc-500 mb-0.5">Arguments</div>
              <pre className="bg-zinc-900 dark:bg-zinc-950 rounded p-1.5 overflow-x-auto text-[10px] font-mono text-zinc-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {(() => {
                  try { return JSON.stringify(typeof toolCall.arguments === 'string' ? JSON.parse(toolCall.arguments) : toolCall.arguments, null, 2); }
                  catch { return toolCall.arguments; }
                })()}
              </pre>
            </div>
          )}
          {toolCall.result && toolCall.isComplete && (
            <div>
              <div className="text-[10px] font-medium text-zinc-500 mb-0.5">Result</div>
              <pre className="bg-zinc-900 dark:bg-zinc-950 rounded p-1.5 overflow-x-auto text-[10px] font-mono text-zinc-300 max-h-40 overflow-y-auto whitespace-pre-wrap">
                {typeof toolCall.result === 'string' ? toolCall.result : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Compact Reasoning Block ────────────────────────────────────────────────

function ReasoningBlock({ reasoning, isStreaming = false }: { reasoning: string; isStreaming?: boolean }) {
  const [expanded, setExpanded] = useState(false);

  if (!reasoning && !isStreaming) return null;

  return (
    <div className="my-1.5 rounded-md border border-purple-200 dark:border-purple-900/50 bg-purple-50/30 dark:bg-purple-950/10 text-[11px] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-2.5 py-1.5 flex items-center gap-2 hover:bg-purple-100/30 dark:hover:bg-purple-900/20 transition-colors"
      >
        <BrainCircuitIcon className={`w-3 h-3 text-purple-500 ${isStreaming ? 'animate-pulse' : ''}`} />
        <span className="font-medium text-purple-700 dark:text-purple-300">
          {isStreaming ? 'Reasoning...' : 'Reasoning'}
        </span>
        <span className="flex-1" />
        {expanded ? <ChevronDownIcon className="w-3 h-3 text-purple-400" /> : <ChevronRightIcon className="w-3 h-3 text-purple-400" />}
      </button>
      {expanded && (
        <div className="px-2.5 pb-2 border-t border-purple-200/50 dark:border-purple-800/50">
          <pre className="mt-1.5 bg-purple-50 dark:bg-purple-950/30 rounded p-1.5 overflow-x-auto text-[10px] font-mono text-purple-800 dark:text-purple-300 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
            {reasoning}
            {isStreaming && <span className="inline-block w-0.5 h-3 bg-purple-500 ml-0.5 animate-pulse" />}
          </pre>
        </div>
      )}
    </div>
  );
}

// ─── Message Bubble ─────────────────────────────────────────────────────────

function MessageBubble({ message, isStreaming = false, streamingReasoning }: {
  message: ChatMessage;
  isStreaming?: boolean;
  streamingReasoning?: string;
}) {
  const isUser = message.role === 'user';
  const msgToolCalls = message.toolCalls || [];
  const reasoning = isStreaming ? streamingReasoning : message.reasoning;

  return (
    <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5 ${
        isUser
          ? 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300'
          : 'bg-gradient-to-br from-amber-400 to-amber-600 text-white'
      }`}>
        {isUser ? 'P' : 'N'}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        {/* Reasoning block (above message content) */}
        {!isUser && reasoning && (
          <div className="text-left mb-1">
            <ReasoningBlock reasoning={reasoning} isStreaming={isStreaming && !message.content} />
          </div>
        )}
        <div className={`inline-block text-left max-w-full rounded-xl px-3 py-2 text-xs leading-relaxed ${
          isUser
            ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200'
            : message.isError
              ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200/50 dark:border-red-800/50'
              : 'bg-white/60 dark:bg-zinc-800/60 text-zinc-700 dark:text-zinc-300 border border-zinc-200/30 dark:border-zinc-700/30'
        }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="cockpit-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-flex items-center ml-0.5 align-middle">
                  <span className="w-0.5 h-3.5 bg-amber-500 animate-pulse rounded-sm" />
                </span>
              )}
            </div>
          )}
        </div>
        {/* Tool calls below message */}
        {!isUser && msgToolCalls.length > 0 && (
          <div className="mt-1 text-left">
            {msgToolCalls.map(tc => <ToolCallPill key={tc.id} toolCall={tc} />)}
          </div>
        )}
        {message.timestamp && (
          <div className={`text-[10px] text-zinc-400 mt-0.5 ${isUser ? 'text-right' : ''}`}>
            {message.timestamp}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Processing Indicator ───────────────────────────────────────────────────

function ProcessingIndicator({ status }: { status: string }) {
  const getMessage = () => {
    switch (status) {
      case 'thinking': return 'Thinking...';
      case 'executing_tool': return 'Running tool...';
      case 'searching': return 'Searching...';
      case 'analyzing': return 'Analyzing...';
      case 'writing': return 'Writing...';
      default: return 'Processing...';
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <div className="w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
        <Loader2Icon className="h-3 w-3 text-white animate-spin" />
      </div>
      <span className="text-[11px] text-zinc-500 dark:text-zinc-400">{getMessage()}</span>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function CockpitChat({ authToken, contextPrefix, onClearContext, onClose }: CockpitChatProps) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCall[]>([]);
  const [streamingReasoning, setStreamingReasoning] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const threadInitRef = useRef(false);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent, activeToolCalls, streamingReasoning]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    requestAnimationFrame(() => {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(Math.max(ta.scrollHeight, 36), 120)}px`;
    });
  }, [input]);

  // Prepend context to input when set
  useEffect(() => {
    if (contextPrefix) {
      setInput(contextPrefix);
      // Focus textarea when context is loaded
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [contextPrefix]);

  // Initialize cockpit thread on mount — uses dedicated backend endpoint
  // that creates/finds the daily thread with proper [Cockpit] title
  useEffect(() => {
    if (!authToken || threadInitRef.current) return;
    threadInitRef.current = true;

    (async () => {
      try {
        const res = await fetch('/api/cockpit/daily-thread', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        });
        if (!res.ok) {
          console.warn('[CockpitChat] daily-thread endpoint failed:', res.status);
          setThreadId(`cockpit_fallback_${Date.now()}`);
          return;
        }

        const data = await res.json();
        setThreadId(data.threadId);

        if (data.compacted) {
          console.info('[CockpitChat] Thread was auto-compacted');
        }

        // Load messages from response
        if (data.messages?.length) {
          const loaded: ChatMessage[] = data.messages
            .filter((m: any) => m.role === 'user' || m.role === 'assistant')
            .map((m: any) => ({
              id: m.id || `msg_${Date.now()}_${Math.random()}`,
              role: m.role as 'user' | 'assistant',
              content: m.content,
              timestamp: m.timestamp
                ? new Date(m.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
                : '',
            }));
          setMessages(loaded);
        }
      } catch (err) {
        console.warn('[CockpitChat] Thread init error:', err);
        setThreadId(`cockpit_fallback_${Date.now()}`);
      }
    })();
  }, [authToken]);

  // Cancel streaming
  const handleCancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming || !authToken || !threadId) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsStreaming(true);
    setStreamingContent('');
    setProcessingStatus('thinking');
    setActiveToolCalls([]);
    setStreamingReasoning('');
    if (onClearContext) onClearContext();

    const allMessages = [...messages, userMsg].map((msg, idx) => ({
      role: msg.role,
      id: msg.id || `${msg.role}_${idx}`,
      content: msg.content,
    }));

    const requestData = {
      threadId,
      runId: `cockpit_run_${Date.now()}`,
      messages: allMessages,
      state: {},
      tools: [],
      context: [],
      forwardedProps: {},
    };

    let currentContent = '';
    let localToolCalls: ToolCall[] = [];
    let accumulatedReasoning = '';

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const response = await fetch('/api/agent/ag-ui', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(requestData),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));

            switch (data.type) {
              case 'TEXT_MESSAGE_CONTENT':
                currentContent += data.delta;
                setStreamingContent(currentContent);
                setProcessingStatus('writing');
                break;

              case 'TEXT_MESSAGE_END':
                if (currentContent.trim()) {
                  const assistantMsg: ChatMessage = {
                    id: data.messageId || `assistant_${Date.now()}`,
                    role: 'assistant',
                    content: currentContent,
                    timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
                    toolCalls: localToolCalls.length > 0 ? [...localToolCalls] : undefined,
                    reasoning: accumulatedReasoning || undefined,
                  };
                  setMessages(prev => [...prev, assistantMsg]);
                  currentContent = '';
                  localToolCalls = [];
                  accumulatedReasoning = '';
                  setStreamingContent('');
                  setStreamingReasoning('');
                  setActiveToolCalls([]);
                }
                break;

              case 'TOOL_CALL_START': {
                const toolCallId = data.toolCallId || `tool_${Date.now()}`;
                const tc: ToolCall = {
                  id: toolCallId,
                  name: data.toolCallName || 'unknown',
                  arguments: data.toolCallArguments || '',
                  isComplete: false,
                  startTime: Date.now(),
                };
                localToolCalls.push(tc);
                setActiveToolCalls([...localToolCalls]);

                const name = (data.toolCallName || '').toLowerCase();
                if (name.includes('search') || name.includes('find')) setProcessingStatus('searching');
                else if (name.includes('analyz')) setProcessingStatus('analyzing');
                else setProcessingStatus('executing_tool');
                break;
              }

              case 'TOOL_CALL_ARGS': {
                const idx = localToolCalls.findIndex(tc => tc.id === data.toolCallId);
                if (idx >= 0) {
                  localToolCalls[idx] = { ...localToolCalls[idx], arguments: (localToolCalls[idx].arguments || '') + data.delta };
                  setActiveToolCalls([...localToolCalls]);
                }
                break;
              }

              case 'TOOL_CALL_RESULT': {
                const idx = localToolCalls.findIndex(tc => tc.id === data.toolCallId);
                if (idx >= 0) {
                  localToolCalls[idx] = { ...localToolCalls[idx], result: data.content };
                  setActiveToolCalls([...localToolCalls]);
                }
                break;
              }

              case 'TOOL_CALL_END': {
                const idx = localToolCalls.findIndex(tc => tc.id === data.toolCallId);
                if (idx >= 0) {
                  localToolCalls[idx] = { ...localToolCalls[idx], isComplete: true };
                  setActiveToolCalls([...localToolCalls]);
                }
                setProcessingStatus('thinking');
                break;
              }

              case 'REASONING_START':
                setProcessingStatus('thinking');
                break;

              case 'REASONING_CONTENT':
                accumulatedReasoning += data.delta || '';
                setStreamingReasoning(accumulatedReasoning);
                break;

              case 'REASONING_END':
                // Reasoning complete, keep accumulated for attachment to message
                break;

              case 'ERROR':
                setMessages(prev => [
                  ...prev,
                  {
                    id: `error_${Date.now()}`,
                    role: 'assistant',
                    content: `**Error**: ${data.error || 'An unexpected error occurred'}`,
                    timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
                    isError: true,
                  },
                ]);
                setStreamingContent('');
                setIsStreaming(false);
                setProcessingStatus(null);
                setActiveToolCalls([]);
                break;

              case 'RUN_FINISHED':
                // If there's remaining streaming content, add it as final message
                if (currentContent.trim()) {
                  const finalMsg: ChatMessage = {
                    id: `assistant_${Date.now()}`,
                    role: 'assistant',
                    content: currentContent,
                    timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
                    toolCalls: localToolCalls.length > 0 ? [...localToolCalls] : undefined,
                    reasoning: accumulatedReasoning || undefined,
                  };
                  setMessages(prev => [...prev, finalMsg]);
                  currentContent = '';
                  accumulatedReasoning = '';
                }
                setStreamingContent('');
                setStreamingReasoning('');
                setIsStreaming(false);
                setProcessingStatus(null);
                setActiveToolCalls([]);
                localToolCalls = [];
                break;

              case 'THINKING':
                setProcessingStatus('thinking');
                break;
            }
          } catch {
            // Skip unparseable lines
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        // Add interrupted indicator
        if (currentContent.trim()) {
          setMessages(prev => [
            ...prev,
            {
              id: `assistant_${Date.now()}`,
              role: 'assistant',
              content: currentContent + '\n\n*— response interrupted —*',
              timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
            },
          ]);
        }
      } else {
        console.error('[CockpitChat] Stream error:', err);
        setMessages(prev => [
          ...prev,
          {
            id: `error_${Date.now()}`,
            role: 'assistant',
            content: `Something went wrong: ${err.message}`,
            timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
            isError: true,
          },
        ]);
      }
    } finally {
      setIsStreaming(false);
      setStreamingContent('');
      setStreamingReasoning('');
      setProcessingStatus(null);
      setActiveToolCalls([]);
      abortRef.current = null;
    }
  }, [input, isStreaming, authToken, threadId, messages, onClearContext]);

  // Keyboard handler
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setInput('');
    }
  }, [handleSend]);

  const todayStr = new Date().toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
            <SparklesIcon className="h-3.5 w-3.5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">Cockpit Chat</h3>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-zinc-400">{todayStr}</span>
              <Badge color="amber" className="text-[9px]">Daily Thread</Badge>
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          title="Close chat"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>

      {/* Quick Prompts (only when no messages) */}
      {messages.length === 0 && !isStreaming && (
        <div className="px-3 pt-3 pb-1 flex-shrink-0">
          <div className="text-center py-4">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center mx-auto mb-2">
              <SparklesIcon className="h-5 w-5 text-white" />
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
              Ask about your trades, portfolio, or the market.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                onClick={() => { setInput(prompt); textareaRef.current?.focus(); }}
                className="px-2.5 py-1 text-[11px] font-medium rounded-full border border-zinc-200/60 dark:border-zinc-700/60 text-zinc-600 dark:text-zinc-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 hover:text-amber-700 dark:hover:text-amber-300 hover:border-amber-200 dark:hover:border-amber-800 transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-3 space-y-3 min-h-0">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {/* Active tool calls (during streaming, before text) */}
        {isStreaming && activeToolCalls.length > 0 && !streamingContent && (
          <div className="flex gap-2">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center text-[10px] font-bold text-white mt-0.5">
              N
            </div>
            <div className="flex-1 min-w-0">
              {streamingReasoning && <ReasoningBlock reasoning={streamingReasoning} isStreaming />}
              {activeToolCalls.map(tc => <ToolCallPill key={tc.id} toolCall={tc} />)}
            </div>
          </div>
        )}
        {/* Streaming reasoning only (no tool calls, no text yet) */}
        {isStreaming && streamingReasoning && !streamingContent && activeToolCalls.length === 0 && (
          <div className="flex gap-2">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center text-[10px] font-bold text-white mt-0.5">
              N
            </div>
            <div className="flex-1 min-w-0">
              <ReasoningBlock reasoning={streamingReasoning} isStreaming />
            </div>
          </div>
        )}
        {/* Streaming content */}
        {isStreaming && streamingContent && (
          <div>
            <MessageBubble
              message={{
                id: 'streaming',
                role: 'assistant',
                content: streamingContent,
                timestamp: '',
                toolCalls: activeToolCalls.length > 0 ? activeToolCalls : undefined,
              }}
              isStreaming
              streamingReasoning={streamingReasoning}
            />
          </div>
        )}
        {/* Processing indicator (no content yet, no tool calls) */}
        {isStreaming && !streamingContent && activeToolCalls.length === 0 && processingStatus && (
          <ProcessingIndicator status={processingStatus} />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Context Banner */}
      {contextPrefix && (
        <div className="mx-3 mb-1 px-2.5 py-1.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200/50 dark:border-amber-800/50 rounded-lg flex items-center justify-between">
          <span className="text-[11px] text-amber-700 dark:text-amber-400 font-medium truncate">
            Context loaded from dashboard
          </span>
          <button
            onClick={onClearContext}
            className="text-[11px] text-amber-500 hover:text-amber-700 font-medium ml-2 flex-shrink-0"
          >
            Clear
          </button>
        </div>
      )}

      {/* Input Area */}
      <div className="px-3 py-2 border-t border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
        <div className="flex flex-col gap-1.5 bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-2 focus-within:ring-1 focus-within:ring-amber-500/50 focus-within:border-amber-500/50 transition-all">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your positions..."
            disabled={false}
            rows={1}
            className="w-full bg-transparent border-0 resize-none text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 leading-relaxed px-1 py-1 focus:outline-none"
            style={{ minHeight: '36px', maxHeight: '120px' }}
          />
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-400 pl-1">
              {isStreaming ? '' : 'Enter to send, Shift+Enter for newline'}
            </span>
            {isStreaming ? (
              <button
                onClick={handleCancel}
                className="p-1.5 rounded-lg bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-300 dark:hover:bg-zinc-600 transition-colors flex-shrink-0"
                title="Stop generating"
              >
                <SquareIcon className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="p-1.5 rounded-lg bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex-shrink-0"
                title="Send message"
              >
                <SendIcon className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
