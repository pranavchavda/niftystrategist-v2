// PositionsTable — segmented tabs + sortable dense table with expandable row footer.
function PositionsTable({ positions, holdings, onSymbolSelect, onAskAI }) {
  const [tab, setTab] = React.useState('positions');
  const [sortKey, setSortKey] = React.useState('pnlPct');
  const [sortDir, setSortDir] = React.useState('desc');
  const [expanded, setExpanded] = React.useState(null);

  const data = tab === 'positions' ? positions : holdings;
  const sorted = [...data].sort((a, b) => {
    const av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  const toggleSort = (k) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(k); setSortDir('desc'); }
  };

  const SortIcon = ({ col }) => sortKey === col
    ? <Icon name={sortDir === 'desc' ? 'chevron-down' : 'chevron-up'} size={12} color="var(--amber-500)" />
    : null;

  const totalInvested = data.reduce((s, p) => s + p.avgPrice * p.qty, 0);
  const totalCurrent = data.reduce((s, p) => s + p.ltp * p.qty, 0);
  const totalPnl = data.reduce((s, p) => s + p.pnl, 0);
  const totalPnlPct = totalInvested ? (totalPnl / totalInvested) * 100 : 0;

  return (
    <div className="pt">
      <div className="pt-header">
        <div className="pt-tabs">
          <button className={`pt-tab ${tab === 'positions' ? 'pt-tab-active' : ''}`} onClick={() => setTab('positions')}>Open ({positions.length})</button>
          <button className={`pt-tab ${tab === 'holdings'  ? 'pt-tab-active' : ''}`} onClick={() => setTab('holdings')}>Holdings ({holdings.length})</button>
          <button className={`pt-tab`} disabled title="Demo">Trades (5)</button>
          <button className={`pt-tab`} disabled title="Demo">Mutual funds (3)</button>
        </div>
        <div className="pt-summary">
          <span className="pt-sum-item">Invested: <span className="ns-num pt-sum-val">{fmtINR(totalInvested)}</span></span>
          <span className="pt-sum-item">Current: <span className="ns-num pt-sum-val">{fmtINR(totalCurrent)}</span></span>
          <span className={`ns-num pt-sum-pnl ${totalPnl >= 0 ? 'ns-profit' : 'ns-loss'}`}>{fmtMoneySigned(totalPnl)} ({fmtPct(totalPnlPct)})</span>
        </div>
      </div>

      <div className="pt-table-wrap">
        <table className="pt-table">
          <thead>
            <tr>
              <th style={{ width: 28 }}></th>
              <th onClick={() => toggleSort('symbol')}>Symbol</th>
              <th className="right">Qty</th>
              <th className="right pt-hide-lg">Avg price</th>
              <th className="right">LTP</th>
              <th className="right" onClick={() => toggleSort('pnl')}>P&L <SortIcon col="pnl" /></th>
              <th className="right" onClick={() => toggleSort('pnlPct')}>P&L % <SortIcon col="pnlPct" /></th>
              <th className="right pt-hide-lg" onClick={() => toggleSort('dayChangePct')}>Day <SortIcon col="dayChangePct" /></th>
              <th className="right pt-hide-lg">Days</th>
              <th className="right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(pos => {
              const isExpanded = expanded === pos.symbol;
              const tone = pos.pnl >= 0 ? 'profit' : 'loss';
              return (
                <React.Fragment key={pos.symbol}>
                  <tr className={`pt-row pt-row-${tone}`}>
                    <td>
                      <button className="icon-btn icon-btn-mini" onClick={() => setExpanded(isExpanded ? null : pos.symbol)}>
                        <Icon name="chevron-right" size={12} style={{ transform: isExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 150ms' }} />
                      </button>
                    </td>
                    <td><span className="pt-sym" onClick={() => onSymbolSelect(pos.symbol)}>{pos.symbol}</span></td>
                    <td className="right ns-num pt-muted">{pos.qty}</td>
                    <td className="right ns-num pt-muted pt-hide-lg">{fmtINRdec(pos.avgPrice)}</td>
                    <td className="right ns-num pt-strong">{fmtINRdec(pos.ltp)}</td>
                    <td className={`right ns-num pt-pnl ${tone === 'profit' ? 'ns-profit' : 'ns-loss'}`}>{fmtMoneySigned(pos.pnl)}</td>
                    <td className={`right ns-num pt-pnl ${tone === 'profit' ? 'ns-profit' : 'ns-loss'}`}>{fmtPct(pos.pnlPct)}</td>
                    <td className={`right ns-num pt-day pt-hide-lg ${pos.dayChangePct >= 0 ? 'ns-profit' : 'ns-loss'}`}>{fmtPct(pos.dayChangePct)}</td>
                    <td className="right ns-num pt-muted pt-hide-lg">{pos.holdDays != null ? `${pos.holdDays}d` : '—'}</td>
                    <td className="right">
                      <div className="pt-actions">
                        <button className="icon-btn icon-btn-mini" title="Ask AI" onClick={() => onAskAI(pos.symbol)}><Icon name="sparkles" size={14} color="var(--amber-600)" /></button>
                        {tab === 'positions' && <button className="icon-btn icon-btn-mini" title="Exit position"><Icon name="log-out" size={14} color="var(--loss-600)" /></button>}
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="pt-expanded">
                      <td colSpan={10}>
                        <div className="pt-exp-content">
                          <span className="pt-exp-label">Company: <span className="pt-exp-value">{pos.company}</span></span>
                          {pos.stopLoss && <span className="pt-exp-label">SL: <span className="ns-num pt-exp-value" style={{ color: 'var(--loss-text-light)' }}>{fmtINRdec(pos.stopLoss)}</span></span>}
                          {pos.target && <span className="pt-exp-label">Target: <span className="ns-num pt-exp-value" style={{ color: 'var(--profit-text-light)' }}>{fmtINRdec(pos.target)}</span></span>}
                          <span className="pt-exp-label">Value: <span className="ns-num pt-exp-value">{fmtINR(pos.ltp * pos.qty)}</span></span>
                          {pos.stopLoss && (
                            <span className="pt-exp-label">Risk: <span className="pt-exp-badge">{Math.abs((pos.ltp - pos.stopLoss) / pos.ltp * 100).toFixed(1)}% to SL</span></span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.PositionsTable = PositionsTable;
