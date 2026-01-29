# Live Trading Switch with Upstox OAuth

**Date:** 2026-01-29
**Status:** Implementation complete and tested

## Overview

Implement a live trading toggle that allows users to switch between paper trading (simulated) and live trading (real money via Upstox).

## User Flow

1. **New user** - Sees toggle in sidebar showing "Paper Trading" (default). Toggle prompts "Connect Upstox" when attempting to switch to live.

2. **Connecting Upstox** - User clicks "Connect Upstox" → redirected to Upstox OAuth → authorizes app → redirected back with tokens stored encrypted in DB.

3. **Switching to live** - User clicks toggle → confirmation dialog ("You're about to trade with real money...") → confirms → mode switches to "Live Trading".

4. **Trading** - Order tools check user's trading mode. Paper = simulated orders; Live = real Upstox API with user's tokens.

## Token Architecture

| Operation | Token Used |
|-----------|------------|
| Get stock quote | App token (shared, from .env) |
| Get historical data | App token (shared) |
| Place order | User's OAuth token |
| View user's portfolio | User's OAuth token |
| Cancel order | User's OAuth token |

## Database Changes

Add to `users` table:
- `trading_mode` - VARCHAR, 'paper' or 'live', default 'paper'

Existing columns (already present):
- `upstox_access_token` - Encrypted
- `upstox_refresh_token` - Encrypted
- `upstox_token_expiry` - DateTime

## Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/upstox/authorize` | GET | Generate OAuth URL, redirect to Upstox |
| `/api/auth/upstox/callback` | GET | Handle callback, exchange code, store tokens |
| `/api/auth/upstox/disconnect` | POST | Remove user's Upstox tokens |
| `/api/auth/upstox/status` | GET | Check if user has valid Upstox connection |
| `/api/user/trading-mode` | GET | Get current trading mode |
| `/api/user/trading-mode` | POST | Set trading mode (paper/live) |

## OAuth Flow

```
User clicks "Connect Upstox"
        ↓
Frontend redirects to: /api/auth/upstox/authorize
        ↓
Backend redirects to Upstox OAuth URL with:
  - client_id (API key)
  - redirect_uri
  - state (CSRF token + user_id encoded)
        ↓
User logs into Upstox, authorizes app
        ↓
Upstox redirects to: /auth/upstox/callback?code=XXX&state=YYY
        ↓
Frontend forwards to backend API
        ↓
Backend exchanges code for tokens, encrypts & stores
        ↓
Returns success, frontend updates UI
```

## Redirect URLs

- Development: `http://localhost:5173/auth/upstox/callback`
- Production: `https://yourdomain.com/auth/upstox/callback`

## Frontend Components

### Sidebar Toggle
- Location: Sidebar, below navigation items
- States:
  - Paper Trading (orange indicator)
  - Live Trading (green indicator)
  - Upstox not connected (shows "Connect" button)

### Confirmation Dialog
Shown when switching paper → live:
```
⚠️ Switch to Live Trading?

You're about to trade with real money from your Upstox account.
All orders will be executed on the actual market.

[Cancel]  [Yes, Enable Live Trading]
```

## Security

- Tokens encrypted with Fernet (ENCRYPTION_KEY from .env)
- State parameter includes CSRF token to prevent attacks
- Token refresh handled automatically when expired
- Users can disconnect Upstox at any time

## Implementation Order

1. Add `trading_mode` column to users table
2. Create encryption utilities for tokens
3. Implement OAuth endpoints (authorize, callback, disconnect, status)
4. Implement trading mode endpoints
5. Update UpstoxClient to use per-user tokens for live trading
6. Build frontend OAuth callback route
7. Build sidebar toggle component
8. Build confirmation dialog
9. Test end-to-end flow
