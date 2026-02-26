import React, { useState, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CheckIcon, ClipboardIcon, ArrowPathRoundedSquareIcon, PencilIcon, TrashIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { Volume2, VolumeX, Pause, Play } from 'lucide-react';
import A2UIRenderer from './a2ui/A2UIRenderer';
import { Avatar } from './catalyst/avatar';
// Logo import removed - using initials avatar instead
// import ReasoningDisplay from './ReasoningDisplay';

function MessageBubble({
  message,
  isStreaming = false,
  onForkFromHere = null,
  onEdit = null,
  onDelete = null,
  a2uiSurfaces = [],
  threadId = null,
  onSendMessage = null,
}) {
  const isUser = message.role === 'user';
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);
  const textareaRef = useRef(null);

  // Handle text-to-speech playback
  const handlePlayAudio = async () => {
    // If audio exists and is paused, resume it
    if (audioRef.current && isPaused) {
      audioRef.current.play();
      setIsPaused(false);
      setIsPlayingAudio(true);
      return;
    }

    // If audio is already loaded, just play it
    if (audioRef.current && !isPlayingAudio) {
      audioRef.current.play();
      setIsPlayingAudio(true);
      return;
    }

    // Generate new audio
    setIsSynthesizing(true);

    try {
      const response = await fetch('/api/voice/synthesize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: message.content,
          voice: 'sage', // Default voice
          speed: 1.1,
        }),
      });

      if (!response.ok) {
        throw new Error('Speech synthesis failed');
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      audioUrlRef.current = audioUrl;
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onplay = () => {
        setIsPlayingAudio(true);
        setIsPaused(false);
        setIsSynthesizing(false);
      };

      audio.onpause = () => {
        setIsPlayingAudio(false);
        setIsPaused(true);
      };

      audio.onended = () => {
        setIsPlayingAudio(false);
        setIsPaused(false);
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
          audioUrlRef.current = null;
        }
        audioRef.current = null;
      };

      audio.onerror = () => {
        setIsPlayingAudio(false);
        setIsPaused(false);
        setIsSynthesizing(false);
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
          audioUrlRef.current = null;
        }
        audioRef.current = null;
        alert('Failed to play audio. Please try again.');
      };

      audio.play();
    } catch (error) {
      console.error('Error synthesizing speech:', error);
      setIsSynthesizing(false);
      alert('Failed to generate audio. Please try again.');
    }
  };

  const handlePauseAudio = () => {
    if (audioRef.current && isPlayingAudio) {
      audioRef.current.pause();
    }
  };

  const handleStopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      audioRef.current = null;
    }
    setIsPlayingAudio(false);
    setIsPaused(false);
  };

  // Handle edit mode
  const handleStartEdit = () => {
    setEditContent(message.content);
    setIsEditing(true);
    // Focus textarea after render
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(
          textareaRef.current.value.length,
          textareaRef.current.value.length
        );
      }
    }, 50);
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  const handleSaveEdit = async () => {
    if (!editContent.trim() || editContent.trim() === message.content) {
      setIsEditing(false);
      return;
    }

    if (onEdit) {
      await onEdit(message.id, editContent.trim());
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleCancelEdit();
    } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSaveEdit();
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (onDelete) {
      setIsDeleting(true);
      await onDelete(message.id);
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  // Custom components for ReactMarkdown
  const components = {
    code({ node, inline, className, children, ...props }) {
      const [copied, setCopied] = useState(false);
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';
      const codeContent = String(children).replace(/\n$/, '');

      const handleCopy = () => {
        navigator.clipboard.writeText(codeContent);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      };

      if (!inline && match) {
        return (
          <div className="relative group/code my-4 not-prose">
            {/* Language label and copy button */}
            <div className="flex items-center justify-between px-4 py-2 bg-zinc-800 dark:bg-zinc-900 border-b border-zinc-700 dark:border-zinc-800 rounded-t-lg">
              <span className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
                {language}
              </span>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-2 py-1 bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-xs font-medium rounded transition-colors"
              >
                {copied ? (
                  <>
                    <CheckIcon className="w-3.5 h-3.5" />
                    Copied!
                  </>
                ) : (
                  <>
                    <ClipboardIcon className="w-3.5 h-3.5" />
                    Copy
                  </>
                )}
              </button>
            </div>
            <pre className="bg-zinc-900 dark:bg-zinc-950 rounded-b-lg overflow-x-auto p-4 border border-zinc-700 dark:border-zinc-800 border-t-0">
              <code className={`${className} text-sm leading-relaxed text-zinc-100`} {...props}>
                {children}
              </code>
            </pre>
          </div>
        );
      }

      // Inline code
      return (
        <code
          className="bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 px-1.5 py-0.5 rounded font-mono text-[0.9em]"
          {...props}
        >
          {children}
        </code>
      );
    },
    pre({ node, children, ...props }) {
      // Don't wrap code blocks in additional pre tags
      return <>{children}</>;
    },
    h1({ node, children, ...props }) {
      return (
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-6 mb-4 pb-2 border-b border-zinc-200 dark:border-zinc-800" {...props}>
          {children}
        </h1>
      );
    },
    h2({ node, children, ...props }) {
      return (
        <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-5 mb-3" {...props}>
          {children}
        </h2>
      );
    },
    h3({ node, children, ...props }) {
      return (
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-4 mb-2" {...props}>
          {children}
        </h3>
      );
    },
    ul({ node, children, ...props }) {
      return (
        <ul className="list-disc list-outside ml-4 my-3 space-y-1.5" {...props}>
          {children}
        </ul>
      );
    },
    ol({ node, children, ...props }) {
      return (
        <ol className="list-decimal list-outside ml-4 my-3 space-y-1.5" {...props}>
          {children}
        </ol>
      );
    },
    li({ node, children, ...props }) {
      return (
        <li className="text-zinc-700 dark:text-zinc-300 leading-relaxed" {...props}>
          {children}
        </li>
      );
    },
    blockquote({ node, children, ...props }) {
      return (
        <blockquote className="border-l-4 border-zinc-300 dark:border-zinc-700 pl-4 my-4 italic text-zinc-600 dark:text-zinc-400" {...props}>
          {children}
        </blockquote>
      );
    },
    table({ node, children, ...props }) {
      return (
        <div className="my-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800 border border-zinc-200 dark:border-zinc-800 rounded-lg" {...props}>
            {children}
          </table>
        </div>
      );
    },
    thead({ node, children, ...props }) {
      return (
        <thead className="bg-zinc-50 dark:bg-zinc-900" {...props}>
          {children}
        </thead>
      );
    },
    th({ node, children, ...props }) {
      return (
        <th className="px-4 py-2 text-left text-xs font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider" {...props}>
          {children}
        </th>
      );
    },
    td({ node, children, ...props }) {
      return (
        <td className="px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 border-t border-zinc-200 dark:border-zinc-800" {...props}>
          {children}
        </td>
      );
    },
    a({ node, children, href, ...props }) {
      return (
        <a
          href={href}
          className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 underline underline-offset-2 decoration-blue-600/30 hover:decoration-blue-600/60 transition-colors"
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        >
          {children}
        </a>
      );
    },
    p({ node, children, ...props }) {
      return (
        <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed my-3" {...props}>
          {children}
        </p>
      );
    },
    strong({ node, children, ...props }) {
      return (
        <strong className="font-semibold text-zinc-900 dark:text-zinc-100" {...props}>
          {children}
        </strong>
      );
    },
    em({ node, children, ...props }) {
      return (
        <em className="italic" {...props}>
          {children}
        </em>
      );
    },
    hr({ node, ...props }) {
      return (
        <hr className="my-6 border-zinc-200 dark:border-zinc-800" {...props} />
      );
    },
  };

  return (
    <div className={`group py-8 px-4 animate-slide-in-bottom ${isUser
      ? 'bg-white dark:bg-zinc-950'
      : 'bg-zinc-50/50 dark:bg-zinc-900/50'
      }`}>
      <div className="max-w-3xl mx-auto">
        {/* Message with optional avatar */}
        <div className="flex items-start gap-3">
          {/* Avatar for assistant only */}
          {!isUser && (
            <div className="shrink-0">
              <Avatar
                className="size-10 bg-gradient-to-b from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-800"
                alt="Nifty Strategist"
                initials="NS"
                square
              />
            </div>
          )}

          <div className="flex-1 min-w-0">
            {/* Message Label */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                  {isUser ? 'You' : 'Nifty Strategist'}
                </div>
                {/* Show "edited" indicator */}
                {message.edited_at && (
                  <span className="text-xs text-zinc-400 dark:text-zinc-500 italic">
                    (edited)
                  </span>
                )}
                {/* Auto follow-up indicator for thread-awakening messages */}
                {message.role === 'assistant' && message.extra_metadata?.auto_followup && (
                  <span className="inline-flex items-center gap-1 text-xs text-indigo-500 dark:text-indigo-400 font-medium">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Auto follow-up
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {message.timestamp && !isStreaming && (
                  <div className="text-xs text-zinc-400 dark:text-zinc-500">
                    {new Date(message.timestamp).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </div>
                )}
                {/* Edit/Delete buttons for user messages */}
                {isUser && !isStreaming && !isEditing && onEdit && onDelete && (
                  <div className="inline-flex items-center gap-1">
                    <button
                      onClick={handleStartEdit}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
                      title="Edit message"
                    >
                      <PencilIcon className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Edit</span>
                    </button>
                    <button
                      onClick={() => setShowDeleteConfirm(true)}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                      title="Delete message"
                    >
                      <TrashIcon className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Delete</span>
                    </button>
                  </div>
                )}
                {/* Voice output controls for assistant messages */}
                {!isUser && !isStreaming && message.content && (
                  <div className="inline-flex items-center gap-1 border border-transparent rounded-md overflow-hidden">
                    {/* Play/Resume button */}
                    {(!isPlayingAudio || isPaused) && (
                      <button
                        onClick={handlePlayAudio}
                        disabled={isSynthesizing}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 border-r border-emerald-200 dark:border-emerald-800 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={isPaused ? "Resume audio" : isSynthesizing ? "Generating audio..." : "Play audio"}
                      >
                        {isSynthesizing ? (
                          <>
                            <Volume2 className="w-3.5 h-3.5 animate-pulse" />
                            <span className="hidden sm:inline">Loading...</span>
                          </>
                        ) : (
                          <>
                            <Play className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">{isPaused ? 'Resume' : 'Play'}</span>
                          </>
                        )}
                      </button>
                    )}

                    {/* Pause button (only when playing) */}
                    {isPlayingAudio && !isPaused && (
                      <button
                        onClick={handlePauseAudio}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 border-r border-amber-200 dark:border-amber-800"
                        title="Pause audio"
                      >
                        <Pause className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Pause</span>
                      </button>
                    )}

                    {/* Stop button (only when audio exists) */}
                    {(isPlayingAudio || isPaused) && (
                      <button
                        onClick={handleStopAudio}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                        title="Stop audio"
                      >
                        <VolumeX className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Stop</span>
                      </button>
                    )}
                  </div>
                )}
                {onForkFromHere && !isStreaming && (
                  <button
                    onClick={() => onForkFromHere(message.id)}
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md border border-transparent hover:border-blue-200 dark:hover:border-blue-800"
                    title="Fork conversation from this message"
                  >
                    <ArrowPathRoundedSquareIcon className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Fork from here</span>
                  </button>
                )}
              </div>
            </div>

            {/* Message Content */}
            <div className={`${message.isError
              ? 'text-red-600 dark:text-red-400'
              : ''
              }`}>
              {message.role === 'assistant' ? (
                <div className="markdown-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                    {message.content}
                  </ReactMarkdown>
                  {isStreaming && (
                    <span className="inline-flex items-center ml-1 align-middle">
                      <span className="w-1 h-4 bg-zinc-400 dark:bg-zinc-500 animate-pulse rounded-sm"></span>
                    </span>
                  )}
                  {message.isInterrupted && (
                    <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-700 dark:text-amber-300">
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      Response was interrupted - partial answer shown
                    </div>
                  )}
                  {/* A2UI Surfaces */}
                  {a2uiSurfaces.length > 0 && (
                    <div className="a2ui-surfaces mt-4">
                      {a2uiSurfaces.map((surface) => (
                        <A2UIRenderer
                          key={surface.surfaceId}
                          surface={surface}
                          threadId={threadId}
                          onInteraction={async (userAction) => {
                            // A2UI v0.8 userAction format:
                            // { name, surfaceId, sourceComponentId, timestamp, context }
                            console.log('[A2UI] userAction:', userAction);

                            if (!onSendMessage) return;

                            const actionName = userAction.name;
                            const context = userAction.context || {};

                            // For submit/search, send form data as a message
                            if (actionName === 'submit' || actionName === 'search') {
                              const query = context.query || context.value || context.search || JSON.stringify(context);
                              if (query) {
                                onSendMessage(`[User submitted form] ${query}`, threadId);
                              }
                              return;
                            }

                            // For all other actions (button clicks), send as a chat message
                            // so the agent sees it and can respond
                            const contextStr = Object.keys(context).length > 0
                              ? ` with: ${JSON.stringify(context)}`
                              : '';
                            onSendMessage(`[User clicked '${actionName}']${contextStr}`, threadId);
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ) : isEditing ? (
                /* Inline edit mode for user messages */
                <div className="space-y-3">
                  <textarea
                    ref={textareaRef}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="w-full min-h-[100px] p-3 text-zinc-900 dark:text-zinc-100 bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                    placeholder="Edit your message..."
                  />
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      Press <kbd className="px-1.5 py-0.5 bg-zinc-100 dark:bg-zinc-800 rounded text-xs">⌘/Ctrl + Enter</kbd> to save, <kbd className="px-1.5 py-0.5 bg-zinc-100 dark:bg-zinc-800 rounded text-xs">Esc</kbd> to cancel
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCancelEdit}
                        className="px-3 py-1.5 text-sm font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSaveEdit}
                        disabled={!editContent.trim() || editContent.trim() === message.content}
                        className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-zinc-900 dark:text-zinc-100 leading-relaxed">
                  {/* Check if message contains uploaded file reference */}
                  {(message.content.includes('[Uploaded image:') || message.content.includes('[Uploaded file:')) ? (
                    <div className="space-y-3">
                      {/* Extract message text and file info */}
                      {(() => {
                        const lines = message.content.split('\n');
                        const textLines = [];
                        let fileName = '';
                        let filePath = '';
                        let fileType = 'file';

                        for (let i = 0; i < lines.length; i++) {
                          const line = lines[i].trim();
                          if (line.startsWith('[Uploaded image:')) {
                            fileName = line.match(/\[Uploaded image: (.+)\]/)?.[1] || '';
                            fileType = 'image';
                          } else if (line.startsWith('[Uploaded file:')) {
                            fileName = line.match(/\[Uploaded file: (.+)\]/)?.[1] || '';
                            fileType = 'file';
                          } else if (line.startsWith('File path:')) {
                            filePath = line.replace('File path:', '').trim();
                          } else if (line.length > 0) {
                            textLines.push(line);
                          }
                        }

                        return (
                          <>
                            {/* Display user's text message */}
                            {textLines.length > 0 && (
                              <p className="whitespace-pre-wrap leading-relaxed">
                                {textLines.join('\n')}
                              </p>
                            )}

                            {/* Display file attachment badge */}
                            <div className="inline-flex items-center gap-2 px-3 py-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                              {fileType === 'image' ? (
                                <svg className="w-4 h-4 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                              ) : (
                                <svg className="w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                                </svg>
                              )}
                              <div className="flex flex-col">
                                <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                                  {fileName}
                                </span>
                                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                  {fileType === 'image' ? 'Image' : 'Document'} • Uploaded
                                </span>
                              </div>
                            </div>

                            {/* Note about file availability */}
                            {filePath && (
                              <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">
                                File available to agent at: <code className="font-mono bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">{filePath}</code>
                              </p>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  )}
                </div>
              )}

              {/* Show reasoning if message has it */}
              {/* {!isUser && message.reasoning && (
            <div className="mt-4">
              <ReasoningDisplay
                reasoning={message.reasoning}
                isStreaming={false}
              />
            </div>
          )} */}
            </div>
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl p-6 max-w-md mx-4 animate-slide-in-bottom">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-full">
                <TrashIcon className="w-6 h-6 text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                  Delete message?
                </h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
                  This will permanently delete this message <strong>and all responses after it</strong>. This action cannot be undone.
                </p>
                <div className="flex items-center gap-3 justify-end">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={isDeleting}
                    className="px-4 py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isDeleting ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Memoize to prevent re-renders when parent updates (e.g., during input typing)
export default React.memo(MessageBubble);