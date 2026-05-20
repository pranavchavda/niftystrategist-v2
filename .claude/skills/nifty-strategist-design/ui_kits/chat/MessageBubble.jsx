// MessageBubble — render a single message. Assistant messages support
// a small subset of markdown (headings, bold, lists) and an optional
// inline trade-confirmation card.

function renderInline(text) {
  // **bold** + `code` (very small markdown subset)
  const parts = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) parts.push(<strong key={parts.length}>{tok.slice(2, -2)}</strong>);
    else parts.push(<code key={parts.length} className="ns-mono inline-code">{tok.slice(1, -1)}</code>);
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function MarkdownBlock({ text }) {
  // Walk line-by-line. Headings → h2/h3 stand alone. Consecutive
  // bullet lines → ul. Other consecutive lines → paragraph block.
  const lines = text.trim().split('\n');
  const out = [];
  let buf = []; // { kind: 'p' | 'ul', items: [...] }

  const flush = () => {
    if (!buf.length) return;
    const kind = buf[0].kind;
    if (kind === 'ul') {
      out.push(<ul key={out.length} className="md-ul">{buf.map((b, j) => <li key={j}>{renderInline(b.text)}</li>)}</ul>);
    } else {
      out.push(<p key={out.length} className="md-p">{buf.map((b, j) => (
        <React.Fragment key={j}>{renderInline(b.text)}{j < buf.length - 1 && <br />}</React.Fragment>
      ))}</p>);
    }
    buf = [];
  };

  for (const line of lines) {
    if (line.startsWith('### ')) {
      flush();
      out.push(<h3 key={out.length} className="md-h3">{renderInline(line.slice(4))}</h3>);
    } else if (line.startsWith('## ')) {
      flush();
      out.push(<h2 key={out.length} className="md-h2">{renderInline(line.slice(3))}</h2>);
    } else if (line.startsWith('- ')) {
      if (buf.length && buf[0].kind !== 'ul') flush();
      buf.push({ kind: 'ul', text: line.slice(2) });
    } else if (line.trim() === '') {
      flush();
    } else {
      if (buf.length && buf[0].kind !== 'p') flush();
      buf.push({ kind: 'p', text: line });
    }
  }
  flush();
  return out;
}

function ToolCallBadge({ tool }) {
  return (
    <div className="toolcall">
      <Icon name="terminal" size={11} className="muted" />
      <span className="toolcall-name">{tool}</span>
      <span className="toolcall-status">
        <Icon name="check" size={11} color="var(--profit-600)" />
        <span>completed</span>
      </span>
    </div>
  );
}

function TradeConfirm({ order, onApprove, onReject, status }) {
  if (status === 'approved') {
    return (
      <div className="confirm confirm-approved">
        <Icon name="check-circle-2" size={16} color="var(--profit-600)" />
        <span>Order placed — <strong>{order.action} {order.qty} {order.symbol}</strong> at {order.priceLabel}.</span>
      </div>
    );
  }
  if (status === 'rejected') {
    return (
      <div className="confirm confirm-rejected">
        <Icon name="x-circle" size={16} color="var(--loss-600)" />
        <span>Order cancelled.</span>
      </div>
    );
  }
  return (
    <div className="confirm">
      <div className="confirm-head">
        <span className="confirm-warn">⚠️</span>
        <div>
          <div className="confirm-title">Confirm trade</div>
          <div className="confirm-body">
            {order.action} <span className="ns-num">{order.qty}</span> shares of <strong>{order.symbol}</strong> at {order.priceLabel}. Total: <span className="ns-num confirm-strong">{order.totalLabel}</span>.
          </div>
        </div>
      </div>
      <div className="confirm-actions">
        <button className="btn btn-approve" onClick={onApprove}>Approve</button>
        <button className="btn btn-reject" onClick={onReject}>Reject</button>
      </div>
    </div>
  );
}

function MessageBubble({ msg, onApprove, onReject }) {
  if (msg.role === 'user') {
    return (
      <div className="msg msg-user">
        <div className="msg-bubble msg-bubble-user">{msg.content}</div>
      </div>
    );
  }
  return (
    <div className="msg msg-assistant">
      <div className="msg-mark"><Icon name="trending-up" size={14} color="#fff" strokeWidth={1.75} /></div>
      <div className="msg-body">
        {msg.tools && msg.tools.map(t => <ToolCallBadge key={t} tool={t} />)}
        <div className="md">
          <MarkdownBlock text={msg.content} />
        </div>
        {msg.confirm && (
          <TradeConfirm
            order={msg.confirm}
            status={msg.confirmStatus}
            onApprove={() => onApprove(msg.id)}
            onReject={() => onReject(msg.id)}
          />
        )}
        <div className="msg-foot">
          <span className="msg-time">{msg.time}</span>
        </div>
      </div>
    </div>
  );
}

window.MessageBubble = MessageBubble;
