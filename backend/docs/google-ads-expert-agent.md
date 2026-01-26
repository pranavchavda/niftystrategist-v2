# Marketing Agent - Google Ads Capabilities

The Marketing Agent is the unified agent for GA4 analytics and comprehensive Google Ads campaign management. It combines **read-only GA4 analytics** (via MCP) with **full read/write Google Ads API access** (via native Python client).

## Key Features

### Campaign Types Supported
- **Performance Max (PMax)** - Primary focus with asset group and listing group optimization
- **Search Campaigns** - Keyword management, bid optimization
- **Shopping Campaigns** - Product feed optimization, listing groups
- **Display Campaigns** - Audience targeting, bid adjustments
- **Video Campaigns** - YouTube ads optimization

### Optimization Capabilities

#### Analysis Tools
| Tool | Description |
|------|-------------|
| `get_campaign_performance` | Campaign metrics with ROAS, CPA, conversions |
| `get_pmax_performance` | PMax-specific analysis including asset groups |
| `get_keyword_performance` | Keyword-level analysis with tier classification |
| `get_search_terms` | Search term mining for negative keywords |
| `analyze_optimization_opportunities` | AI-powered recommendations |

#### Action Tools (Write Operations)
| Tool | Description | Risk Level |
|------|-------------|------------|
| `add_negative_keyword` | Block irrelevant searches | Low |
| `add_negative_keywords_bulk` | Bulk negative additions | Low |
| `pause_keyword` | Pause underperforming keywords | Low |
| `update_keyword_bid` | Change CPC bids | Medium |
| `update_campaign_budget` | Adjust daily budgets | Medium |
| `update_campaign_status` | Enable/pause campaigns | Medium |
| `set_device_bid_modifier` | Device bid adjustments | Medium |

#### Extension/Asset Tools
| Tool | Description | Risk Level |
|------|-------------|------------|
| `add_sitelink_to_campaign` | Add sitelink extensions | Low |
| `add_promotion_to_campaign` | Add promotion extensions | Low |
| `list_campaign_extensions` | List existing extensions | Read-only |
| `remove_campaign_extension` | Remove an extension | Medium |

#### Performance Max Tools
| Tool | Description | Risk Level |
|------|-------------|------------|
| `get_asset_groups` | List asset groups with status | Read-only |
| `get_asset_group_performance` | Asset group metrics (ROAS, CPA) | Read-only |
| `update_asset_group_status` | Enable/pause asset groups | Medium |
| `get_listing_group_filters` | View product group filters | Read-only |
| `add_listing_group_filter` | Add product include/exclude filters | Medium |
| `remove_listing_group_filter` | Remove product filters | Medium |
| `get_asset_group_assets` | View creative assets with performance | Read-only |

## Usage

### Invoking the Agent

The orchestrator routes to `marketing` for all Google Ads and GA4 analytics tasks:

```python
# Via call_agent tool
call_agent(
    agent_name="marketing",
    task="Analyze our PMax campaigns and identify optimization opportunities"
)
```

### Example Tasks

1. **Campaign Analysis**
   - "Show me campaign performance for the last 30 days"
   - "Which campaigns have the best ROAS?"
   - "Analyze our Performance Max campaigns"

2. **Optimization Actions**
   - "Find and add negative keywords from search terms"
   - "Pause keywords that have spent over $50 with no conversions"
   - "Increase bids on high-converting keywords by 20%"
   - "Reduce mobile bids by 30% for our Shopping campaign"

3. **Budget Management**
   - "Reallocate budget from low ROAS to high ROAS campaigns"
   - "Increase budget on campaigns with ROAS > 4x"

4. **Extensions Management**
   - "Add sitelinks for our best categories to all campaigns"
   - "Create a Black Friday promotion extension for 20% off"
   - "List all extensions on our PMax campaign"
   - "Add a sitelink for 'Free Shipping' to the catch-all campaign"

5. **Performance Max Management**
   - "Show me all asset groups and their status"
   - "Pause the underperforming asset groups in our PMax campaign"
   - "What assets are in asset group X and how are they performing?"
   - "Show the product groups in our espresso machines asset group"
   - "Exclude brand Y from our catch-all asset group"
   - "What's the ROAS for each asset group in our PMax campaign?"

### Supported Promotion Occasions

**Holidays:** NEW_YEARS, CHINESE_NEW_YEAR, VALENTINES_DAY, EASTER, MOTHERS_DAY, FATHERS_DAY, PARENTS_DAY, LABOR_DAY, HALLOWEEN, BLACK_FRIDAY, CYBER_MONDAY, CHRISTMAS, BOXING_DAY, EPIPHANY, ST_NICHOLAS_DAY, CARNIVAL

**Cultural/Religious:** RAMADAN, EID_AL_FITR, EID_AL_ADHA, HOLI, DIWALI, NAVRATRI, ROSH_HASHANAH, PASSOVER, HANUKKAH

**Sales:** BACK_TO_SCHOOL, END_OF_SEASON, WINTER_SALE, SUMMER_SALE, FALL_SALE, SPRING_SALE, SINGLES_DAY

**Other:** INDEPENDENCE_DAY, NATIONAL_DAY, WOMENS_DAY

## Performance Targets

The agent uses these benchmarks for iDrinkCoffee.com:

| Metric | Target | Good | Excellent |
|--------|--------|------|-----------|
| ROAS | 3.0x | 3.0-5.0x | >5.0x |
| CPA | $30-50 | <$50 | <$30 |
| CTR | 2%+ | 2-4% | >4% |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator                              │
│  (Routes marketing/Google Ads tasks to marketing agent)     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Marketing Agent                          │
│  - Model: Claude Haiku 4.5 (fast, capable)                  │
│  - GA4 Analytics: MCP (read-only)                           │
│  - Google Ads: Native Python (read/write)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Google Ads Service                          │
│  - Uses google-ads Python client                            │
│  - Full read/write API access                               │
│  - Per-user OAuth authentication                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Google Ads API                              │
│  - Customer ID: 522-285-1423 (iDrinkCoffee.com)            │
│  - API Version: v18                                          │
└─────────────────────────────────────────────────────────────┘
```

## Authentication

The agent uses **per-user OAuth** for authentication:

1. User authorizes Google account via OAuth flow
2. Tokens stored in database (`google_access_token`, `google_refresh_token`)
3. Tokens automatically refreshed when expired
4. `GOOGLE_ADS_DEVELOPER_TOKEN` required in environment

### Required Environment Variables

```bash
GOOGLE_CLIENT_ID=           # OAuth client ID
GOOGLE_CLIENT_SECRET=       # OAuth client secret
GOOGLE_ADS_DEVELOPER_TOKEN= # Google Ads API developer token
```

## API Access Methods

| Data Source | Access Method | Capabilities |
|-------------|---------------|--------------|
| GA4 Analytics | MCP Server (on-demand) | Read-only traffic/conversion data |
| Google Ads | Native Python Client | Full read/write access |

The unified marketing agent provides both analytics insights and optimization actions in a single interface.

## Action Authorization Levels

### Self-Execute (Low Risk)
- Adding negative keywords
- Minor bid adjustments (< 20%)
- Pausing keywords with 0 conversions and high spend

### Recommend First (Medium Risk)
- Budget changes > 20%
- Pausing campaigns
- Major bid adjustments
- Device/location bid modifiers

### Human Approval Required (High Risk)
- Enabling paused campaigns
- Budget increases > 50%
- Structural changes (new campaigns/ad groups)
- Changing bidding strategies

## Files

| File | Purpose |
|------|---------|
| `backend/agents/marketing_agent.py` | Unified marketing agent with GA4 + Google Ads |
| `backend/services/google_ads_service.py` | Google Ads API service layer |
| `backend/docs/google-ads-mcp-reference.md` | GAQL field reference |
| `backend/docs/google-ads-expert-agent.md` | This documentation |

## Future Enhancements

1. **Audience Signals** - PMax audience signal recommendations
2. **Asset Performance** - Asset rating analysis and recommendations
3. **Automated Rules** - Schedule-based optimizations
4. **A/B Testing** - Ad copy experiment management
5. **Competitor Insights** - Auction insights analysis
6. **Smart Bidding** - Bidding strategy recommendations
