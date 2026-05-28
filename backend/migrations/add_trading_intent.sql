-- Agent's self-authored trading intent/theses, rewritten each awakening.
-- Full-rewrite-each-turn: each `nf-intent set` inserts a NEW row; the snapshot
-- injects only the latest (newest wins). Accumulated rows = the intra-day trail
-- ("log") of how the agent's thinking evolved. Intent only (why/plan/
-- invalidation) — never live positions/P&L/levels. Scoped to the daily thread.

CREATE TABLE IF NOT EXISTS trading_intent (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    thread_id   VARCHAR NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_trading_intent_thread_id  ON trading_intent (thread_id);
CREATE INDEX IF NOT EXISTS ix_trading_intent_user_id    ON trading_intent (user_id);
CREATE INDEX IF NOT EXISTS ix_trading_intent_created_at ON trading_intent (created_at);
