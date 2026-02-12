import React, { useState, useRef, useEffect, useCallback, forwardRef } from 'react';
import { ImagePlus, Paperclip, Send, X, Square, Mic, MicOff } from 'lucide-react';
import { Button } from './catalyst/button';

/**
 * Enhanced chat input component with auto-resize, drag & drop, paste, and file upload
 *
 * Features:
 * - Auto-resizing textarea (1-6 rows)
 * - Drag & drop file zone with visual feedback
 * - Paste images directly from clipboard (Ctrl/Cmd+V)
 * - Image and document upload buttons
 * - Keyboard shortcuts (Enter to send, Shift+Enter for new line, Esc to clear)
 * - Glass morphism styling with smooth transitions
 * - File preview in attachment area
 * - Markdown formatting hints on hover (optional)
 * - Exposes textarea ref for autocomplete integration
 */
const ChatInput = forwardRef(({
  value,
  onChange,
  onSubmit,
  onFileAttach,
  onCancel,
  disabled = false,
  isLoading = false,
  placeholder = "Message Nifty Strategist...",
  attachedFile = null,
  attachedImage = null,
  onRemoveAttachment,
  showMarkdownHints = false,
  authToken = null,
  recentMessages = [],
  enableAutocomplete = false  // Disabled by default for performance
}, ref) => {
  const [isDragging, setIsDragging] = useState(false);
  const [showHints, setShowHints] = useState(showMarkdownHints);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [autocompleteSuggestion, setAutocompleteSuggestion] = useState('');
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [isLoadingAutocomplete, setIsLoadingAutocomplete] = useState(false);
  const internalRef = useRef(null);
  const imageInputRef = useRef(null);
  const fileInputRef = useRef(null);
  const dragCounterRef = useRef(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const autocompleteTimeoutRef = useRef(null);
  // Store recentMessages in a ref to avoid recreating callbacks when messages change
  const recentMessagesRef = useRef(recentMessages);
  recentMessagesRef.current = recentMessages;

  // Combine internal ref with forwarded ref
  const textareaRef = ref || internalRef;

  // Auto-resize textarea - use requestAnimationFrame to batch DOM reads/writes
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Use requestAnimationFrame to batch DOM operations and avoid layout thrashing
    requestAnimationFrame(() => {
      // Reset height to auto to get proper scrollHeight
      textarea.style.height = 'auto';
      // Calculate new height (min 40px, max 200px to match CSS max-h-[200px])
      const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 200);
      textarea.style.height = `${newHeight}px`;
    });
  }, [value]);

  // Fetch autocomplete suggestion - uses ref for recentMessages to avoid callback recreation
  const fetchAutocompleteSuggestion = useCallback(async (text) => {
    if (!text || text.length < 5 || !authToken) {
      setAutocompleteSuggestion('');
      setShowAutocomplete(false);
      return;
    }

    try {
      setIsLoadingAutocomplete(true);

      // Build context from recent messages (read from ref to avoid dependency)
      let context = '';
      const messages = recentMessagesRef.current;
      if (messages && messages.length > 0) {
        // Only use last 10 messages to limit context size
        const recentSlice = messages.slice(-10);
        context = recentSlice
          .map(msg => {
            const role = msg.role === 'user' ? 'User' : 'Assistant';
            return `${role}: ${msg.content}`;
          })
          .join('\n\n');
      }

      const response = await fetch('/api/notes/autocomplete', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          current_text: text,
          note_title: '',
          note_category: 'personal',
          max_tokens: 50,
          mode: 'chat',
          context: context
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
  }, [authToken]);

  // Handle drag events
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounterRef.current = 0;

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files || []);
    if (files.length > 0) {
      onFileAttach(files);
    }
  }, [disabled, onFileAttach]);

  // Handle paste events (for images)
  const handlePaste = useCallback((e) => {
    if (disabled) return;

    const items = e.clipboardData?.items;
    if (!items) return;

    // Collect all image/file items from clipboard
    const files = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];

      // Check if it's an image or file
      if (item.type.startsWith('image/') || item.kind === 'file') {
        const file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }

    if (files.length > 0) {
      e.preventDefault(); // Prevent default paste behavior for files
      onFileAttach(files);
    }
  }, [disabled, onFileAttach]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    // Tab: Accept autocomplete suggestion
    if (e.key === 'Tab' && showAutocomplete && autocompleteSuggestion) {
      e.preventDefault();

      // Smart merge: detect overlap
      let newValue = value;
      let overlapLength = 0;

      for (let i = 1; i <= Math.min(autocompleteSuggestion.length, value.length); i++) {
        const suggestionStart = autocompleteSuggestion.substring(0, i);
        const contentEnd = value.substring(value.length - i);
        if (suggestionStart.toLowerCase() === contentEnd.toLowerCase()) {
          overlapLength = i;
        }
      }

      if (overlapLength > 0) {
        newValue = value.substring(0, value.length - overlapLength) + autocompleteSuggestion;
      } else {
        newValue = value + autocompleteSuggestion;
      }

      onChange(newValue);
      setAutocompleteSuggestion('');
      setShowAutocomplete(false);
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) {
        onSubmit();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onChange('');
      onRemoveAttachment?.();
      setAutocompleteSuggestion('');
      setShowAutocomplete(false);
    }
  }, [value, disabled, onSubmit, onChange, onRemoveAttachment, showAutocomplete, autocompleteSuggestion]);

  // Handle file input change
  const handleImageChange = useCallback((e) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      onFileAttach(files);
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  }, [onFileAttach]);

  const handleFileChange = useCallback((e) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      onFileAttach(files);
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  }, [onFileAttach]);

  // Dismiss markdown hints after first use
  const handleFirstInteraction = useCallback(() => {
    if (showHints) {
      setShowHints(false);
    }
  }, [showHints]);

  // Handle textarea value change - memoized to prevent re-renders
  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    onChange(newValue);
    handleFirstInteraction();

    // Skip autocomplete logic entirely when disabled for better performance
    if (!enableAutocomplete) return;

    // Clear existing timeout
    if (autocompleteTimeoutRef.current) {
      clearTimeout(autocompleteTimeoutRef.current);
    }

    // Hide autocomplete immediately while typing
    setShowAutocomplete(false);

    // Debounce autocomplete - wait 1000ms after last keystroke
    if (newValue.length > 5) {
      autocompleteTimeoutRef.current = setTimeout(() => {
        fetchAutocompleteSuggestion(newValue);
      }, 1000);
    } else {
      setAutocompleteSuggestion('');
    }
    // Height is handled by useEffect
  }, [onChange, handleFirstInteraction, enableAutocomplete, fetchAutocompleteSuggestion]);

  // Voice recording handlers
  const startRecording = useCallback(async () => {
    if (disabled || isRecording) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await transcribeAudio(audioBlob);

        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error accessing microphone:', error);
      alert('Could not access microphone. Please check your browser permissions.');
    }
  }, [disabled, isRecording]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  const transcribeAudio = useCallback(async (audioBlob) => {
    setIsTranscribing(true);

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');

      const response = await fetch('/api/voice/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Transcription failed');
      }

      const data = await response.json();

      // Append transcribed text to current input
      onChange(value ? `${value} ${data.text}` : data.text);
    } catch (error) {
      console.error('Error transcribing audio:', error);
      alert('Failed to transcribe audio. Please try again.');
    } finally {
      setIsTranscribing(false);
    }
  }, [value, onChange]);

  const hasAttachment = attachedFile || attachedImage;

  return (
    <div className="relative">


      {/* Drag & drop overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-blue-50/90 dark:bg-blue-900/20 border-2 border-blue-400 dark:border-blue-500 border-dashed rounded-xl backdrop-blur-sm">
          <div className="text-center">
            <ImagePlus className="w-8 h-8 mx-auto mb-2 text-blue-600 dark:text-blue-400" />
            <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
              Drop files here
            </p>
          </div>
        </div>
      )}

      {/* Main input container */}
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
        <div
          className={`
            relative flex flex-col gap-2 p-3 rounded-2xl transition-all duration-300
            ${isDragging
              ? 'bg-blue-50/50 dark:bg-blue-900/20 ring-2 ring-blue-500/50'
              : 'bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-200 shadow-sm hover:shadow-md focus-within:ring-2 focus-within:ring-amber-200/50 focus-within:border-amber-500/50'
            }
          `}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          {/* Textarea Container */}
          <div className="relative w-full min-w-0">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              className="w-full py-2 px-1 bg-transparent border-0 resize-none text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 text-base leading-relaxed max-h-[200px] custom-scrollbar"
              style={{ minHeight: '44px' }}
            />

            {/* Autocomplete Ghost Text */}
            {showAutocomplete && autocompleteSuggestion && (
              <div className="absolute top-0 left-0 py-2 px-1 pointer-events-none flex">
                <span className="invisible whitespace-pre-wrap">{value}</span>
                <span className="text-zinc-300 dark:text-zinc-600 truncate">
                  {autocompleteSuggestion.slice(value.length)}
                  <span className="ml-2 text-[10px] uppercase tracking-wider opacity-60 border border-zinc-200 dark:border-zinc-200 rounded px-1">Tab</span>
                </span>
              </div>
            )}
          </div>

          {/* Bottom Actions Row */}
          <div className="flex items-center justify-between w-full">
            {/* Left Actions Group */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                className="p-2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-200/50 dark:hover:bg-zinc-800 rounded-xl transition-all duration-200"
                title="Upload image"
              >
                <ImagePlus className="w-5 h-5" />
              </button>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-200/50 dark:hover:bg-zinc-800 rounded-xl transition-all duration-200"
                title="Attach file"
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                className={`p-2 rounded-xl transition-all duration-200 ${isRecording
                  ? 'text-red-500 bg-red-50 dark:bg-red-900/20 animate-pulse'
                  : 'text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-200/50 dark:hover:bg-zinc-800'
                  }`}
                title={isRecording ? "Stop recording" : "Voice input"}
              >
                {isRecording ? (
                  <MicOff className="w-5 h-5" />
                ) : (
                  <Mic className="w-5 h-5" />
                )}
              </button>
            </div>

            {/* Send Button */}
            <div>
              {isLoading ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    onCancel?.();
                  }}
                  className="p-2 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-all duration-200"
                  title="Stop generating"
                >
                  <Square className="w-5 h-5" />
                </button>
              ) : (
                <Button
                  outline
                  type="submit"
                  disabled={!value.trim() || disabled}
                  className={`
                    p-2 rounded-lg transition-all duration-200
                    ${!value.trim() || disabled
                      ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-300 dark:text-zinc-600 cursor-not-allowed'
                      : 'bg-zinc-500 hover:bg-zinc-400 text-white shadow-md hover:shadow-lg hover:shadow-zinc-500/20 active:scale-105'
                    }
                  `}
                  title="Send message"
                >
                  <Send className="w-5 h-5 translate-x-0.5 -translate-y-0.5" />Send
                </Button>
              )}
            </div>
          </div>

          {/* Hidden Inputs */}
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileChange}
            multiple
          />
          <input
            type="file"
            ref={imageInputRef}
            className="hidden"
            onChange={handleImageChange}
            accept="image/*"
            multiple
          />
        </div>
      </form>
    </div>
  );
});

// Display name for debugging
ChatInput.displayName = 'ChatInput';

// Wrap in React.memo to prevent unnecessary re-renders when parent state changes
export default React.memo(ChatInput);
