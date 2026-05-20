// Navbar — top-of-page chrome above the dashboard.
function Navbar({ dark, onToggleDark }) {
  return (
    <div className="navbar">
      <div className="navbar-left">
        <span className="navbar-mark"><Icon name="trending-up" size={22} strokeWidth={1.75} color="var(--blue-600)" /></span>
        <span className="navbar-title">Nifty Strategist</span>
      </div>
      <div className="navbar-right">
        <div className="navbar-thread">
          <Icon name="message-square" size={14} className="muted" />
          <span>Chat history</span>
        </div>
        <div className="navbar-divider" />
        <button className="icon-btn" title={dark ? 'Light mode' : 'Dark mode'} onClick={onToggleDark}>
          <Icon name={dark ? 'sun' : 'moon'} size={16} />
        </button>
        <div className="navbar-avatar">PC</div>
      </div>
    </div>
  );
}

window.Navbar = Navbar;
