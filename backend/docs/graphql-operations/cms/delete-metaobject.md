# Delete Metaobject

Permanently deletes a metaobject by ID. This action cannot be undone.

## Use Cases
- Remove obsolete category sections
- Delete outdated educational blocks
- Clean up test metaobjects
- Remove FAQ items that are no longer relevant
- Delete comparison features not in use

## GraphQL

```graphql
mutation deleteMetaobject($id: ID!) {
  metaobjectDelete(id: $id) {
    deletedId
    userErrors {
      field
      message
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | ID! | Yes | Metaobject GID to delete (e.g., `gid://shopify/Metaobject/123456`) |

## Required Scopes
- `write_metaobjects`

## Example

### Delete with Confirmation Prompt
```bash
python3 cms/delete_metaobject.py --id "gid://shopify/Metaobject/123456"
```

This will prompt:
```
WARNING: You are about to delete metaobject gid://shopify/Metaobject/123456
This action cannot be undone.
Are you sure? (yes/no):
```

### Delete without Confirmation (Automated Scripts)
```bash
python3 cms/delete_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --confirm
```

### Pretty Output
```bash
python3 cms/delete_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --confirm \
  --output-format pretty
```

## Response Format

```json
{
  "success": true,
  "deletedId": "gid://shopify/Metaobject/123456",
  "message": "Successfully deleted metaobject gid://shopify/Metaobject/123456"
}
```

## Notes
- **Irreversible**: Deletion is permanent and cannot be undone
- **Confirmation Required**: By default, the script prompts for confirmation unless `--confirm` flag is used
- **GID Format**: Must provide full metaobject GID in the format `gid://shopify/Metaobject/ID`
- **Referenced Objects**: Be cautious when deleting metaobjects that are referenced by other metaobjects (e.g., FAQ items referenced by FAQ sections)
- **Cascade Behavior**: Deleting a metaobject does NOT automatically remove references to it from other metaobjects
- **Error Handling**: Check `userErrors` in response for issues (e.g., metaobject not found, permission denied)
- **Validation**: Script validates GID format before attempting deletion

## Safety Recommendations
1. Always test deletions in a development environment first
2. Back up data or export metaobjects before bulk deletions
3. Use the confirmation prompt in production environments
4. Verify the correct GID before deleting
5. Consider updating references in other metaobjects before deletion
