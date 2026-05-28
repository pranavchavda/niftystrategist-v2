-- Cached candidate-scan results, refreshed on a ~3-min cron (own clock).
-- Decouples the slow nf-morning-scan from the fast snapshot build: the cron
-- stores the latest rows here; the snapshot reads the newest fresh row instead
-- of scanning inline. Falls back to inline scan when no fresh row exists.

CREATE TABLE IF NOT EXISTS scan_snapshots (
    id          SERIAL PRIMARY KEY,
    universe    VARCHAR NOT NULL,
    rows        JSONB NOT NULL,
    nifty_pct   DOUBLE PRECISION,
    elapsed_ms  INTEGER,
    created_at  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_scan_snapshots_universe   ON scan_snapshots (universe);
CREATE INDEX IF NOT EXISTS ix_scan_snapshots_created_at ON scan_snapshots (created_at);
