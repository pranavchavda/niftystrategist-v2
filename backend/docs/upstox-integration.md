# Upstox Integration

Nifty Strategist connects to Upstox for live market data, portfolio management, and order execution on NSE/BSE.

## Overview

- **Not a registered multi-user app** — Upstox multi-user approval is separate. The app owner's (Pranav's) credentials are in `.env`. Other users must enter their own API key/secret via Settings.
- **Tokens expire daily** (~3:30 AM IST) — SEBI regulations prevent refresh tokens. TOTP auto-refresh is the workaround.
- **All credentials encrypted** — Fernet (AES-128) encryption for stored tokens, API keys, and TOTP secrets.

## OAuth Authorization Flow

**File:** `api/upstox_oauth.py`

### 1. Initiate Authorization

`GET /api/auth/upstox/authorize` (redirect) or `GET /api/auth/upstox/authorize-url` (JSON)

- Generates signed OAuth state token using HMAC-SHA256 (`JWT_SECRET`)
- State payload: `user_id`, timestamp, nonce
- Uses per-user API credentials from DB, or falls back to `.env` defaults
- Redirects to Upstox OAuth dialog

### 2. Handle Callback

`GET /api/auth/upstox/callback`

- Verifies state signature and 10-minute expiry
- Extracts `user_id` from state (stateless verification)
- Exchanges auth code for access token via Upstox token endpoint
- Fetches user profile to get `upstox_user_id`
- Encrypts and stores token in database

### 3. Disconnect

`POST /api/auth/upstox/disconnect`

- Clears all Upstox tokens from database
- Resets trading mode to "paper"

## Token Storage

**Database columns (User model):**

| Column | Type | Contents |
|--------|------|----------|
| `upstox_access_token` | Text | Fernet-encrypted access token |
| `upstox_refresh_token` | Text | Fernet-encrypted refresh token |
| `upstox_token_expiry` | DateTime | Naive UTC expiry time |
| `upstox_user_id` | String(100) | Upstox account identifier |
| `upstox_api_key` | Text | Fernet-encrypted per-user API key |
| `upstox_api_secret` | Text | Fernet-encrypted per-user API secret |

**Encryption** (`utils/encryption.py`):
- `encrypt_token(plaintext)` — Fernet encrypt, returns base64 blob
- `decrypt_token(encrypted)` — Fernet decrypt, returns plaintext
- Key from `ENCRYPTION_KEY` env var (must be a valid Fernet key)

## Daily Token Expiry

Upstox tokens expire daily around 3:30 AM IST. Without TOTP auto-refresh, users must re-authenticate via OAuth each morning.

**Detection:** `get_user_upstox_token(user_id)` in `api/upstox_oauth.py` checks `upstox_token_expiry < datetime.utcnow()`. If expired:
1. Attempts TOTP auto-refresh (if credentials saved)
2. Returns `None` if refresh fails or no TOTP credentials

**Critical:** Always call `get_user_upstox_token(user_id)` to get the access token. Never read `user.upstox_access_token` directly — that's an encrypted blob.

## TOTP Auto-Refresh

**Migration:** `migrations/015_add_totp_credentials.sql`

### TOTP Credentials

| Column | Type | Contents |
|--------|------|----------|
| `upstox_mobile` | Text | Encrypted mobile number |
| `upstox_pin` | Text | Encrypted login PIN |
| `upstox_totp_secret` | Text | Encrypted TOTP secret |
| `upstox_totp_last_failed_at` | DateTime | Cooldown timestamp |

### How It Works

1. User saves TOTP credentials via Settings page (`POST /api/auth/upstox/totp-credentials`)
2. When token expires, `auto_refresh_upstox_token(user_id)` is called:
   - Decrypts TOTP credentials from DB
   - Gets user's API credentials (per-user or env fallback)
   - Calls `upstox-totp` library (handles SMS OTP + TOTP generation)
   - On success: stores new encrypted token, sets 24h expiry, clears cooldown
   - On failure: sets `upstox_totp_last_failed_at`, blocks retries for 30 minutes

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/upstox/totp-credentials` | Save TOTP credentials |
| DELETE | `/api/auth/upstox/totp-credentials` | Clear TOTP credentials |
| POST | `/api/auth/upstox/totp-test` | Manually test auto-refresh |

## Per-User Credentials

Since the app isn't registered for multi-user access, other users must provide their own Upstox API key/secret.

**Endpoints:**
- `POST /api/auth/upstox/credentials` — Save encrypted credentials
- `GET /api/auth/upstox/credentials` — Check if credentials exist
- `DELETE /api/auth/upstox/credentials` — Clear credentials

**Resolution order** (`_get_user_upstox_credentials(user_id)`):
1. Try per-user credentials from DB (encrypted)
2. Fall back to `.env` defaults (`UPSTOX_API_KEY`, `UPSTOX_API_SECRET`)

## Token Injection into CLI Tools

When the orchestrator runs CLI tools via `execute_bash`:

1. `main.py` decrypts `upstox_access_token` via `get_user_upstox_token(user_id)`
2. Passes plaintext token to `OrchestratorDeps.upstox_access_token`
3. Orchestrator injects into subprocess environment:
   ```python
   subprocess_env["NF_ACCESS_TOKEN"] = ctx.deps.upstox_access_token
   subprocess_env["NF_USER_ID"] = str(ctx.deps.user_id)
   ```
4. CLI tool reads from env: `os.environ.get("NF_ACCESS_TOKEN")`
5. If token present: live trading mode. If absent: paper trading mode.

## Integration Points

| System | How it gets the token |
|--------|----------------------|
| Chat (orchestrator) | `get_user_upstox_token(user_id)` via `main.py` |
| Dashboard API | `get_user_upstox_token(user_id)` directly |
| Monitor daemon | `get_user_upstox_token(user_id)` on each poll cycle |
| Workflow engine (awakenings) | `get_user_upstox_token(user_id)` at execution |

All callers benefit from automatic TOTP refresh when tokens expire.

## Trading Mode

Users can switch between paper and live trading:

- `GET /api/auth/upstox/trading-mode` — Check current mode
- `POST /api/auth/upstox/trading-mode` — Set mode (paper/live)

Paper mode: CLI tools run in simulation (no real orders placed).
Live mode: Requires valid Upstox token.

## Environment Variables

```
UPSTOX_API_KEY=...              # Default app owner credentials
UPSTOX_API_SECRET=...
UPSTOX_REDIRECT_URI=http://localhost:5173/auth/upstox/callback
ENCRYPTION_KEY=<Fernet key>     # For encrypting/decrypting all credentials
```
