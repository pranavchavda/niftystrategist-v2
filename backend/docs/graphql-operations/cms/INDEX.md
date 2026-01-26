# CMS GraphQL Operations Documentation

Comprehensive documentation for all GraphQL operations used in the EspressoBot CMS system for managing Shopify metaobjects.

## Overview

The CMS system manages category landing pages through a hierarchy of metaobject types:
- `category_landing_page` - Top-level landing page container
- `category_section` - Product category display sections
- `educational_block` - Rich content blocks with images/videos
- `faq_section` - FAQ container
- `faq_item` - Individual FAQ questions/answers
- `comparison_table` - Product comparison tables
- `comparison_feature` - Individual comparison features
- `sorting_option` - Product sorting options

## Core CRUD Operations

### [Create Metaobject](./create-metaobject.md)
Create new metaobjects of any type with custom fields.

**Mutation**: `metaobjectCreate`
**Use Cases**: Creating category sections, FAQ items, educational blocks, etc.
**Script**: `cms/create_metaobject.py`

```bash
python3 cms/create_metaobject.py --type faq_item \
  --question "How long does shipping take?" \
  --answer "2-5 business days"
```

### [Update Metaobject](./update-metaobject.md)
Update existing metaobject fields (partial updates).

**Mutation**: `metaobjectUpdate`
**Use Cases**: Modifying titles, descriptions, references, numeric values
**Script**: `cms/update_metaobject.py`

```bash
python3 cms/update_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --type category_section \
  --title "Updated Title"
```

### [Delete Metaobject](./delete-metaobject.md)
Permanently delete a metaobject by ID.

**Mutation**: `metaobjectDelete`
**Use Cases**: Removing obsolete content, cleanup
**Script**: `cms/delete_metaobject.py`

```bash
python3 cms/delete_metaobject.py --id "gid://shopify/Metaobject/123456" --confirm
```

### [Get Metaobject](./get-metaobject.md)
Fetch single metaobject with all fields and references expanded.

**Query**: `metaobject`
**Use Cases**: Loading for editing, inspecting structure, nested data
**Script**: `cms/get_metaobject.py`

```bash
python3 cms/get_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --include-nested
```

## List Operations

### [List Metaobjects](./list-metaobjects.md)
List all metaobjects of a specific type with pagination.

**Query**: `metaobjects`
**Use Cases**: Dropdown pickers, bulk operations, exports
**Script**: `cms/list_metaobjects.py`

```bash
python3 cms/list_metaobjects.py --type faq_item
```

### [List Category Pages](./list-category-pages.md)
List all category landing pages with complete nested data.

**Query**: `metaobjects` (filtered by `category_landing_page`)
**Use Cases**: CMS dashboard, page management
**Script**: `cms/list_category_landing_pages.py`

```bash
python3 cms/list_category_landing_pages.py
```

## File Operations

### [Upload Files](./upload-files.md)
Upload images to Shopify Files using staged upload process.

**Mutations**: `stagedUploadsCreate`, `fileCreate`, `metaobjectUpdate`
**Use Cases**: Hero images, educational block images
**Script**: `cms/upload_hero_image.py`

```bash
python3 cms/upload_hero_image.py \
  --metaobject-id "gid://shopify/Metaobject/123456" \
  --image-path "/path/to/image.jpg"
```

## GraphQL Validation Status

All GraphQL operations have been validated against the Shopify Admin API schema using the Shopify MCP validation tools:

- ✅ `metaobjectCreate` - **VALID** (Scopes: `write_metaobjects`, `read_metaobjects`)
- ✅ `metaobjectUpdate` - **VALID** (Scopes: `write_metaobjects`, `read_metaobjects`)
- ✅ `metaobjectDelete` - **VALID** (Scopes: `write_metaobjects`)
- ✅ `metaobject` (single) - **VALID** (Scopes: `read_metaobjects`)
- ✅ `metaobjects` (list) - **VALID** (Scopes: `read_metaobjects`)
- ✅ `stagedUploadsCreate` - **VALID** (No specific scopes)
- ✅ `fileCreate` - **VALID** (Scopes: `write_files`)
- ✅ `collectionByHandle` - **VALID** (Scopes: `read_products`)

## Required API Scopes

Minimum scopes required for full CMS functionality:

- `read_metaobjects` - Read metaobject data
- `write_metaobjects` - Create, update, delete metaobjects
- `read_products` - Query collections and products
- `write_files` - Upload images
- `read_files` - Query uploaded images

## Common Patterns

### Creating with References
```bash
# 1. Create the referenced item first
python3 cms/create_metaobject.py --type faq_item \
  --question "Q1" --answer "A1"
# Returns: {"id": "gid://shopify/Metaobject/111"}

# 2. Create container with reference
python3 cms/create_metaobject.py --type faq_section \
  --title "FAQs" \
  --questions '["gid://shopify/Metaobject/111"]'
```

### Updating References
```bash
# Update a list reference field (overwrites)
python3 cms/update_metaobject.py \
  --id "gid://shopify/Metaobject/123" \
  --type faq_section \
  --questions '["gid://shopify/Metaobject/111", "gid://shopify/Metaobject/222"]'
```

### Uploading and Linking Images
```bash
# Single command uploads and links image
python3 cms/upload_hero_image.py \
  --metaobject-id "gid://shopify/Metaobject/123" \
  --image-path "hero.jpg"
```

## Script Locations

All scripts are located in `backend/bash-tools/cms/`:

- `create_metaobject.py` - Generic metaobject creation
- `update_metaobject.py` - Generic metaobject updates
- `delete_metaobject.py` - Metaobject deletion with confirmation
- `get_metaobject.py` - Single metaobject query with nested support
- `list_metaobjects.py` - List by type with pagination
- `list_category_landing_pages.py` - Complete category page listing
- `upload_hero_image.py` - Image upload and linking

## Integration with Orchestrator

The orchestrator uses these scripts via the `execute_bash` tool:

```python
# Example: Orchestrator creates a FAQ item
result = await orchestrator.execute_bash(
    command="python3 cms/create_metaobject.py",
    args=[
        "--type", "faq_item",
        "--question", user_question,
        "--answer", generated_answer,
        "--priority", "1"
    ]
)
```

## Additional Resources

- **Base Client**: `backend/bash-tools/base.py` - ShopifyClient and utilities
- **Metaobject Definitions**: `backend/bash-tools/metaobject_definitions/` - Schema files
- **CMS Frontend**: `frontend-v2/app/routes/cms/` - React components
- **CMS Backend**: `backend/routes/cms.py` - API endpoints

## Validation Date

All GraphQL operations validated: **2025-01-06**
Validated against: **Shopify Admin API** (latest version)
Validation tool: **@shopify/dev-mcp** (Shopify MCP Server)
