# Upstox Order Webhook — Design

Date: 2026-05-11
Status: Plan (not implemented)
Origin: 2026-05-11 TATACONSUM/JBMA/NIVABUPA multi-fill incident (postmortem TBD).

## Motivation

Today's incident demonstrated that the daemon cannot reliably tell whether
an SDK timeout means "Upstox didn't get the order" or "Upstox got the order
and processed it later." We deployed four client-side defense layers
(per-rule in-flight lock, ambiguous-no-revert, pre-fire idempotency scan,
post-timeout reconcile-by-tag) but they're all polling/inference. The
authoritative source — Upstox itself — has a webhook mechanism we haven't
been using.

Webhooks replace inference with a definitive push signal. Every order state
transition (`put order req received` → `open` → `complete` / `rejected`)
arrives at our endpoint in real-time, including `order_id`, `tag`,
`filled_quantity`, `average_price`. This lets us:

1. **Resolve "ambiguous" outcomes definitively.** SDK timeout no longer
   leaves the rule in limbo — within seconds the webhook tells us whether
   the order is live or rejected.
2. **Detect out-of-band orders.** User manually places/cancels via Upstox
   web — daemon learns instantly instead of next position-fetch poll.
3. **Replace fill-price backfill polling.** Today we poll `get_order_details`
   in a loop until the `complete` status appears (`scalp_session._backfill_fill_price`).
   Webhook delivers the fill in one push.
4. **Audit trail.** Every transition with broker-side timestamps, for free.

## Upstox payload format

Per docs (https://upstox.com/developer/api-documentation/webhook):

```json
{
  "update_type": "order",
  "user_id": "ABCD12",
  "exchange": "NSE",
  "instrument_token": "NSE_EQ|INE848E01016",
  "instrument_key": "NSE_EQ|INE848E01016",
  "trading_symbol": "NHPC-EQ",
  "product": "D",
  "order_type": "MARKET",
  "average_price": 0,
  "price": 0,
  "trigger_price": 0,
  "quantity": 1,
  "disclosed_quantity": 0,
  "pending_quantity": 1,
  "filled_quantity": 0,
  "transaction_type": "BUY",
  "order_id": "240221025997024",
  "order_ref_id": "57744821658411",
  "exchange_order_id": "",
  "parent_order_id": null,
  "order_request_id": "1",
  "order_timestamp": "2024-02-21 14:40:02",
  "exchange_timestamp": null,
  "validity": "DAY",
  "status": "put order req received",
  "status_message": "",
  "status_message_raw": null,
  "is_amo": false,
  "variety": "SIMPLE",
  "tag": null,
  "guid": null,
  "placed_by": "ABCD12"
}
```

Known `status` values observed: `put order req received`, `open`,
`trigger pending`, `validation pending`, `modified`, `complete`, `rejected`,
`cancelled`, `after market order req received`. (Will validate against live
events once endpoint is up.)

GTT order updates use `update_type: "gtt_order"` with a separate schema —
deferred (we don't use GTT yet at scale).

## Endpoint contract

Per Upstox: **"Should not require authentication. Should respond with a 2XX
status. Must be open to receive POST requests."**

- **URL:** `POST https://niftystrategist.com/api/webhooks/upstox/order`
- **Auth:** none (Upstox requirement). We compensate with payload-driven
  validation — no record creation from webhook, only updates to existing
  rows keyed on `order_id` we already know about.
- **Response:** 200 OK with empty body. Even on internal errors return 200
  so Upstox doesn't retry-spam; log + alert internally instead. Exception:
  if the payload is malformed enough that we can't even log it, 400.

### Caddy routing

```
niftystrategist.com {
    ...
    handle /api/webhooks/upstox/* {
        # No auth, public POST. Body size limit: 16 KB.
        request_body {
            max_size 16KB
        }
        reverse_proxy localhost:8000
    }
}
```

## Multi-tenant routing

We already store `User.upstox_user_id` (populated from `/v2/user/profile`
during OAuth). The webhook payload's `user_id` field is the same Upstox
internal id — look up the local user with a single indexed query.

Each user enters our single endpoint URL `https://niftystrategist.com/api/webhooks/upstox/order`
in their Upstox app's Postback URL field. No per-user URL needed; payload's
`user_id` does the routing.

**Setup friction:** every user has to update their Upstox app config once.
For Pranav (owner) we do it directly. For other users, the Settings page
already has a "Trading Settings → Upstox API Credentials" section — add a
new "Postback URL" info block there ("Set this in your Upstox app config:")
plus a copy-to-clipboard button.

## Database schema

New table `upstox_webhook_events`:

```sql
CREATE TABLE upstox_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    upstox_user_id VARCHAR(100) NOT NULL,
    update_type VARCHAR(32) NOT NULL,          -- 'order' | 'gtt_order'
    order_id VARCHAR(64),                       -- nullable for gtt
    gtt_order_id VARCHAR(64),                   -- nullable for order
    status VARCHAR(64) NOT NULL,
    tag VARCHAR(64),                            -- our client_request_id (40 chars + safety)
    instrument_key VARCHAR(64),
    transaction_type VARCHAR(8),
    quantity INTEGER,
    filled_quantity INTEGER,
    pending_quantity INTEGER,
    average_price NUMERIC(18,4),
    order_timestamp TIMESTAMP,                  -- Upstox's clock
    exchange_timestamp TIMESTAMP,
    status_message TEXT,
    raw_payload JSONB NOT NULL,                 -- full payload for forensics
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,                     -- null = still processing
    processed_outcome VARCHAR(32),              -- 'applied' | 'duplicate' | 'unknown_order' | 'mismatch' | 'error'
    processed_error TEXT
);

CREATE UNIQUE INDEX idx_uwe_dedup
    ON upstox_webhook_events (order_id, status, order_timestamp)
    WHERE order_id IS NOT NULL;

CREATE INDEX idx_uwe_user_received ON upstox_webhook_events (user_id, received_at DESC);
CREATE INDEX idx_uwe_tag ON upstox_webhook_events (tag) WHERE tag IS NOT NULL;
CREATE INDEX idx_uwe_order_id ON upstox_webhook_events (order_id) WHERE order_id IS NOT NULL;
```

The unique index makes duplicate webhook deliveries no-ops. Upstox may
retry; our INSERT will conflict and we ack 200 without re-processing.

## State updates triggered

### Monitor rules

Parse `tag` for pattern `rule:<id>:fire:<count>`:
- Look up the rule.
- If `status="complete"`:
  - Confirm `linked_order_id` set on the rule (write if missing).
  - For the matching `monitor_log` (joined on `order_id`), update `action_result`
    with fill data.
  - If a scalp/strategy chain expected fill confirmation, advance state.
- If `status="rejected"` or `"cancelled"`:
  - This is the resolution of an `ambiguous` timeout. Now we know it's
    definitively dead.
  - Call `daemon._revert_failed_fire()` retroactively: rearm the rule,
    restore `also_cancel_rules`, etc. (Currently we skip revert on ambiguous
    timeout precisely because we couldn't tell; webhook resolves the doubt.)

### Scalp sessions

Parse `tag` for pattern `scalp:<user_id>:<uuid12>`:
- Look up the open `scalp_session_log` for that session/event.
- If `status="complete"`:
  - Update entry/exit fill price + filled_quantity in the log row.
  - For an ENTRY: set `session.runtime.entry_price` from `average_price`,
    set `entry_time` to `exchange_timestamp`.
  - For an EXIT: stamp realized P&L, then trigger `_log_event` for the
    realized exit row.
- If `status="rejected"`:
  - If state is `HOLDING_*` and this was an exit attempt: leave HOLDING,
    let the exit-retry backoff path kick in.
  - If state is `IDLE` and this was an entry attempt: position never opened,
    clear `current_*` runtime fields (defensive — they should already be
    cleared, but webhook is authoritative).

### Cross-checks

On every webhook event with a known `order_id` that doesn't match a known
rule/scalp tag: log at WARN level with the full payload. This catches
orders placed by other channels (CLI tools, manual UI orders, chat agent
direct orders). Useful audit trail.

## Race-condition handling

### Webhook arrives before SDK call returns

Currently the daemon's `_execute_and_record` waits on `proxy.place_order`
to return before doing any state update. With webhooks, the `complete`
event might arrive in parallel.

Resolution: webhook processor only updates state for orders that exist in
our DB. If the rule/scalp doesn't yet have `linked_order_id` written, the
webhook stores the event and processes it lazily — when the SDK call
returns and writes `linked_order_id`, a follow-up job picks up pending
webhook events for that order_id and applies them.

Implementation: webhook handler does `INSERT INTO upstox_webhook_events`
unconditionally (subject to dedup constraint). A separate processor
function `apply_pending_webhook_events(order_id)` is called both from
the webhook handler (best-effort) AND from the daemon's post-SDK-call
path (definitive — ensures state stays consistent even if first attempt
failed).

### Out-of-order delivery

`put order req received` → `open` → `complete` is the expected sequence,
but Upstox might deliver them out of order under load. State machine
should be tolerant:

- Each `status` is a one-way transition. Once we mark a fill complete,
  ignore subsequent `open` events for that `order_id`.
- Final statuses (`complete`, `rejected`, `cancelled`) are sticky — never
  walk backward.
- Track `last_status_timestamp` per order; ignore older transitions.

### Webhook arrives after daemon already gave up

Most relevant to today's bug. Daemon SDK times out → marks ambiguous →
keeps fire_count incremented. Five minutes later webhook delivers
`complete`. Webhook processor finds the rule, confirms the fill, no state
change needed (rule is already in the right "consumed" state). Just
updates the `monitor_log` with fill data. Clean.

Inverse: SDK times out → ambiguous → webhook eventually says `rejected`.
Now we know the rule should be rearmed. Webhook processor triggers
`_revert_failed_fire`. Note: this only works if the rule's `chain_affected`
state can be reconstructed — we may need to persist `also_cancel_rules`
list in `monitor_logs` to support retroactive revert. (Quick check needed:
do we already?)

## Security (without auth)

Upstox's "no auth" requirement is a real concern. Mitigations:

1. **No record creation from webhook.** Webhook handler only UPDATEs rows
   keyed on `order_id` that exist in `monitor_logs` or `scalp_session_logs`.
   An attacker sending a fake `order_id` finds nothing to update; their
   event lands in `upstox_webhook_events` as `processed_outcome=unknown_order`.
2. **No financial action triggered by webhook alone.** Webhook can't *cause*
   a new order to be placed — it can only annotate orders we already placed.
   Revert-on-rejected is the riskiest action; mitigation: require the
   `order_id` in the webhook to match a known rule's `linked_order_id`
   AND the `user_id` in the payload to match that rule's user.
3. **Rate-limit at Caddy.** 100 req/min per source IP. Real Upstox traffic
   is bursty (one order = 3-4 events) but not infinite.
4. **Optional: IP allowlist.** Upstox publishes a static IP range for their
   webhook senders (TBD — need to confirm with support). Caddy `@upstox-ips`
   matcher.
5. **Idempotency unique index** prevents replay attacks via duplicates.
6. **Sanitize logging.** Don't log full payload to stdout (system journal),
   only to the events table. Payloads include `placed_by` which is PII.

## Implementation phases

### Phase 1 — passive observability (low-risk)

1. Caddy + FastAPI route accepts POSTs, validates payload shape, writes
   to `upstox_webhook_events`. No state updates. Always returns 200.
2. Pranav sets the Postback URL in his Upstox app.
3. Run for a day; verify payloads match docs, observe what statuses
   actually arrive, look for surprises.

### Phase 2 — backfill fills (low-risk, high-value)

1. Webhook handler also writes fill data (`average_price`,
   `filled_quantity`, `exchange_timestamp`) into `monitor_logs` and
   `scalp_session_logs` on `status=complete`.
2. Disable / remove the polling-based `_backfill_fill_price` in
   `scalp_session.py`. Saves Upstox API budget.

### Phase 3 — ambiguous resolution (medium-risk)

1. On `status=rejected/cancelled`, trigger retroactive revert of any
   rule fire we earlier marked `ambiguous`. Requires persisting
   `chain_affected` in `monitor_logs` (or a sibling table) so we can
   reconstruct what to revert.
2. Adjust scalp session state-machine accordingly.

### Phase 4 — out-of-band detection (nice-to-have)

1. Log + Telegram alert when a webhook arrives for an order whose tag
   doesn't match any rule/scalp (manual UI order, CLI order).
2. Sync into local `trades` table.

## Open questions

1. **Exact `status` enum.** Listed values come from doc samples; need to
   observe what we actually receive in production.
2. **Retry behavior.** What HTTP status does Upstox treat as "retry"?
   Docs say "respond with a 2XX" — we should test what happens on 5xx
   or timeout from our side.
3. **Order of webhook vs SDK response.** Empirically — does the webhook
   arrive before, during, or after `place_order` returns? If usually
   before, the SDK timeout becomes much less of a problem (webhook
   resolves it).
4. **GTT order updates** — we don't use GTT today, but if/when we do
   the schema is different and needs its own handler.
5. **Latency for late-arriving webhooks.** Today's `manual:recover:tata:`
   order took 8 minutes from our SDK timeout to Upstox processing it.
   Did the webhook fire at 8 minutes too? If yes, we'd catch it. If
   webhook arrived earlier, we'd catch it even sooner.
6. **IP allowlist for Caddy?** Need Upstox to confirm their webhook
   sender IPs are stable.

## Non-goals

- Replacing the polling-based reconciliation entirely. Webhooks are the
  primary signal but the existing layers stay as fallback for the case
  where webhooks are delayed/dropped.
- GTT order updates (phase 2+).
- Real-time client UI updates from webhook (websocket relay). Future.

## Files to add/edit

New:
- `backend/migrations/036_add_upstox_webhook_events.sql` (or next number)
- `backend/api/upstox_webhooks.py` — FastAPI router
- `backend/services/webhook_processor.py` — apply event → state machine

Edit:
- `backend/main.py` — mount router
- `backend/database/models.py` — `UpstoxWebhookEvent` ORM model
- `backend/monitor/daemon.py` — call `apply_pending_webhook_events(order_id)`
  after SDK return when `ambiguous=True`
- `backend/monitor/scalp_session.py` — same; also remove
  `_backfill_fill_price` polling in phase 2
- `backend/monitor/crud.py` — persist `chain_affected` in monitor_logs
  (phase 3 prerequisite)
- `frontend-v2/app/components/Settings.jsx` — instructions block + copy
  button for the Postback URL
- `Caddyfile` (prod server) — route + rate limit
