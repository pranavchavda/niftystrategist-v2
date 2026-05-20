// TopStrip — sticky portfolio summary at the top of the dashboard.
function TopStrip({ portfolio, marketOpen, autoRefresh, onToggleAutoRefresh, onRefresh, lastUpdated }) {
  const [refreshing, setRefreshing] = React.useState(false);
  const handleRefresh = () => { setRefreshing(true); onRefresh(); setTimeout(() => setRefreshing(false), 1000); };

  return (
    <div className="topstrip">
      <div className="topstrip-data">
        <div className="topstrip-item">
          <Icon name="wallet" size={14} className="muted" />
          <span className="ns-eyebrow" style={{ letterSpacing: '0.08em', fontSize: 10 }}>Portfolio</span>
          <span className="ns-num topstrip-value">{fmtINR(portfolio.totalValue)}</span>
        </div>
        <div className="topstrip-item topstrip-divider">
          <Icon name={portfolio.dayPnl >= 0 ? 'trending-up' : 'trending-down'} size={14} color={portfolio.dayPnl >= 0 ? 'var(--profit-text-light)' : 'var(--loss-text-light)'} />
          <span className="ns-eyebrow" style={{ letterSpacing: '0.08em', fontSize: 10 }}>Day</span>
          <span className={`ns-num topstrip-value ${portfolio.dayPnl >= 0 ? 'ns-profit' : 'ns-loss'}`}>{fmtMoneySigned(portfolio.dayPnl)}</span>
          <span className={`ns-num topstrip-sub ${portfolio.dayPnl >= 0 ? 'ns-profit' : 'ns-loss'}`}>{fmtPct(portfolio.dayPnlPct)}</span>
        </div>
        <div className="topstrip-item topstrip-divider topstrip-hide-md">
          <span className="ns-eyebrow" style={{ letterSpacing: '0.08em', fontSize: 10 }}>Overall</span>
          <span className={`ns-num topstrip-value ${portfolio.totalPnl >= 0 ? 'ns-profit' : 'ns-loss'}`}>{fmtMoneySigned(portfolio.totalPnl)}</span>
          <span className={`ns-num topstrip-sub ${portfolio.totalPnl >= 0 ? 'ns-profit' : 'ns-loss'}`}>{fmtPct(portfolio.totalPnlPct)}</span>
        </div>
        <div className="topstrip-item topstrip-divider topstrip-hide-md">
          <span className="ns-eyebrow" style={{ letterSpacing: '0.08em', fontSize: 10 }}>Margin</span>
          <span className="ns-num topstrip-value" style={{ color: 'var(--fg-default)' }}>{fmtINR(portfolio.availableCash)}</span>
          <span className="ns-eyebrow" style={{ letterSpacing: '0.08em', fontSize: 10 }}>Used</span>
          <span className="ns-num topstrip-sub" style={{ color: 'var(--amber-600)' }}>{fmtINR(portfolio.marginUsed)}</span>
        </div>
      </div>

      <div className="topstrip-controls">
        <div className={`market-pill ${marketOpen ? 'market-pill-open' : 'market-pill-closed'}`}>
          <span className="market-dot" />
          <span>{marketOpen ? 'LIVE' : 'CLOSED'}</span>
        </div>
        <button className={`auto-pill ${autoRefresh ? 'auto-pill-on' : 'auto-pill-off'}`} onClick={onToggleAutoRefresh} title="Auto-refresh">AUTO</button>
        {lastUpdated && <span className="topstrip-ago ns-num">{lastUpdated}</span>}
        <button className="icon-btn" onClick={handleRefresh} title="Refresh data">
          <Icon name="refresh-cw" size={14} className={refreshing ? 'spin' : ''} />
        </button>
      </div>
    </div>
  );
}

window.TopStrip = TopStrip;
