# Google Ads MCP Tool Reference

Complete reference for using the Google Ads MCP `search` tool correctly.

## ⚠️ Critical Rules

### Customer ID Format
- **ALWAYS** use format: `"522-285-1423"` (with dashes) for iDrinkCoffee.com
- Customer ID is a **string**, not a number

### Date Format
- **ALWAYS** use `'YYYY-MM-DD'` format with single quotes in conditions
- Example: `"segments.date BETWEEN '2025-01-01' AND '2025-01-15'"`
- **NEVER** use date literals like `LAST_7_DAYS` directly - use `DURING` operator instead

### Date Range Conditions
- Use `DURING` operator for relative dates: `"segments.date DURING LAST_7_DAYS"`
- Use `BETWEEN` for absolute dates: `"segments.date BETWEEN '2025-01-01' AND '2025-01-15'"`
- **MUST** specify both start and end dates (finite ranges only)

### Field Names
- **ALWAYS** use fully-qualified field names: `campaign.name`, `metrics.clicks`
- **NEVER** use wildcards or partial fields
- **NEVER** use fields that don't exist in the resource (see reference below)

### Referenced Fields Must Be in SELECT
- **CRITICAL GAQL RULE**: Any field used in `conditions` (WHERE clause) or `orderings` (ORDER BY clause) **MUST also be included in `fields` (SELECT clause)**
- Example of **CORRECT** query:
  ```python
  # campaign.name is in conditions, so it MUST be in fields
  search(
      fields=["campaign.name", "metrics.clicks"],  # ✅ campaign.name included
      conditions=["campaign.name = 'Summer Sale'"],  # Uses campaign.name
      ...
  )
  ```
- Example of **WRONG** query:
  ```python
  # ❌ This will FAIL with: "field must be present in SELECT clause"
  search(
      fields=["metrics.clicks"],  # ❌ campaign.name missing
      conditions=["campaign.name = 'Summer Sale'"],  # References campaign.name
      ...
  )
  ```
- **This applies to both conditions AND orderings**:
  - If you filter by a field (WHERE), include it in SELECT
  - If you sort by a field (ORDER BY), include it in SELECT
  - Metrics and segments used for filtering/sorting must also be in SELECT

### Aggregation: DO NOT Include segments.date for Totals
- **CRITICAL GAQL RULE**: Including `segments.date` in SELECT returns **ONE ROW PER DATE** for each product/campaign
- When you want **aggregated totals over a date range**, **DO NOT include segments.date** in the SELECT clause
- **WRONG - Returns daily rows** (incomplete data with LIMIT):
  ```python
  # ❌ This returns ONE ROW PER DATE per product
  # With LIMIT 10 on a 30-day period, you only get 10 days of data!
  search(
      customer_id="522-285-1423",
      fields=[
          "segments.date",  # ❌ This causes daily rows
          "segments.product_title",
          "metrics.clicks",
          "metrics.conversions"
      ],
      resource="shopping_performance_view",
      conditions=["segments.date BETWEEN '2025-09-15' AND '2025-10-14'"],
      orderings=["metrics.clicks DESC"],
      limit=10  # Only 10 date+product rows = INCOMPLETE TOTALS
  )
  ```
- **CORRECT - Returns aggregated totals**:
  ```python
  # ✅ Google Ads automatically aggregates across the date range
  search(
      customer_id="522-285-1423",
      fields=[
          "segments.product_title",  # No segments.date!
          "metrics.clicks",
          "metrics.conversions"
      ],
      resource="shopping_performance_view",
      conditions=["segments.date BETWEEN '2025-09-15' AND '2025-10-14'"],
      orderings=["metrics.clicks DESC"],
      limit=10  # Top 10 products by total clicks across all 30 days
  )
  ```
- **When to use segments.date**:
  - ✅ For daily trend analysis (show performance by day)
  - ✅ When you want to see day-by-day breakdown
  - ✅ With NO LIMIT or very high limit to get all days
- **When NOT to use segments.date**:
  - ❌ When you want product/campaign totals over a period
  - ❌ When using LIMIT to get "top N" items
  - ❌ When aggregating metrics across dates

### change_event Resource
- **MUST** specify `LIMIT` ≤ 10000 when querying `change_event` resource

## 🎯 Common Resources & Their Fields

### campaign Resource

**Essential Fields (always work):**
- `campaign.id` - Campaign ID
- `campaign.name` - Campaign name
- `campaign.status` - Status (ENABLED, PAUSED, REMOVED)
- `campaign.advertising_channel_type` - Channel (SEARCH, DISPLAY, SHOPPING, VIDEO, etc.)
- `campaign.bidding_strategy_type` - Bidding strategy
- `campaign.start_date` - Start date (YYYY-MM-DD)
- `campaign.end_date` - End date (YYYY-MM-DD)

**Budget & Bidding:**
- `campaign.campaign_budget` - Budget resource name
- `campaign.target_cpa.target_cpa_micros` - Target CPA (in micros)
- `campaign.target_roas.target_roas` - Target ROAS
- `campaign.target_spend.target_spend_micros` - Target spend (in micros)

**All campaign fields are selectable, filterable, and sortable** (except a few nested ones).

### ad_group Resource

**Essential Fields:**
- `ad_group.id` - Ad group ID
- `ad_group.name` - Ad group name
- `ad_group.campaign` - Parent campaign resource name
- `ad_group.status` - Status (ENABLED, PAUSED, REMOVED)
- `ad_group.type` - Ad group type
- `ad_group.cpc_bid_micros` - CPC bid (in micros)
- `ad_group.cpm_bid_micros` - CPM bid (in micros)
- `ad_group.target_cpa_micros` - Target CPA (in micros)
- `ad_group.target_roas` - Target ROAS

**All ad_group fields are selectable, filterable, and sortable**.

### keyword_view Resource

**⚠️ LIMITED**: This resource only has:
- `keyword_view.resource_name` - Resource name (selectable, filterable)

**NO sortable fields available!**

**To get keyword data**, use `ad_group_criterion` resource instead with:
- `ad_group_criterion.keyword.text` - Keyword text
- `ad_group_criterion.keyword.match_type` - Match type

### metrics (Cross-Resource)

Metrics can be used with ANY resource. Common metrics:

**Performance:**
- `metrics.impressions` - Number of impressions
- `metrics.clicks` - Number of clicks
- `metrics.ctr` - Click-through rate
- `metrics.average_cpc` - Average cost per click
- `metrics.average_cpm` - Average cost per thousand impressions
- `metrics.average_cpv` - Average cost per view (video)

**Cost & Conversions:**
- `metrics.cost_micros` - Total cost in micros (divide by 1,000,000 for dollars)
- `metrics.conversions` - Total conversions
- `metrics.conversions_value` - Conversion value
- `metrics.all_conversions` - All conversions (includes cross-device)
- `metrics.all_conversions_value` - All conversions value

**Advanced:**
- `metrics.search_impression_share` - Impression share (%)
- `metrics.search_absolute_top_impression_percentage` - Top of page %
- `metrics.average_quality_score` - Quality score
- `metrics.bounce_rate` - Bounce rate

**ALL metrics are selectable, filterable, and sortable**.

### segments (Cross-Resource)

Segments break down data by dimensions. Common segments:

**Time:**
- `segments.date` - Date (YYYY-MM-DD)
- `segments.week` - Week
- `segments.month` - Month
- `segments.quarter` - Quarter
- `segments.year` - Year
- `segments.hour` - Hour of day (0-23)
- `segments.day_of_week` - Day (MONDAY, TUESDAY, etc.)

**Device & Location:**
- `segments.device` - Device type (MOBILE, DESKTOP, TABLET, etc.)
- `segments.geo_target_city` - City
- `segments.geo_target_metro` - Metro area
- `segments.geo_target_region` - State/region
- `segments.geo_target_country` - Country

**Ad Performance:**
- `segments.ad_network_type` - Network (SEARCH, CONTENT, etc.)
- `segments.click_type` - Click type
- `segments.conversion_action` - Conversion action
- `segments.conversion_action_name` - Conversion action name

**ALL segments are selectable, filterable, and sortable**.

## 📋 Query Examples

### 1. Basic Campaign Performance (Last 7 Days)
```python
search(
    customer_id="522-285-1423",
    fields=[
        "campaign.id",
        "campaign.name",
        "campaign.status",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.cost_micros",
        "metrics.conversions"
    ],
    resource="campaign",
    conditions=[
        "campaign.status = 'ENABLED'",
        "segments.date DURING LAST_7_DAYS"
    ],
    orderings=["metrics.cost_micros DESC"],
    limit=10
)
```

### 2. Ad Group Performance with CTR
```python
search(
    customer_id="522-285-1423",
    fields=[
        "ad_group.id",
        "ad_group.name",
        "ad_group.campaign",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.ctr",
        "metrics.cost_micros"
    ],
    resource="ad_group",
    conditions=[
        "ad_group.status = 'ENABLED'",
        "metrics.impressions > 100"
    ],
    orderings=["metrics.ctr DESC"],
    limit=20
)
```

### 3. Keyword Performance (Use ad_group_criterion)
```python
search(
    customer_id="522-285-1423",
    fields=[
        "ad_group.name",
        "ad_group_criterion.keyword.text",
        "ad_group_criterion.keyword.match_type",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.ctr",
        "metrics.average_cpc"
    ],
    resource="ad_group_criterion",
    conditions=[
        "ad_group_criterion.status = 'ENABLED'",
        "ad_group_criterion.type = 'KEYWORD'",
        "segments.date DURING LAST_30_DAYS"
    ],
    orderings=["metrics.clicks DESC"],
    limit=50
)
```

### 4. Campaign Performance by Device
```python
search(
    customer_id="522-285-1423",
    fields=[
        "campaign.name",
        "segments.device",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.ctr",
        "metrics.cost_micros",
        "metrics.conversions"
    ],
    resource="campaign",
    conditions=[
        "campaign.status = 'ENABLED'",
        "segments.date BETWEEN '2025-01-01' AND '2025-01-31'"
    ],
    orderings=["metrics.conversions DESC"]
)
```

### 5. Daily Performance Trend
```python
search(
    customer_id="522-285-1423",
    fields=[
        "segments.date",
        "campaign.name",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.cost_micros",
        "metrics.conversions"
    ],
    resource="campaign",
    conditions=[
        "campaign.status = 'ENABLED'",
        "segments.date DURING LAST_14_DAYS"
    ],
    orderings=["segments.date DESC"]
)
```

### 6. Top Spending Campaigns
```python
search(
    customer_id="522-285-1423",
    fields=[
        "campaign.name",
        "campaign.status",
        "metrics.cost_micros",
        "metrics.clicks",
        "metrics.conversions",
        "metrics.conversions_value"
    ],
    resource="campaign",
    conditions=[
        "segments.date DURING THIS_MONTH"
    ],
    orderings=["metrics.cost_micros DESC"],
    limit=10
)
```

## 🚨 Common Errors & Fixes

### Error: "Unrecognized field"
**Problem**: Field doesn't exist in the resource or is misspelled.

**Common mistakes**:
- ❌ `campaign.currency_code` - Does NOT exist (use account-level `customer.currency_code` instead)
- ❌ `campaign.budget` - Wrong (use `campaign.campaign_budget` which is a resource name)
- ❌ `asset_group_listing_group_filter.display_name` - Doesn't exist (too deeply nested)

**Fix**:
- Check field name against reference above
- Ensure field is fully qualified: `campaign.name`, not just `name`
- Use `customer.currency_code` for currency (from `customer` resource, not `campaign`)
- Avoid deeply nested fields that don't exist

### Error: "Request contains an invalid argument"
**Problem**: Usually date format or invalid field combination.

**Fix**:
- Check date format: Use `'YYYY-MM-DD'` with single quotes
- Check date range: Use `DURING` or `BETWEEN` operators
- Verify all fields are valid for the resource

### Error: "Cannot select field X with resource Y"
**Problem**: Field is not selectable for that specific resource.

**Fix**:
- Use simpler fields (campaign.id, campaign.name, etc.)
- Check if the field requires a segment (e.g., `segments.date` with metrics)

## 💡 Best Practices

### 1. Start Simple
Always start with basic fields and add complexity gradually:
```python
# Start with this
fields=["campaign.name", "metrics.clicks"]

# Then add more
fields=["campaign.name", "campaign.status", "metrics.clicks", "metrics.impressions"]
```

### 2. Use Appropriate Resources
- **campaign**: Campaign-level data
- **ad_group**: Ad group-level data
- **ad_group_criterion**: Keyword/placement data (NOT keyword_view)
- **ad_group_ad**: Ad creative data
- **search_term_view**: Search query data

### 3. Filter Intelligently
```python
# Good - specific status filter
conditions=["campaign.status = 'ENABLED'"]

# Good - date range
conditions=["segments.date DURING LAST_7_DAYS"]

# Good - performance threshold
conditions=["metrics.impressions > 1000"]
```

### 4. Cost Conversion
**ALL cost values are in micros**. Divide by 1,000,000 for dollars:
```python
# API returns: cost_micros = 5432100
# Actual cost: $5.43
actual_cost = cost_micros / 1_000_000
```

## 📊 Resource Selection Guide

| What You Need | Use Resource | Key Fields |
|--------------|-------------|------------|
| Campaign overview | `campaign` | `campaign.name`, `campaign.status` |
| Ad group performance | `ad_group` | `ad_group.name`, `ad_group.campaign` |
| Keyword performance | `ad_group_criterion` | `ad_group_criterion.keyword.text` |
| Ad creative data | `ad_group_ad` | `ad_group_ad.ad.id` |
| Search queries | `search_term_view` | `search_term_view.search_term` |
| Geographic data | Use `segments.geo_target_*` | With any resource |
| Device breakdown | Use `segments.device` | With any resource |
| Time-series | Use `segments.date` | With any resource |

## 🎯 When Things Fail

1. **Simplify the query** - Remove complex fields
2. **Remove segments** - Try without `segments.*` first
3. **Use basic fields** - Stick to `.id`, `.name`, `.status`
4. **Check spelling** - Field names are case-sensitive
5. **Verify resource** - Ensure field exists for that resource

## 📚 Additional Resources

- Official GAQL Guide: https://developers.google.com/google-ads/api/docs/query/overview
- Field Reference: https://developers.google.com/google-ads/api/fields/v18/overview
- Google Ads MCP GitHub: https://github.com/googleads/google-ads-mcp
