// QuickLinks — six secondary-nav tiles below the KPI strip.
function QuickLinks() {
  const links = [
    { to: '/charts',         label: 'Charts',     icon: 'candlestick-chart' },
    { to: '/monitor',        label: 'Monitor',    icon: 'shield' },
    { to: '/mandates',       label: 'Mandates',   icon: 'target' },
    { to: '/scalp-sessions', label: 'Scalp',      icon: 'zap' },
    { to: '/notes',          label: 'Notes',      icon: 'sticky-note' },
    { to: '/strategies',     label: 'Strategies', icon: 'book-open' },
  ];
  return (
    <div className="quicklinks">
      {links.map(l => (
        <a key={l.to} href="#" className="quicklink" onClick={(e) => e.preventDefault()}>
          <span className="quicklink-icon"><Icon name={l.icon} size={16} /></span>
          <span className="quicklink-label">{l.label}</span>
        </a>
      ))}
    </div>
  );
}

window.QuickLinks = QuickLinks;
