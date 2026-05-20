// WatchlistPanel — tabbed watchlist with sparklines and hover actions.
function Sparkline({ data, isUp }) {
  const color = isUp ? 'var(--profit-600)' : 'var(--loss-600)';
  const w = 48, h = 20;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 2) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  // Build area path
  const areaPts = points + ` ${w},${h} 0,${h}`;
  const gradId = `spark-${isUp ? 'u' : 'd'}-${data[0]}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={areaPts} fill={`url(#${gradId})`} />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function WatchlistPanel({ watchlists, onSymbolSelect, onAskAI }) {
  const lists = Object.keys(watchlists);
  const [active, setActive] = React.useState(lists[0]);
  const [search, setSearch] = React.useState('');
  const [hover, setHover] = React.useState(null);

  const items = (watchlists[active] || []).filter(it =>
    it.symbol.toLowerCase().includes(search.toLowerCase()) ||
    it.company.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="wl">
      <div className="ns-eyebrow wl-eyebrow">Watchlist</div>

      <div className="wl-tabs">
        {lists.map(n => (
          <button key={n} onClick={() => setActive(n)} className={`wl-tab ${active === n ? 'wl-tab-active' : ''}`}>{n}</button>
        ))}
      </div>

      <div className="wl-search">
        <Icon name="search" size={12} className="wl-search-icon" />
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter..." />
      </div>

      <div className="wl-items">
        {items.map(it => {
          const isUp = it.changePct >= 0;
          const hovered = hover === it.symbol;
          return (
            <div key={it.symbol} className="wl-row" onMouseEnter={() => setHover(it.symbol)} onMouseLeave={() => setHover(null)} onClick={() => onSymbolSelect(it.symbol)}>
              <div className="wl-row-left">
                <div className="wl-row-sym">
                  <span className="wl-sym">{it.symbol}</span>
                  {it.alert && <Icon name="bell" size={10} color="var(--amber-500)" />}
                </div>
                <div className="wl-co">{it.company}</div>
              </div>
              <div className="wl-row-right">
                <Sparkline data={it.spark} isUp={isUp} />
                <div className="wl-prices">
                  <div className="ns-num wl-ltp">{it.ltp.toLocaleString('en-IN')}</div>
                  <div className={`ns-num wl-pct ${isUp ? 'ns-profit' : 'ns-loss'}`}>{isUp ? '+' : ''}{it.changePct.toFixed(2)}%</div>
                </div>
              </div>
              {hovered && (
                <div className="wl-actions">
                  <button className="wl-action" title="View chart"><Icon name="bar-chart-3" size={12} /></button>
                  <button className="wl-action wl-action-buy" title="Buy"><Icon name="shopping-cart" size={12} color="var(--profit-600)" /></button>
                  <button className="wl-action wl-action-ai" onClick={(e) => { e.stopPropagation(); onAskAI(it.symbol); }} title="Ask AI"><Icon name="sparkles" size={12} color="var(--amber-600)" /></button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.WatchlistPanel = WatchlistPanel;
