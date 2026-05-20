// PortfolioOverview — six KPI cards in a horizontal grid.
function KPI({ label, value, sub, icon, tone = 'neutral' }) {
  const valueClass = tone === 'profit' ? 'ns-profit' : tone === 'loss' ? 'ns-loss' : '';
  const subClass = tone === 'profit' ? 'ns-profit' : tone === 'loss' ? 'ns-loss' : '';
  return (
    <div className="kpi">
      <div className="kpi-icon"><Icon name={icon} size={16} /></div>
      <div className="kpi-body">
        <div className="ns-eyebrow kpi-label">{label}</div>
        <div className={`ns-num kpi-value ${valueClass}`}>{value}</div>
        {sub && <div className={`ns-num kpi-sub ${subClass}`}>{sub}</div>}
      </div>
    </div>
  );
}

function PortfolioOverview({ portfolio }) {
  return (
    <div className="kpi-grid">
      <KPI label="Total value" value={fmtINR(portfolio.totalValue)} icon="wallet" />
      <KPI label="Day P&L" value={fmtMoneySigned(portfolio.dayPnl)} sub={fmtPct(portfolio.dayPnlPct)} icon={portfolio.dayPnl >= 0 ? 'trending-up' : 'trending-down'} tone={portfolio.dayPnl >= 0 ? 'profit' : 'loss'} />
      <KPI label="Total P&L" value={fmtMoneySigned(portfolio.totalPnl)} sub={fmtPct(portfolio.totalPnlPct)} icon={portfolio.totalPnl >= 0 ? 'trending-up' : 'trending-down'} tone={portfolio.totalPnl >= 0 ? 'profit' : 'loss'} />
      <KPI label="Invested" value={fmtINR(portfolio.investedValue)} icon="piggy-bank" />
      <KPI label="Available" value={fmtINR(portfolio.availableCash)} icon="coins" />
      <KPI label="Margin used" value={fmtINR(portfolio.marginUsed)} icon="gauge" />
    </div>
  );
}

window.PortfolioOverview = PortfolioOverview;
