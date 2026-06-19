# Web Push Notifications

**Date:** 2026-06-19
**Status:** Plan — not started
**Goal:** Replace the *outbound notification* half of Telegram with native Web Push (PWA), so monitor fires, awakening digests, system alerts, and the agent's `message_user` land as phone notifications with no third-party dependency. Telegram stays in place untouched (dormant during the India ban; returns when lifted). Web Push is **notifications + short messages only — not a chat channel.**

## Motivation

- Telegram is banned in India (2026-06). Its outbound notifier (`services/telegram_notifier.py`) now no-ops for everyone — alerts are silent.
- All current users are on Android → Web Push works frictionlessly (no iOS "Add to Home Screen" caveat).
- The PWA + service worker already ship (`vite-plugin-pwa`, `generateSW`, `PWAHandler.tsx`), and the category/prefs system already exists. The lift is small.
- Keep Telegram code intact: it costs nothing dormant (`notify()` already no-ops for unpaired users) and will be reusable when the ban lifts.

## Design principle: add the abstraction Telegram never had

The Telegram integration has **no notification abstraction** — 5 call sites import `telegram_notifier.notify` directly. This migration introduces a thin dispatcher *additively* (callers change their import, nothing else), and plugs both channels behind it:

```
services/notifier.py
  notify_user(user_id, category, text, *, markdown=False, url=None) -> dict
     ├── telegram_notifier.notify(...)     # existing, UNCHANGED — dormant but ready
     └── webpush_notifier.push(...)         # NEW
```

Both channels share `users.notification_prefs` (muting `monitor_fire` mutes it everywhere). Per-channel granularity is out of scope for v1. Each channel is independently best-effort and never raises; the dispatcher returns `{"telegram": bool, "webpush": int}` (push count = devices delivered) for logging.

### The 5 call sites to repoint (`telegram_notifier.notify` → `notifier.notify_user`)

| File:line | Category | Notes |
|---|---|---|
| `monitor/action_executor.py:199` (`_notify_fire`) | `monitor_fire` / `monitor_failure` | one-line summary, plain text |
| `monitor/daemon.py:333` | `system` | stream auth / TOTP recovery |
| `api/upstox_oauth.py:728` | `system` | TOTP refresh failure (post-cooldown) |
| `services/workflow_engine.py:898` | `awakening` | digest; pass `url=<daily thread link>` |
| `agents/orchestrator.py:4729` (`message_user`) | variable | `markdown=True`; already out-of-band by design — no dedup work needed |

No caller logic changes beyond the import + (for the awakening) passing a deep-link `url`.

## Backend

### Dependency
- `pywebpush` (+ its `cryptography` dep, already present) → `backend/requirements.txt`.

### Env vars (NEW — note in CLAUDE.md "Environment Variables")
```
VAPID_PUBLIC_KEY=...      # base64url; also served to the frontend
VAPID_PRIVATE_KEY=...     # base64url; signing key, server-only
VAPID_SUBJECT=mailto:pranav@idrinkcoffee.com
```
Generate once with `pywebpush`/`py-vapid` (`vapid --gen`); store in `.env` and prod env. Unlike Telegram tokens these are app-global, not per-user — no encryption needed (private key is an env secret, not a DB value).

### DB migration `048_add_web_push.sql`
A user has multiple devices/browsers → a **subscription table**, not a column (contrast Telegram's single `chat_id`):
```sql
CREATE TABLE IF NOT EXISTS web_push_subscriptions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint    TEXT NOT NULL,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    user_agent  TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    last_used_at TIMESTAMP,
    UNIQUE (user_id, endpoint)
);
CREATE INDEX IF NOT EXISTS idx_web_push_sub_user ON web_push_subscriptions(user_id);
```
ORM: `WebPushSubscription` in `database/models.py` (naive `utc_now()` timestamps per repo convention).
`notification_prefs` is reused as-is — no schema change there.

### `services/webpush_notifier.py` (mirrors `telegram_notifier.py`)
- `async def push(user_id, category, text, *, url=None, markdown=False) -> int` — returns count of devices delivered.
- Loads all subscriptions for the user; checks `_category_enabled(prefs, category)` (lift the helper from `telegram_notifier` into a shared spot, or duplicate — it's 5 lines).
- Builds payload `{title, body, url, tag}`:
  - `title` = category label/emoji map (`monitor_fire`→"📉 Monitor", `awakening`→"🌅 Awakening", `system`→"⚙️ Nifty Strategist", etc.) — Telegram puts everything in the body; push has a title slot, so derive a short one.
  - `body` = `text` (markdown ignored — push renders plain; optionally strip basic md).
  - `url` = deep link to open on tap (default `/`).
  - `tag` = category, so repeated fires in a category collapse instead of stacking.
- Sends via `pywebpush(subscription_info, json.dumps(payload), vapid_private_key=..., vapid_claims={"sub": VAPID_SUBJECT})`.
- **Prune dead subs:** on `WebPushException` with status `404`/`410` → delete that subscription row. Other errors → log + swallow (never raise).
- Reuse the per-user rate-limit pattern (`_rate_check`) from the Telegram notifier — same 60/hr cap is fine; share or duplicate.
- Runs from any process (web, monitor daemon, scheduler): it's just HTTPS POSTs + DB read. No shared event-loop concern like the Telegram inbound poller.

### `api/push.py` (new router, mounted in `main.py`)
- `GET  /api/push/vapid-public-key` → `{key}` (so the frontend can subscribe without a build-time env).
- `POST /api/push/subscribe` → body = the browser `PushSubscription` JSON `{endpoint, keys:{p256dh, auth}}`; upsert on `(user_id, endpoint)`.
- `DELETE /api/push/subscribe` → body `{endpoint}`; remove this device.
- `GET  /api/push/status` → `{enabled: bool, device_count: int, notification_prefs}` (mirrors `/api/telegram/status`).
- Reuse the existing `notification_prefs` PUT from `api/telegram.py` rather than duplicating — or hoist prefs CRUD to a neutral `/api/notifications/prefs`. v1: just import/reuse the telegram one.
- All routes `Depends(get_current_user)`.

## Frontend

### Service worker push handler
Current config is `strategies: "generateSW"` — Workbox generates the SW, so custom listeners go in an imported script:
- Add `frontend-v2/public/push-sw.js`:
  ```js
  self.addEventListener('push', (e) => {
    const d = e.data?.json() ?? {};
    e.waitUntil(self.registration.showNotification(d.title || 'Nifty Strategist', {
      body: d.body, tag: d.tag, data: { url: d.url || '/' },
      icon: '/icons/icon-192x192.png', badge: '/icons/icon-96x96.png',
    }));
  });
  self.addEventListener('notificationclick', (e) => {
    e.notification.close();
    e.waitUntil(clients.openWindow(e.notification.data?.url || '/'));
  });
  ```
- In `vite.config.js` `VitePWA({ workbox: { importScripts: ['push-sw.js'], ... } })` so the generated SW pulls it in.

### Subscription flow (Settings — replaces the Telegram section for now, or sits beside it)
1. New "Push Notifications" block in `app/components/Settings.jsx`.
2. On enable: `Notification.requestPermission()` → if granted, `registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: <vapid public key from /api/push/vapid-public-key> })` → POST the subscription to `/api/push/subscribe`.
3. Show device count + a disable button (unsubscribe + `DELETE /api/push/subscribe`).
4. Reuse the existing per-category toggles (they already drive `notification_prefs`).
5. Get the SW registration from the existing `PWAHandler.tsx` flow (don't register a second time).

## Out of scope (v1)
- **Inbound / chat over push** — push is one-way by spec. "DM the agent from anywhere" stays a Telegram capability (returns when unbanned); tapping a push opens the web chat, which covers the gap.
- Per-channel pref granularity (telegram-on/push-off) — shared prefs for now.
- iOS handling — all users on Android; revisit if an iOS user appears (works on iOS 16.4+ only as an installed PWA).
- Persistent outbox / retry queue — add when a real outage demands it (same stance as the Telegram plan).
- Rich actions on the notification (approve/cancel buttons) — notifications-only; any approval still flows through the web app.

## Test plan
- VAPID key endpoint returns the configured public key.
- Subscribe → row upserts; re-subscribe same endpoint → no duplicate (unique constraint).
- `notify_user` fans out: paired-telegram + subscribed-push both fire; unpaired-telegram + subscribed-push → push only; category muted → neither.
- Dead subscription (simulate 410) → row pruned, other devices unaffected, no raise.
- Each of the 5 repointed call sites delivers a push end-to-end (monitor fire on staging, awakening digest with working deep link, TOTP-fail system alert).
- `notificationclick` opens the correct URL (daily thread for awakenings, `/` otherwise).
- Multi-device: two browsers subscribed → both receive.

## Rollout
- Migration `048` applied to Supabase.
- VAPID env vars added to `.env` + prod.
- `requirements.txt` + CI uv install picks up `pywebpush`.
- No new systemd unit — push sends ride inside the existing web/daemon/scheduler processes (unlike the Telegram inbound poller).
- CLAUDE.md: add VAPID vars to the env section; add a short "Web Push" note alongside the Telegram one.
```
