# In-App Notification Center

**Date:** 2026-06-20
**Status:** Plan — not started
**Goal:** Persist every outbound notification and surface an unread bell + dropdown panel on every page, so the user has an in-app history and unread state (not just ephemeral push/Telegram messages).

## Motivation

- Notifications are currently fire-and-forget: `services/notifier.py::notify_user()` fans out to Web Push + Telegram and **persists nothing**. There is no notifications table (confirmed 2026-06-20 — none in `database/models.py` or migrations).
- If a push is missed/dismissed, or the user wasn't on the device, the information is gone. A persistent inbox is the canonical record regardless of channel delivery.
- Builds directly on the multi-channel work: `docs/plans/2026-06-19-web-push-notifications.md`.

## Backend

### DB migration `049_add_notifications.sql`
```sql
CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category    VARCHAR(40) NOT NULL,   -- same set as api/telegram.py NOTIFICATION_CATEGORIES
    title       TEXT,                   -- short, for the panel row + push title
    body        TEXT NOT NULL,
    url         TEXT,                    -- deep link opened on click (e.g. /chat/<thread_id>)
    read_at     TIMESTAMP,              -- NULL = unread
    created_at  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON notifications(user_id, read_at, created_at DESC);
```
ORM: `Notification` in `database/models.py` (naive `utc_now()` per repo convention; relationship on `User`).

### Persist at the dispatcher seam
Write the row inside `notify_user()` (`services/notifier.py`) **before** fanning out to channels, so the inbox is the source of truth even when a channel send fails. The dispatcher already receives `(user_id, category, text, *, markdown, url)` — derive `title` from the category label map already in `webpush_notifier._CATEGORY_TITLES`, `body = text`. Keep it best-effort (a DB failure must not block channel delivery — wrap in try/except, log).

### API — new `api/notifications.py`, mounted in `main.py`
- `GET    /api/notifications?limit=&before=` — list, newest first (unread + recent read).
- `GET    /api/notifications/unread-count` — `{count}` (cheap, indexed). Polled by the bell.
- `POST   /api/notifications/{id}/read` — mark one read.
- `POST   /api/notifications/read-all` — mark all read for the user.
- (optional) `DELETE /api/notifications/{id}` — dismiss.
All `Depends(get_current_user)`; scope every query to `user.id`.

## Frontend (mount points already mapped 2026-06-20)

- **Bell + unread badge → `app/components/TopBar.jsx`**, right-side action group, after the "Logs" button (~line 123) before the user-menu divider. `Bell` from `lucide-react` is already imported in `Settings.jsx`. Use Catalyst `Button` + `Badge` for the icon + count.
  - ⚠️ TopBar is not literally on every route; the always-present chrome is `Sidebar.jsx`. If some routes render without TopBar, also surface the bell in the Sidebar header so it's truly global. Root authed layout is `app/routes/_auth.tsx` (renders children via `<Outlet>` ~line 283).
- **Dropdown panel:** reuse `app/components/catalyst/dropdown.jsx` (Headless UI) — same pattern as the existing user menu in `TopBar.jsx` (~lines 132-183), `anchor="bottom end"`, `min-w-80`. Each row: category icon, title/body, relative time, unread dot. Footer: "Mark all read".
- **Auth + fetch:** components get `authToken` via `useOutletContext()` (stored in localStorage as `auth_token` by `_auth.tsx`); fetch `/api/...` with `Authorization: Bearer ${authToken}`.
- **Click → navigate:** `useNavigate()` from `react-router` → the notification's `url`; mark read on click (optimistic), then navigate.
- **Icons:** `lucide-react` (already the app's lib).

## Live updates

- **MVP:** poll `/api/notifications/unread-count` (e.g. every 30–60s) + refetch on window focus. No focus-refetch helper exists yet — add a simple `window.addEventListener('focus', refetch)`.
- **Stretch (real-time):** the service worker already receives `push` events (`public/push-sw.js`). Have it `postMessage` to open clients on push so the badge bumps instantly without a poll. Alternatively copy the SSE pattern in `app/routes/backtest.tsx` (`openSseStream()` — manual `fetch` + `data:` parse, since `EventSource` can't send auth headers) for a `/api/notifications/stream` endpoint.

## Retention
Cap history per user (e.g. keep last 200, or age out > 90 days) via a periodic cleanup or a trigger. Decide when building; not MVP-critical.

## Test plan
- `notify_user` writes a row for every category; channel-send failure still persists the row.
- unread-count reflects inserts and drops to 0 after read-all.
- mark-one-read / read-all scope to the calling user only (no cross-user leakage).
- Bell badge shows on all pages (verify routes without TopBar still show it via Sidebar).
- Click navigates to `url` and marks read; awakening notifications deep-link to the daily thread.
- Poll + focus refetch update the badge.

## Out of scope (v1)
- Cross-device read-state sync beyond the shared DB (it's already server-side, so this is free).
- Grouping/threading of notifications.
- Per-category filters in the panel (prefs already mute at send time).
- Real-time SSE/postMessage (MVP polls).
```
