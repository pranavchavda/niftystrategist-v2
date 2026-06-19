-- Web Push notifications (PWA). Native replacement for the OUTBOUND half of
-- Telegram while Telegram is banned in India. One row per device/browser a user
-- subscribes from (contrast Telegram's single users.telegram_chat_id).
-- VAPID keys live in env (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT);
-- subscriptions here are not secret. Reuses users.notification_prefs for muting.
-- See docs/plans/2026-06-19-web-push-notifications.md.

CREATE TABLE IF NOT EXISTS web_push_subscriptions (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint     TEXT NOT NULL,
    p256dh       TEXT NOT NULL,
    auth         TEXT NOT NULL,
    user_agent   TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    last_used_at TIMESTAMP,
    UNIQUE (user_id, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_web_push_sub_user ON web_push_subscriptions(user_id);
