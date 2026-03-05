# API Endpoints Reference

All endpoints are served by FastAPI on port 8000. Most require JWT authentication via `Authorization: Bearer <token>` header.

## Conversations (`/api/conversations`)

**File:** `api/conversations.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user conversations |
| GET | `/{id}` | Get conversation details |
| GET | `/{id}/messages` | Get conversation messages |
| PATCH | `/{id}` | Update conversation (title, etc.) |
| DELETE | `/{id}` | Delete conversation |
| PATCH | `/{id}/messages/{msg_id}` | Update message |
| PATCH | `/{id}/messages/{msg_id}/timeline` | Update message timeline |
| DELETE | `/{id}/messages/{msg_id}` | Delete message |
| GET | `/search` | Search conversations |
| POST | `/{id}/star` | Star conversation |
| POST | `/{id}/unstar` | Unstar conversation |
| POST | `/{id}/fork` | Fork conversation (new thread from summary) |
| POST | `/{id}/compact` | Compact thread (replace messages with summary) |
| GET | `/{id}/token-usage` | Get token usage stats |
| GET | `/{id}/cache/stats` | Cache statistics |
| GET | `/{id}/cache/entries` | Cache entries |
| DELETE | `/{id}/cache` | Clear cache |

## Runs (`/api/runs`)

**File:** `api/runs.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/active` | List active agent runs |
| GET | `/{run_id}/status` | Get run status |
| GET | `/{run_id}/stream` | SSE stream for agent run (AG-UI) |
| POST | `/{run_id}/cancel` | Cancel active run |
| POST | `/{run_id}/retry` | Retry failed run |

## Dashboard (`/api/dashboard`)

**File:** `api/dashboard.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/market-status` | NSE market open/closed status |
| GET | `/portfolio` | Holdings and P&L |
| GET | `/positions` | Open positions |
| GET | `/indices` | Nifty/Sensex/BankNifty indices |
| GET | `/watchlist` | User's watchlist with live prices |
| GET | `/chart/{symbol}` | Chart data for symbol |
| GET | `/scorecard` | Trading scorecard |
| POST | `/daily-thread` | Create/get daily trading thread |
| POST | `/invalidate-client` | Force Upstox client refresh |

## Cockpit (`/api/cockpit`)

**File:** `api/cockpit.py`

Same endpoints as Dashboard (alternative UI view). Market status, portfolio, positions, indices, watchlist, chart, scorecard, daily thread.

## Memories (`/api/memories`)

**File:** `api/memories.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List memories (with optional category filter) |
| GET | `/all` | (`/api/memory/all`) Get all memories |
| POST | `/` | Create memory |
| PATCH | `/{id}` | Update memory |
| DELETE | `/{id}` | Delete memory |
| POST | `/bulk-delete` | Bulk delete memories |
| GET | `/{id}/similar` | Find similar memories |
| POST | `/conversations/{id}/extract-memories` | Extract memories from conversation |

## Upstox OAuth (`/api/auth/upstox`)

**File:** `api/upstox_oauth.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/credentials` | Save per-user Upstox API credentials |
| GET | `/credentials` | Check if credentials exist |
| DELETE | `/credentials` | Clear credentials |
| GET | `/authorize` | Redirect to Upstox OAuth |
| GET | `/authorize-url` | Get OAuth URL (for frontend) |
| GET | `/callback` | OAuth callback handler |
| POST | `/disconnect` | Disconnect Upstox account |
| GET | `/status` | Connection status + token expiry |
| GET | `/trading-mode` | Get paper/live trading mode |
| POST | `/trading-mode` | Set paper/live trading mode |
| POST | `/totp-credentials` | Save TOTP auto-refresh credentials |
| DELETE | `/totp-credentials` | Clear TOTP credentials |
| POST | `/totp-test` | Test TOTP auto-refresh |

## Monitor (`/api/monitor`)

**File:** `api/monitor.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/symbols` | Symbol autocomplete search |
| GET | `/rules` | List user's monitor rules |
| POST | `/rules` | Create a rule |
| PATCH | `/rules/{id}` | Update rule (enable/disable, config) |
| DELETE | `/rules/{id}` | Delete rule |
| POST | `/oco` | Create OCO (One-Cancels-Other) pair |
| GET | `/logs` | Rule firing history |

## HITL (`/api/hitl`)

**File:** `routes/hitl.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/respond` | Respond to HITL approval request |
| POST | `/cancel/{approval_id}` | Cancel pending approval |
| GET | `/pending` | List pending approvals |

## Auth (`/api/auth`)

**File:** `routes/auth_routes.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/me` | Current user info |
| GET | `/preferences` | User preferences |
| PATCH | `/preferences/hitl` | Update HITL preferences |

## Admin (`/api/admin`)

**File:** `routes/admin.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/permissions` | List all permissions |
| GET | `/roles` | List roles |
| POST | `/roles` | Create role |
| PUT | `/roles/{id}` | Update role |
| DELETE | `/roles/{id}` | Delete role |
| GET | `/users` | List users |
| PUT | `/users/{id}/roles` | Assign roles to user |
| GET | `/models` | List LLM models |
| POST | `/models` | Add model |
| PUT | `/models/{id}` | Update model |
| DELETE | `/models/{id}` | Delete model |

## Admin Docs (`/api/admin/docs`)

**File:** `routes/admin_docs.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tree` | Documentation file tree |
| GET | `/list` | List doc files |
| GET | `/read` | Read doc file content |
| POST | `/write` | Write doc file |
| POST | `/create` | Create doc file |
| DELETE | `/delete` | Delete doc file |
| POST | `/rename` | Rename doc file |
| POST | `/validate` | Validate doc content |
| POST | `/reindex` | Reindex docs for search |
| POST | `/export` | Export docs |
| POST | `/import` | Import docs |
| GET | `/sync-status` | Doc sync status |

## Notes (`/api/notes`)

**File:** `routes/notes.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Create note |
| GET | `/` | List notes |
| GET | `/graph-connections` | Note graph connections |
| GET | `/lookup` | Lookup note by title |
| GET | `/{id}` | Get note |
| PATCH | `/{id}` | Update note |
| DELETE | `/{id}` | Delete note |
| POST | `/reindex` | Reindex notes |
| POST | `/search` | Search notes |
| GET | `/{id}/similar` | Similar notes |
| GET | `/{id}/backlinks` | Note backlinks |
| POST | `/import-obsidian` | Import from Obsidian |
| GET | `/obsidian-status/{vault_id}` | Obsidian sync status |
| POST | `/autocomplete` | Note title autocomplete |
| GET | `/{id}/export/pdf` | Export note as PDF |
| POST | `/{id}/publish` | Publish note |
| DELETE | `/{id}/publish` | Unpublish note |
| GET | `/{id}/publish-status` | Publish status |

## Stats (`/api/stats`)

**File:** `api/stats.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats` | Usage statistics |
| GET | `/activity` | Activity log |
| GET | `/trading-summary` | Trading performance summary |

## Workflows (`/api/workflows`)

**File:** `routes/workflows.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/types` | List workflow types |
| GET | `/types/{type}` | Get workflow type details |
| GET | `/configs` | List workflow configs |
| GET | `/{type}/config` | Get config for workflow type |
| PUT | `/{type}/config` | Update workflow config |
| POST | `/{type}/run` | Run workflow manually |
| GET | `/{type}/history` | Workflow run history |
| POST | `/followup/activate/{id}` | Activate awakening (internal, no JWT) |
| GET | `/history` | All workflow history |
| GET | `/custom` | List custom workflows |
| POST | `/custom` | Create custom workflow |
| GET | `/custom/{id}` | Get custom workflow |
| PUT | `/custom/{id}` | Update custom workflow |
| DELETE | `/custom/{id}` | Delete custom workflow |
| POST | `/custom/{id}/run` | Run custom workflow |
| GET | `/custom/{id}/history` | Custom workflow history |

## MCP Servers (`/api/mcp-servers`)

**File:** `routes/mcp_servers.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List MCP servers |
| POST | `/` | Add MCP server |
| GET | `/{id}` | Get server details |
| PUT | `/{id}` | Update server |
| DELETE | `/{id}` | Delete server |
| POST | `/validate` | Validate server config |
| POST | `/{id}/test` | Test server connection |
| POST | `/{id}/toggle` | Enable/disable server |
| GET | `/{id}/oauth/authorize` | OAuth authorize for MCP |
| GET | `/callback` | (`/api/mcp-oauth/callback`) OAuth callback |
| DELETE | `/{id}/oauth` | Revoke MCP OAuth |
| POST | `/{id}/oauth/refresh` | Refresh MCP OAuth token |

## Tools (`/api/tools`)

**File:** `api/tools.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List available tools |
| GET | `/landing` | Tools landing page data |

## Voice (`/api/voice`)

**File:** `routes/voice.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/transcribe` | Transcribe audio to text |
| POST | `/synthesize` | Text to speech |

## Uploads (`/api/upload`)

**File:** `routes/uploads.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/image` | Upload image |
| POST | `/file` | Upload file |
| GET | `/file/{email}/{filename}` | Get uploaded file |
| DELETE | `/file/{email}/{filename}` | Delete uploaded file |
| GET | `/list` | List uploaded files |

## Scratchpad (`/api/scratchpad`)

**File:** `routes/scratchpad.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{thread_id}` | Get scratchpad for thread |
| POST | `/{thread_id}` | Add scratchpad entry |
| PUT | `/{thread_id}/{index}` | Update scratchpad entry |
| DELETE | `/{thread_id}/{index}` | Delete scratchpad entry |
