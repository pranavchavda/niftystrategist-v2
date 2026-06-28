-- Cached intraday sector-flow snapshots, refreshed on a ~5-min cron (own clock).
-- The sensor's full-universe candle fetch trips Upstox's per-token rate limit on
-- the request path, so a cron computes the two-layer reading (market regime-roll +
-- per-sector relative strength) as an isolated subprocess and stores it here; the
-- live nf-sector-flow tool and awakenings read the newest fresh row. Mirrors
-- scan_snapshots. Auto-created by Base.metadata.create_all on startup; this file
-- is for prod-explicit application / convention.

CREATE TABLE IF NOT EXISTS sector_flow_snapshots (
    id            SERIAL PRIMARY KEY,
    universe      VARCHAR NOT NULL,
    snapshot      JSONB NOT NULL,
    session_date  VARCHAR,
    elapsed_ms    INTEGER,
    created_at    TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_sector_flow_snapshots_universe   ON sector_flow_snapshots (universe);
CREATE INDEX IF NOT EXISTS ix_sector_flow_snapshots_created_at ON sector_flow_snapshots (created_at);
