# Segment Query Language Reference

The segment query language is a subset of ShopifyQL used specifically for customer segmentation in the Shopify Admin. It uses only the `WHERE` clause syntax to filter customers by their attributes.

## Overview

**Purpose**: Create collections of customers filtered by specific criteria
- **Filtered customers** = "segment members"
- **Collections of filtered customers** = "segments"
- **Merchants**: Can create segments in Shopify admin
- **Apps**: Can programmatically create segments via Admin API

## Key Differences from Full ShopifyQL

| Feature | Full ShopifyQL | Segment Query Language |
|---------|----------------|------------------------|
| Datasets | orders, products, payment_attempts | Customers only |
| Clauses | FROM, SHOW, GROUP BY, WHERE, etc. | WHERE only |
| Purpose | Analytics queries | Customer filtering |
| Output | Table data | Customer list |
| API | shopifyqlQuery | Customer segments API |

## Syntax

The segment query language uses only `WHERE` clause syntax:

```
WHERE { condition }
```

Where `condition` is an expression using:
- Customer attributes (fields)
- Comparison operators (=, !=, <, >, <=, >=)
- Logical operators (AND, OR, NOT)

## Customer Attributes

### Core Customer Fields

| Attribute | Type | Description |
|-----------|------|-------------|
| `email` | string | Customer email address |
| `first_name` | string | Customer first name |
| `last_name` | string | Customer last name |
| `phone` | string | Customer phone number |
| `city` | string | Customer city |
| `country` | string | Customer country |
| `province` | string | Customer state/province |
| `zip` | string | Customer postal/ZIP code |
| `tags` | string | Customer tags |
| `accepts_marketing` | boolean | Email marketing consent |
| `accepts_sms_marketing` | boolean | SMS marketing consent |

### Purchase History Fields

| Attribute | Type | Description |
|-----------|------|-------------|
| `total_spent` | number | Total amount customer has spent |
| `orders_count` | number | Total number of orders |
| `average_order_value` | number | Average order value |
| `first_order_date` | date | Date of first order |
| `last_order_date` | date | Date of most recent order |
| `days_since_last_order` | number | Days since last purchase |

### Engagement Fields

| Attribute | Type | Description |
|-----------|------|-------------|
| `email_marketing_state` | string | Email marketing status (subscribed, unsubscribed, etc.) |
| `sms_marketing_state` | string | SMS marketing status |
| `account_creation_date` | date | When customer account was created |
| `days_since_account_creation` | number | Days since account creation |

## Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equal to | `country = 'United States'` |
| `!=` | Not equal to | `email_marketing_state != 'unsubscribed'` |
| `<` | Less than | `total_spent < 100` |
| `>` | Greater than | `orders_count > 5` |
| `<=` | Less than or equal to | `days_since_last_order <= 30` |
| `>=` | Greater than or equal to | `total_spent >= 500` |

## Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Both conditions must be true | `total_spent > 500 AND orders_count >= 3` |
| `OR` | Either condition must be true | `city = 'Toronto' OR city = 'Montreal'` |
| `NOT` | Condition must be false | `NOT accepts_marketing` |

## Common Patterns

### High-Value Customers
```shopifyql
WHERE total_spent > 1000 AND orders_count >= 5
```

### Recent Customers
```shopifyql
WHERE days_since_first_order <= 30
```

### Lapsed Customers
```shopifyql
WHERE days_since_last_order > 180 AND orders_count > 0
```

### VIP Customers (Multiple Criteria)
```shopifyql
WHERE total_spent > 2000
AND orders_count >= 10
AND accepts_marketing = true
```

### Location-Based Segments
```shopifyql
WHERE country = 'United States'
AND (province = 'CA' OR province = 'NY' OR province = 'TX')
```

### Email Marketing Eligibility
```shopifyql
WHERE accepts_marketing = true
AND email_marketing_state = 'subscribed'
AND email != ''
```

### At-Risk Customers
```shopifyql
WHERE total_spent > 500
AND days_since_last_order > 90
AND days_since_last_order <= 180
```

### First-Time Buyers
```shopifyql
WHERE orders_count = 1
AND days_since_first_order <= 60
```

### Potential Repeat Buyers
```shopifyql
WHERE orders_count = 1
AND days_since_first_order > 7
AND days_since_first_order <= 30
```

### Geographic Targeting
```shopifyql
WHERE country = 'Canada'
AND province != 'QC'
AND city != 'Montreal'
```

### Customer Tags
```shopifyql
WHERE tags = 'wholesale'
OR tags = 'vip'
```

### Combined Behavioral + Demographic
```shopifyql
WHERE (total_spent > 1000 OR orders_count >= 10)
AND country = 'United States'
AND accepts_marketing = true
```

## Best Practices

### 1. Start Broad, Refine Later
Begin with simple conditions and add complexity:
```shopifyql
-- Start simple
WHERE total_spent > 500

-- Add refinement
WHERE total_spent > 500 AND orders_count >= 3

-- Add more criteria
WHERE total_spent > 500
AND orders_count >= 3
AND days_since_last_order <= 90
```

### 2. Use Parentheses for Clarity
Group conditions explicitly:
```shopifyql
WHERE (total_spent > 1000 OR orders_count >= 10)
AND accepts_marketing = true
```

### 3. Consider Edge Cases
Account for null/empty values:
```shopifyql
WHERE email != ''
AND accepts_marketing = true
```

### 4. Test Segment Size
Check resulting customer count before using:
- Too broad: May include unintended customers
- Too narrow: May exclude valuable targets

### 5. Use Meaningful Time Windows
Choose appropriate day ranges:
- Recent: 0-30 days
- Active: 31-90 days
- At-risk: 91-180 days
- Lapsed: 180+ days

## Common Pitfalls

### ❌ Don't Use Full ShopifyQL Syntax
```shopifyql
-- WRONG - No FROM clause
FROM customers WHERE total_spent > 500

-- WRONG - No SHOW clause
WHERE total_spent > 500 SHOW email

-- WRONG - No GROUP BY
WHERE total_spent > 500 GROUP BY country
```

### ✅ Use Only WHERE Clause
```shopifyql
-- CORRECT
WHERE total_spent > 500
```

### ❌ Don't Forget Operator Spacing
```shopifyql
-- WRONG - No spaces
WHERE total_spent>500

-- CORRECT - Proper spacing
WHERE total_spent > 500
```

### ❌ Don't Mix Data Types
```shopifyql
-- WRONG - Comparing string to number
WHERE orders_count = '5'

-- CORRECT - Match types
WHERE orders_count = 5
```

## Advanced Examples

### Win-Back Campaign Target
Customers who spent well but haven't ordered recently:
```shopifyql
WHERE total_spent > 500
AND orders_count >= 3
AND days_since_last_order > 120
AND days_since_last_order <= 365
AND accepts_marketing = true
```

### Upsell Opportunity
Low order count but good average order value:
```shopifyql
WHERE average_order_value > 200
AND orders_count >= 2
AND orders_count <= 5
AND days_since_last_order <= 60
```

### Loyalty Program Candidates
Consistent buyers with high lifetime value:
```shopifyql
WHERE total_spent > 1500
AND orders_count >= 8
AND days_since_last_order <= 90
AND accepts_marketing = true
```

### Location-Specific Promotion
Target specific regions excluding others:
```shopifyql
WHERE country = 'United States'
AND province IN ('CA', 'WA', 'OR')
AND city != 'San Francisco'
AND total_spent > 250
```

*Note: `IN` operator availability depends on Shopify API version*

## API Integration

### Creating Segments via API

```graphql
mutation {
  segmentCreate(
    name: "High Value Customers"
    query: "total_spent > 1000 AND orders_count >= 5"
  ) {
    segment {
      id
      name
      query
    }
    userErrors {
      field
      message
    }
  }
}
```

### Retrieving Segment Members

```graphql
{
  segment(id: "gid://shopify/Segment/12345") {
    id
    name
    query
    segmentMemberConnection(first: 50) {
      edges {
        node {
          customer {
            id
            email
            firstName
            lastName
            totalSpent
            ordersCount
          }
        }
      }
    }
  }
}
```

## See Also

- [Full ShopifyQL Syntax Reference](./syntax-reference.md)
- [ShopifyQL Overview](./shopifyql-overview.md)
- [Shopify Customer Segments Documentation](https://shopify.dev/docs/api/admin-graphql/latest/objects/Segment)
- [Customer Object Reference](https://shopify.dev/docs/api/admin-graphql/latest/objects/Customer)

---

**Last Updated**: 2025-01-06
**API Compatibility**: Admin GraphQL API 2024-04+
