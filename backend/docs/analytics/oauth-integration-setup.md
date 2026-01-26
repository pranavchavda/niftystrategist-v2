# Marketing Agent - Unified OAuth Integration

## Overview

The marketing agent now uses **unified OAuth authentication** that integrates with your frontend login system. This means:

- ✅ Users authenticate once via Google OAuth (same as dashboard)
- ✅ Marketing agent automatically uses their credentials
- ✅ No separate ADC setup required per user
- ✅ Proper multi-tenant support (each user's own Google account)
- ✅ Secure per-request authentication

## How It Works

### Architecture

```
User logs in via Google OAuth
    ↓
Frontend stores JWT token
    ↓
JWT contains user_id (email)
    ↓
Backend looks up user in database
    ↓
Retrieves google_access_token & google_refresh_token
    ↓
Creates temporary ADC file: /tmp/espressobot_adc/adc_{user_email}.json
    ↓
Initializes MCP servers with user's credentials
    ↓
Runs GA4/Google Ads queries
    ↓
Cleans up temporary ADC file
```

### Code Flow

1. **User Authentication** (`google_auth.py`)
   - User logs in with Google OAuth
   - Tokens stored in database: `google_access_token`, `google_refresh_token`
   - Same tokens used by dashboard for Gmail/Calendar/Drive

2. **Orchestrator** (`orchestrator.py:588-632`)
   - When marketing agent is called
   - Fetches user's OAuth tokens from database
   - Passes them to marketing agent via `MarketingDeps`

3. **Marketing Agent** (`marketing_agent.py:244-341`)
   - Checks if OAuth tokens provided in deps
   - If yes: Creates temporary ADC file from OAuth tokens
   - Initializes MCP servers with that ADC file
   - Runs query with user's credentials
   - Cleans up temporary file

4. **OAuth to ADC Converter** (`utils/oauth_to_adc.py`)
   - Converts OAuth tokens to ADC format
   - Creates secure temporary files (mode 0o600)
   - Provides cleanup functionality

## User Experience

### For Authenticated Users

When a logged-in user asks marketing questions:

```
User: "How many people are on the site right now?"
```

**Backend automatically:**
1. Retrieves user's OAuth tokens from database
2. Creates temporary ADC credentials
3. Queries GA4 with user's account access
4. Returns personalized results
5. Cleans up credentials

**User sees:**
```
Based on real-time analytics, there are 58 active users on idrinkcoffee.com right now...
```

### For Unauthenticated/Test Users

If OAuth tokens not available (e.g., CLI testing):

- Falls back to system-wide ADC (if configured)
- Or returns helpful auth error message
- User needs to log in via frontend for full functionality

## Setup Requirements

### OAuth Scopes (Already Configured)

Your Google OAuth already includes the necessary scopes:
```python
SCOPES = [
    'https://www.googleapis.com/auth/analytics.readonly',  # GA4
    'https://www.googleapis.com/auth/adwords',             # Google Ads
    'https://www.googleapis.com/auth/gmail.readonly',      # Gmail
    'https://www.googleapis.com/auth/calendar.readonly',   # Calendar
    # ... other scopes
]
```

### Google Cloud APIs (Must Be Enabled)

1. **Google Analytics Admin API**
   - Enable at: https://console.developers.google.com/apis/api/analyticsadmin.googleapis.com
   - Required for: `get_account_summaries`, `get_property_details`

2. **Google Analytics Data API**
   - Should already be enabled
   - Required for: `run_report`, `run_realtime_report`

3. **Google Ads API**
   - Enabled automatically with OAuth
   - Requires: Developer Token (test token currently active)

### Database Schema

User table must have OAuth token columns:
```sql
google_access_token TEXT
google_refresh_token TEXT
google_token_expiry TIMESTAMP
ga4_property_id VARCHAR(50)  -- Optional, for default property
```

## Testing

### Via Web UI (Recommended)

1. Log in to frontend with Google OAuth
2. Navigate to chat
3. Ask: "Show me realtime traffic on the site"
4. Agent uses your Google account automatically

### Via API (With Auth Token)

```bash
curl -X POST http://localhost:8000/api/agent/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "message": "What GA4 properties do I have access to?",
    "user_id": "your@email.com"
  }'
```

### Via CLI (Falls Back to System ADC)

```bash
# Only if you've run: gcloud auth application-default login
python cli.py
> Show me GA4 properties
```

## Security Features

### Credentials Isolation

- ✅ Each user's credentials stored in separate temp file
- ✅ File permissions: `0o600` (owner read/write only)
- ✅ Temp directory: `/tmp/espressobot_adc/` (mode `0o700`)
- ✅ Files automatically cleaned up after each request

### Token Management

- ✅ Access tokens refreshed automatically (via `google.auth`)
- ✅ Refresh tokens never exposed to MCP servers
- ✅ ADC files contain only `refresh_token`, not `access_token`
- ✅ MCP servers request fresh tokens from Google OAuth as needed

### Multi-Tenant Safety

- ✅ User A cannot access User B's GA4 data
- ✅ Each request creates fresh MCP servers with correct credentials
- ✅ No credential caching between users
- ✅ Proper database-level user isolation

## Troubleshooting

### "User not authenticated with Google"

**Cause:** User hasn't logged in via Google OAuth or tokens expired

**Solution:**
1. User logs out
2. User logs in again via "Login with Google"
3. Ensure OAuth consent includes analytics scopes

### "Google Analytics Admin API not enabled"

**Cause:** API not enabled for your Google Cloud project

**Solution:**
1. Visit: https://console.developers.google.com/apis/api/analyticsadmin.googleapis.com
2. Click "Enable"
3. Wait 1-2 minutes for propagation

### "No GA4 property ID configured"

**Cause:** User hasn't set default GA4 property

**Options:**
1. Set in database: `UPDATE users SET ga4_property_id = '325181275' WHERE email = 'user@example.com'`
2. Or specify in query: "Show me traffic for property 325181275"
3. Or agent will ask user to choose from available properties

### "Invalid refresh token"

**Cause:** User revoked access or token expired

**Solution:**
1. User revokes app access: https://myaccount.google.com/permissions
2. User logs out of EspressoBot
3. User logs in again (fresh OAuth consent)

## Deployment Notes

### Production Checklist

- [ ] Google OAuth credentials configured (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- [ ] Google Analytics Admin API enabled
- [ ] Google Analytics Data API enabled
- [ ] Developer Token for Google Ads (production token, not test)
- [ ] `/tmp/espressobot_adc/` directory writable by backend process
- [ ] Backend service has internet access for Google APIs

### Performance Considerations

**MCP Server Creation:**
- Created fresh per request (no caching)
- Overhead: ~100-200ms per request
- Acceptable for infrequent marketing queries

**Future Optimization (if needed):**
- Cache MCP servers per user (with TTL)
- Reuse servers for same user within session
- Trade-off: Complexity vs performance

## Comparison: Before vs After

### Before (System-wide ADC)

❌ Single Google account for all users
❌ Manual ADC setup via `gcloud auth`
❌ No multi-tenant support
❌ Security risk (shared credentials)
❌ Different auth flow than dashboard

### After (Unified OAuth)

✅ Per-user Google accounts
✅ Automatic via frontend login
✅ Proper multi-tenant support
✅ Secure credential isolation
✅ Consistent with dashboard auth
✅ Production-ready architecture

## Example Queries

Once authenticated, users can ask:

**GA4 Analytics:**
- "How many people are on the site right now?"
- "What were the top traffic sources last week?"
- "Show me conversion rates by device type"
- "Compare revenue this month vs last month"

**Google Ads (when production token enabled):**
- "Which campaigns are spending the most?"
- "Show me keyword performance this week"
- "What's our ROAS across all campaigns?"
- "Which ad groups have the best conversion rate?"

## References

- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
- [GA4 MCP Server](https://github.com/googleanalytics/google-analytics-mcp)
- [Google Ads MCP Server](https://github.com/googleads/google-ads-mcp)
