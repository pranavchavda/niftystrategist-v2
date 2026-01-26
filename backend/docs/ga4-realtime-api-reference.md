# GA4 Realtime API Reference

Complete reference for using the GA4 Realtime API correctly.

**Source**: Official Google Analytics Data API v1 Realtime Schema
**URL**: https://developers.google.com/analytics/devguides/reporting/data/v1/realtime-api-schema

---

## ⚠️ Critical Rules

### Realtime API is VERY LIMITED

The Realtime API has **far fewer dimensions and metrics** than standard GA4 reports. Many common fields like `sessionSource`, `sessionMedium`, `totalRevenue`, and `sessions` are **NOT available** in realtime.

**If you need traffic source data, conversion values, or session counts**: Use `run_report()` instead of `run_realtime_report()`.

---

## Valid Dimensions for Realtime Reports

**ONLY these dimensions work with `run_realtime_report`:**

| API Name | Description | Notes |
|----------|-------------|-------|
| `appVersion` | App's version name | For Android/iOS apps |
| `audienceId` | Numeric identifier of an Audience | Historical audience membership |
| `audienceName` | Given name of an Audience | Historical audience membership |
| `audienceResourceName` | Resource name of the audience | Unique identifier |
| `city` | City of user activity origin | Derived from IP address |
| `cityId` | Geographic ID of the city | Derived from IP address |
| `country` | Country of user activity origin | Derived from IP address |
| `countryId` | Geographic ID of the country | ISO 3166-1 alpha-2 |
| `deviceCategory` | Device type | Desktop, Tablet, or Mobile |
| `eventName` | Name of the event | - |
| `minutesAgo` | Minutes since event collection | 00 is current minute |
| `platform` | Platform of app/website | Web, iOS, Android |
| `streamId` | Numeric data stream identifier | - |
| `streamName` | Data stream name | - |
| `unifiedScreenName` | Page title or screen name | Web/app event location |
| `customUser:*` | User-scoped Custom Dimension | Requires prior registration |

### ❌ Common Mistakes - Fields That DON'T Exist in Realtime

These fields work in `run_report()` but **NOT** in `run_realtime_report()`:

- ❌ `sessionSource` - NOT available in realtime (use `run_report()` instead)
- ❌ `sessionMedium` - NOT available in realtime (use `run_report()` instead)
- ❌ `sessionCampaignName` - NOT available in realtime (use `run_report()` instead)
- ❌ `source` - Does NOT exist (it's `sessionSource` in standard reports)
- ❌ `medium` - Does NOT exist (it's `sessionMedium` in standard reports)
- ❌ `pagePath` - NOT available in realtime (use `unifiedScreenName` instead)
- ❌ `date` - NOT available in realtime (realtime is always "now")
- ❌ `newVsReturning` - NOT available in realtime

---

## Valid Metrics for Realtime Reports

**ONLY these 4 metrics work with `run_realtime_report`:**

| API Name | Description | Notes |
|----------|-------------|-------|
| `activeUsers` | Number of distinct users | Currently active on site/app |
| `eventCount` | Count of events | Total events fired |
| `keyEvents` | Count of key events | Events marked as "key" (conversions) |
| `screenPageViews` | Number of app screens/web pages viewed | Includes repeated views |

### ❌ Metrics That DON'T Work in Realtime

These metrics work in `run_report()` but **NOT** in `run_realtime_report()`:

- ❌ `conversions` - Use `keyEvents` instead
- ❌ `totalRevenue` - NOT available in realtime
- ❌ `sessions` - NOT available in realtime
- ❌ `bounceRate` - NOT available in realtime
- ❌ `averageSessionDuration` - NOT available in realtime
- ❌ `engagementRate` - NOT available in realtime
- ❌ Custom metrics - NOT supported in realtime

---

## Query Examples

### 1. Active Users Right Now (Overall)

```python
run_realtime_report(
    property_id="325181275",
    dimensions=[],  # No dimensions = overall count
    metrics=["activeUsers"]
)
```

### 2. Active Users by Country

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["country"],
    metrics=["activeUsers", "screenPageViews"],
    limit=10
)
```

### 3. Active Users by Device

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["deviceCategory"],
    metrics=["activeUsers", "screenPageViews", "eventCount"]
)
```

### 4. Top Pages/Screens Right Now

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["unifiedScreenName"],
    metrics=["activeUsers", "screenPageViews"],
    limit=10
)
```

### 5. Events by Name (Last 30 Minutes)

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["eventName"],
    metrics=["eventCount", "keyEvents"],
    limit=20
)
```

### 6. Activity by City

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["city", "country"],
    metrics=["activeUsers", "screenPageViews"],
    limit=15
)
```

### 7. Filter by Specific Event

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["unifiedScreenName"],
    metrics=["eventCount"],
    dimension_filter={
        "filter": {
            "field_name": "eventName",
            "string_filter": {
                "match_type": "EXACT",
                "value": "purchase"
            }
        }
    },
    limit=10
)
```

---

## Minute Ranges

Realtime data covers the **last 30 minutes** by default. You can filter by specific minute ranges:

```python
run_realtime_report(
    property_id="325181275",
    dimensions=["minutesAgo"],
    metrics=["activeUsers", "screenPageViews"],
    dimension_filter={
        "filter": {
            "field_name": "minutesAgo",
            "numeric_filter": {
                "operation": "LESS_THAN",
                "value": {"int64_value": 5}  # Last 5 minutes
            }
        }
    }
)
```

---

## When to Use Realtime vs Standard Reports

### Use `run_realtime_report()` when:
- ✅ You need data from the **last 30 minutes**
- ✅ You want to see **currently active users**
- ✅ You only need basic dimensions (country, device, page, event)
- ✅ You don't need traffic source or campaign data

### Use `run_report()` when:
- ✅ You need **historical data** (yesterday, last week, last month)
- ✅ You need **traffic source dimensions** (sessionSource, sessionMedium)
- ✅ You need **revenue or conversion values**
- ✅ You need **session-level metrics**
- ✅ You need **custom metrics**
- ✅ You need **date ranges and time-series data**

---

## Best Practices

1. **Don't use realtime for traffic source analysis** - Use `run_report()` with `sessionSource` and `sessionMedium` dimensions
2. **Use `unifiedScreenName`** - NOT `pagePath` for page data in realtime
3. **Use `keyEvents`** - NOT `conversions` for conversion counting in realtime
4. **Keep it simple** - Realtime API has only 16 dimensions and 4 metrics
5. **Consider latency** - Realtime data may have a 1-2 minute delay

---

## Property ID

For iDrinkCoffee.com: **325181275**

---

## Error Troubleshooting

### "Field X is not a valid dimension"
**Cause**: Using a dimension that doesn't exist in realtime API
**Solution**: Check the "Valid Dimensions" table above. If you need traffic sources, use `run_report()` instead.

### "Field X is not a valid metric"
**Cause**: Using a metric that doesn't exist in realtime API
**Solution**: Check the "Valid Metrics" table above. For revenue/sessions, use `run_report()` instead.

### "Event-scoped custom dimensions not supported"
**Cause**: Trying to use custom dimensions other than user-scoped
**Solution**: Only `customUser:*` dimensions work in realtime, not event-scoped or item-scoped.

---

## Official Documentation

- **Realtime API Schema**: https://developers.google.com/analytics/devguides/reporting/data/v1/realtime-api-schema
- **Realtime Basics**: https://developers.google.com/analytics/devguides/reporting/data/v1/realtime-basics
- **Google Analytics MCP**: https://github.com/googleanalytics/google-analytics-mcp
