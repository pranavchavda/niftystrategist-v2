// Sidebar — left rail with new-chat button and thread list.
function Sidebar({ threads, activeId, onSelect, onNew }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="sidebar-brand">
          <span className="sidebar-mark"><Icon name="trending-up" size={20} strokeWidth={1.75} color="var(--blue-600)" /></span>
          <span className="sidebar-title">Nifty Strategist</span>
        </div>
      </div>

      <button className="new-chat" onClick={onNew}>
        <Icon name="plus" size={14} />
        <span>New chat</span>
      </button>

      <div className="sidebar-section">
        <div className="ns-eyebrow" style={{ paddingLeft: 12, marginBottom: 4 }}>Recent</div>
        <div className="thread-list">
          {threads.map(t => (
            <button key={t.id} className={`thread-item ${t.id === activeId ? 'thread-item-active' : ''}`} onClick={() => onSelect(t.id)}>
              <div className="thread-title">{t.title}</div>
              <div className="thread-meta">{t.time}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-nav">
        {[
          { icon: 'layout-dashboard', label: 'Dashboard' },
          { icon: 'bell', label: 'Monitor' },
          { icon: 'target', label: 'Mandates' },
          { icon: 'sticky-note', label: 'Notes' },
          { icon: 'settings', label: 'Settings' },
        ].map(item => (
          <a key={item.label} href="#" className="sidebar-nav-item" onClick={(e) => e.preventDefault()}>
            <Icon name={item.icon} size={14} />
            <span>{item.label}</span>
          </a>
        ))}
      </div>

      <div className="sidebar-foot">
        <div className="sidebar-avatar">PC</div>
        <div className="sidebar-user">
          <div className="sidebar-user-name">Pranav Chavda</div>
          <div className="sidebar-user-mode">Live trading · Upstox</div>
        </div>
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;
