# Shopify Image Uploads: Staged vs Permanent Files

## Overview

When uploading images to Shopify, there are two types of URLs:

1. **Staged Upload URLs** - Temporary URLs that expire after 24-48 hours
2. **Permanent CDN URLs** - Persistent URLs stored in Shopify Files

## The Problem with Staged Uploads

Staged uploads are designed for temporary use during product creation workflows. They:
- Expire after 24-48 hours
- Don't appear in Shopify Admin → Content → Files
- Will break if used directly in landing pages or metafields

## Workflow: Converting Staged Uploads to Permanent Files

### Step 1: Create Staged Uploads

Use `stagedUploadsCreate` to get temporary upload URLs:

```graphql
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets {
      url
      resourceUrl
      parameters {
        name
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

Variables:
```json
{
  "input": [
    {
      "filename": "My-Image.jpg",
      "mimeType": "image/jpeg",
      "resource": "FILE",
      "fileSize": "123456"
    }
  ]
}
```

### Step 2: Upload File to Staged URL

Use curl or similar to upload the actual file to the staged URL with the provided parameters.

### Step 3: Convert to Permanent File

**This is the critical step often missed.** Use `fileCreate` to convert staged uploads to permanent files:

```graphql
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files {
      id
      alt
      fileStatus
      ... on MediaImage {
        image {
          url
          originalSrc
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

Variables:
```json
{
  "files": [
    {
      "alt": "Descriptive alt text",
      "contentType": "IMAGE",
      "originalSource": "https://shopify-staged-uploads.storage.googleapis.com/tmp/12013604/products/abc123/My-Image.jpg"
    }
  ]
}
```

### Step 4: Wait for Processing & Get Permanent URL

Files may take a few seconds to process. Query the file to get the permanent CDN URL:

```graphql
query {
  node(id: "gid://shopify/MediaImage/12345678") {
    ... on MediaImage {
      id
      alt
      fileStatus
      image {
        url
        originalSrc
      }
    }
  }
}
```

Wait until `fileStatus` is `READY`, then use the `image.url` value.

## URL Comparison

| Type | Example URL | Expires |
|------|-------------|---------|
| Staged | `https://shopify-staged-uploads.storage.googleapis.com/tmp/12013604/products/abc123/image.jpg` | 24-48 hours |
| Permanent | `https://cdn.shopify.com/s/files/1/1201/3604/files/image.jpg?v=1764599707` | Never |

## Finding Existing Files

Search for files by filename:

```graphql
query {
  files(first: 20, query: "filename:My-Image") {
    edges {
      node {
        ... on MediaImage {
          id
          alt
          fileStatus
          createdAt
          image {
            url
          }
        }
      }
    }
  }
}
```

Get recent files:

```graphql
query {
  files(first: 50, sortKey: CREATED_AT, reverse: true) {
    edges {
      node {
        ... on MediaImage {
          id
          alt
          fileStatus
          createdAt
          image {
            url
          }
        }
      }
    }
  }
}
```

## Using with tools/graphql_mutation.py

### Create permanent files from staged URLs:

```bash
python tools/graphql_mutation.py 'mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files {
      id
      alt
      fileStatus
      ... on MediaImage {
        image {
          url
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}' --variables '{
  "files": [
    {
      "alt": "My Image Description",
      "contentType": "IMAGE",
      "originalSource": "https://shopify-staged-uploads.storage.googleapis.com/tmp/12013604/products/abc123/My-Image.jpg"
    }
  ]
}'
```

### Query file status:

```bash
python tools/graphql_mutation.py 'query {
  node(id: "gid://shopify/MediaImage/28939886133282") {
    ... on MediaImage {
      id
      alt
      fileStatus
      image {
        url
      }
    }
  }
}'
```

## Best Practices

1. **Always convert to permanent files** before using URLs in:
   - Landing pages
   - Product descriptions
   - Metafields
   - Email templates

2. **Add descriptive alt text** when creating files for better organization

3. **Verify file status is READY** before using the URL

4. **Use permanent CDN URLs** in all customer-facing content

## Existing Upload Tools

- `tools/upload_product_images.py` - Handles product image uploads (uses correct `resource: IMAGE`)
- `tools/graphql_mutation.py` - General GraphQL execution for file operations

## Common Issues

### Images not appearing in Shopify Admin Files
- **Cause**: Only staged uploads were created, not permanent files
- **Fix**: Run `fileCreate` mutation with the staged URL as `originalSource`

### Broken images after 24-48 hours
- **Cause**: Using staged upload URLs directly
- **Fix**: Convert to permanent files and update URLs

### `image: null` in fileCreate response
- **Cause**: File is still processing
- **Fix**: Wait a few seconds and query the file again by ID

---

*Last updated: December 1, 2025 (Cyber Monday)*