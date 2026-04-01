-- Add per-user order node URL for SEBI static IP compliance.
-- Each user's orders are proxied through their dedicated order node
-- (a thin FastAPI service running on a Linode with a registered static IP).
-- For the primary user on the main instance, this is http://localhost:8001.

ALTER TABLE users ADD COLUMN IF NOT EXISTS order_node_url VARCHAR(255);
