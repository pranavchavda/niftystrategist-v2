# Prefix-Cache Memory Refactor + EB Memory Port

**Date:** 2026-05-23 (Sat) → target: shippable before Monday 2026-05-25 market open
**Inspiration:** NousResearch Hermes agent memory architecture (see analysis in chat 2026-05-23)
**Related:** [[project_cross_thread_awareness]], [[project_eb_port_plan]], `docs/plans/2026-05-11-eb-port-plan.md`

## Motivation

Hermes keeps its LLM prefix byte-stable across a session so prompt caching hits on
the whole system-prompt + history, and pushes all volatile/query-specific content to
the tail (the current user turn). NS currently does the opposite: semantic memory
recall, datetime, scratchpad, tool-cache stats, recent-thread titles, and paper
portfolio are all injected via dynamic `@agent.instructions` / instruction-emitting
capabilities — i.e. **early in the prompt, before the message history**. Because they
change every turn, they bust the implicit cache for the entire (growing) history.

### Provider caching is real for our default model
- Default model: `z-ai/glm-5.1` (OpenRouter). **Z.AI GLM-5/4.x support implicit prompt
  caching** (automatic, no `cache_control` needed; reported in
  `usage.prompt_tokens_details.cached_tokens`, ~50% input discount). OpenRouter uses
  sticky routing to keep hitting the warm Z.AI cache.
- Implication: the only thing we must do is **keep the prompt prefix byte-stable and
  push variations to the tail**. No `cache_control` plumbing needed for GLM.
- `pydantic_ai.messages.CachePoint` is **Anthropic/Bedrock only** (filtered out for
  other models). It becomes a bonus when running on Claude; irrelevant for GLM.

## Pydantic AI 1.96 mechanics (by-the-book)

Confirmed from `~/.claude/skills/pydantic-ai-framework/references/pydantic-ai-llms-full.txt`
(refreshed 2026-05-23 from https://pydantic.dev/docs/ai/llms-full.txt):

1. **Static `instructions=` are auto-sorted before dynamic `@agent.instructions`**, so
   the static base prompt is already the cacheable prefix. (llms-full §Instructions,
   ~line 39424.) But dynamic instructions still sit **before message history**, so
   anything volatile there busts the cache for all history.
2. **Native capabilities** (`pydantic_ai.capabilities.AbstractCapability`) can emit
   instructions via `get_instructions()` AND hook the lifecycle. NS already uses these.
3. **`before_model_request(ctx, request_context) -> ModelRequestContext`** can modify
   the messages sent to the model. Appending a `ModelRequest([UserPromptPart(...)])` to
   `request_context.messages` injects content **at the tail**, on every model request,
   **without persisting it to stored history**. NS already does exactly this for
   steering (`orchestrator.py:1448 inject_steering`).

### The cache-stability argument
- Volatile block appended at the tail (after the current user turn) → never part of the
  cacheable prefix. Persisted history stays clean. Next turn reconstructs clean history
  from DB → prefix `[static instr][stable dynamic instr][clean u1..aN]` is byte-stable →
  cached. Only the new turn + its volatile block are uncached (unavoidable).
- **VERIFIED 2026-05-23**: NS persists via `main.py::save_assistant_message_to_db`
  (content-based: assistant text + tool_calls + reasoning), NOT by saving the request
  message list. So hook-injected `UserPromptPart`s (steering today, volatile context in
  Phase 4) are never written to the DB; next-turn history rebuilds from clean `Message`
  rows. **No save-time filter needed** — the argument holds as designed.
- **Frozen content** (user profile, optional session-start memory snapshot, session-stable
  trade-safety blocks) stays in instructions but must return the **same string every turn
  within a session** so it extends the stable prefix.

## Scope (decided with user 2026-05-23)

Phases 1–4 this weekend, tested well. Phase 4 (#1/#2 restructure) behind a flag,
**default ON for interactive chat, force-OFF when `is_awakening=True`** (autonomous
trade path stays on the proven instruction-injection path until validated post-Monday).
#7 (forked background-review nudge) deferred to next week.

---

## Phase 1 — Port EB curated user profile (additive, low risk)

The "frozen, always-injected, non-searched" profile — the foundation of the Hermes
design. EB source: `/home/pranav/apydanticebot/backend`.

- **DB**: new `user_profiles` table (port `migrations/memory_enhancements.sql`):
  `user_id PK, profile JSONB, profile_text TEXT, last_synthesized, memory_count_at_synthesis, created_at`.
  Adapt to NS conventions: naive `TIMESTAMP`, `utc_now()`.
- **Deps**: add `user_profile: Optional[str] = None` to `OrchestratorDeps`.
- **Load**: in `main.py` chat path, `SELECT profile_text FROM user_profiles WHERE user_id = :email`
  → `deps.user_profile` (mirror EB `main.py:2413`).
- **Inject**: new `UserProfileCapability(AbstractCapability)` with `get_instructions()`
  emitting `## USER PROFILE (Auto-synthesized)` — this is FROZEN/stable content, correct
  to keep in instructions. Register in `_get_capabilities()` under capabilities-v2.
- **Synthesis job**: port `jobs/memory_distillation.py::synthesize_user_profile()` —
  top ~100 active memories → LLM → structured JSON + ≤200-word markdown. Schedule nightly
  (APScheduler, after memory fade/consolidation). Use a current model (not gpt-4/4o).
- **Test**: profile loads, injects, survives empty/missing; synthesis idempotent.

## Phase 2 — Interrupted-turn memory guard (#6, defensive, low risk)

Don't extract/persist memories from crashed/partial awakening turns (the JSONDecodeError
class — strategies silently lost, half-finished state polluting recall).

- **Tag the partial-summary message** (`extra_metadata.crashed = true`) in
  `awakening_scheduler.py::_write_partial_summary_on_crash`, and have
  `scripts/extract_memories_daily.py` **exclude only that message** from the extraction
  input — NOT skip the whole conversation (a long thread that ended on a crash still has
  many good turns of facts; only the crash/partial turn is untrustworthy).
- Mirror Hermes: a backend can't tell partial-but-plausible from complete → gate at source.
- **Test**: a crash-tagged message is excluded from extractor input; surrounding good
  turns still produce memories.

## Phase 3 — Pre-compress memory rescue (#5, additive, low risk)

Before compaction deletes messages, extract durable facts so they survive.

- In `ConversationOps.compact_conversation()` (`database/operations.py`) / the auto-compact
  path (`main.py::_auto_compact_conversation`), call the memory extractor on the full
  message set **before** deleting, persisting new memories.
- Hermes `on_pre_compress` analogue. Worst case: a few extra memories.
- **Cost/latency note**: auto-compaction is a background task; this adds an LLM call (and
  charge) on the auto-trigger path. **Wrap extraction in try/except — compaction MUST
  proceed even if extraction fails**, or threads accumulate uncompacted.
- **Test**: compaction of a fact-bearing thread writes ≥1 memory before deletion;
  extractor failure still completes compaction.

## Phase 4 — Prefix-cache restructure (#1/#2, MEDIUM risk, flagged)

New flag `ENABLE_PREFIX_CACHE_LAYOUT` (default ON for chat, OFF when `is_awakening`).

- **Move volatile blocks from instructions → tail of `request_context.messages`** via a
  `before_model_request` hook (same pattern as `inject_steering`):
  - Semantic memory recall (`deps.user_memories`), datetime, scratchpad current state,
    tool-cache stats, recent-thread titles, paper portfolio.
  - Wrap in a fenced `<context>`-style block with a system note ("reference data, not new
    user input") — Hermes-style isolation.
  - **Inject once per run**: gate on `ctx.run_step` (first model request of the run) — same
    field the steering hook reads at `orchestrator.py:1473`. No deps state needed.
- **Keep in instructions (frozen prefix)**: static base prompt, `UserProfileCapability`,
  session-stable trade-safety blocks (live-mode, scalp guards, awakening mandate).
- **Force OFF on awakenings**: hook checks `ctx.deps.is_awakening` (and flag) and no-ops,
  leaving the legacy instruction path intact for the autonomous trade path.
- **Validation (acceptance gate, not optional)**: log `usage.prompt_tokens_details.cached_tokens`
  on chat responses; on the **second turn of a thread** confirm it's >0 and grows
  turn-over-turn. This is the only proof the refactor actually paid off.
- **Byte-stability is a hidden cliff**: `UserProfileCapability` (and any frozen instruction)
  must return **identical bytes** turn-over-turn within a session. Watch trailing whitespace,
  dict-key ordering, set/dict iteration. One char drift kills the cache for everything after.
- **Test**: hook injects at tail; no double-injection in tool loop (assert via `ctx.run_step`
  gate); awakening path bypasses; history not mutated; frozen `build(ctx) == build(ctx)`
  byte-equal across two simulated turns with same deps.

## Risk register
- Phase 4 touches the live prompt assembly. Mitigations: flag, awakening force-off, the
  injection pattern is already proven in `inject_steering`, history-clean assertion in tests.
- `ReinjectSystemPrompt` + awakening replay double-injection risk already noted in
  `orchestrator.py:1522` — keep that concern in scope when toggling capabilities-v2.
- Synthesis/extraction jobs must use current models per user pref (no gpt-4/4o).

## STATUS — 2026-05-23 (implemented, tested, unmerged)

All four phases implemented and unit-tested (23 new tests pass; 187 others pass;
the only suite failures are pre-existing `test_order_node_dedup.py` UDAPI100050
token errors in untouched `order_node/` code). Full suite still collects (700).

**Files added:** `migrations/044_add_user_profiles.sql`,
`jobs/memory_profile.py`, `agents/capabilities/volatile_context.py`,
`tests/test_user_profile_capability.py`, `tests/test_crash_memory_guard.py`,
`tests/test_precompact_rescue.py`, `tests/test_prefix_cache_layout.py`.
**Files edited:** `agents/orchestrator.py` (deps field, UserProfileCapability +
VolatileContextCapability registration, six volatile sections gated/routed to
shared builders), `agents/capabilities/{__init__,context_injection}.py`,
`main.py` (profile load + pre-compact rescue), `api/conversations.py` (rescue),
`services/{scheduler,workflow_engine,awakening_scheduler}.py`,
`scripts/extract_memories_daily.py`.

**Two manual deploy steps required (NOT done — outward-facing prod writes):**
1. Apply `migrations/044_add_user_profiles.sql` to Supabase. Until then Phase 1
   degrades gracefully (profile load try/excepts → None → capability emits "").
2. `ENABLE_PREFIX_CACHE_LAYOUT` defaults **ON** — Phase 4 is live on chat the
   moment this deploys (forced OFF on awakenings). To stage it off first, set
   `ENABLE_PREFIX_CACHE_LAYOUT=0` in prod `.env`.

**Validation gate (do this after deploy):** watch `[prefix-cache] usage:` log
lines. On the **2nd+ turn of a chat thread**, `cache_read` should be > 0 and grow.
If it stays 0, the prefix isn't stabilizing — investigate before trusting the win.
GLM caches at ~50% discount; cache_read>0 is the proof it's working.

## Known minor notes (non-blocking)
- **Tail section order ≠ legacy instruction order.** Tail emits memory →
  recent-threads → scratchpad → toolcache → paper → datetime; legacy emitted
  scratchpad/toolcache earlier. Functionally equivalent (model gets same info);
  cache doesn't care about within-tail order. Not "byte-identical layout".
- **Manual compact endpoint now runs the rescue extractor inline** (extra LLM
  call before the TOON summary). Auto-compact is backgrounded so invisible, but
  the user-triggered "Compact Thread" button waits longer (~10–60s). Ensure UI
  spinner. (try/except guards against hangs.)
- **Sentinel idempotency check matches literal `<volatile_context>`.** If a chat
  message ever contains that exact string the hook skips injection. Negligible
  for trading chat; a UUID-suffixed sentinel would be unbreakable if ever needed.

## Out of scope this weekend
- #7 forked background-review nudge (replaces cron extractor quality with turn-context).
  Bigger build; cron extractor stays as fallback. Next week.
