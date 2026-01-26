# Google Ads MCP Tools Reference

EspressoBot has access to Google's official Google Ads MCP server for campaign and ad data.

## Authentication
- Uses Application Default Credentials (ADC)
- Requires `adwords` scope (✅ already in OAuth)
- **CRITICAL**: Also requires Developer Token (see setup below)

## Setup Requirements

### Developer Token
Google Ads requires a Developer Token in addition to OAuth:

1. Applied for Developer Token at: https://ads.google.com/aw/apicenter
2. Added to environment variables:
```bash
GOOGLE_ADS_DEVELOPER_TOKEN=<your-production-token>
```

**✅ Status**: Production Developer Token **APPROVED** and active
- Full API access enabled
- All query capabilities available
- No restrictions on data access

### Customer ID
Most queries require a Customer ID (format: "123-456-7890")
- For iDrinkCoffee.com: Use hardcoded `522-285-1423`

## Available Tools

### `search`
- **Purpose**: Query Google Ads data using structured parameters
- **Function Signature**:
  ```python
  search(
      customer_id: str,
      fields: List[str],
      resource: str,
      conditions: List[str] = None,
      orderings: List[str] = None,
      limit: int | str = None
  ) -> List[Dict[str, Any]]
  ```
- **Parameters**:
  - `customer_id` (required): Customer ID (e.g., "522-285-1423")
  - `fields` (required): List of field names to retrieve
  - `resource` (required): Resource type (e.g., "campaign", "ad_group", "keyword_view")
  - `conditions` (optional): List of WHERE conditions combined with AND
  - `orderings` (optional): List of ORDER BY clauses (can include ASC/DESC)
  - `limit` (optional): Maximum number of rows to return

**Example Queries**:

1. **Campaign Performance**:
```python
search(
    customer_id="522-285-1423",
    fields=[
        "campaign.name",
        "campaign.status",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.ctr",
        "metrics.cost_micros",
        "metrics.conversions",
        "metrics.conversions_value"
    ],
    resource="campaign",
    conditions=[
        "campaign.status = 'ENABLED'",
        "segments.date DURING LAST_30_DAYS"
    ],
    orderings=["metrics.cost_micros DESC"],
    limit=10
)
```

2. **Keyword Analysis**:
```python
search(
    customer_id="522-285-1423",
    fields=[
        "ad_group.name",
        "ad_group_criterion.keyword.text",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.ctr",
        "metrics.cost_micros",
        "metrics.quality_score"
    ],
    resource="keyword_view",
    conditions=[
        "campaign.status = 'ENABLED'",
        "segments.date DURING LAST_7_DAYS"
    ],
    orderings=["metrics.clicks DESC"],
    limit=50
)
```

3. **Ad Group Performance**:
```python
search(
    customer_id="522-285-1423",
    fields=[
        "campaign.name",
        "ad_group.name",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.conversions",
        "metrics.cost_micros"
    ],
    resource="ad_group",
    conditions=["segments.date DURING THIS_MONTH"],
    orderings=["metrics.conversions DESC"],
    limit=20
)
```

4. **Search Terms Report**:
```python
search(
    customer_id="522-285-1423",
    fields=[
        "search_term_view.search_term",
        "metrics.impressions",
        "metrics.clicks",
        "metrics.ctr",
        "metrics.conversions"
    ],
    resource="search_term_view",
    conditions=["segments.date DURING LAST_14_DAYS"],
    orderings=["metrics.impressions DESC"],
    limit=100
)
```

### `list_accessible_customers`
- **Purpose**: Get list of all Google Ads customer accounts user can access
- **Parameters**: None
- **Returns**: List of customer IDs and account names
- **Use when**: Need to discover available accounts or verify access

## Common Use Cases

### 1. Daily Campaign Performance
```
User: "How are our Google Ads campaigns performing today?"

Steps:
1. Use search tool:
   search(
       customer_id="522-285-1423",
       fields=["campaign.name", "metrics.clicks", "metrics.cost_micros", "metrics.conversions"],
       resource="campaign",
       conditions=["segments.date = TODAY"]
   )
2. Format results for user, converting cost_micros to dollars
```

### 2. Budget Analysis
```
User: "Which campaigns are spending the most?"

Steps:
1. Use search:
   search(
       customer_id="522-285-1423",
       fields=["campaign.name", "campaign.budget_amount_micros", "metrics.cost_micros"],
       resource="campaign",
       conditions=["segments.date DURING LAST_7_DAYS"],
       orderings=["metrics.cost_micros DESC"],
       limit=10
   )
```

### 3. Keyword Optimization
```
User: "Show me low-performing keywords"

Steps:
1. Use search with quality_score filter:
   search(
       customer_id="522-285-1423",
       fields=["ad_group_criterion.keyword.text", "metrics.quality_score", "metrics.ctr"],
       resource="keyword_view",
       conditions=["metrics.quality_score < 5"],
       limit=50
   )
```

## Available Resources

### Common Resources (for `resource` parameter):
- `campaign` - Campaign data
- `ad_group` - Ad group data
- `ad_group_ad` - Ad creative data
- `keyword_view` - Keyword performance
- `search_term_view` - Search query data
- `customer` - Account-level data
- `ad_group_criterion` - Targeting criteria
- `campaign_budget` - Campaign budget data

### Common Metrics:
- `metrics.impressions` - Ad impressions
- `metrics.clicks` - Clicks
- `metrics.ctr` - Click-through rate
- `metrics.cost_micros` - Cost in micros (divide by 1,000,000 for dollars)
- `metrics.conversions` - Total conversions
- `metrics.conversions_value` - Conversion value
- `metrics.quality_score` - Keyword quality score (1-10)

### Common Dimensions:
- `campaign.name` - Campaign name
- `campaign.status` - Campaign status (ENABLED, PAUSED, REMOVED)
- `ad_group.name` - Ad group name
- `ad_group_criterion.keyword.text` - Keyword text
- `segments.date` - Date segment

### Date Filtering:
- `segments.date = TODAY`
- `segments.date = YESTERDAY`
- `segments.date DURING LAST_7_DAYS`
- `segments.date DURING THIS_MONTH`
- `segments.date DURING LAST_30_DAYS`
- `segments.date BETWEEN '2025-01-01' AND '2025-01-31'`

## Error Handling

Common errors:
- "Developer token required" → Set GOOGLE_ADS_DEVELOPER_TOKEN env var
- "Customer not found" → Verify customer ID format (with hyphens)
- "GAQL syntax error" → Check query syntax (similar to SQL)
- "Permission denied" → Ensure user has access to customer account

## Important Notes

- **Cost values are in micros**: Divide by 1,000,000 to convert to dollars
- **Customer ID format**: "123-456-7890" (with hyphens, not "1234567890")
- **Field names are case-sensitive**: Use exact field names from API reference
- **Selectability**: Not all fields can be selected together - check field compatibility
- **Results limit**: Default 10,000 rows maximum per query
- **Date ranges**: Limited to 1 year maximum
- **Conditions syntax**: Use proper operators (=, !=, <, >, <=, >=, IN, NOT IN, LIKE, DURING, BETWEEN)

## Field Reference

For a complete list of available fields, resources, and their properties:
- Official Google Ads API Field Reference: https://developers.google.com/google-ads/api/fields/v18/overview
- The MCP server dynamically loads field metadata including selectability, filterability, and sortability
