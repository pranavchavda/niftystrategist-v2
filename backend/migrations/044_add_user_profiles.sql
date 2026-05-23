-- 044_add_user_profiles.sql
-- Curated, always-injected per-user profile synthesized from accumulated memories.
-- Ported from EspressoBot (memory_enhancements.sql). This is the "frozen" profile that
-- gets injected into the prompt unconditionally (not semantically searched) — the
-- foundation of the prefix-cache-stable memory layout (Hermes-style).
-- See docs/plans/2026-05-23-prefix-cache-memory-port.md.
--
-- NS conventions: TIMESTAMP WITHOUT TIME ZONE, naive UTC (use utc_now()/datetime.utcnow()).

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(255) PRIMARY KEY,           -- user's email (matches memories.user_id)
    profile JSONB NOT NULL DEFAULT '{}',         -- structured profile
    profile_text TEXT,                           -- <=200-word markdown summary, injected verbatim
    last_synthesized TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    memory_count_at_synthesis INTEGER DEFAULT 0, -- staleness tracker: re-synth when count changes
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
