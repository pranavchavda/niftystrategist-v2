import React, { useState, useRef, useCallback, useEffect } from 'react';

/**
 * Textarea wrapper with AI autocomplete for documentation editing
 *
 * Uses Pydantic AI service with ghost-text suggestions (Cursor/Windsurf style).
 * Optimized for markdown/docs editing with mode-specific prompts.
 */
const TextareaWithAutocomplete = ({
  value,
  onChange,
  authToken,
  className = '',
  mode = 'docs',  // 'docs' or 'chat'
  ...textareaProps
}) => {
  const [suggestion, setSuggestion] = useState('');
  const [showSuggestion, setShowSuggestion] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);

  const textareaRef = useRef(null);
  const debounceTimerRef = useRef(null);

  // Fetch autocomplete suggestion from Pydantic service
  const fetchSuggestion = async (text) => {
    if (!text || text.length < 5 || !authToken) {
      setSuggestion('');
      setShowSuggestion(false);
      return;
    }

    try {
      setIsLoading(true);
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
          mode: mode  // 'docs' or 'chat'
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.suggestion && data.confidence > 0.5) {
          setSuggestion(data.suggestion);
          setShowSuggestion(true);
        } else {
          setSuggestion('');
          setShowSuggestion(false);
        }
      } else {
        setSuggestion('');
        setShowSuggestion(false);
      }
    } catch (error) {
      console.error('Error fetching autocomplete suggestion:', error);
      setSuggestion('');
      setShowSuggestion(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle text changes with debounced autocomplete
  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    onChange(e);

    // Update cursor position
    if (textareaRef.current) {
      setCursorPosition(textareaRef.current.selectionStart);
    }

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Hide suggestion immediately while typing
    setShowSuggestion(false);

    // Debounce autocomplete - wait 1000ms after last keystroke
    if (newValue.length > 5) {
      debounceTimerRef.current = setTimeout(() => {
        fetchSuggestion(newValue);
      }, 1000);
    } else {
      setSuggestion('');
    }
  }, [onChange]);

  // Handle scroll for ghost text sync
  const handleScroll = (e) => {
    setScrollTop(e.target.scrollTop);
  };

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    // Tab: Accept suggestion
    if (e.key === 'Tab' && showSuggestion && suggestion) {
      e.preventDefault();

      // Smart merge: detect overlap between end of typed text and start of suggestion
      let newValue = value;
      let overlapLength = 0;

      // Check if the suggestion starts with text that's already at the end of current content
      for (let i = 1; i <= Math.min(suggestion.length, value.length); i++) {
        const suggestionStart = suggestion.substring(0, i);
        const contentEnd = value.substring(value.length - i);
        if (suggestionStart.toLowerCase() === contentEnd.toLowerCase()) {
          overlapLength = i;
        }
      }

      // If there's overlap, replace it; otherwise just append
      if (overlapLength > 0) {
        newValue = value.substring(0, value.length - overlapLength) + suggestion;
      } else {
        newValue = value + suggestion;
      }

      // Create synthetic event and call onChange
      const syntheticEvent = {
        target: { value: newValue }
      };
      onChange(syntheticEvent);

      // Clear suggestion after accepting
      setSuggestion('');
      setShowSuggestion(false);

      return;
    }

    // Escape: Clear suggestion
    if (e.key === 'Escape' && showSuggestion) {
      e.preventDefault();
      setSuggestion('');
      setShowSuggestion(false);
      return;
    }
  }, [showSuggestion, suggestion, value, onChange]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="relative h-full bg-white dark:bg-zinc-950">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onScroll={handleScroll}
        className={`${className.replace(/bg-\S+/g, '')} bg-transparent relative z-10`}
        placeholder="Start writing... (Press Tab for AI autocomplete)"
        {...textareaProps}
      />

      {/* Ghost text overlay at cursor position */}
      {showSuggestion && suggestion && (
        <div
          className="absolute top-0 left-0 p-6 pointer-events-none font-mono text-sm leading-relaxed whitespace-pre-wrap break-words w-full overflow-hidden"
          style={{ transform: `translateY(-${scrollTop}px)` }}
        >
          <span className="invisible">{value.substring(0, cursorPosition)}</span>
          <span className="text-zinc-400 dark:text-zinc-500" style={{ opacity: 0.5 }}>
            {suggestion}
          </span>
        </div>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div className="absolute top-2 right-2 z-20">
          <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}
    </div>
  );
};

export default TextareaWithAutocomplete;
