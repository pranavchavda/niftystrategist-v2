// App — chat thread shell with sample conversation.
const SEED_THREADS = [
  { id: 't1', title: 'TCS swing setup — buy 10', time: 'Today' },
  { id: 't2', title: 'Morning scan — Feb 7',     time: 'Today' },
  { id: 't3', title: 'INFY stop-loss review',    time: 'Yesterday' },
  { id: 't4', title: 'BAJFINANCE holding analysis', time: '2 days ago' },
  { id: 't5', title: 'Weekly portfolio review',  time: '5 days ago' },
];

const SEED_MESSAGES = [
  {
    id: 'm1',
    role: 'assistant',
    time: '09:00',
    content: `### Good morning, Pranav — trading day, Feb 7, 2026

### Your positions
- **RELIANCE** +2.43% (3 days) — approaching target at 2,950
- **INFY** -1.40% (7 days) — watch stop loss at 1,730
- **TCS** +1.69% — steady, holding well

### Watchlist alerts
- TATAMOTORS nearing alert at 970 (currently 952)

### Today's focus
1. Monitor INFY — close to stop loss
2. RELIANCE approaching target zone`,
    tools: ['nf-portfolio', 'nf-watchlist'],
  },
  {
    id: 'm2',
    role: 'user',
    time: '10:30',
    content: "Should I exit INFY? It's been dropping for a week.",
  },
  {
    id: 'm3',
    role: 'assistant',
    time: '10:31',
    tools: ['nf-quote --symbol=INFY', 'nf-analyze --symbol=INFY'],
    content: `INFY is at **1,755** — just 25 points (1.4%) above your stop loss at **1,730**.

### Technical picture
- RSI: 38 (approaching oversold)
- Below 20-day SMA (bearish)
- Support at 1,730–1,740 zone

**My take:** the stop loss is doing its job. Rather than panic-exit, let it play out. If it hits 1,730, the stop triggers automatically. If it bounces from here, you catch the reversal.

**But** — your hold is already 7 days, longer than your typical 2-5 day swing. Consider tightening your stop to **1,745** to protect more capital.`,
  },
  {
    id: 'm4',
    role: 'user',
    time: '10:34',
    content: 'OK tighten the stop to 1,745. Also, buy 10 TCS at market.',
  },
  {
    id: 'm5',
    role: 'assistant',
    time: '10:34',
    tools: ['nf-monitor edit-rule', 'nf-quote --symbol=TCS'],
    content: `Stop on **INFY** moved to **1,745** ✓

For TCS — current market price is **₹4,125.00**. Confirm before I place the order:`,
    confirm: {
      action: 'Buy', qty: 10, symbol: 'TCS',
      priceLabel: '₹4,125.00 (market)',
      totalLabel: '₹41,250',
    },
  },
];

function App() {
  const [threads] = React.useState(SEED_THREADS);
  const [activeId, setActiveId] = React.useState('t1');
  const [messages, setMessages] = React.useState(SEED_MESSAGES);
  const [input, setInput] = React.useState('');
  const [confirmStatus, setConfirmStatus] = React.useState({});
  const [dark, setDark] = React.useState(false);
  const bottomRef = React.useRef(null);

  React.useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  React.useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollTop = bottomRef.current.scrollHeight;
  }, [messages.length, Object.keys(confirmStatus).length]);

  const send = () => {
    if (!input.trim()) return;
    const userMsg = { id: 'u' + Date.now(), role: 'user', time: now(), content: input.trim() };
    setMessages(m => [...m, userMsg]);
    setInput('');
    setTimeout(() => {
      const reply = {
        id: 'a' + Date.now(), role: 'assistant', time: now(),
        tools: ['nf-quote'],
        content: `I hear you. Let me check the latest read on this and come back with a recommendation.

**My take:** without a clearer setup, I'd hold off on action — the noise this hour isn't a signal.`,
      };
      setMessages(m => [...m, reply]);
    }, 600);
  };

  const approve = (id) => setConfirmStatus(s => ({ ...s, [id]: 'approved' }));
  const reject  = (id) => setConfirmStatus(s => ({ ...s, [id]: 'rejected' }));

  return (
    <div className="chat-app">
      <Sidebar
        threads={threads}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={() => setMessages([])}
      />

      <main className="thread">
        <div className="thread-top">
          <div className="thread-top-left">
            <div className="thread-top-title">{threads.find(t => t.id === activeId)?.title || 'New chat'}</div>
            <div className="thread-top-meta">
              <span className="model-pill">glm-5</span>
              <span className="ns-helper">2 tools available · live</span>
            </div>
          </div>
          <div className="thread-top-right">
            <button className="icon-btn" title="Toggle theme" onClick={() => setDark(d => !d)}>
              <Icon name={dark ? 'sun' : 'moon'} size={16} />
            </button>
            <button className="icon-btn" title="Open dashboard"><Icon name="layout-dashboard" size={16} /></button>
            <button className="icon-btn" title="Thread actions"><Icon name="more-horizontal" size={16} /></button>
          </div>
        </div>

        <div className="thread-scroll" ref={bottomRef}>
          <div className="thread-inner">
            {messages.map(m => (
              <MessageBubble
                key={m.id}
                msg={{ ...m, confirmStatus: confirmStatus[m.id] }}
                onApprove={approve}
                onReject={reject}
              />
            ))}
          </div>
        </div>

        <div className="thread-bottom">
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={send}
            suggestions={messages.length < 3 ? ['Morning scan', 'What\'s happening with RELIANCE?', 'Show today\'s P&L'] : null}
            onSuggest={s => setInput(s)}
          />
        </div>
      </main>
    </div>
  );
}

function now() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
