-- 045_add_daily_learnings.sql
-- Deterministic, always-injected daily carry-over learnings.
--
-- A dedicated pre-market summarizer (services/daily_learnings.py) reads each
-- user's daily trading thread for the most recent trading day — including any
-- post-close discussion the user had with the orchestrator — and distills it
-- into a headline + markdown bullets. The next day's daily thread injects the
-- most recent row verbatim (full text) plus the headlines of the prior 2 days.
--
-- This COMPLEMENTS the semantic memory pipeline (memories table / extract_memories_daily.py):
-- that table is semantically searched and injected by relevance; this one is a
-- deterministic, always-present "what did we learn yesterday" block.
--
-- NS conventions: TIMESTAMP WITHOUT TIME ZONE, naive UTC (use utc_now()/datetime.utcnow()).

CREATE TABLE IF NOT EXISTS daily_learnings (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trading_date    DATE NOT NULL,                 -- IST trading day the learnings are FROM
    headline        TEXT,                          -- one-sentence digest (used in rolling trail)
    learnings_text  TEXT NOT NULL,                 -- full markdown bullets, injected verbatim next day
    source_thread_id VARCHAR(255),                 -- daily thread the summary was distilled from
    created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    CONSTRAINT unique_daily_learning UNIQUE (user_id, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_learnings_user_date
    ON daily_learnings (user_id, trading_date DESC);
