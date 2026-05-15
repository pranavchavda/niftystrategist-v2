# Awakening Phase Chains — Design Plan

**Date:** 2026-05-14
**Status:** Drafted, awaiting review
**Dependencies:** Waits on EB port plan **Phases 0 → 1 → 2** (pydantic-ai 1.96 upgrade, memory v2 ports, **and the capabilities/hooks skeleton**). Sequencing decision 2026-05-14: build phase chains on the capability/hooks canvas, not on today's `OrchestratorDeps`. Avoids double-refactor of the orchestrator. EB Phase 3 is explicitly DO-NOT-PORT; EB Phase 4 is optional follow-ups and can run in parallel with chains.
**Inspiration:** [anthropics/financial-services](https://github.com/anthropics/financial-services) `orchestrate.py` handoff loop + [pydantic-ai multi-agent programmatic handoff](https://pydantic.dev/docs/ai/guides/multi-agent-applications/)

## Problem statement

Today, one awakening = one monolithic `agent.run()`. Morning Scan does **scan + analyze + size + execute** in a single 5–10 minute run. This causes:

1. **Silent partial-result loss** — If the final response fails to parse (e.g. JSONDecodeError 2026-05-08), all in-flight agent work is lost. Strategies the agent *already deployed* via tool calls aren't recoverable because the run never wrote anything back to the thread. (TODO: `project_awakening_partial_results.md`)
2. **Frontend timeout on "Run now"** — `POST /api/awakenings/schedules/{id}/run` blocks for 5–10 min. UI shows "Failed" while the server keeps running. (TODO in `project_recurring_awakenings.md`)
3. **No resumability** — If the daemon crashes at step 3 of 4, there's no way to restart from step 3. Whole awakening has to be re-run, possibly placing duplicate orders.
4. **Monolithic context** — Sizing reasoning, candidate scanning, and execution reasoning all share one growing context window. By the execute phase the agent is reasoning over its own scan output.

## Concept

An awakening becomes a **chain of discrete phases**, each its own `agent.run()`. Each phase:
- Receives the previous phase's structured output as input
- Loads the same daily-thread history for continuity
- Writes its result back to the daily thread as a normal assistant message
- Persists a `WorkflowPhaseRun` row before signaling the next phase

Between phases, the orchestrator decides "what's next" by calling a new `next_phase` CLI tool — same mechanism as the existing `schedule_followup` tool, but for immediate-next-phase rather than time-deferred.

## Pydantic-AI alignment

Pydantic-AI (1.96 target) documents three multi-agent patterns:
1. **Agent-as-tool** — synchronous, parent blocks waiting for child. Not what we want; doesn't solve durability.
2. **Programmatic handoff** — app code drives sequential `agent.run()` calls, passing output from one to next. **This is the target.**
3. **Graph control flow** — heavyweight, overkill for our use case.

Our chain loop *is* programmatic handoff. The `next_phase` tool is the agent's way of saying "here's my output, here's what should run next, end my run." The application picks up that signal and starts the next `agent.run()`.

## Multi-mandate model

Today, `users.trading_mandate` is a single JSON blob — one mandate per user. Phase chains expose a structural need to split this: a `Morning Scan` chain operates under intraday rules, a `Swing Position Review` chain operates under swing rules, and a `Portfolio Rebalance` chain operates under portfolio rules. Different cutoffs, different risk-per-trade, different daily caps.

New shape: **N mandates per user, each tagged by `kind`**. The orchestrator sees all of them at all times (so it can reason about cross-mandate interactions — e.g. "this stock is already held under the swing mandate; don't scalp it intraday"), but only **one is in scope** for any given chain run. The active mandate is named in the system-prompt prelude and is the only one whose caps gate the `execute` phase.

### Schema

```sql
CREATE TABLE mandates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users.id ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,            -- "intraday", "swing", "portfolio", or user-defined
    kind VARCHAR(32) NOT NULL,            -- "intraday" | "swing" | "portfolio" | "custom"
    spec JSONB NOT NULL,                  -- risk_per_trade, daily_loss_cap, cutoff_time,
                                          -- allowed_instruments, auto_squareoff, etc.
    active BOOLEAN NOT NULL DEFAULT true, -- soft-disable without deleting
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

CREATE INDEX idx_mandates_user_active ON mandates(user_id, active) WHERE active = true;
```

`users.trading_mandate` stays in place during migration and is read as a fallback. Migration `037_add_mandates_table.sql` also seeds: for each user with a non-null `trading_mandate`, insert one row `name='intraday'`, `kind='intraday'`, `spec = users.trading_mandate`. After two weeks of running on the new table, drop the column in `038`.

### Orchestrator awareness

`get_or_create_daily_thread()` system-prompt prelude is extended:

```
Active mandates for this user:
- intraday: risk_per_trade ₹5k, daily_cap ₹15k, cutoff 15:15, ...
- swing:    risk_per_trade ₹50k, daily_cap none, cutoff none, ...
- portfolio: risk_per_trade — N/A, rebalance window, ...

This run is operating under: **intraday**
Cross-mandate awareness: do not enter intraday on a symbol already
in the swing or portfolio books unless explicitly directed. Check
`nf-portfolio` before sizing.
```

### CLI

`nf-mandate` gains `--name`:
- `nf-mandate list` — all mandates for user
- `nf-mandate show --name swing`
- `nf-mandate set --name swing --kind swing --spec @swing.json`
- `nf-mandate active --name intraday` (set the default for the active chat session)

### Schedule binding

`UserAwakeningSchedule` gains `mandate_id INTEGER REFERENCES mandates(id)`. The scheduler resolves it at run-time and threads it through to the first phase's `input_payload`. Backfill on migration: existing schedules bind to the user's `intraday` mandate.

### Cross-mandate edge cases worth flagging now

- **Daily cap interaction.** Intraday cap hit at 11:30. Does that block a swing exit triggered by a `pre_close` chain at 14:00? Plan: caps are per-mandate; swing exit goes through swing's cap, not intraday's.
- **Symbol held in multiple books.** Intraday scalp wants TCS, but TCS is a swing holding. Decision lives in the orchestrator's reasoning (with `nf-portfolio --book swing` to inspect), not in a hard rule. Add a `view_other_book` permission flag on each mandate if we want to be strict later.
- **Mandate edit during a running chain.** If the user edits the intraday mandate while a phase chain is mid-flight, the running chain should keep its snapshot. Store the resolved mandate spec in `workflow_runs.mandate_snapshot JSONB` at chain start; phases read from the snapshot, not the live row.

## Data model

New table `workflow_phase_runs` (migration `036_add_workflow_phase_runs.sql`):

```sql
CREATE TABLE workflow_phase_runs (
    id SERIAL PRIMARY KEY,
    workflow_run_id INTEGER NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    parent_phase_id INTEGER REFERENCES workflow_phase_runs(id) ON DELETE SET NULL,

    phase_name VARCHAR(64) NOT NULL,           -- e.g. "scan", "size", "execute"
    phase_index INTEGER NOT NULL,              -- 1-based order within the chain

    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|running|succeeded|failed|skipped
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    -- Payload handed in from the previous phase (validated JSON)
    input_payload JSONB,
    -- Structured output the agent produced (validated against phase output schema)
    output_payload JSONB,
    -- The thread message ID this phase's response was written to
    thread_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,

    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_phase_runs_workflow ON workflow_phase_runs(workflow_run_id);
CREATE INDEX idx_phase_runs_status ON workflow_phase_runs(status) WHERE status IN ('pending', 'running');
```

`WorkflowRun` itself gains:
- `current_phase_id INTEGER REFERENCES workflow_phase_runs(id)` — pointer to the in-flight phase
- `chain_template_id INTEGER REFERENCES chain_templates(id)` — names the template instance (see below)
- `mandate_snapshot JSONB` — frozen copy of the active mandate's `spec` at chain start, so mandate edits mid-chain don't change the rules under a running run

`workflow_phase_runs` also gets:
- `last_heartbeat_at TIMESTAMP` — phase emits a heartbeat every ~30s; watchdog uses this to detect unplanned stoppage
- `tool_calls JSONB` — captured pydantic-ai message-history dump (tool calls + results) for resume-from-extent
- `retry_count INTEGER NOT NULL DEFAULT 0` — bounded auto-retry budget
- `parent_phase_run_id INTEGER` — when a phase is a retry of an earlier crashed one, points back to the original

Status values: `pending | running | succeeded | failed | crashed | validation_failed`. (See [Failure & resume](#failure--resume) below.)

## Chain templates — hybrid code + DB

You leaned toward DB-stored templates so users can edit prompts and settings without a deploy. Worth doing, but **I'd push back on one part of it.** A chain template has two kinds of content:

| Part | Should live in… | Why |
|---|---|---|
| **Phase names, order, transition graph** | Code (engineered) | A bad transition graph silently breaks runs. Not a knob users should turn. |
| **Per-phase input/output JSON-schemas** | Code (engineered) | Schema-on-write is what gives us "never drop data on parse failure." Editable schemas drift from agent behaviour in subtle ways. |
| **Phase prompts, timeouts, model overrides, retry budget** | DB (user-editable) | These are the high-iteration knobs. Genuine product value to let users tune them. |
| **Mandate binding** | DB (per-schedule) | Already covered above via `UserAwakeningSchedule.mandate_id`. |

So: a **chain kind** is code-defined (`morning_scan_kind_v1` declares the phase graph + schemas). A **chain template** is a DB row that picks a kind and customises the prompts, models, and timeouts. Schedules bind to a template, not a kind directly. System defaults ship as seeded rows; users fork → edit. This keeps the durability rule intact while giving you the dynamism you want.

If you want fully-DB templates anyway (schemas included), the alternative is a `schema_jsonb` column on each phase row plus a server-side JSON-schema linter that runs on save. Doable but the failure modes are uglier — a user-edited schema that's syntactically valid but semantically wrong will only show up at phase exit time, mid-run.

### Schema

```sql
CREATE TABLE chain_kinds (
    -- this is just a registry of code-defined kinds, populated at startup
    name VARCHAR(64) PRIMARY KEY,             -- e.g. "morning_scan_kind_v1"
    description TEXT,
    phase_graph JSONB NOT NULL,               -- {phases: [{name, input_schema_ref, output_schema_ref, terminal}, ...]}
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE chain_templates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users.id ON DELETE CASCADE,  -- NULL for system defaults
    kind_name VARCHAR(64) NOT NULL REFERENCES chain_kinds(name),
    name VARCHAR(128) NOT NULL,               -- user-visible label
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, name, version)
);

CREATE TABLE chain_template_phases (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES chain_templates(id) ON DELETE CASCADE,
    phase_name VARCHAR(64) NOT NULL,          -- must match one of kind.phase_graph.phases[].name
    prompt_template TEXT NOT NULL,            -- Jinja-style {{ payload.x }} substitution
    timeout_seconds INTEGER NOT NULL DEFAULT 180,
    model_override VARCHAR(64),               -- nullable; falls back to user.preferred_model
    retry_budget INTEGER NOT NULL DEFAULT 1,  -- max auto-retries on crash (not on failure)
    UNIQUE (template_id, phase_name)
);
```

### Initial kinds (code-defined, seeded into `chain_kinds` at startup)

**`morning_scan_kind_v1`** — 4 phases:
```
scan       → output: {candidates: [{symbol, signal, rationale}, ...]}
analyze    → input:  {candidates: [...]}
             output: {analyzed: [{symbol, entry_zone, sl_zone, target_zone, conviction, rationale}, ...]}
size       → input:  {analyzed: [...], active_mandate: {...}, available_margin: float}
             output: {trade_specs: [{symbol, qty, entry, sl, target, side}, ...]}
execute    → input:  {trade_specs: [...]}
             output: {placed: [{order_id, symbol, status}, ...], skipped: [{symbol, reason}, ...]}
```

**`mid_day_check_kind_v1`** — 2 phases (review → adjust)
**`pre_close_kind_v1`** — 2 phases (squareoff-decisions → execute)
**`post_close_review_kind_v1`** — 1 phase (review only; cannot execute)
**`swing_review_kind_v1`** — 2 phases (review → place-or-adjust); bound to swing mandate
**`portfolio_rebalance_kind_v1`** — 3 phases (assess → propose → execute); bound to portfolio mandate

Output validation failures mark the phase `validation_failed` but **preserve `output_payload` raw** for inspection — the partial-result-loss bug demands we never drop data on parse failure.

## The `next_phase` CLI tool

New file: `backend/cli-tools/automations/next_phase.py`

Mirrors `schedule_followup.py` in shape. The orchestrator calls it when it's done with the current phase and wants to hand off:

```bash
nf-next-phase --phase-run-id 1234 \
  --next-phase analyze \
  --payload '{"candidates": [...]}'
```

Behavior:
1. Validates `--next-phase` is the legal successor in the chain template
2. Validates `--payload` against the next phase's input schema
3. Marks current `workflow_phase_runs` row `succeeded`, stores `output_payload`
4. Creates the next `workflow_phase_runs` row in `pending` status with `input_payload` set
5. Returns `{"ok": true, "next_phase_id": 1235}` (or validation errors)
6. The orchestrator, on seeing `ok: true`, naturally terminates its run

A separate **phase dispatcher** (see below) picks up pending phase runs and starts them.

## Phase dispatcher

New service: `backend/services/phase_dispatcher.py`

Runs as part of the FastAPI lifespan (not a separate process — phase runs are infrequent, ~4 awakenings × 4 phases × 1 user = 16/day initially).

Loop:
1. Every 5 seconds, `SELECT * FROM workflow_phase_runs WHERE status = 'pending' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED`
2. Mark `running`
3. Load the chain template, look up the phase's prompt template
4. Load daily-thread history via existing `_load_thread_messages()`
5. Build the orchestrator input: `prompt_template.format(payload=input_payload, mandate=user.trading_mandate)`
6. Run `orchestrator.agent.run(input, message_history=history, deps=OrchestratorDeps(is_awakening=True, current_phase_id=phase.id))`
7. On completion: validate output, write thread message, embed, mark `succeeded`
8. On exception: log full stack trace, mark `failed`, store `error_message`. **Do not** auto-cancel the chain — leave pending follow-ups intact so a manual retry can resume.

The dispatcher is *not* a scheduler — APScheduler still fires the **first** phase at 09:20 IST. The dispatcher only picks up subsequent phases the orchestrator queues via `nf-next-phase`.

## Mandate enforcement (cross-cutting)

The trading mandate is already injected into the daily thread's system message. With phase chains it gains extra mileage:
- `size` phase output schema enforces `qty × entry ≤ mandate.risk_per_trade × capital`
- `execute` phase verifies cumulative day P&L hasn't crossed `mandate.daily_loss_cap` before placing
- `execute` is the only phase whose system prompt grants `nf-order` permission (via per-phase prompt scoping)

This is the lighter-weight cousin of the role-split idea — instead of three different agent definitions, one orchestrator with per-phase prompt sections that gate tool usage by convention.

## Frontend "Run now" fix

`POST /api/awakenings/schedules/{id}/run` becomes:
1. Create the `WorkflowRun` + first `workflow_phase_runs` row (status `pending`)
2. Return `{run_id, status: "started"}` immediately (HTTP 202)
3. The dispatcher picks it up within ~5 seconds

New endpoint: `GET /api/awakenings/runs/{run_id}` returns the chain's current state — phases completed, current phase, last error if any. Frontend polls this for live status (1–2 second interval while running).

## Failure & resume

Three terminal failure modes, treated differently:

| Status | Cause | Auto-retry? | Resume strategy |
|---|---|---|---|
| `crashed` | Unplanned stoppage — process died, dispatcher restarted, heartbeat timed out | **Yes, up to `retry_budget`** (default 1) | Resume-from-extent (see below) |
| `failed` | Clean exception during `agent.run()` (e.g. tool error, model API failure) | **No** | Manual review; resume button optional |
| `validation_failed` | Output didn't match phase output schema | **No** | Manual review; output is preserved raw for inspection |

### Heartbeat & crash detection

- Each phase's dispatcher loop writes `last_heartbeat_at = now()` every 30 seconds while `status='running'`. This is a dispatcher-side write, not an agent tool call — the agent can be fully in-flight and we still know it's alive because the executing thread is alive.
- A watchdog inside `phase_dispatcher.py` runs every 60 seconds:
  ```sql
  UPDATE workflow_phase_runs
     SET status = 'crashed', error_message = 'heartbeat timeout'
   WHERE status = 'running' AND last_heartbeat_at < now() - interval '5 minutes';
  ```
- Crashed phases with `retry_count < retry_budget` are auto-picked for retry after a 60-second cooldown.

### Resume-from-extent

The hard part. When a phase crashes mid-run, the agent may have already:
- Written assistant messages to the daily thread
- Called `nf-order` and placed real orders
- Created monitor rules or scalp sessions
- Called read-only tools many times (cheap to redo)

The retry phase needs to know what was already done and **not duplicate** the irreversible parts. Two angles, both used:

**1. Tool-call audit captured in `tool_calls` JSONB.** After every model turn, the dispatcher serialises the pydantic-ai message history into `workflow_phase_runs.tool_calls` (append-only within the phase). On crash detection, this column is the source of truth for what the prior attempt did. The retry phase loads this and is prompted explicitly:

```
Your prior attempt at this phase crashed at <timestamp>. Here is the
record of work it completed before crashing:
- Tools called: <list with arguments + results>
- Orders placed: <list from nf-order outputs>
- Monitor rules created: <list>

DO NOT REPEAT IRREVERSIBLE ACTIONS. Continue from where the prior
attempt left off. If unsure whether an action was completed, prefer
to check current state (nf-portfolio, nf-monitor list, etc.) before
re-attempting.
```

**2. Client-side dedup keyed by Upstox `tag`.** Upstox's [Place Order v3](https://upstox.com/developer/api-documentation/v3/place-order/) has a `tag` field — free-form label, **not** server-enforced unique. We use it as a *carrier* of our idempotency key, then dedup client-side. Concretely:
   - `nf-order` gains `--tag <key>` flag. The dispatcher derives `tag = "nf:p<phase_run_id>:<short-intent-hash>"` (fits comfortably in Upstox's tag length budget — needs final verification, but well under typical 40-char limits).
   - **Pre-place check**: before placing, `nf-order` queries today's orders filtered by tag prefix `nf:p<phase_run_id>:`. If a matching `<intent-hash>` exists, skip and return the existing order ID. This is a small race window (two concurrent retries could both check + both miss + both place), bounded by the dispatcher's `FOR UPDATE SKIP LOCKED` (only one retry of a given phase row runs at a time) and a status-precondition on manual `/resume` (only valid if phase is terminal).
   - **Post-execute reconciliation**: at end of `execute` phase, the dispatcher compares the `size` phase's `trade_specs` to actual orders placed under this run's tag prefix. Any extra orders or missing intents are flagged in the phase output and the daily-thread message, *and* surfaced via a `mandate_violation` or `reconciliation_drift` event the orchestrator can see in subsequent phases.
   - `nf-monitor add-*` already has names; resume can check `nf-monitor list` and skip duplicates by name.
   - Scalp session creates are already idempotent by session name.

The audit layer (angle 1) is the always-on safety net. Tag-based dedup is best-effort; reconciliation catches the residual cases. Combined, the residual risk is "two orders placed in the race window before either could see the other's tag" — bounded but not zero. Open-eyed acceptance, not a bulletproof guarantee.

**Bonus from tags**: every chain-placed order is queryable by tag prefix → "what did this run execute?" / "what did morning scans place this week?" become one API call. Worth threading even if we never use the dedup property.

### Endpoints

- `POST /api/awakenings/runs/{run_id}/resume` — manual resume of a `failed` or `validation_failed` phase. Creates a fresh `workflow_phase_runs` row with `parent_phase_run_id` pointing to the failed one, preserving audit. Same resume-from-extent prompt is applied.
- `POST /api/awakenings/runs/{run_id}/resume?from_phase=N` — re-run starting from an earlier phase (e.g. re-do sizing with fresh margin data). Useful for ops.
- `GET /api/awakenings/runs/{run_id}/extent` — returns the prior phase's `tool_calls` so the UI can show "what was already done" before the user clicks resume.

## Migration path — start with Morning Scan only

Phase 1 of the rollout doesn't touch existing awakenings. It ships:
- Schema migration `036`
- `next_phase` CLI tool + phase dispatcher
- One chain template: `morning_scan_v1`
- A feature flag on `UserAwakeningSchedule.metadata` JSON: `{ "chain_template": "morning_scan_v1" }`. When set, the scheduler dispatches via the phase chain; when unset (default), it runs monolithically as today.
- Apply only to Pranav's Morning Scan, run for 1 week.

If the week is clean, port Mid-Day, Pre-Close, Post-Close one at a time. Other users untouched.

## Phases of work

### Phase 0 — Prerequisites
- [ ] **EB port plan complete through Phase 2** (pydantic-ai 1.96 upgrade + memory v2 + capabilities/hooks skeleton merged). This is the hard prerequisite — chains build on the capability canvas.
- [x] Chain-template storage: **hybrid** (code-defined kinds, DB-defined templates)
- [x] Upstox order idempotency: **no `client_order_id`** — use `tag` field + client-side dedup + post-execute reconciliation
- [ ] Confirm Upstox `tag` field max length (assumed ≤40 chars; format `nf:p<phase_run_id>:<8-char-hash>` is ~25 chars — should be safe)
- [ ] Decide whether `OrchestratorDeps` extensions (`current_phase_id`, `active_mandate_id`, `chain_template_snapshot`) become a dedicated `PhaseChainCapability` or stay as deps fields. Best assessed once the capability skeleton lands.

### Phase 1A — Multi-mandate (independent ship, ~2 days)
This phase has no dependency on chain plumbing. Ship it alone if useful.
- [ ] Migration `037_add_mandates_table.sql` (table + backfill from `users.trading_mandate`)
- [ ] ORM model `Mandate`; relationship on `User`
- [ ] `nf-mandate` CLI extensions: `list`, `--name`, `show --name`, `set --name --kind`, `active --name`
- [ ] `api/mandates.py` CRUD endpoints
- [ ] `frontend-v2/app/routes/mandates.tsx`: list view + per-mandate edit (was single-mandate)
- [ ] `get_or_create_daily_thread()` prelude lists all active mandates + flags the in-scope one
- [ ] `UserAwakeningSchedule.mandate_id` column + UI selector
- [ ] **Drop `users.trading_mandate` column scheduled for `038` after 2 weeks of dual-write**

### Phase 1B — Chain foundation (~3 days)
- [ ] Migration `036_add_workflow_phase_runs.sql` (phase runs table + workflow_runs additions)
- [ ] Migration `039_add_chain_template_tables.sql` (chain_kinds, chain_templates, chain_template_phases)
- [ ] ORM models for `WorkflowPhaseRun`, `ChainKind`, `ChainTemplate`, `ChainTemplatePhase`
- [ ] `backend/services/phase_chains/kinds.py` — code-defined kinds (`morning_scan_kind_v1` first), populates `chain_kinds` table at startup
- [ ] `backend/services/phase_chains/registry.py` — `get_template(id)`, `validate_phase_input/output`, transition graph check
- [ ] Seed system-default templates per kind during migration
- [ ] Unit tests: schema validation, transition graph rejection, missing-phase rejection

### Phase 2 — The `next_phase` tool (~2 days)
- [ ] `backend/cli-tools/automations/next_phase.py` — argparse, schema validation, DB write
- [ ] `nf-next-phase` shim in `cli-tools/`
- [ ] Orchestrator system prompt section: when `is_awakening=True` and `current_phase_id` is set, document the chain template inline so the agent knows the legal next-phase set
- [ ] Tests: tool rejects illegal transitions, malformed payloads

### Phase 3 — Phase dispatcher + heartbeat (~4 days)
- [ ] `backend/services/phase_dispatcher.py` — `start_dispatcher()`, `_pick_pending()`, `_execute_phase()`, `_heartbeat_loop()`, `_watchdog_loop()`
- [ ] FastAPI lifespan integration in `main.py`
- [ ] Reuse `_load_thread_messages()` and `_write_followup_to_thread()` from `workflow_engine.py`
- [ ] Embed thread messages via existing `embed_thread_immediately()` after each phase
- [ ] Per-phase timeout from `chain_template_phases.timeout_seconds`
- [ ] Heartbeat write loop (30s interval) for running phases
- [ ] Watchdog detects `running` phases past 5-min heartbeat staleness → marks `crashed`
- [ ] Tool-call audit: after each agent turn, append pydantic-ai message-history dump to `tool_calls` JSONB
- [ ] Failure mode: `crashed` auto-retries up to `retry_budget`; `failed` and `validation_failed` need manual resume

### Phase 4 — Resume-from-extent (~4 days)
- [ ] `_execute_phase()` checks `parent_phase_run_id`; if set, loads parent's `tool_calls` and prepends a resume prompt
- [ ] System-prompt template for resume context (lists tools called, orders placed, monitor rules created)
- [ ] `nf-order --tag` flag — derives `nf:p<phase_run_id>:<intent-hash>`, threads through to Upstox `tag` field
- [ ] `nf-order` pre-place dedup check — queries today's orders by tag prefix, skips on match
- [ ] Post-execute reconciliation: compare `size` phase's `trade_specs` to orders placed under run's tag prefix; surface drift in phase output
- [ ] `nf-monitor add-*` resume-safety: rejects duplicate-by-name
- [ ] Tests: simulated mid-phase crash → auto-retry → verify no duplicate orders via tag check
- [ ] Tests: simulated reconciliation-drift scenario (manual order placed mid-run, surfaced in output)

### Phase 5 — Schedule integration (~2 days)
- [ ] `_execute_awakening_job()` in `services/scheduler.py`: if `schedule.chain_template_id` set, create `WorkflowRun` + snapshot mandate spec + first `workflow_phase_runs` row, return immediately
- [ ] When unset: existing monolithic path (no regression)
- [ ] `POST /api/awakenings/schedules/{id}/run` returns HTTP 202 in chain mode
- [ ] `GET /api/awakenings/runs/{id}` endpoint for status polling
- [ ] `GET /api/awakenings/runs/{id}/extent` for resume-preview

### Phase 6 — Frontend (~3 days)
- [ ] Mandates page: multi-mandate UI (shipped in 1A; refresh here if needed)
- [ ] Schedule editor: chain-template selector + mandate selector
- [ ] `AwakeningRunStatus` component: polls `/api/awakenings/runs/{id}`, shows phase progress, current phase, retry count
- [ ] Failed/crashed-phase resume button with extent preview
- [ ] Template editor (chain-template prompts/timeouts/models per phase) — admin-only initially

### Phase 7 — Production trial (~1 week)
- [ ] Enable `morning_scan_kind_v1` on Pranav's Morning Scan only, bound to `intraday` mandate
- [ ] Daily review: phase durations, output-schema hits, crash/retry stats
- [ ] **Success criteria:**
  - No silent partial-result losses (every phase produces a persisted output OR a logged failure)
  - "Run now" returns in <2s
  - At least one auto-resume from `crashed` works in the wild without duplicate orders (verified via tag dedup + reconciliation)
  - Reconciliation correctly surfaces a drift in at least one synthetic test
  - Resume-from-failure works at least once when manually triggered
- [ ] If clean for 5 trading days: port Mid-Day Check, then Pre-Close, then Swing Review

## Risks & open questions

1. **Chain kind churn.** Output schemas will need iteration once the agent runs in production. Plan: version kinds (`morning_scan_kind_v1` → `_v2`) and let templates pin to a kind version. Don't auto-migrate template rows.

2. **Cross-phase reasoning loss.** Today the agent in the execute phase remembers *why* it picked the candidates because it did the scanning. With chain phases, the analyze-phase reasoning is in the thread history, but not in the orchestrator's working memory. **Mitigation:** the `analyze` phase output schema includes `rationale` text, surfaced to the `execute` phase via input payload (not just thread scrollback).

3. **Mandate drift between phases.** If the daily P&L cap is hit *between* `size` and `execute`, we'd still execute. **Mitigation:** the `execute` phase prompt requires a fresh mandate check via `nf-mandate show --name <active>` as its first tool call. The mandate snapshot on `WorkflowRun` is for "don't change the rules mid-chain"; the live cap check is a separate, runtime concern.

4. **Cross-mandate symbol overlap.** Intraday wants to scalp a stock the swing book is holding. No hard rule today — orchestrator must reason. May need a `block_overlap_with: [swing, portfolio]` flag on the intraday mandate spec once we see how this plays out.

5. **Phase dispatcher single-instance assumption.** Multiple FastAPI workers would all poll. **Mitigation:** `SELECT ... FOR UPDATE SKIP LOCKED` is the standard Postgres pattern; safe for N workers. Current NS prod runs single-worker uvicorn, but designing for multi-worker now is cheap.

6. **Awakening duration vs phase chain latency.** A 4-phase chain has 4× the orchestrator-warmup cost. For Morning Scan that's maybe +30s total, acceptable. For something tight like a real-time scalp entry, chain phases are wrong — use existing monolithic path.

7. **Tool-call attribution for trade audits.** A trade placed in `execute` phase needs to be traceable back to which `scan` decided on it. The `parent_phase_id` chain + `chain_template` name make this queryable, but UI for it is out of scope here.

8. **Heartbeat false positives.** A perfectly healthy phase with a 6-minute LLM call would trigger the watchdog. **Mitigation:** heartbeat is dispatcher-side, not agent-side — written every 30s by the executing thread regardless of whether the agent is mid-call. False positives only happen if the executing thread itself is blocked on GIL/IO, which means the process is effectively dead anyway.

9. **Best-effort idempotency, not bulletproof.** Upstox has no server-enforced idempotency key. We carry our key in the `tag` field and dedup client-side via a pre-place tag query. **Race window**: two concurrent retries could both check + both miss + both place. Bounded by `FOR UPDATE SKIP LOCKED` (only one retry of a phase row at a time) and status-precondition on `/resume` (only valid for terminal phases). Post-execute reconciliation catches residual drift but cannot prevent it. Residual risk is open-eyed accepted.

10. **DB templates editable while running.** A user edits a template mid-chain. Snapshot the resolved phase prompts onto `WorkflowRun.template_snapshot JSONB` at chain start, same as mandate. Add to schema if Phase 1B confirms this is wanted.

## What this does NOT do

- **Does not split the orchestrator into multiple agent definitions.** Same orchestrator runs each phase, just with different inputs and (eventually) different per-phase prompt scoping.
- **Does not introduce subagent depth.** Already capped at 1 today via `web_search`/`vision`; phase chains are *serial peers*, not nested.
- **Does not change interactive chat.** Phase chains are awakening-only. Manual chat sessions stay one `agent.run()` per message.
- **Does not solve the role-split / executor-isolation question.** That's a separate, larger structural change. Phase chains are the cheaper, less-invasive starting point that gets durability + resumability without the "one writer" architectural commitment.

## Files to be created / modified

**New:**
- `backend/migrations/036_add_workflow_phase_runs.sql`
- `backend/migrations/037_add_mandates_table.sql`
- `backend/migrations/038_drop_users_trading_mandate.sql` (deferred 2 weeks)
- `backend/migrations/039_add_chain_template_tables.sql`
- `backend/services/phase_chains/__init__.py`
- `backend/services/phase_chains/kinds.py` (code-defined chain kinds)
- `backend/services/phase_chains/registry.py` (loaders, validators, transition checks)
- `backend/services/phase_chains/resume.py` (extent extraction + resume-prompt builder)
- `backend/services/phase_dispatcher.py` (dispatcher, heartbeat, watchdog)
- `backend/api/mandates.py`
- `backend/cli-tools/automations/next_phase.py`
- `backend/cli-tools/nf-next-phase`
- `backend/tests/services/test_phase_chains.py`
- `backend/tests/services/test_phase_dispatcher.py`
- `backend/tests/services/test_phase_resume.py`
- `backend/tests/api/test_mandates.py`
- `frontend-v2/app/components/AwakeningRunStatus.jsx`
- `frontend-v2/app/components/ChainTemplateEditor.jsx`

**Modified:**
- `backend/database/models.py` (`Mandate`, `ChainKind`, `ChainTemplate`, `ChainTemplatePhase`, `WorkflowPhaseRun`; updates to `User`, `WorkflowRun`, `UserAwakeningSchedule`)
- `backend/services/workflow_engine.py` (`_load_thread_messages`, `_write_followup_to_thread` made re-usable; existing path preserved as the non-chain branch)
- `backend/services/scheduler.py` (`_execute_awakening_job` branches on `schedule.chain_template_id`; resolves mandate; snapshots both)
- `backend/services/daily_thread.py` (system-prompt prelude lists all mandates, flags active)
- `backend/api/awakenings.py` (run-status endpoint, extent endpoint, resume endpoint, 202 response, mandate_id on schedule create/update)
- `backend/agents/orchestrator.py` (system prompt addition for chain mode + multi-mandate awareness)
- `backend/cli-tools/automations/mandate.py` (multi-mandate CLI: `list`, `--name`, `set --name --kind`, `active`)
- `backend/cli-tools/automations/order.py` (`--tag` flag wired to Upstox `tag` field, plus pre-place tag-query dedup)
- `backend/services/phase_chains/reconciliation.py` (post-execute drift detection between `trade_specs` and placed orders)
- `backend/main.py` (lifespan startup for dispatcher + heartbeat + watchdog)
- `frontend-v2/app/routes/mandates.tsx` (multi-mandate list/edit; chain-template + mandate selectors on schedule editor)

## Memory entry to add after kickoff

Add `project_awakening_phase_chains.md` once implementation starts. Link from MEMORY.md under TODO section.
