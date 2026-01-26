"""API routes for Notes system (Second Brain)"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
import zipfile
import tempfile
import os
import yaml
from pathlib import Path
import logging

from database.session import get_db
from database.notes_operations import NotesOperations
from database.models import User
from auth import get_current_user, requires_permission
from services.autocomplete_service import (
    AutocompleteRequest,
    AutocompleteResponse,
    get_autocomplete_service
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/notes",
    tags=["notes"],
    dependencies=[Depends(requires_permission("notes.access"))]
)


# Pydantic models for request/response
class CreateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="")
    category: str = Field(default="personal")
    tags: List[str] = Field(default_factory=list)
    conversation_id: Optional[str] = None


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_starred: Optional[bool] = None


class SearchNotesRequest(BaseModel):
    query: str = Field(..., min_length=1)
    category: Optional[str] = None
    search_type: str = Field(default="semantic")  # "semantic" or "fulltext"
    limit: int = Field(default=10, ge=1, le=50)


@router.post("")
async def create_note(
    request: CreateNoteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create a new note"""
    try:
        note = await NotesOperations.create_note(
            db=db,
            user_id=user.email,
            title=request.title,
            content=request.content,
            category=request.category,
            tags=request.tags,
            conversation_id=request.conversation_id
        )
        return {"success": True, "note": note}
    except Exception as e:
        logger.error(f"Error creating note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_notes(
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    is_starred: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_order: str = "DESC",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List notes with pagination and filtering"""
    try:
        result = await NotesOperations.list_notes(
            db=db,
            user_id=user.email,
            limit=limit,
            offset=offset,
            category=category,
            is_starred=is_starred,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
    except Exception as e:
        logger.error(f"Error listing notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph-connections")
async def get_graph_connections(
    similarity_threshold: float = 0.65,
    limit_per_note: int = 5,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get semantic connections between all notes for graph visualization.

    Returns pairs of notes with similarity scores above the threshold.
    Uses pgvector embeddings to find semantically related notes.

    Args:
        similarity_threshold: Minimum similarity (0-1) to include connection (default: 0.65)
        limit_per_note: Max connections per note to prevent graph overload (default: 5)

    Returns:
        List of {source: id, target: id, similarity: float} connections
    """
    try:
        connections = await NotesOperations.get_all_semantic_connections(
            db=db,
            user_id=user.email,
            similarity_threshold=similarity_threshold,
            limit_per_note=limit_per_note
        )
        return {"connections": connections, "count": len(connections)}
    except Exception as e:
        logger.error(f"Error getting graph connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lookup")
async def lookup_note_by_title(
    title: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Look up a note by its title (case-insensitive) for wikilink navigation"""
    try:
        note = await NotesOperations.get_note_by_title(db, user.email, title)
        if note:
            return {"note_id": note["id"], "title": note["title"]}
        return {"note_id": None, "message": f"No note found with title '{title}'"}
    except Exception as e:
        logger.error(f"Error looking up note by title: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{note_id}")
async def get_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get a single note by ID"""
    note = await NotesOperations.get_note(db, note_id, user.email)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note}


@router.patch("/{note_id}")
async def update_note(
    note_id: int,
    request: UpdateNoteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update a note"""
    try:
        note = await NotesOperations.update_note(
            db=db,
            note_id=note_id,
            user_id=user.email,
            title=request.title,
            content=request.content,
            category=request.category,
            tags=request.tags,
            is_starred=request.is_starred
        )
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"success": True, "note": note}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{note_id}")
async def delete_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete a note"""
    success = await NotesOperations.delete_note(db, note_id, user.email)
    if not success:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": True, "message": "Note deleted"}


@router.post("/reindex")
async def reindex_notes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Rebuild embeddings for all notes belonging to the authenticated user."""
    try:
        result = await NotesOperations.reindex_user_notes(db=db, user_id=user.email)

        message = f"Reindexed {result['updated']} of {result['total']} notes."
        if result["failed"]:
            message += f" {len(result['failed'])} note(s) failed."

        return {
            "success": True,
            "message": message,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Error reindexing notes: {e}")
        raise HTTPException(status_code=500, detail="Failed to reindex notes")


@router.post("/search")
async def search_notes(
    request: SearchNotesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Search notes using semantic or full-text search"""
    try:
        if request.search_type == "semantic":
            results = await NotesOperations.search_notes_semantic(
                db=db,
                user_id=user.email,
                query=request.query,
                category=request.category,
                limit=request.limit
            )
        elif request.search_type == "fulltext":
            results = await NotesOperations.search_notes_fulltext(
                db=db,
                user_id=user.email,
                query=request.query,
                limit=request.limit
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid search_type")

        return {"results": results, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{note_id}/similar")
async def get_similar_notes(
    note_id: int,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get similar notes"""
    try:
        similar = await NotesOperations.get_similar_notes(
            db=db,
            note_id=note_id,
            user_id=user.email,
            limit=limit
        )
        return {"similar_notes": similar, "count": len(similar)}
    except Exception as e:
        logger.error(f"Error finding similar notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{note_id}/backlinks")
async def get_backlinks(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get all notes that link to this note via [[wikilinks]]"""
    try:
        backlinks = await NotesOperations.get_backlinks(
            db=db,
            note_id=note_id,
            user_id=user.email
        )
        return {"backlinks": backlinks, "count": len(backlinks)}
    except Exception as e:
        logger.error(f"Error finding backlinks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-obsidian")
async def import_obsidian_vault(
    file: UploadFile = File(...),
    vault_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Import notes from Obsidian vault (.zip file)"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    # Create temp directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, file.filename)

        # Save uploaded file
        with open(zip_path, 'wb') as f:
            content = await file.read()
            f.write(content)

        # Extract zip
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid zip file")

        # Generate vault_id if not provided
        if not vault_id:
            vault_id = f"obsidian_{user.email}_{file.filename.replace('.zip', '')}"

        # Find all .md files
        md_files = list(Path(temp_dir).rglob("*.md"))
        imported_count = 0
        errors = []

        for md_file in md_files:
            try:
                # Read file content
                content = md_file.read_text(encoding='utf-8')

                # Parse frontmatter if exists
                frontmatter = {}
                markdown_content = content

                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        try:
                            frontmatter = yaml.safe_load(parts[1]) or {}
                            markdown_content = parts[2].strip()
                        except yaml.YAMLError:
                            pass

                # Extract metadata
                title = frontmatter.get('title') or md_file.stem
                category = frontmatter.get('category', 'personal')
                tags = frontmatter.get('tags', [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',')]

                # Extract dates from frontmatter or file metadata
                created_date = None
                updated_date = None

                # Try to parse dates from frontmatter (Obsidian uses various field names)
                from datetime import datetime as dt
                date_fields_created = ['created', 'date', 'created_at', 'creation_date']
                date_fields_updated = ['modified', 'updated', 'updated_at', 'modification_date']

                for field in date_fields_created:
                    if field in frontmatter and frontmatter[field]:
                        try:
                            date_val = frontmatter[field]
                            if isinstance(date_val, str):
                                # Try multiple date formats
                                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                                    try:
                                        created_date = dt.strptime(date_val, fmt)
                                        break
                                    except ValueError:
                                        continue
                            elif hasattr(date_val, 'year'):  # datetime object
                                created_date = date_val
                            if created_date:
                                break
                        except Exception as e:
                            logger.warning(f"Failed to parse created date from {field}: {e}")

                for field in date_fields_updated:
                    if field in frontmatter and frontmatter[field]:
                        try:
                            date_val = frontmatter[field]
                            if isinstance(date_val, str):
                                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                                    try:
                                        updated_date = dt.strptime(date_val, fmt)
                                        break
                                    except ValueError:
                                        continue
                            elif hasattr(date_val, 'year'):
                                updated_date = date_val
                            if updated_date:
                                break
                        except Exception as e:
                            logger.warning(f"Failed to parse updated date from {field}: {e}")

                # Fallback to file modification time if no frontmatter dates
                if not created_date and not updated_date:
                    try:
                        stat = md_file.stat()
                        created_date = dt.fromtimestamp(stat.st_ctime)
                        updated_date = dt.fromtimestamp(stat.st_mtime)
                    except Exception as e:
                        logger.warning(f"Failed to get file timestamps: {e}")

                # Calculate relative path from vault root
                relative_path = str(md_file.relative_to(temp_dir))

                # Upsert note (insert or update if exists) with preserved dates
                await NotesOperations.upsert_obsidian_note(
                    db=db,
                    user_id=user.email,
                    title=title,
                    content=markdown_content,
                    category=category,
                    tags=tags,
                    obsidian_vault_id=vault_id,
                    obsidian_file_path=relative_path,
                    created_at=created_date,
                    updated_at=updated_date
                )
                imported_count += 1

            except Exception as e:
                # Rollback the transaction to reset state after error
                await db.rollback()
                error_msg = f"{type(e).__name__}: {str(e)}"
                logger.error(f"Error importing {md_file}: {error_msg}")
                errors.append({"file": str(md_file.name), "error": error_msg})

        return {
            "success": True,
            "imported_count": imported_count,
            "total_files": len(md_files),
            "vault_id": vault_id,
            "errors": errors if errors else None
        }


@router.get("/obsidian-status/{vault_id}")
async def get_obsidian_status(
    vault_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get sync status for an Obsidian vault"""
    status = await NotesOperations.get_obsidian_sync_status(
        db=db,
        user_id=user.email,
        obsidian_vault_id=vault_id
    )
    return status


@router.post("/autocomplete")
async def autocomplete(
    request: AutocompleteRequest,
    user: User = Depends(get_current_user)
):
    """Generate autocomplete suggestions for note content using LLM"""
    try:
        service = get_autocomplete_service()
        suggestion = await service.get_suggestion(request)
        return {
            "success": True,
            "suggestion": suggestion.suggestion,
            "confidence": suggestion.confidence
        }
    except Exception as e:
        logger.error(f"Error generating autocomplete suggestion: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate suggestion")


# PDF Export and Web Publishing Endpoints

class PublishNoteRequest(BaseModel):
    password: Optional[str] = None
    expires_at: Optional[str] = None  # ISO date string


@router.get("/{note_id}/export/pdf")
async def export_note_as_pdf(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Export note as PDF file"""
    from fastapi.responses import StreamingResponse
    import markdown
    import io
    from datetime import datetime

    try:
        # Get the note
        note_dict = await NotesOperations.get_note(db, note_id, user.email)
        if not note_dict:
            raise HTTPException(status_code=404, detail="Note not found")

        # Convert markdown to HTML
        md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc', 'tables'])
        content_html = md.convert(note_dict['content'])

        # Create HTML document with styling
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{note_dict['title']}</title>
            <style>
                @page {{ margin: 2cm; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    color: #111827;
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                }}
                h1 {{ font-size: 2.5em; border-bottom: 2px solid #3b82f6; padding-bottom: 0.3em; }}
                h2 {{ font-size: 2em; }}
                h3 {{ font-size: 1.5em; }}
                code {{
                    background: #f3f4f6;
                    padding: 0.2em 0.4em;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background: #1f2937;
                    color: #f9fafb;
                    padding: 1em;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
                pre code {{
                    background: none;
                    color: inherit;
                    padding: 0;
                }}
                blockquote {{
                    border-left: 4px solid #3b82f6;
                    margin-left: 0;
                    padding-left: 1em;
                    color: #6b7280;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                }}
                th, td {{
                    border: 1px solid #d1d5db;
                    padding: 0.5em;
                    text-align: left;
                }}
                th {{ background: #f3f4f6; font-weight: 600; }}
                .metadata {{
                    color: #6b7280;
                    font-size: 0.9em;
                    margin-bottom: 2em;
                    padding-bottom: 1em;
                    border-bottom: 1px solid #e5e7eb;
                }}
            </style>
        </head>
        <body>
            <h1>{note_dict['title']}</h1>
            <div class="metadata">
                <p><strong>Category:</strong> {note_dict.get('category', 'personal')}</p>
                <p><strong>Created:</strong> {note_dict.get('created_at', 'Unknown')}</p>
                <p><strong>Tags:</strong> {', '.join(note_dict.get('tags', [])) if note_dict.get('tags') else 'None'}</p>
            </div>
            {content_html}
            <div class="metadata" style="margin-top: 3em; border-top: 1px solid #e5e7eb; padding-top: 1em;">
                <p>Exported from EspressoBot on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </body>
        </html>
        """

        # Try to use weasyprint for better PDF rendering, fallback to basic HTML if not available
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf()
        except ImportError:
            # Fallback: return HTML with print-friendly styles
            logger.warning("weasyprint not installed, returning HTML for browser PDF printing")
            return StreamingResponse(
                io.BytesIO(html.encode('utf-8')),
                media_type="text/html",
                headers={
                    "Content-Disposition": f"inline; filename=\"{note_dict['title'][:50]}.html\""
                }
            )

        # Return PDF
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{note_dict['title'][:50]}.pdf\""
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting note as PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{note_id}/publish")
async def publish_note(
    note_id: int,
    request: PublishNoteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Publish note publicly with optional password protection and expiry"""
    import secrets
    import bcrypt
    from datetime import datetime, timezone
    from utils.datetime_utils import utc_now_naive
    from sqlalchemy import select
    from database.models import Note, PublishedNote

    try:
        # Verify note exists and belongs to user
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user.email)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if already published
        result = await db.execute(
            select(PublishedNote).where(PublishedNote.note_id == note_id)
        )
        published = result.scalar_one_or_none()

        # Generate unique public_id
        public_id = secrets.token_urlsafe(12)  # 16 chars, URL-safe

        # Hash password if provided
        password_hash = None
        if request.password:
            password_hash = bcrypt.hashpw(
                request.password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')

        # Parse expiry date if provided
        expires_at = None
        if request.expires_at:
            expires_at = datetime.fromisoformat(request.expires_at.replace('Z', '+00:00'))

        if published:
            # Update existing publication
            published.public_id = public_id
            published.password_hash = password_hash
            published.expires_at = expires_at
            published.updated_at = utc_now_naive()
        else:
            # Create new publication
            published = PublishedNote(
                note_id=note_id,
                user_id=user.email,
                public_id=public_id,
                password_hash=password_hash,
                expires_at=expires_at
            )
            db.add(published)

        await db.commit()
        await db.refresh(published)

        return {
            "success": True,
            "public_id": published.public_id,
            "public_url": f"/public/notes/{published.public_id}",
            "has_password": password_hash is not None,
            "expires_at": published.expires_at.isoformat() if published.expires_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing note: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{note_id}/publish")
async def unpublish_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Unpublish a note (remove from public access)"""
    from sqlalchemy import select, delete
    from database.models import Note, PublishedNote

    try:
        # Verify note belongs to user
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user.email)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        # Delete published note
        await db.execute(
            delete(PublishedNote).where(PublishedNote.note_id == note_id)
        )
        await db.commit()

        return {"success": True, "message": "Note unpublished successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unpublishing note: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{note_id}/publish-status")
async def get_publish_status(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Check if a note is published and get publication details"""
    from sqlalchemy import select
    from database.models import Note, PublishedNote

    try:
        # Verify note belongs to user
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user.email)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if published
        result = await db.execute(
            select(PublishedNote).where(PublishedNote.note_id == note_id)
        )
        published = result.scalar_one_or_none()

        if not published:
            return {"is_published": False}

        return {
            "is_published": True,
            "public_id": published.public_id,
            "public_url": f"/public/notes/{published.public_id}",
            "has_password": published.password_hash is not None,
            "expires_at": published.expires_at.isoformat() if published.expires_at else None,
            "view_count": published.view_count,
            "last_viewed_at": published.last_viewed_at.isoformat() if published.last_viewed_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting publish status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
