// ChatInput — sticky composer at the bottom of the thread.
function ChatInput({ value, onChange, onSubmit, suggestions, onSuggest }) {
  const ref = React.useRef(null);

  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(Math.max(el.scrollHeight, 44), 200) + 'px';
  }, [value]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) onSubmit();
    }
  };

  return (
    <div className="composer-wrap">
      {suggestions && suggestions.length > 0 && (
        <div className="suggestions">
          {suggestions.map(s => (
            <button key={s} className="suggestion" onClick={() => onSuggest(s)}>{s}</button>
          ))}
        </div>
      )}
      <div className="composer">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Message Nifty Strategist..."
          className="composer-textarea"
        />
        <div className="composer-foot">
          <div className="composer-actions">
            <button className="icon-btn" title="Upload image"><Icon name="image-plus" size={18} /></button>
            <button className="icon-btn" title="Attach file"><Icon name="paperclip" size={18} /></button>
            <button className="icon-btn" title="Voice input"><Icon name="mic" size={18} /></button>
          </div>
          <button
            className={`send-btn ${value.trim() ? 'send-btn-active' : ''}`}
            disabled={!value.trim()}
            onClick={onSubmit}
            title="Send"
          >
            <Icon name="send" size={16} />
            <span>Send</span>
          </button>
        </div>
      </div>
      <div className="composer-hint">Enter to send · Shift+Enter for new line · Trades require your approval.</div>
    </div>
  );
}

window.ChatInput = ChatInput;
