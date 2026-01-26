# GA4 Query Examples

Common GA4 report patterns for quick reference.

(To be populated with real query examples as we use the system)

## Traffic Sources

### Basic Traffic Source Report
```python
run_report(
    property_id="YOUR_PROPERTY_ID",
    date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
    dimensions=["sessionSource", "sessionMedium"],
    metrics=["sessions", "activeUsers", "conversions"]
)
```

### Top Landing Pages
```python
run_report(
    property_id="YOUR_PROPERTY_ID",
    date_ranges=[{"start_date": "30daysAgo", "end_date": "today"}],
    dimensions=["landingPage"],
    metrics=["sessions", "bounceRate", "averageSessionDuration"],
    order_bys=[{"metric": {"metricName": "sessions"}, "desc": True}],
    limit=25
)
```

## E-commerce Performance

### Revenue by Product
```python
run_report(
    property_id="YOUR_PROPERTY_ID",
    date_ranges=[{"start_date": "30daysAgo", "end_date": "today"}],
    dimensions=["itemName"],
    metrics=["itemRevenue", "itemsPurchased", "itemsViewed"],
    order_bys=[{"metric": {"metricName": "itemRevenue"}, "desc": True}],
    limit=50
)
```

### Conversion Funnel
```python
run_report(
    property_id="YOUR_PROPERTY_ID",
    date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
    dimensions=["eventName"],
    metrics=["eventCount", "conversions"],
    dimension_filter={
        "filter": {
            "fieldName": "eventName",
            "inListFilter": {"values": ["page_view", "add_to_cart", "begin_checkout", "purchase"]}
        }
    }
)
```

## User Behavior

### Device Breakdown
```python
run_report(
    property_id="YOUR_PROPERTY_ID",
    date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
    dimensions=["deviceCategory"],
    metrics=["activeUsers", "sessions", "engagementRate", "averageSessionDuration"]
)
```

### Geographic Analysis
```python
run_report(
    property_id="YOUR_PROPERTY_ID",
    date_ranges=[{"start_date": "30daysAgo", "end_date": "today"}],
    dimensions=["country", "city"],
    metrics=["activeUsers", "sessions", "purchaseRevenue"],
    order_bys=[{"metric": {"metricName": "sessions"}, "desc": True}],
    limit=100
)
```

## Real-time Monitoring

### Current Active Users
```python
run_realtime_report(
    property_id="YOUR_PROPERTY_ID",
    metrics=["activeUsers"]
)
```

### Live Traffic Sources
```python
run_realtime_report(
    property_id="YOUR_PROPERTY_ID",
    dimensions=["sessionSource"],
    metrics=["activeUsers"],
    order_bys=[{"metric": {"metricName": "activeUsers"}, "desc": True}],
    limit=10
)
```

### Currently Active Pages
```python
run_realtime_report(
    property_id="YOUR_PROPERTY_ID",
    dimensions=["unifiedScreenName"],
    metrics=["screenPageViews"],
    order_bys=[{"metric": {"metricName": "screenPageViews"}, "desc": True}],
    limit=20
)
```

---

*This file will be expanded with more examples as EspressoBot uses GA4 MCP tools in production.*
