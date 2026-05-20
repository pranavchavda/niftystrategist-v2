// DailyScorecard — end-of-day W/L summary.
function DailyScorecard({ scorecard }) {
  return (
    <div className="ds">
      <div className="ds-head">
        <div className="ns-eyebrow">Daily scorecard</div>
        <span className={`ds-streak ds-streak-${scorecard.streakType}`}>
          {scorecard.streak}-trade {scorecard.streakType} streak
        </span>
      </div>
      <div className="ds-grid">
        <div className="ds-cell">
          <div className="ns-eyebrow ds-cell-label">Trades</div>
          <div className="ns-num ds-cell-value">{scorecard.trades}</div>
          <div className="ns-num ds-cell-sub">{scorecard.won}W · {scorecard.lost}L</div>
        </div>
        <div className="ds-cell">
          <div className="ns-eyebrow ds-cell-label">Win rate</div>
          <div className="ns-num ds-cell-value ns-profit">{scorecard.winRate}%</div>
          <div className="ds-cell-bar">
            <div className="ds-cell-bar-fill" style={{ width: `${scorecard.winRate}%`, background: 'var(--profit-600)' }} />
          </div>
        </div>
        <div className="ds-cell">
          <div className="ns-eyebrow ds-cell-label">Net P&L</div>
          <div className="ns-num ds-cell-value ns-profit">{fmtMoneySigned(scorecard.netPnl)}</div>
          <div className="ns-num ds-cell-sub">Profit factor {scorecard.profitFactor}×</div>
        </div>
        <div className="ds-cell">
          <div className="ns-eyebrow ds-cell-label">Biggest win</div>
          <div className="ns-num ds-cell-value ns-profit">{fmtMoneySigned(scorecard.biggestWin)}</div>
          <div className="ns-num ds-cell-sub">Avg {fmtINR(scorecard.avgWinner)}</div>
        </div>
        <div className="ds-cell">
          <div className="ns-eyebrow ds-cell-label">Biggest loss</div>
          <div className="ns-num ds-cell-value ns-loss">{fmtMoneySigned(-scorecard.biggestLoss)}</div>
          <div className="ns-num ds-cell-sub">Avg {fmtINR(scorecard.avgLoser)}</div>
        </div>
      </div>
    </div>
  );
}

window.DailyScorecard = DailyScorecard;
