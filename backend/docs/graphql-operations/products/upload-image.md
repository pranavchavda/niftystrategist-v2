# Upload Product Image (Staged)

Upload product images using Shopify's staged upload API. This method bypasses URL upload limitations and supports direct file uploads.

## Use Cases
- Add product images from local files
- Upload high-resolution images
- Bypass URL upload restrictions
- Add multiple images to products
- Replace or update product imagery

## GraphQL

### 1. Create Staged Upload

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

### 2. Add Media to Product

```graphql
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media {
      id
      alt
      mediaContentType
      status
    }
    mediaUserErrors {
      field
      message
    }
  }
}
```

## Variables

### Staged Upload Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input.filename | String | Yes | Original filename |
| input.mimeType | String | Yes | MIME type (e.g., "image/png", "image/jpeg") |
| input.resource | StagedUploadResourceType | Yes | PRODUCT_IMAGE |
| input.httpMethod | StagedUploadHttpMethodType | Yes | POST |
| input.fileSize | String | Yes | File size in bytes |

### Create Media Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| productId | ID | Yes | Product GID |
| media.alt | String | No | Alt text for image (accessibility/SEO) |
| media.mediaContentType | MediaContentType | Yes | IMAGE |
| media.originalSource | String | Yes | Resource URL from staged upload |

## Workflow

The script follows a 3-step process:

### Step 1: Create Staged Upload
Request a staged upload target from Shopify:
```
1️⃣ Creating staged upload...
   Resource URL: https://shopify-staged-uploads.storage.googleapis.com/...
```

### Step 2: Upload File to Staging URL
Upload the file to the provided staging URL using POST with multipart/form-data:
```
2️⃣ Uploading file to staging URL...
✅ File uploaded to staging successfully
```

### Step 3: Add Media to Product
Attach the uploaded media to the product:
```
3️⃣ Adding image to product...
✅ Image added to product!
   Media ID: gid://shopify/ProductImage/1234567890
   Alt Text: Product image
   Status: READY
```

## Example

```bash
# Upload image with auto-generated alt text
python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "/path/to/image.jpg"

# Upload with custom alt text
python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "/path/to/delonghi-front.jpg" \
  --alt "DeLonghi Dedica front view"

# Upload multiple images
python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "image1.jpg" --alt "Front view"

python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "image2.jpg" --alt "Side view"

python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "image3.jpg" --alt "Back view"
```

## Request Examples

### Step 1: Create Staged Upload

```json
{
  "input": [
    {
      "filename": "delonghi-dedica.jpg",
      "mimeType": "image/jpeg",
      "resource": "PRODUCT_IMAGE",
      "httpMethod": "POST",
      "fileSize": "524288"
    }
  ]
}
```

Response:
```json
{
  "data": {
    "stagedUploadsCreate": {
      "stagedTargets": [
        {
          "url": "https://shopify-staged-uploads.storage.googleapis.com/tmp/12345",
          "resourceUrl": "https://shopify-staged-uploads.storage.googleapis.com/tmp/12345/delonghi-dedica.jpg",
          "parameters": [
            {"name": "key", "value": "tmp/12345/delonghi-dedica.jpg"},
            {"name": "Content-Type", "value": "image/jpeg"},
            {"name": "success_action_status", "value": "201"},
            {"name": "acl", "value": "private"}
          ]
        }
      ],
      "userErrors": []
    }
  }
}
```

### Step 2: Upload File (HTTP POST)

**Note**: This is a standard HTTP multipart/form-data POST, NOT a GraphQL request.

```http
POST https://shopify-staged-uploads.storage.googleapis.com/tmp/12345
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="key"

tmp/12345/delonghi-dedica.jpg
------WebKitFormBoundary
Content-Disposition: form-data; name="Content-Type"

image/jpeg
------WebKitFormBoundary
Content-Disposition: form-data; name="success_action_status"

201
------WebKitFormBoundary
Content-Disposition: form-data; name="acl"

private
------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="delonghi-dedica.jpg"
Content-Type: image/jpeg

[Binary image data]
------WebKitFormBoundary--
```

### Step 3: Add Media to Product

```json
{
  "productId": "gid://shopify/Product/1234567890",
  "media": [
    {
      "alt": "DeLonghi Dedica front view",
      "mediaContentType": "IMAGE",
      "originalSource": "https://shopify-staged-uploads.storage.googleapis.com/tmp/12345/delonghi-dedica.jpg"
    }
  ]
}
```

## Response Structure

### Successful Upload

```json
{
  "data": {
    "productCreateMedia": {
      "media": [
        {
          "id": "gid://shopify/ProductImage/1234567890",
          "alt": "DeLonghi Dedica front view",
          "mediaContentType": "IMAGE",
          "status": "READY"
        }
      ],
      "mediaUserErrors": []
    }
  }
}
```

## Supported File Types

| Extension | MIME Type | Support |
|-----------|-----------|---------|
| .jpg, .jpeg | image/jpeg | ✅ Yes |
| .png | image/png | ✅ Yes |
| .gif | image/gif | ✅ Yes |
| .webp | image/webp | ✅ Yes |

## File Size Limits

- **Maximum**: 20 MB per image
- **Recommended**: Under 5 MB for fast page loads
- **Dimensions**: Up to 5472 x 5472 pixels

## Alt Text Best Practices

Alt text improves accessibility and SEO:

```bash
# ✅ Good alt text
--alt "DeLonghi Dedica espresso machine front view"
--alt "Breville Barista Express with portafilter"
--alt "Coffee grinder burr detail close-up"

# ❌ Poor alt text
--alt "image1"
--alt "product"
--alt ""  # Empty
```

**Guidelines**:
- Be descriptive and specific
- Include product name and view angle
- Mention important visual details
- Keep under 125 characters
- Don't start with "Image of..." or "Picture of..."

## Auto-Generated Alt Text

If `--alt` is not provided, the script generates alt text from the filename:

```
Filename: delonghi-dedica-front-view.jpg
Auto-generated: "delonghi dedica front view"
```

The script:
1. Removes file extension
2. Replaces hyphens and underscores with spaces
3. Uses as alt text

## Image Order

Images are displayed in the order they are uploaded:
- First image uploaded becomes the **featured image**
- Subsequent images are additional product images
- Use product admin to reorder images if needed

## Notes
- Staged uploads are temporary - must be attached to product within 24 hours
- Images are processed asynchronously - may take a few seconds to appear
- The `status` field indicates processing state:
  - `UPLOADING`: Upload in progress
  - `PROCESSING`: Image being optimized
  - `READY`: Image ready and visible
  - `FAILED`: Upload or processing failed
- Shopify automatically creates optimized versions (thumbnails, etc.)
- Original images are stored and served via Shopify CDN
- This method is faster and more reliable than URL-based uploads
- Images can be removed using `delete_product_images.py`

## Advantages Over URL Upload

| Feature | Staged Upload | URL Upload |
|---------|--------------|------------|
| Local files | ✅ Yes | ❌ No (requires public URL) |
| Large files | ✅ Yes (up to 20MB) | ⚠️ Limited |
| Reliability | ✅ High | ⚠️ Can fail with SSL/timeout |
| Speed | ✅ Fast | ⚠️ Depends on source server |
| Control | ✅ Full | ⚠️ External dependency |

## Common Errors

### File Not Found
```
❌ File not found: /path/to/image.jpg
```
**Solution**: Check file path is correct and file exists.

### File Too Large
```
❌ Error creating staged upload: [{'field': ['fileSize'], 'message': 'File too large'}]
```
**Solution**: Compress image or reduce dimensions to under 20MB.

### Invalid MIME Type
```
❌ Error creating staged upload: [{'field': ['mimeType'], 'message': 'Unsupported MIME type'}]
```
**Solution**: Convert image to JPG, PNG, GIF, or WebP format.

### Upload Failed
```
❌ Failed to upload file: 403
```
**Solution**: Check staged upload URL is valid and not expired. Retry the operation.

## Required Scopes
- `write_products`
- `read_products`
- `write_files` (for staged uploads)
