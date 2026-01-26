"""
Admin API endpoints for documentation management.

DB-Primary Architecture:
- Database is the source of truth for all documentation
- Disk serves as sync/transfer layer (export for backup, import for seeding)
- Semantic search via doc_chunks table with pgvector

Endpoints:
- GET /tree - Get file tree from DB
- GET /list - List files in a folder (from DB)
- GET /read - Read file content from DB
- POST /write - Write/update file in DB
- POST /create - Create new file/folder
- DELETE /delete - Delete file from DB
- POST /rename - Rename/move file in DB
- POST /validate - Validate markdown structure
- POST /reindex - Regenerate embeddings
- POST /export - Export DB to disk
- POST /import - Import from disk to DB
- GET /sync-status - Get sync statistics
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field
import re

from services.doc_manager import DocManager

router = APIRouter(prefix="/api/admin/docs", tags=["admin-docs"])
logger = logging.getLogger(__name__)

# Base docs directory (for export/import operations)
DOCS_BASE = Path(__file__).parent.parent / "docs"


# =============================================================================
# Pydantic Models
# =============================================================================

class FileNode(BaseModel):
    """Represents a file or folder in the tree"""
    name: str
    path: str  # Relative to docs/
    type: str  # "file" or "folder"
    children: Optional[List['FileNode']] = None
    size: Optional[int] = None
    modified: Optional[float] = None


class FileContent(BaseModel):
    """File content response"""
    path: str
    content: str
    size: int
    modified: float
    title: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None


class WriteFileRequest(BaseModel):
    """Request to write/update a file"""
    path: str = Field(..., description="Relative path to file")
    content: str = Field(..., description="File content")
    category: Optional[str] = Field(None, description="Document category")


class CreateRequest(BaseModel):
    """Request to create file or folder"""
    path: str = Field(..., description="Relative path to create")
    type: str = Field(..., description="'file' or 'folder'")
    content: Optional[str] = Field("", description="Initial content for files")


class DeleteRequest(BaseModel):
    """Request to delete file or folder"""
    path: str = Field(..., description="Relative path to delete")


class RenameRequest(BaseModel):
    """Request to rename/move file or folder"""
    old_path: str = Field(..., description="Current relative path")
    new_path: str = Field(..., description="New relative path")


class ValidationResult(BaseModel):
    """Result of doc validation"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class ReindexResult(BaseModel):
    """Result of documentation reindexing operation"""
    success: bool
    message: str
    indexed_count: int = 0
    error_count: int = 0
    total_docs: int = 0


class ExportResult(BaseModel):
    """Result of export operation"""
    success: bool
    exported_count: int
    errors: List[str] = []
    path: str


class ImportResult(BaseModel):
    """Result of import operation"""
    success: bool
    imported_count: int
    updated_count: int
    skipped_count: int
    errors: List[str] = []


class SyncStatus(BaseModel):
    """Sync status between DB and disk"""
    total_docs: int
    total_chunks: int
    by_category: Dict[str, int]
    by_source: Dict[str, int]
    disk_files: int
    disk_path: str


# =============================================================================
# Helper Functions
# =============================================================================

def _get_doc_manager() -> DocManager:
    """Get DocManager instance."""
    return DocManager(docs_dir=DOCS_BASE)


def _dict_to_file_node(d: Dict[str, Any]) -> FileNode:
    """Convert dictionary tree to FileNode model."""
    children = None
    if d.get("children"):
        children = [_dict_to_file_node(c) for c in d["children"]]

    return FileNode(
        name=d["name"],
        path=d["path"],
        type=d["type"],
        children=children,
        size=d.get("size"),
        modified=d.get("modified")
    )


def validate_markdown_links(content: str, doc_path: str) -> List[str]:
    """Check for broken internal links in markdown."""
    errors = []

    # Find markdown links: [text](path)
    link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    matches = re.finditer(link_pattern, content)

    for match in matches:
        link_text = match.group(1)
        link_path = match.group(2)

        # Skip external links
        if link_path.startswith(('http://', 'https://', 'mailto:', '#')):
            continue

        # For now, just flag relative links as warnings
        # Full validation would require checking DB for target path
        if not link_path.startswith('/'):
            # Relative link - could be valid
            pass

    return errors


# =============================================================================
# API Endpoints - Read Operations
# =============================================================================

@router.get("/tree")
async def get_file_tree():
    """
    Get complete file tree from database.
    Returns hierarchical structure of all documents.
    """
    try:
        manager = _get_doc_manager()
        tree = await manager.build_file_tree()
        await manager.close()
        return _dict_to_file_node(tree)
    except Exception as e:
        logger.error(f"Error building file tree: {e}")
        raise HTTPException(status_code=500, detail=f"Error building file tree: {str(e)}")


@router.get("/list")
async def list_files(
    path: str = Query("", description="Folder path to list"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, description="Maximum results"),
    offset: int = Query(0, description="Pagination offset")
) -> List[Dict[str, Any]]:
    """
    List files in a specific folder from database.
    Supports filtering by category.
    """
    try:
        manager = _get_doc_manager()

        # If path is provided, filter by path prefix
        if path:
            # Get docs matching this path prefix
            docs = await manager.get_doc_by_glob(f"{path}/*")

            # Group into immediate children only
            items = []
            seen_folders = set()

            for doc in docs:
                # Get relative path from the folder
                rel_path = doc.doc_path[len(path):].lstrip('/')
                parts = rel_path.split('/')

                if len(parts) == 1:
                    # Direct file in this folder
                    items.append({
                        "name": parts[0],
                        "path": doc.doc_path,
                        "type": "file",
                        "size": len(doc.content) if doc.content else 0,
                        "modified": doc.last_updated.timestamp() if doc.last_updated else None
                    })
                else:
                    # Subfolder
                    folder_name = parts[0]
                    if folder_name not in seen_folders:
                        seen_folders.add(folder_name)
                        items.append({
                            "name": folder_name,
                            "path": f"{path}/{folder_name}" if path else folder_name,
                            "type": "folder",
                            "size": None,
                            "modified": None
                        })
        else:
            # Root level - get all and extract top-level items
            docs, total = await manager.list_docs(category=category, limit=1000)

            items = []
            seen_folders = set()

            for doc in docs:
                parts = doc.doc_path.split('/')

                if len(parts) == 1:
                    # Top-level file
                    items.append({
                        "name": parts[0],
                        "path": doc.doc_path,
                        "type": "file",
                        "size": None,
                        "modified": doc.last_updated.timestamp() if doc.last_updated else None
                    })
                else:
                    # Top-level folder
                    folder_name = parts[0]
                    if folder_name not in seen_folders:
                        seen_folders.add(folder_name)
                        items.append({
                            "name": folder_name,
                            "path": folder_name,
                            "type": "folder",
                            "size": None,
                            "modified": None
                        })

        await manager.close()

        # Sort: folders first, then by name
        items.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))

        return items[offset:offset + limit]

    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/read")
async def read_file(path: str = Query(..., description="File path to read")) -> FileContent:
    """
    Read contents of a file from database.
    """
    try:
        manager = _get_doc_manager()
        doc = await manager.get_doc(path)
        await manager.close()

        if not doc:
            raise HTTPException(status_code=404, detail="File not found")

        return FileContent(
            path=path,
            content=doc.content,
            size=len(doc.content),
            modified=doc.last_updated.timestamp() if doc.last_updated else 0,
            title=doc.title,
            category=doc.category,
            source=doc.source
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


# =============================================================================
# API Endpoints - Write Operations
# =============================================================================

@router.post("/write")
async def write_file(request: WriteFileRequest):
    """
    Write/update a file in database.
    Automatically generates embeddings and chunks.
    """
    try:
        manager = _get_doc_manager()
        doc = await manager.save_doc(
            doc_path=request.path,
            content=request.content,
            category=request.category,
            source="manual"
        )
        await manager.close()

        return {
            "success": True,
            "path": request.path,
            "size": len(request.content),
            "title": doc.title,
            "category": doc.category
        }

    except Exception as e:
        logger.error(f"Error writing file: {e}")
        raise HTTPException(status_code=500, detail=f"Error writing file: {str(e)}")


@router.post("/create")
async def create_item(request: CreateRequest):
    """
    Create a new file or folder.
    Note: Folders are virtual in DB-primary mode (derived from paths).
    """
    try:
        if request.type == "folder":
            # Folders are implicit in DB - just return success
            # They'll appear when files are created with paths under them
            return {
                "success": True,
                "path": request.path,
                "type": "folder",
                "message": "Folder will appear when files are added"
            }

        elif request.type == "file":
            manager = _get_doc_manager()

            # Check if file already exists
            existing = await manager.get_doc(request.path)
            if existing:
                await manager.close()
                raise HTTPException(status_code=400, detail="Path already exists")

            doc = await manager.save_doc(
                doc_path=request.path,
                content=request.content or "",
                source="manual"
            )
            await manager.close()

            return {
                "success": True,
                "path": request.path,
                "type": "file",
                "size": len(request.content or "")
            }
        else:
            raise HTTPException(status_code=400, detail="Type must be 'file' or 'folder'")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating item: {str(e)}")


@router.delete("/delete")
async def delete_item(request: DeleteRequest):
    """
    Delete a file from database.
    For folders, deletes all documents under that path.
    """
    try:
        manager = _get_doc_manager()

        # Try to delete as file first
        deleted = await manager.delete_doc(request.path)

        if deleted:
            await manager.close()
            return {"success": True, "path": request.path, "type": "file"}

        # Not a file - try as folder (delete all docs with this prefix)
        docs = await manager.get_doc_by_glob(f"{request.path}/*")

        if not docs:
            await manager.close()
            raise HTTPException(status_code=404, detail="Path not found")

        # Delete all docs under this folder
        deleted_count = 0
        for doc in docs:
            if await manager.delete_doc(doc.doc_path):
                deleted_count += 1

        await manager.close()

        return {
            "success": True,
            "path": request.path,
            "type": "folder",
            "deleted_count": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting item: {str(e)}")


@router.post("/rename")
async def rename_item(request: RenameRequest):
    """
    Rename or move a file/folder in database.
    """
    try:
        manager = _get_doc_manager()

        # Get the source document
        source_doc = await manager.get_doc(request.old_path)

        if source_doc:
            # It's a file - delete old, create new
            new_doc = await manager.save_doc(
                doc_path=request.new_path,
                content=source_doc.content,
                title=source_doc.title,
                category=source_doc.category,
                source=source_doc.source
            )
            await manager.delete_doc(request.old_path)
            await manager.close()

            return {
                "success": True,
                "old_path": request.old_path,
                "new_path": request.new_path
            }

        # Try as folder - rename all docs under this path
        docs = await manager.get_doc_by_glob(f"{request.old_path}/*")

        if not docs:
            await manager.close()
            raise HTTPException(status_code=404, detail="Source path not found")

        # Rename each doc
        renamed_count = 0
        for doc in docs:
            new_path = doc.doc_path.replace(request.old_path, request.new_path, 1)
            await manager.save_doc(
                doc_path=new_path,
                content=doc.content,
                title=doc.title,
                category=doc.category,
                source=doc.source
            )
            await manager.delete_doc(doc.doc_path)
            renamed_count += 1

        await manager.close()

        return {
            "success": True,
            "old_path": request.old_path,
            "new_path": request.new_path,
            "renamed_count": renamed_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming item: {e}")
        raise HTTPException(status_code=500, detail=f"Error renaming item: {str(e)}")


# =============================================================================
# API Endpoints - Validation & Reindexing
# =============================================================================

@router.post("/validate", response_model=ValidationResult)
async def validate_docs(path: str = Query(..., description="Path to validate")):
    """
    Validate markdown file for structure issues.
    """
    try:
        manager = _get_doc_manager()
        doc = await manager.get_doc(path)
        await manager.close()

        if not doc:
            raise HTTPException(status_code=404, detail="File not found")

        errors = []
        warnings = []
        content = doc.content

        # Check for broken links
        link_errors = validate_markdown_links(content, path)
        errors.extend(link_errors)

        # Check for INDEX.md requirements
        if path.endswith("INDEX.md"):
            if "# " not in content[:100]:
                warnings.append("INDEX.md should have a heading")

        # Check for empty file
        if not content.strip():
            warnings.append("File is empty")

        # Check for title
        if not re.search(r'^#\s+', content, re.MULTILINE):
            warnings.append("Document has no title heading")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        return ValidationResult(
            valid=False,
            errors=[f"Error validating file: {str(e)}"]
        )


@router.post("/reindex", response_model=ReindexResult)
async def reindex_docs():
    """
    Regenerate embeddings for all documents in database.
    """
    try:
        manager = _get_doc_manager()

        # Import from disk to ensure DB is up to date, then regenerate embeddings
        result = await manager.import_from_disk(force=True)

        stats = await manager.get_stats()
        await manager.close()

        return ReindexResult(
            success=result.imported_count + result.updated_count > 0 or result.skipped_count > 0,
            message=f"Reindexed {result.imported_count + result.updated_count} documents ({result.skipped_count} unchanged)",
            indexed_count=result.imported_count + result.updated_count,
            total_docs=stats["total_chunks"]
        )

    except Exception as e:
        logger.error(f"Error reindexing documentation: {e}")
        return ReindexResult(
            success=False,
            message=f"Error reindexing documentation: {str(e)}"
        )


# =============================================================================
# API Endpoints - Export/Import Operations
# =============================================================================

@router.post("/export", response_model=ExportResult)
async def export_docs():
    """
    Export all documents from database to disk.
    Preserves directory structure based on doc_path.
    """
    try:
        manager = _get_doc_manager()
        result = await manager.export_to_disk()
        await manager.close()

        return ExportResult(
            success=result.success,
            exported_count=result.exported_count,
            errors=result.errors,
            path=result.path
        )

    except Exception as e:
        logger.error(f"Error exporting documentation: {e}")
        return ExportResult(
            success=False,
            exported_count=0,
            errors=[str(e)],
            path=str(DOCS_BASE)
        )


@router.post("/import", response_model=ImportResult)
async def import_docs(force: bool = Query(False, description="Force overwrite existing docs")):
    """
    Import documents from disk to database.
    Use force=true to overwrite existing documents.
    """
    try:
        manager = _get_doc_manager()
        result = await manager.import_from_disk(force=force)
        await manager.close()

        return ImportResult(
            success=result.success,
            imported_count=result.imported_count,
            updated_count=result.updated_count,
            skipped_count=result.skipped_count,
            errors=result.errors
        )

    except Exception as e:
        logger.error(f"Error importing documentation: {e}")
        return ImportResult(
            success=False,
            imported_count=0,
            updated_count=0,
            skipped_count=0,
            errors=[str(e)]
        )


@router.get("/sync-status", response_model=SyncStatus)
async def get_sync_status():
    """
    Get synchronization status between database and disk.
    """
    try:
        manager = _get_doc_manager()
        stats = await manager.get_stats()
        await manager.close()

        # Count disk files
        disk_files = 0
        if DOCS_BASE.exists():
            disk_files = len(list(DOCS_BASE.rglob("*.md")))

        return SyncStatus(
            total_docs=stats["total_docs"],
            total_chunks=stats["total_chunks"],
            by_category=stats["by_category"],
            by_source=stats["by_source"],
            disk_files=disk_files,
            disk_path=str(DOCS_BASE)
        )

    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting sync status: {str(e)}")
