-- 047_add_memory_block.sql
-- Managed memory block — a single, always-present, agent-curated "core memory"
-- per user (MemGPT/Letta-style).
--
-- Distinct from the two existing context layers:
--   * Auto-surfaced semantic memories — top-10 embedding matches per query.
--   * Session scratchpad (services/scratchpad_db.py) — thread-scoped, ephemeral.
--
-- The memory block is a living document the orchestrator itself rewrites
-- (current strategy stance, active experiments / tagged-trade tallies, open
-- context, recent lessons). It is injected into EVERY request's dynamic
-- instructions (chat AND awakenings), bounded to 6000 chars, and editable only
-- through the explicit nf-memory-block CLI tool the agent calls. Full-rewrite
-- semantics (MemGPT-style) — the agent re-curates the whole document each time.
--
-- ADDITIVE + backward-compatible: old application code that doesn't reference
-- these columns keeps working, so this can be applied to the shared Supabase
-- BEFORE the code that uses it deploys.
--
-- NS conventions: TIMESTAMP WITHOUT TIME ZONE, naive UTC (utc_now()/datetime.utcnow()).

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS memory_block TEXT,
    ADD COLUMN IF NOT EXISTS memory_block_updated_at TIMESTAMP;  -- naive UTC
