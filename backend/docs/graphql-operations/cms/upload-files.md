# Upload Files to Shopify

Uploads image files to Shopify Files using the staged upload process. Used for hero images and educational block images.

## Use Cases
- Upload custom hero images for category landing pages
- Add images to educational blocks
- Replace existing images with new versions
- Bulk upload images for CMS content
- Migrate images from external sources

## GraphQL Operations

This process requires **three steps**:

### Step 1: Create Staged Upload Target

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

### Step 2: HTTP POST to Upload URL

After getting the staged upload target, upload the file via HTTP POST (not GraphQL):

```bash
curl -X POST "UPLOAD_URL" \
  -F "key=VALUE" \
  -F "policy=VALUE" \
  -F "signature=VALUE" \
  -F "file=@/path/to/image.webp"
```

### Step 3: Create File Record

```graphql
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files {
      id
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
}
```

### Step 4: Update Metaobject (Optional)

After uploading, update the metaobject to reference the new file:

```graphql
mutation updateMetaobject($id: ID!, $fields: [MetaobjectFieldInput!]!) {
  metaobjectUpdate(id: $id, metaobject: {fields: $fields}) {
    metaobject {
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
            }
          }
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

## Variables

### stagedUploadsCreate
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `input[].resource` | String! | Yes | Resource type (always `"FILE"`) |
| `input[].filename` | String! | Yes | Filename (e.g., `hero-upload-espresso.webp`) |
| `input[].mimeType` | String! | Yes | MIME type (e.g., `image/webp`) |
| `input[].httpMethod` | String! | Yes | HTTP method (always `"POST"`) |

### fileCreate
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `files[].alt` | String | No | Alt text for image |
| `files[].contentType` | String! | Yes | Content type (always `"IMAGE"`) |
| `files[].originalSource` | String! | Yes | Resource URL from staged upload |

### updateMetaobject
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | ID! | Yes | Metaobject GID to update |
| `fields[].key` | String! | Yes | Field key (e.g., `hero_image`) |
| `fields[].value` | String! | Yes | File GID from fileCreate response |

## Required Scopes
- `write_files` (for file upload)
- `write_metaobjects` (for updating metaobject)
- `read_files` (for querying uploaded files)
- `read_metaobjects` (for querying updated metaobject)

## Example

### Upload Hero Image for Category Page
```bash
python3 cms/upload_hero_image.py \
  --metaobject-id "gid://shopify/Metaobject/123456" \
  --image-path "/path/to/hero-image.jpg"
```

### Upload with JSON Output
```bash
python3 cms/upload_hero_image.py \
  --metaobject-id "gid://shopify/Metaobject/123456" \
  --image-path "/path/to/hero-image.png" \
  --output-format json
```

## Response Format

```json
{
  "page": {
    "id": "gid://shopify/Metaobject/123456",
    "handle": "espresso-machines",
    "displayName": "Espresso Machines",
    "heroImageUrl": "https://cdn.shopify.com/s/files/1/...hero-upload-espresso.webp",
    "heroTitle": "Premium Espresso Machines",
    "heroDescription": "Professional-grade machines"
  },
  "success": true
}
```

## Image Processing

The script automatically:
1. **Validates file exists** - Checks if image path is valid
2. **Opens image** - Uses PIL to load image
3. **Converts to RGB** - Handles RGBA, LA, and P modes with white background
4. **Converts to WebP** - Optimizes as WebP with quality=92
5. **Uploads to Shopify** - Uses staged upload process
6. **Updates metaobject** - Links file to metaobject field

## Supported Formats

### Input Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- GIF (.gif) - converted to static WebP
- BMP (.bmp)
- Any format supported by PIL

### Output Format
- WebP (quality=92, method=6) for optimal compression and quality

## Notes
- **Automatic Conversion**: All images are converted to WebP for optimal web performance
- **Quality Preservation**: Uses quality=92 to maintain high visual quality
- **RGB Conversion**: Transparencies are replaced with white background
- **File Naming**: Uploaded files are named `hero-upload-{original-stem}.webp`
- **Alt Text**: Automatically set to `"Hero image - {filename}"`
- **Performance**: WebP compression method 6 provides best compression
- **Size Limits**: Shopify enforces file size limits (typically 20MB)
- **Error Handling**: Returns detailed error messages for each step
- **Debug Output**: Prints progress to stderr (doesn't pollute JSON output)
- **Idempotent**: Re-uploading same image creates new file (doesn't update existing)

## Troubleshooting

### Common Issues

**Image not found**
```
Error: Image file not found: /path/to/image.jpg
```
- Verify file path is correct and file exists

**Upload timeout**
```
Upload error: HTTPError: timeout
```
- Increase timeout or check network connection
- Large files may take longer to upload

**Invalid GID**
```
Error: Invalid metaobject ID format
```
- Ensure GID is in format `gid://shopify/Metaobject/123456`

**Insufficient permissions**
```
userErrors: [{"message": "Access denied"}]
```
- Verify API credentials have `write_files` and `write_metaobjects` scopes
