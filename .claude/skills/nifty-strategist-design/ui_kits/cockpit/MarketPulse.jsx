// MarketPulse — three index quote pills.
function MarketPulse({ indices }) {
  return (
    <div className="mp">
      <div className="ns-eyebrow mp-eyebrow">Market pulse</div>
      <div className="mp-list">
        {indices.map(idx => {
          const isUp = idx.change >= 0;
          return (
            <div key={idx.name} className={`mp-row ${isUp ? 'up' : 'down'}`}>
              <div className="mp-left">
                <Icon name={isUp ? 'trending-up' : 'trending-down'} size={12} color={isUp ? 'var(--profit-text-light)' : 'var(--loss-text-light)'} />
                <span className="mp-name">{idx.name}</span>
              </div>
              <div className="mp-right">
                <div className="ns-num mp-value">{idx.value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                <div className={`ns-num mp-delta ${isUp ? 'ns-profit' : 'ns-loss'}`}>
                  {isUp ? '+' : ''}{idx.change.toFixed(2)} ({isUp ? '+' : ''}{idx.changePct.toFixed(2)}%)
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.MarketPulse = MarketPulse;
