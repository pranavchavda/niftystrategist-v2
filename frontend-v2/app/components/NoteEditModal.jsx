import React, { useState, useEffect, useRef } from 'react';
import { Save, Trash2, Loader2, X } from 'lucide-react';
import { Button } from './catalyst/button';
import {
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
} from './Modal';

export default function NoteEditModal({
  note,
  isOpen,
  onClose,
  onSave,
  onDelete,
  autocompleteSuggestion,
  showAutocomplete,
  isLoadingAutocomplete,
  onContentChange,
  onKeyDown,
  isSaving,
}) {
  const [editedNote, setEditedNote] = useState(note);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [newTag, setNewTag] = useState('');
  const textareaRef = useRef(null);
  const prevIsOpenRef = useRef(isOpen);
  const typingTimeoutRef = useRef(null);
  const contentRef = useRef(editedNote?.content || '');
  const [cursorPosition, setCursorPosition] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);

  useEffect(() => {
    // Sync from parent whenever the note changes OR modal is opened
    const wasJustOpened = isOpen && !prevIsOpenRef.current;
    prevIsOpenRef.current = isOpen;

    // Update editedNote when:
    // 1. Modal is just opened with a note
    // 2. Note prop changes while modal is already open (user selected different note)
    if (isOpen && note && (!editedNote || note.id !== editedNote.id || wasJustOpened)) {
      setEditedNote(note);
      setNewTag('');
      // Reset content ref to match the new note
      contentRef.current = note.content || '';
      // Also update the textarea value directly
      if (textareaRef.current) {
        textareaRef.current.value = note.content || '';
      }
    }
  }, [note, isOpen, editedNote]);

  // Calculate tooltip position based on cursor position
  const calculateTooltipPosition = () => {
    if (!textareaRef.current) return;
    
    const textarea = textareaRef.current;
    const cursorPos = textarea.selectionStart;
    
    // Get text before cursor
    const textBeforeCursor = textarea.value.substring(0, cursorPos);
    
    // Create a temporary div to measure text dimensions
    const div = document.createElement('div');
    const style = window.getComputedStyle(textarea);
    
    // Copy relevant styles
    ['fontFamily', 'fontSize', 'fontWeight', 'letterSpacing', 'lineHeight', 'padding', 'border', 'boxSizing'].forEach(prop => {
      div.style[prop] = style[prop];
    });
    
    div.style.position = 'absolute';
    div.style.visibility = 'hidden';
    div.style.whiteSpace = 'pre-wrap';
    div.style.wordWrap = 'break-word';
    div.textContent = textBeforeCursor;
    
    document.body.appendChild(div);
    
    const height = div.offsetHeight;
    const width = div.offsetWidth;
    
    document.body.removeChild(div);
    
    // Get textarea position
    const rect = textarea.getBoundingClientRect();
    const paddingValues = style.padding.split(' ');
    const paddingTop = parseInt(paddingValues[0] || '0', 10);
    const paddingLeft = parseInt(paddingValues[1] || paddingValues[0] || '0', 10);

    setTooltipPosition({
      top: rect.top + height + paddingTop,
      left: rect.left + width + paddingLeft,
    });
  };

  const handleContentChangeWithPosition = (e) => {
    calculateTooltipPosition();
    handleContentChange(e);
  };

  const handleAddTag = () => {
    const tag = newTag.trim();
    if (!tag || !editedNote) return;
    if ((editedNote.tags || []).some(existing => existing.toLowerCase() === tag.toLowerCase())) {
      setNewTag('');
      return;
    }

    setEditedNote({
      ...editedNote,
      tags: [...(editedNote.tags || []), tag],
    });
    setNewTag('');
  };

  // Don't render anything if there's no note data
  if (!editedNote) return null;

  const handleSave = () => {
    // Get latest content from ref before saving
    const finalNote = {
      ...editedNote,
      content: contentRef.current
    };
    onSave(finalNote);
  };

  const handleContentChange = (e) => {
    // Store in ref only - don't update state on every keystroke
    contentRef.current = e.target.value;
    setCursorPosition(e.target.selectionStart);

    // Debounce autocomplete to avoid lag
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    typingTimeoutRef.current = setTimeout(() => {
      onContentChange(e);
    }, 1000);
  };

  const handleScroll = (e) => {
    setScrollTop(e.target.scrollTop);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Tab' && showAutocomplete && autocompleteSuggestion) {
      e.preventDefault();

      // Smart merge: detect overlap between end of typed text and start of suggestion
      let newContent = contentRef.current;
      let overlapLength = 0;

      // Check if the suggestion starts with text that's already at the end of current content
      for (let i = 1; i <= Math.min(autocompleteSuggestion.length, contentRef.current.length); i++) {
        const suggestionStart = autocompleteSuggestion.substring(0, i);
        const contentEnd = contentRef.current.substring(contentRef.current.length - i);
        if (suggestionStart.toLowerCase() === contentEnd.toLowerCase()) {
          overlapLength = i;
        }
      }

      // If there's overlap, replace it; otherwise just append
      if (overlapLength > 0) {
        newContent = contentRef.current.substring(0, contentRef.current.length - overlapLength) + autocompleteSuggestion;
      } else {
        newContent = contentRef.current + autocompleteSuggestion;
      }

      contentRef.current = newContent;
      if (textareaRef.current) {
        textareaRef.current.value = newContent;
      }
      return;
    }
    onKeyDown(e);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="xl"
      className="h-[90vh] flex flex-col"
    >
      {/* Header with Title Input */}
      <ModalHeader className="flex-shrink-0">
        <input
          type="text"
          value={editedNote.title}
          onChange={(e) => setEditedNote({ ...editedNote, title: e.target.value })}
          className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 bg-transparent border-none outline-none focus:ring-0 w-full pr-10"
          placeholder="Note title..."
        />
      </ModalHeader>

      {/* Metadata Bar */}
      <div className="px-6 py-4 border-b border-zinc-200/50 dark:border-zinc-800/50 flex flex-wrap items-center gap-4 flex-shrink-0">
        <select
          value={editedNote.category}
          onChange={(e) => setEditedNote({ ...editedNote, category: e.target.value })}
          className="px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="personal">Personal</option>
          <option value="work">Work</option>
          <option value="ideas">Ideas</option>
          <option value="reference">Reference</option>
        </select>

        {/* Tags */}
        <div className="flex flex-1 flex-col lg:flex-row lg:items-center gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {(editedNote.tags || []).map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300"
              >
                {tag}
                <button
                  onClick={() =>
                    setEditedNote({
                      ...editedNote,
                      tags: (editedNote.tags || []).filter((t) => t !== tag),
                    })
                  }
                  className="hover:text-red-600 dark:hover:text-red-400 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddTag();
                }
              }}
              placeholder="Add tag..."
              className="w-32 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <Button onClick={handleAddTag} className="text-xs py-1 px-2.5">
              Add
            </Button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <ModalBody className="flex-1 overflow-hidden flex flex-col !max-h-none !p-6">
        <div className="flex-1 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden flex flex-col relative bg-white dark:bg-zinc-900">
          <textarea
            ref={textareaRef}
            defaultValue={editedNote.content}
            onChange={handleContentChange}
            onKeyDown={handleKeyDown}
            onScroll={handleScroll}
            className="flex-1 p-4 resize-none bg-transparent text-zinc-900 dark:text-zinc-100 font-mono text-sm leading-relaxed focus:outline-none relative z-10"
            placeholder="Start writing... (Press Tab for AI autocomplete)"
          />
          {/* Ghost text overlay at cursor position */}
          {showAutocomplete && autocompleteSuggestion && (
            <div
              className="absolute top-0 left-0 p-4 pointer-events-none font-mono text-sm leading-relaxed whitespace-pre-wrap break-words w-full overflow-hidden"
              style={{ transform: `translateY(-${scrollTop}px)` }}
            >
              <span className="invisible">{contentRef.current.substring(0, cursorPosition)}</span>
              <span className="text-zinc-400 dark:text-zinc-500" style={{ opacity: 0.5 }}>
                {autocompleteSuggestion}
              </span>
            </div>
          )}
        </div>
      </ModalBody>

      {/* Footer */}
      <ModalFooter className="justify-between flex-shrink-0">
        <Button
          onClick={() => onDelete(editedNote.id)}
          color="red"
          outline
          className="gap-1.5"
        >
          <Trash2 data-slot="icon" className="w-4 h-4" />
          Delete
        </Button>
        <div className="flex items-center gap-3">
          <Button onClick={onClose} outline>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving} color="blue" className="gap-1.5">
            {isSaving ? (
              <>
                <Loader2 data-slot="icon" className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save data-slot="icon" className="w-4 h-4" />
                Save
              </>
            )}
          </Button>
        </div>
      </ModalFooter>
    </Modal>
  );
}
