# Google Ads GAQL Query Examples

Sample GAQL queries for common use cases.

(To be populated with real queries as we use the system)

## Campaign Performance

### Overall Campaign Metrics
```sql
SELECT
  campaign.name,
  campaign.status,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.average_cpc
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.cost_micros DESC
```

### Campaign Performance by Day
```sql
SELECT
  campaign.name,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
  AND campaign.status = 'ENABLED'
ORDER BY segments.date DESC, metrics.clicks DESC
```

## Keyword Analysis

### Top Performing Keywords
```sql
SELECT
  campaign.name,
  ad_group.name,
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros,
  metrics.conversions,
  metrics.quality_score
FROM keyword_view
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status = 'ENABLED'
  AND ad_group.status = 'ENABLED'
ORDER BY metrics.conversions DESC
LIMIT 50
```

### Low Quality Score Keywords
```sql
SELECT
  ad_group_criterion.keyword.text,
  metrics.quality_score,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros
FROM keyword_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.quality_score < 5
  AND metrics.impressions > 100
ORDER BY metrics.cost_micros DESC
LIMIT 100
```

## Budget Optimization

### Daily Spend by Campaign
```sql
SELECT
  campaign.name,
  segments.date,
  metrics.cost_micros,
  campaign.budget_amount_micros
FROM campaign
WHERE segments.date DURING THIS_MONTH
ORDER BY segments.date DESC, metrics.cost_micros DESC
```

### Budget Utilization
```sql
SELECT
  campaign.name,
  campaign.budget_amount_micros,
  metrics.cost_micros,
  metrics.impressions,
  metrics.clicks
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
ORDER BY metrics.cost_micros DESC
```

## Search Terms

### Search Terms Report
```sql
SELECT
  search_term_view.search_term,
  campaign.name,
  ad_group.name,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros,
  metrics.conversions
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.impressions > 10
ORDER BY metrics.impressions DESC
LIMIT 200
```

### High-Cost Search Terms
```sql
SELECT
  search_term_view.search_term,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.cost_micros > 50000000  -- $50 in micros
ORDER BY metrics.cost_micros DESC
LIMIT 50
```

## Ad Group Analysis

### Ad Group Performance
```sql
SELECT
  campaign.name,
  ad_group.name,
  ad_group.status,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros,
  metrics.conversions
FROM ad_group
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.conversions DESC
```

### Underperforming Ad Groups
```sql
SELECT
  campaign.name,
  ad_group.name,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros
FROM ad_group
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.impressions > 1000
  AND metrics.ctr < 0.01  -- CTR below 1%
ORDER BY metrics.cost_micros DESC
```

## Conversion Tracking

### Conversion by Campaign
```sql
SELECT
  campaign.name,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_per_conversion,
  metrics.conversions_from_interactions_rate
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.conversions > 0
ORDER BY metrics.conversions DESC
```

### Conversion Actions
```sql
SELECT
  segments.conversion_action_name,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_per_conversion
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.conversions > 0
ORDER BY metrics.conversions DESC
```

---

*This file will be expanded with more examples as EspressoBot uses Google Ads MCP tools in production.*
