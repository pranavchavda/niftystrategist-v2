// App — wires Cockpit components into a single live dashboard.
function App() {
  const [dark, setDark] = React.useState(false);
  const [autoRefresh, setAutoRefresh] = React.useState(true);
  const [chatOpen, setChatOpen] = React.useState(false);
  const [chatContext, setChatContext] = React.useState(null);
  const [lastUpdated, setLastUpdated] = React.useState('5s ago');

  React.useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  React.useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => setLastUpdated('just now'), 30000);
    return () => clearInterval(id);
  }, [autoRefresh]);

  const askAI = (symbol) => {
    setChatContext(symbol);
    setChatOpen(true);
  };

  const onSymbolSelect = (symbol) => {
    // In production this navigates to /charts?symbol=X.
    askAI(symbol);
  };

  return (
    <div className="app">
      <Navbar dark={dark} onToggleDark={() => setDark(d => !d)} />
      <TopStrip
        portfolio={mockPortfolio}
        marketOpen={true}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={() => setAutoRefresh(a => !a)}
        onRefresh={() => setLastUpdated('just now')}
        lastUpdated={lastUpdated}
      />

      <div className="main">
        <aside className="left-rail">
          <MarketPulse indices={mockIndices} />
          <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
          <WatchlistPanel watchlists={mockWatchlists} onSymbolSelect={onSymbolSelect} onAskAI={askAI} />
        </aside>

        <main className="center">
          <PortfolioOverview portfolio={mockPortfolio} />
          <QuickLinks />
          <PositionsTable positions={mockPositions} holdings={mockHoldings} onSymbolSelect={onSymbolSelect} onAskAI={askAI} />
          <DailyScorecard scorecard={mockScorecard} />
        </main>
      </div>

      <button className="fab fab-watch" title="Watchlist"><Icon name="list" size={20} color="#fff" /></button>
      <button className="fab fab-chat" title="Chat" onClick={() => setChatOpen(true)}>
        <Icon name="message-square" size={20} color="#fff" />
      </button>

      {chatOpen && (
        <aside className="chat-drawer" role="dialog" aria-label="Chat">
          <div className="chat-drawer-header">
            <div className="chat-drawer-title">Nifty Strategist</div>
            <button className="icon-btn" onClick={() => setChatOpen(false)} aria-label="Close"><Icon name="x" size={16} /></button>
          </div>
          <div className="chat-drawer-body">
            <div className="ns-eyebrow">Today · 10:31</div>
            {chatContext ? (
              <>
                <div className="chat-bubble">
                  <strong>{chatContext}</strong> — looking at the latest read.
                </div>
                <div>
                  RSI 38 (approaching oversold), below 20-day SMA. Support zone 1,730–1,740.<br/><br/>
                  <strong>My take:</strong> the stop loss is doing its job. Rather than panic-exit, let it play out. If it hits 1,730, the stop triggers automatically.
                </div>
              </>
            ) : (
              <div>Ask anything — try "What's happening with RELIANCE today?"</div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
