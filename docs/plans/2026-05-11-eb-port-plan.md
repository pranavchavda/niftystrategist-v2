# EspressoBot → NiftyStrategist Port Plan

**Date:** 2026-05-11
**Status:** Drafted, awaiting tomorrow's execution
**Source audit:** `/home/pranav/apydanticebot/` (EB) vs `/home/pranav/niftystrategist-v2/` (NS)

## Context

NS forked from EB months ago. EB has since evolved on three axes:
1. Memory management (real-use signal, identity-aware quality judge, agent-callable recall)
2. Composability (Pydantic AI `AbstractCapability` + `Hooks` pattern)
3. System prompt structure (capability-driven sections, `ReinjectSystemPrompt`)

## Version baseline

| | EB | NS | Target |
|---|---|---|---|
| pydantic-ai (today) | **1.86.1** | **1.79.0** | **1.96.0** for both (latest, released 2026-05-13) |
| pydantic-ai-claude-code | — | 0.8.1 (NS-only, unused) | **Remove from requirements.txt** — see Phase 0 |

**Sequencing decision 2026-05-14 (revised same day):** EB upgrades to **1.96.0 first, in parallel to this planning** — done by the user directly on the EB project. NS then ports from a 1.96-shape EB codebase. This flips the canary direction (EB validates the version), keeps Phase 1's "mechanical port" character intact (because EB will have done the API translations itself), and means NS never has to look at 1.86-era EB source.

### Known pydantic-ai API shifts since 1.86 (handled in EB's upgrade, not in this port)

Two deprecations to be aware of, both becoming hard breaks in v2 (June 2026):

| Deprecated (1.86-era) | Replacement (1.96+) |
|---|---|
| `Agent(history_processors=[...])` kwarg | `Agent(capabilities=[ProcessHistory(...)])` |
| `Agent.instrument` | `Instrumentation` capability |

**Both translations happen in EB's own 1.96 upgrade**, not here. When NS Phase 1 starts, EB's memory code will already be in the new shape. NS's job is mechanical copy + trading-domain adaptation, same as originally planned.

## Phase 0 — pydantic-ai upgrade audit (before any porting)

**Prerequisite:** EB's 1.96 upgrade is complete and merged. Verify before starting.

- [ ] Confirm EB on 1.96.0 (`cat /home/pranav/apydanticebot/pyproject.toml | grep pydantic-ai`) — if not, pause and finish that first
- [ ] Review pydantic-ai release notes **1.79 → 1.96** in full (~17 versions; focus on capability, hooks, instructions, history-processor, message-history, output-validator, `Agent` constructor signatures). Faster review now that EB has already done the translations — use EB's diff as a cheat sheet.
- [ ] **Remove `pydantic-ai-claude-code` from requirements.txt** during the upgrade. Audit confirmed it's not imported anywhere in NS (`grep -r "claude_code" --include="*.py"` returned zero hits 2026-05-14). It was an unused install. Also: subscription-proxy packages of this kind are Anthropic ToS-flagged with account-suspension precedent (openclaw users hit). See [[feedback-no-subscription-proxies]] — never re-add this or similar packages.
- [ ] Spike: bump NS `requirements.txt` to `pydantic-ai==1.96.0` in a branch, run full test suite (`backend/tests/`). Triage failures by category: deprecation warnings vs hard breaks vs unrelated.
- [ ] Verify orchestrator + sub-agent registration still works (`get_orchestrator_for_model`, `web_search`, `vision`)
- [ ] **Risk gates** (all must pass on 1.96 before Phase 1):
  - Awakening tests pass (`backend/tests/services/test_workflow_engine.py` and related)
  - Scalp session tests pass (`backend/tests/monitor/`)
  - Memory ops tests pass (`backend/tests/test_memory*`)
  - Manual smoke: chat session, an awakening run, a scalp session start/stop
- [ ] If 1.96 is too painful: fall back to highest stable version that passes risk gates. EB and NS diverging temporarily is acceptable — the goal is NS works, not NS matches EB exactly.

## Phase 1 — Mechanical memory ports (low risk, ~3 days)

### 1.1 Quality judge upgrade
**Files:** `backend/database/memory_quality_judge.py` (NS 344 lines → EB 445 lines)

- [ ] Port `_REJECT_PATTERNS` + `pre_filter_reject()` (EB lines 83-112). Replace Shopify regexes with NS-relevant:
  - Upstox JWT access tokens: `eyJ[\w-]+\.[\w-]+\.[\w-]+`
  - Instrument keys: `NSE_EQ\|`, `BSE_FO\|`, `NSE_FO\|`, `NSE_INDEX\|`
  - Order IDs (Upstox 18-digit numerics)
  - Database URLs, encryption keys, Fernet blobs
  - File paths under `cli-tools/`, `monitor/`, etc.
- [ ] Port identity-aware scoring prompt (EB lines 147-212). Rewrite "queryable state" examples for trading domain:
  - Portfolio positions, fund balance, current LTP, holdings — anything fetched via `nf-*` CLI
  - Forces `durability ≤ 3` for queryable-state facts
  - Recall-test: "would this help in an unrelated future chat?" → `actionability ≤ 3` if distracting

### 1.2 Memory schema migration
**Files:** new `backend/migrations/036_add_memory_used_count.sql`, `backend/database/models.py:299-325`

- [ ] Add columns: `used_count INTEGER DEFAULT 0`, `last_used_at TIMESTAMP`
- [ ] Add index: `idx_user_last_used ON memories(user_id, last_used_at)`
- [ ] Update `Memory` ORM model

### 1.3 Real-use signal end-to-end
**Files:** `backend/agents/memory_extractor.py`, `backend/scripts/extract_memories_daily.py`

- [ ] Port `used_memory_ids: list[int]` to extractor output schema (EB lines 34-38)
- [ ] Port secondary-task prompt section that asks the extractor to flag pre-existing memories that shaped assistant replies (EB lines 65-92)
- [ ] In `extract_memories_daily.py`: bump `used_count`, set `last_used_at = utc_now()` for each ID returned (mirror EB lines 200-220)
- [ ] Port `scripts/backfill_used_count.py` for one-shot historical backfill

### 1.4 Agent-callable memory tools
**Files:** `backend/agents/orchestrator.py` (add ~150 lines around `@self.agent.tool` block)

- [ ] Port `remember(content: str, category: str)` — dedupes via cosine >0.92 (EB `orchestrator.py:2642-2720`)
- [ ] Port `recall(query: str, sources=["memories","notes","threads"], limit=10)` — unified semantic search returning Markdown (EB `orchestrator.py:2720-2810`)
  - NS already has `Note` model, `MemoryOps.search_memories_semantic`, and conversation embeddings
- [ ] Port orchestrator system-prompt nudge about when to call these tools (EB commit `c8e3d15`)

## Phase 2 — Capabilities skeleton (medium risk, ~2 days)

### 2.1 Create capabilities directory
**Files:** new `backend/agents/capabilities/` (mirror EB structure)

- [ ] `__init__.py`
- [ ] `context_injection.py` — start with two classes only

### 2.2 First capability: MemoryCapability
- [ ] Subclass `AbstractCapability[OrchestratorDeps]`
- [ ] `get_instructions()` reads `ctx.deps.user_memories` and emits the section string (extract verbatim from current `_register_dynamic_instructions` at NS `orchestrator.py:1142-1151`)
- [ ] Wire in `_get_capabilities()` at NS `orchestrator.py:1386-1443`
- [ ] Gate with env flag `ENABLE_CAPABILITIES_V2`
- [ ] Add guard `if not _cap_v2 and ctx.deps.user_memories:` to prevent double-injection in the legacy dynamic instructions path
- [ ] Verify prompt-cache hash stability — wording must match byte-for-byte

### 2.3 Second capability: RecentThreadsCapability
- [ ] NS currently builds recent threads inline at `orchestrator.py:1323-1377`
- [ ] Move data fetching to `main.py` (pre-load into `OrchestratorDeps.recent_threads` before run)
- [ ] Refactor instructions block into capability
- [ ] Same `if not _cap_v2` guard pattern

### 2.4 ReinjectSystemPrompt (stdlib)
**File:** `backend/agents/orchestrator.py` (`_get_capabilities()`)

- [ ] Add `ReinjectSystemPrompt()` from pydantic-ai stdlib
- [ ] **Risk check before enable:** verify `services/workflow_engine.py:_load_thread_messages()` doesn't double-inject when both the rebuilt history and ReinjectSystemPrompt include the system prompt
- [ ] Test against an existing daily-thread awakening on dev backend
- [ ] **CRITICAL:** confirm `is_awakening` mandate text still appears at head of prompt during awakening replay

## Phase 3 — DO NOT PORT (decision logged for future-us)

These are tempting but unsafe for NS. Re-litigate only with strong evidence.

### 3.1 MutationConfirmationCapability + per-thread `auto_mode`
- **Why not:** NS HITL is more nuanced than EB's. Touching it risks:
  - Breaking `is_awakening` override at `orchestrator.py:1224-1242` (depends on mandate text in conversation history)
  - Bypassing F&O scalp session position management (`orchestrator.py:1173-1222`)
  - Conflicting with monitor daemon which places orders bypassing the agent entirely
- **Allowed:** adopt EB's render_ui wording verbatim inside NS's static SAFETY-1 prompt (wording-only, no behavior change)

### 3.2 LLM-summarizing history processor
- **Why not:** conflicts with NS's auto-compaction-at-100-messages (`api/conversations.py:948+`) and the per-day awakening thread pattern (`services/daily_thread.py`)
- NS's design is purpose-built for awakening replay; mid-turn summarization would break it

### 3.3 PromptClassifierCapability
- **Why not:** EB has thousands of tokens of optional reference corpora (Shopify, email style) worth keyword-gating. NS's optional sections (paper-trading status, TODO mode, awakening mode) are already dep-driven and small. Overkill.

## Phase 4 — Optional follow-ups (defer)

- [ ] One-shot memory cleanup pass after new judge live (port `scripts/memory_cleanup.py`)
- [ ] Memory distillation job + `user_profile` synthesis — helps awakenings where user isn't present, but needs new APScheduler job and design discussion first
- [ ] Reflections (Hermes-style persistent learnings) — separate `agent_reflections` table + retrieval. Useful but large surface area.

## Risk-flagged paths that must NOT regress

| Path | Why critical | Where |
|---|---|---|
| `is_awakening` mandate flow | Autonomous trading SAFETY-1 override | `orchestrator.py:1224-1242`, `services/workflow_engine.py`, `OrchestratorDeps.is_awakening` |
| `ACTIVE SCALP SESSIONS` injection | Live per-turn DB pull; positions owned by scalp manager | `orchestrator.py:1173-1222` |
| Live-trading-mode warnings | Prevents accidental real-money orders | `orchestrator.py:1153-1171` |
| Awakening replay path | Reconstructs `message_history` from DB; touches system prompt | `services/workflow_engine.py:_load_thread_messages()` |
| Trade monitor daemon | Order placement bypasses agent entirely | `backend/monitor/daemon.py` |
| F&O scalp session manager | Owns positions, has own state machine | `backend/monitor/scalp_session.py` |

Any capability that touches dynamic instructions must:
- Preserve exact wording (prompt-cache stability)
- Preserve section ordering (memories → reflections → recent threads → CURRENT SESSION → date/time)
- Keep `is_awakening` block intact

## Execution order recommendation

1. **Tomorrow morning:** Phase 0 (version audit + test suite spike on 1.86.1)
2. **If Phase 0 passes:** Phase 1.1 (quality judge — pure code, no schema change)
3. **Then:** Phase 1.2 + 1.3 (migration + extractor signal)
4. **Then:** Phase 1.4 (agent-callable tools)
5. **Validate on dev for a day** before Phase 2
6. **Phase 2 only after** memory ports proven stable

## Key file refs (NS side)

- `backend/agents/orchestrator.py:1023-1377` — dynamic instructions block (refactor incrementally)
- `backend/agents/orchestrator.py:1386-1443` — `_get_capabilities()` extension point
- `backend/database/memory_quality_judge.py` — judge port target
- `backend/database/models.py:299-325` — Memory model
- `backend/agents/memory_extractor.py` — extractor signal port
- `backend/scripts/extract_memories_daily.py:167-200` — used_count bump wiring
- `backend/services/workflow_engine.py` — ReinjectSystemPrompt compatibility check
- `backend/requirements.txt` — pydantic-ai pin to bump

## Key file refs (EB side, for copy reference)

- `backend/agents/orchestrator.py:1302-1443` — capability wiring example
- `backend/agents/capabilities/context_injection.py:24-134` — 5 capability examples
- `backend/agents/capabilities/mutation_confirmation.py:66-95` — HITL capability (reference only, do not port)
- `backend/agents/capabilities/prompt_classifier.py` — classifier (do not port)
- `backend/database/memory_quality_judge.py:83-212` — pre-filter + identity prompt
- `backend/agents/memory_extractor.py:34-92, 200-220` — used_memory_ids signal
- `backend/scripts/backfill_used_count.py` — historical backfill script

## Estimated effort

- Phase 0: 0.5 day
- Phase 1: ~3 days
- Phase 2: ~2 days
- Phase 3: skip
- Phase 4: ~1-2 days if pursued

**Total to production-ready capabilities + new memory: ~5-6 days**
