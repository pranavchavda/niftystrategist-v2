# List Category Landing Pages

Lists all category landing pages with complete data including hero sections, featured products, categories, educational content, and FAQs. Designed for the CMS interface.

## Use Cases
- Load all category landing pages for CMS dashboard
- Populate category page selection dropdowns
- Export category page data
- Audit existing category pages
- Bulk operations on category pages

## GraphQL

```graphql
query listCategoryLandingPages($cursor: String) {
  metaobjects(first: 50, type: "category_landing_page", after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        handle
        displayName
        fields {
          key
          value
          type
          reference {
            ... on MediaImage {
              image {
                url
                altText
              }
            }
          }
          references(first: 50) {
            nodes {
              ... on Product {
                id
                title
                handle
                featuredImage {
                  url
                  altText
                }
              }
              ... on Metaobject {
                id
                type
                handle
                fields {
                  key
                  value
                  type
                  reference {
                    ... on MediaImage {
                      image {
                        url
                        altText
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `cursor` | String | No | Pagination cursor for fetching next page |

## Required Scopes
- `read_metaobjects`
- `read_products` (for featured products and product references)
- `read_files` (for hero images and educational block images)

## Example

### List All Category Pages
```bash
python3 cms/list_category_landing_pages.py
```

### Output Format
```bash
python3 cms/list_category_landing_pages.py --output-format json
```

## Response Format

```json
{
  "pages": [
    {
      "id": "gid://shopify/Metaobject/123456",
      "handle": "espresso-machines",
      "displayName": "Espresso Machines",
      "heroImageUrl": "https://cdn.shopify.com/...",
      "heroTitle": "Premium Espresso Machines",
      "heroDescription": "Professional-grade machines for home baristas",
      "urlHandle": "espresso-machines",
      "title": "Espresso Machines",
      "seoTitle": "Buy Espresso Machines | iDrinkCoffee",
      "seoDescription": "Shop our collection...",
      "enableSorting": true,
      "featuredProducts": [
        {
          "id": "gid://shopify/Product/789012",
          "title": "Breville Barista Express",
          "handle": "breville-barista-express",
          "imageUrl": "https://cdn.shopify.com/..."
        }
      ],
      "sortingOptions": [
        {
          "id": "gid://shopify/Metaobject/111222",
          "label": "Price: Low to High",
          "filterType": "price",
          "filterValue": "asc"
        }
      ],
      "categories": [
        {
          "id": "gid://shopify/Metaobject/333444",
          "title": "Semi-Automatic Machines",
          "description": "Manual control with electric assistance",
          "collectionHandle": "semi-automatic-espresso",
          "maxProducts": 12,
          "productIds": ["gid://shopify/Product/555666"]
        }
      ],
      "comparisonTable": {
        "id": "gid://shopify/Metaobject/777888",
        "title": "Compare Top Espresso Machines",
        "productIds": [
          "gid://shopify/Product/111",
          "gid://shopify/Product/222"
        ],
        "featureIds": [
          "gid://shopify/Metaobject/333",
          "gid://shopify/Metaobject/444"
        ]
      },
      "educationalContent": [
        {
          "id": "gid://shopify/Metaobject/999000",
          "title": "How to Choose an Espresso Machine",
          "content": "{\"root\":{\"children\":[...]}}",
          "imageUrl": "https://cdn.shopify.com/...",
          "position": "1",
          "contentType": "article",
          "videoUrl": "",
          "ctaText": "Learn More",
          "ctaLink": "/pages/buying-guide"
        }
      ],
      "faqSection": {
        "id": "gid://shopify/Metaobject/121212",
        "title": "Espresso Machine FAQs",
        "questionIds": [
          "gid://shopify/Metaobject/131313",
          "gid://shopify/Metaobject/141414"
        ]
      }
    }
  ],
  "count": 1
}
```

## Data Structure

### Top-Level Fields
- `id`: Category landing page GID
- `handle`: Shopify handle (URL-safe identifier)
- `displayName`: Human-readable name
- `urlHandle`: Custom URL path (e.g., `/pages/espresso-machines`)
- `title`: Page title

### Hero Section
- `heroImageUrl`: Full URL to hero image
- `heroTitle`: Main heading for hero section
- `heroDescription`: Subtitle/description for hero

### SEO Fields
- `seoTitle`: Page title for search engines
- `seoDescription`: Meta description for search engines

### Settings
- `enableSorting`: Boolean - whether sorting UI is enabled

### Featured Products
Array of product objects:
- `id`: Product GID
- `title`: Product name
- `handle`: Product handle
- `imageUrl`: Featured image URL

### Sorting Options
Array of sorting option metaobjects:
- `id`: Sorting option GID
- `label`: Display label (e.g., "Price: Low to High")
- `filterType`: Filter type (price, title, etc.)
- `filterValue`: Sort direction (asc, desc)

### Categories
Array of category section metaobjects:
- `id`: Category section GID
- `title`: Section title
- `description`: Section description
- `collectionHandle`: Linked Shopify collection handle
- `maxProducts`: Maximum products to display (1-20)
- `productIds`: Array of manually selected product GIDs

### Comparison Table
Single comparison table metaobject:
- `id`: Comparison table GID
- `title`: Table title
- `productIds`: Array of product GIDs to compare
- `featureIds`: Array of comparison feature GIDs

### Educational Content
Array of educational block metaobjects:
- `id`: Educational block GID
- `title`: Block title
- `content`: Rich text content (JSON format)
- `imageUrl`: Block image URL
- `position`: Display order
- `contentType`: Content type (article, video, guide)
- `videoUrl`: Optional video embed URL
- `ctaText`: Call-to-action button text
- `ctaLink`: CTA button link

### FAQ Section
Single FAQ section metaobject:
- `id`: FAQ section GID
- `title`: Section title
- `questionIds`: Array of FAQ item GIDs

## Pagination

The script automatically handles pagination:
1. Fetches 50 pages per request
2. Continues with cursor if `hasNextPage` is true
3. Returns all pages in single response

## Notes
- **Complete Data**: Fetches all nested references (products, metaobjects) in a single query
- **Performance**: Uses `references(first: 50)` for list fields - adjust if needed
- **JSON Fields**: List reference fields are stored as JSON strings and parsed by the script
- **Rich Text**: Educational content uses Shopify's rich text JSON format
- **CMS Integration**: Response format matches CMS frontend expectations
- **No Parameters**: Always lists all category landing pages (filtered by type)
- **Automatic Expansion**: Script expands all nested metaobjects and extracts relevant fields
- **Error Handling**: Gracefully handles missing or malformed data
