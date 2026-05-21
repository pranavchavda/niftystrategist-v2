# Telegram Integration

**Date:** 2026-05-20
**Status:** Plan — not started
**Goal:** Multi-user Telegram bot for (1) notifications, (2) chatting into the day's mandate thread on the go.

## Motivation

- Awakenings produce results we currently only see by opening the NS web UI.
- Monitor rules fire silently aside from internal logs (FINCABLES-style outages stay invisible until checked).
- Travel / phone-only days = no NS access. Telegram makes the agent reachable from anywhere.
- Multi-user friendly: Ashok benefits too without us building a mobile app.

Reference: NousResearch/hermes-agent has a strong, FOSS Telegram adapter — multi-session topics, command surface, capability checks. Steal patterns, not code structure (their `BasePlatformAdapter` abstracts across many platforms — we only need telegram).

## Phased rollout

### Phase 1 — Outbound notifications

**Per-user bot. Each user creates their own bot via BotFather and pastes the token into NS Settings.** This isolates chat traffic + token blast radius per user and sets us up cleanly for Phase 2 inbound chat.

DB changes (migration `036_add_telegram.sql`):
- `users.telegram_bot_token_encrypted` BYTEA NULL — Fernet-encrypted bot token (reuse existing `ENCRYPTION_KEY`)
- `users.telegram_bot_username` VARCHAR NULL — cached from `getMe`, display only
- `users.telegram_chat_id` BIGINT NULL — bound on first `/start` (or `/confirm` after `/start`)
- `users.telegram_paired_at` TIMESTAMP NULL
- `users.notification_prefs` JSONB DEFAULT '{}' — per-category on/off

Backend additions:
- `backend/services/telegram_notifier.py` — `notify(user_id, category, text, buttons=None)`. Resolves user's bot token + chat_id from DB, decrypts, sends via that user's Bot API. No-op if unpaired or category disabled. Uses a per-user `Bot` client cache to avoid rebuilding `httpx` pools on every call.
- `backend/api/telegram.py`:
  - `POST /api/telegram/bot-token` — body `{token}`. Validates via `getMe`, encrypts, stores, returns bot username. Triggers reload of the user's Application.
  - `DELETE /api/telegram/bot-token` — clears token + chat_id. Stops the user's Application.
  - `GET /api/telegram/status` — returns `{configured, paired, bot_username, chat_id}`.
- `backend/telegram_bot/app.py` — multi-tenant service. On startup: load all users with `telegram_bot_token_encrypted` → start one `Application` per user with that user's token → `application.run_polling()` concurrently in the shared event loop. Handles `/start`, `/confirm`, `/status`, `/unpair`, `/help`. Each handler closure captures the owning `user_id` so we never need a token-to-user lookup at request time.
- `backend/telegram_bot/manager.py` — `start_user_app(user_id)`, `stop_user_app(user_id)`, `reload_user_app(user_id)`. Called by the API endpoints above to hot-add/remove users without restarting the service.

Wire-in points (call `telegram_notifier.notify(...)` from):
- `backend/monitor/action_executor.py` — rule fired (success or failed order)
- `backend/services/workflow_engine.py` — awakening complete (summary excerpt + thread link)
- `backend/monitor/daemon.py::_on_stream_auth_failure` — stream auth failure / TOTP recovery
- `backend/api/upstox_oauth.py::auto_refresh_upstox_token` — TOTP refresh failure (after cooldown)
- Future: Upstox order postback webhook (see `docs/plans/2026-05-11-upstox-webhook-design.md`)

Frontend additions:
- `frontend-v2/app/components/Settings.jsx` — Telegram section:
  1. Onboarding text: "Open Telegram → DM @BotFather → `/newbot` → copy the HTTP API token here."
  2. Token input → submit → backend validates + stores → shows bot username
  3. "Now DM your bot `/start`" instruction → status polls until `chat_id` lands
  4. Per-category toggles (monitor / awakening / order-fill / system)
  5. Unpair button (clears token + chat_id)

Pairing flow (replaces one-time codes):
1. User creates bot via BotFather, copies token
2. User pastes token in Settings → backend validates via `getMe`, stores encrypted, starts Application
3. User DMs their bot `/start` → bot binds the chat_id of that update to the owning `user_id`
4. (Safety) bot replies "send `/confirm` to lock this chat" — chat_id only persists after `/confirm` to avoid accidental binding from a wrong account that has the bot username

Notification categories:
- `monitor_fire` — rule triggered (SL hit, target hit, trailing tightened)
- `monitor_failure` — order rejected by exchange, daemon stream auth fail
- `awakening` — recurring awakening completed (one digest per awakening, not per tool call)
- `order_fill` — Upstox postback received (Phase 1.5, after webhook lands)
- `system` — TOTP failed, daemon restart, deploy notice

Rate limiting:
- Per user, max 30 messages / hour (Telegram limits ~30 msg/sec/bot global, but burst-OK)
- Monitor category supports digest mode: batch all fires in a 60s window into one message

Risks:
- Bot token leak — scoped to that one user. Rotate via BotFather → user re-pastes in Settings. Old token auto-revokes via BotFather flow.
- Telegram sees plaintext trade info — disclose in Settings UI ("not E2E encrypted")
- chat_id squatting — `/confirm` step blocks accidental binding from someone who guessed/learned the bot username. Could tighten further by checking `update.effective_user.id` against a stored Telegram user_id, but `/confirm` covers the common case.
- Bot down → notifications lost. MVP: log skip. Future: persistent outbox queue with retry.
- One bad user's Application crashing the shared event loop — wrap each `application.run_polling()` in a supervisor task that restarts on exception, log + notify owner.

### Phase 2 — Inbound chat → daily thread

Bound user DMs the bot → message routes into today's daily thread → agent runs and replies back.

Flow:
1. Bot receives DM. Look up `user_id` from `chat_id`. Unbound → reply "pair via Settings."
2. Resolve daily thread via `get_or_create_daily_thread(user_email)`.
3. Append incoming text as a user message (`MessageOps.add_message(role="user", source="telegram")`).
4. Run `get_orchestrator_for_model(model_id, user_id=user_id)` with new `OrchestratorDeps.is_telegram=True`.
5. Capture final assistant text via `agent.run()` (NOT `stream_text()` — same trap as awakenings, see memory).
6. Send back via `bot.send_message(chat_id, text)`. For long responses, split at paragraph boundaries.
7. Save assistant message to thread.
8. Trigger thread embedding (debounced) — same as web chat.

Progressive feedback (optional MVP polish):
- Send "_thinking..._" placeholder immediately, edit it as tool calls progress (rate-limited to 1 edit/sec to stay under Telegram limits).

Trade approval over Telegram:
- `render_ui` confirmation cards don't render in Telegram. Translate to inline keyboard buttons:
  - `[✅ Approve]` `[❌ Cancel]` `[📊 Show details]`
  - Button callback → POST to backend → backend records approval → orchestrator continues
- New `is_telegram=True` system prompt section (mirrors awakening section): "User is on Telegram. For trade confirmations, emit a structured inline keyboard via `render_telegram_approval` (new tool) instead of `render_ui`."
- This is the key open design question — see "Open questions" below.

### Phase 3 — Multi-thread (Hermes-style)

Defer until Phase 1+2 used. Pattern:
- Root DM = system lobby (`/threads`, `/new`, `/switch`, `/status`)
- Telegram topics = NS threads (one per topic)
- `message_thread_id` from Telegram maps to NS `conversation_id`
- Existing daily thread auto-binds to a Telegram topic on first activation

Skip if Phase 2 daily-thread routing is enough in practice.

## Open questions

1. **Trade approval UX on Telegram.** Inline keyboard is the obvious answer. But how does the orchestrator know to emit a keyboard instead of render_ui? Options:
   - (a) New `render_telegram_approval` tool only registered when `is_telegram=True`
   - (b) Keep `render_ui`, have the telegram bot translate the rendered card payload to a keyboard
   - (c) Tee both — orchestrator always emits `render_ui`, telegram layer translates
   - Prefer (a) — cleaner agent contract, no fragile translation.

2. **Streaming vs final-only reply.** Telegram doesn't stream like SSE. Edit-in-place is workable but rate-limited. MVP can ship final-text-only with a "_thinking..._" placeholder. Add progressive updates later if users complain.

3. **Order node routing.** Inbound chat that places orders — does the telegram bot process need access to per-user `order_node_url`? Yes, via the orchestrator dep chain. Same as web: orchestrator pulls from `User.order_node_url`, no special handling needed for telegram.

4. **Webhook vs long-poll.** Long-poll is simpler (no public endpoint, no TLS handshake), works fine for <100 users. Webhook lets Caddy + existing TLS handle it and reduces daemon connections. **MVP: long-poll.** Per-user bots makes webhooks even cleaner if we ever switch — route `POST /tg/{user_id}/webhook` and dispatch by URL, no token-to-user lookup at request time.

5. **Group chats?** Hermes supports group chats. NS is a personal trading assistant — DMs only for now. Reject group invites.

6. **Voice / image input.** Phase 2 stretch goal — pipe through existing vision sub-agent. Not MVP.

## Infrastructure

- No new env vars — bot tokens live in DB encrypted with the existing `ENCRYPTION_KEY` (same Fernet used for Upstox creds).
- Bot registration: each user does this themselves via BotFather → `/newbot`. No app-owner bot needed (Pranav still pastes his own token into Settings like any other user).
- Service: `niftystrategist-telegram.service` — runs `python -m backend.telegram_bot.app`. Hosts N `Application` instances in one event loop (one per user with a configured token).
- Deploy: CI restart step adds `niftystrategist-telegram` alongside the others.
- Settings page → backend → telegram service IPC: API endpoints (`POST/DELETE /api/telegram/bot-token`) call into the telegram service's `manager` via an in-process import if running same machine, or an internal HTTP endpoint on the telegram service if separated later. **MVP: single-machine same-process IPC** through a small shared module / function call — simpler than HTTP between systemd units. If the telegram service is its own systemd unit, expose a thin admin HTTP endpoint bound to `127.0.0.1` for reload requests.
- No SEBI IP impact — bot runs on main server; order placement still routed via per-user `order_node_url` by the orchestrator.

## Test plan

- Token submission: valid token → `getMe` succeeds → encrypted store → Application started → bot username returned
- Invalid token → 400 with clear error; nothing persisted
- `/start` + `/confirm` flow: chat_id stored on confirm, not on `/start` alone
- Notifier: paired vs unpaired user, category disabled, rate-limited
- Token deletion: Application stopped, chat_id cleared, subsequent notifications no-op
- Hot reload: new token while service running → old Application stopped → new one starts with new token
- Inbound chat (Phase 2): unbound chat_id reply, bound chat_id → daily thread append
- Trade approval via inline keyboard end-to-end (smoke test on staging)
- Bot down (one user's Application crashed) + notification fires → no crash, log only, other users' bots unaffected

## Dependencies

- `python-telegram-bot[ext]>=21.0` (latest stable)
- Add to `backend/requirements.txt`

## Out of scope (for now)

- Group / channel posting
- Voice transcription
- Image generation in replies (charts) — Phase 2 stretch
- Persistent outbox queue for notification retry — add when first outage hits
- Topic / multi-session UI (Phase 3)
