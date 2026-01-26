# Google Analytics 4 MCP Tools Reference

EspressoBot has access to Google's official GA4 MCP server for real-time analytics queries.

## Authentication
- Uses Application Default Credentials (ADC)
- Requires `analytics.readonly` scope (✅ already in OAuth)
- No additional configuration needed

## Available Tools

### Account & Property Management

#### `get_account_summaries()`
- **Purpose**: List all GA4 accounts and properties user has access to
- **Parameters**: None
- **Returns**: List of accounts with their properties and property IDs
- **Use when**: Need to discover available properties or get property IDs

**Example**:
```
Use: "Show me all GA4 properties I have access to"
Tool: get_account_summaries()
```

#### `get_property_details(property_id: str)`
- **Purpose**: Get detailed information about a specific GA4 property
- **Parameters**:
  - `property_id`: GA4 property ID (format: "123456789")
- **Returns**: Property configuration, timezone, currency, etc.

#### `list_google_ads_links(property_id: str)`
- **Purpose**: Show Google Ads accounts linked to a GA4 property
- **Parameters**:
  - `property_id`: GA4 property ID
- **Returns**: List of linked Google Ads accounts

### Core Reporting

#### `run_report(...)`
- **Purpose**: Run custom GA4 reports with dimensions, metrics, and filters
- **Key Parameters**:
  - `property_id`: GA4 property ID (required)
  - `date_ranges`: List of date ranges, e.g. [{"start_date": "2025-01-01", "end_date": "2025-01-07"}]
  - `dimensions`: List of dimension names (e.g., ["country", "deviceCategory"])
  - `metrics`: List of metric names (e.g., ["activeUsers", "sessions", "conversions"])
  - `dimension_filter`: Optional filter on dimensions
  - `metric_filter`: Optional filter on metrics
  - `order_bys`: Optional sorting
  - `limit`: Max rows to return
- **Returns**: Tabular report data

**Common Use Cases**:
```
1. Traffic by source: dimensions=["sessionSource"], metrics=["sessions", "conversions"]
2. Device breakdown: dimensions=["deviceCategory"], metrics=["activeUsers", "engagementRate"]
3. Page views: dimensions=["pagePath"], metrics=["screenPageViews"]
4. Geographic analysis: dimensions=["country", "city"], metrics=["activeUsers", "purchaseRevenue"]
```

#### `get_dimensions(property_id: str)`
- **Purpose**: List all available dimensions (custom + standard) for a property
- **Use when**: Need to discover what dimensions are available
- **Returns**: List of dimension API names with descriptions

#### `get_metrics(property_id: str)`
- **Purpose**: List all available metrics (custom + standard) for a property
- **Use when**: Need to discover what metrics are available
- **Returns**: List of metric API names with descriptions

#### `get_standard_dimensions()`
- **Purpose**: Get list of all standard GA4 dimensions
- **Returns**: Comprehensive list of built-in dimensions

#### `get_standard_metrics()`
- **Purpose**: Get list of all standard GA4 metrics
- **Returns**: Comprehensive list of built-in metrics

### Real-time Reporting

#### `run_realtime_report(...)`
- **Purpose**: Get live data for what's happening right now
- **Parameters**: Similar to `run_report` but for real-time data (last 30 minutes)
  - `property_id`, `dimensions`, `metrics`, `filters`, `order_bys`, `limit`
- **Returns**: Real-time analytics data

**Use Cases**:
```
1. Current visitors: metrics=["activeUsers"]
2. Live traffic sources: dimensions=["sessionSource"], metrics=["activeUsers"]
3. Active pages: dimensions=["unifiedScreenName"], metrics=["screenPageViews"]
```

#### `get_realtime_dimensions()`
- **Purpose**: List dimensions available for real-time reports
- **Returns**: Real-time dimension names

#### `get_realtime_metrics()`
- **Purpose**: List metrics available for real-time reports
- **Returns**: Real-time metric names

## Common Workflows

### Example 1: Traffic Analysis
```
1. get_property_details(property_id) → Get property info
2. run_report(
     property_id="123456789",
     date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
     dimensions=["sessionSource", "sessionMedium"],
     metrics=["sessions", "conversions", "purchaseRevenue"]
   )
```

### Example 2: Real-time Monitoring
```
1. get_realtime_dimensions() → See available dimensions
2. run_realtime_report(
     property_id="123456789",
     dimensions=["deviceCategory"],
     metrics=["activeUsers"]
   )
```

### Example 3: Custom Dimensions Discovery
```
1. get_dimensions(property_id="123456789") → See all custom dimensions
2. get_metrics(property_id="123456789") → See all custom metrics
3. run_report with discovered custom dimensions/metrics
```

## Important Notes

- Property ID format: Just the numeric ID (e.g., "123456789"), not "properties/123456789"
- Date formats: Use "YYYY-MM-DD" or relative dates like "7daysAgo", "yesterday", "today"
- Dimension/metric names: Use camelCase (e.g., "activeUsers", not "active_users")
- Real-time data: Last 30 minutes only
- Standard reports: Historical data (not older than 14 months by default)

## Error Handling

Common errors:
- "Property not found" → Check property ID is correct
- "Invalid dimension/metric" → Use get_dimensions/get_metrics to discover valid names
- "Insufficient permissions" → Ensure user has Analytics read access
