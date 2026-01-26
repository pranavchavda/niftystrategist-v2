# URL Redirect Operations

Manage URL redirects in your Shopify store to handle old URLs, maintain SEO, and improve user experience.

## Use Cases
- Create 301 redirects for renamed products or pages
- Migrate from old URL structures to new ones
- Maintain SEO rankings when changing URLs
- Handle legacy URLs from store migrations
- Redirect deleted products to category pages

## Operations

### Create URL Redirect

Creates a new URL redirect from an old path to a new target.

**GraphQL Mutation:**

```graphql
mutation createUrlRedirect($redirect: UrlRedirectInput!) {
  urlRedirectCreate(urlRedirect: $redirect) {
    urlRedirect {
      id
      path
      target
    }
    userErrors {
      field
      message
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| redirect | UrlRedirectInput! | Yes | Redirect configuration object |
| redirect.path | String | Yes | Source path to redirect from (e.g., "/old-path") |
| redirect.target | String | Yes | Target path to redirect to (e.g., "/new-path") |

**Required Scopes:** `write_online_store_navigation`, `read_online_store_navigation`

**Example:**

```bash
python utilities/manage_redirects.py --action create --from "/old-espresso-machine" --to "/collections/espresso-machines/products/new-machine"
```

**Notes:**
- Path must start with "/"
- Target can be relative path or full URL
- Creates a 301 (permanent) redirect
- Duplicates are not allowed - delete existing redirect first

---

### List URL Redirects

Retrieves a list of all URL redirects in the store.

**GraphQL Query:**

```graphql
query listRedirects($first: Int!) {
  urlRedirects(first: $first) {
    edges {
      node {
        id
        path
        target
      }
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| first | Int! | Yes | Number of redirects to fetch (max 250 per query) |

**Required Scopes:** `read_online_store_navigation`

**Example:**

```bash
python utilities/manage_redirects.py --action list --limit 50
```

**Notes:**
- Default limit is 50 redirects
- Use pagination (pageInfo) for stores with many redirects
- Results are returned in order of creation

---

### Delete URL Redirect

Deletes an existing URL redirect by ID.

**GraphQL Mutation:**

```graphql
mutation deleteUrlRedirect($id: ID!) {
  urlRedirectDelete(id: $id) {
    deletedUrlRedirectId
    userErrors {
      field
      message
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Global ID of the redirect (gid://shopify/UrlRedirect/{id}) |

**Required Scopes:** `write_online_store_navigation`, `read_online_store_navigation`

**Example:**

```bash
python utilities/manage_redirects.py --action delete --id "gid://shopify/UrlRedirect/123456789"
```

**Notes:**
- ID can be provided as full GID or just numeric ID (script converts automatically)
- Deletion is permanent and cannot be undone
- Returns the deleted redirect's ID on success

---

## Common Workflows

### Migrate Product URLs
```bash
# Step 1: List existing redirects to avoid conflicts
python utilities/manage_redirects.py --action list

# Step 2: Create redirect from old URL to new URL
python utilities/manage_redirects.py --action create \
  --from "/products/old-breville-machine" \
  --to "/products/breville-barista-express"

# Step 3: Verify redirect was created
python utilities/manage_redirects.py --action list
```

### Clean Up Old Redirects
```bash
# List all redirects
python utilities/manage_redirects.py --action list > redirects.txt

# Delete specific redirect
python utilities/manage_redirects.py --action delete --id "gid://shopify/UrlRedirect/123"
```

## Best Practices

1. **Always use relative paths** - Start paths with "/" for consistency
2. **Test redirects** - Verify redirects work before publishing
3. **Keep target URLs valid** - Ensure redirect targets exist and are active
4. **Document redirect reasons** - Keep notes on why redirects were created
5. **Review periodically** - Clean up outdated redirects that are no longer needed
6. **Chain carefully** - Avoid redirect chains (A → B → C), use direct redirects (A → C)

## Error Handling

Common errors and solutions:

- **"Path has already been taken"** - Redirect already exists for this path, delete old one first
- **"Path is invalid"** - Ensure path starts with "/" and has no spaces
- **"Target is invalid"** - Verify target URL is properly formatted
- **"Redirect not found"** - Check the redirect ID is correct and exists

## Related Operations

- Product URL changes: `products/update-product.md`
- Collection URL changes: `collections/update-collection.md`
- Page management: `pages/` operations
