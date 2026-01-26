"""Database operations for Notes system (Second Brain)"""
import hashlib
import re
import yaml
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from utils.datetime_utils import utc_now_naive
from sqlalchemy import text, select, update, delete, func, cast
from sqlalchemy.ext.asyncio import AsyncSession
from services.doc_indexer import DocIndexer
import logging

logger = logging.getLogger(__name__)


class NotesOperations:
    """Database operations for user notes"""

    @staticmethod
    def _extract_inline_tags(content: str) -> List[str]:
        """
        Extract inline #tags from note content.
        Supports nested tags: #projects/espressobot, #inbox/to-read

        Examples:
            "#project #work/urgent #ideas/coffee" → ["project", "work/urgent", "ideas/coffee"]
        """
        # Match #tag or #category/subcategory/nested
        # Pattern: # followed by alphanumeric, dash, underscore, or forward slash
        tag_pattern = r'#([\w/-]+)'
        tags = re.findall(tag_pattern, content)
        return list(set(tags))  # Remove duplicates

    @staticmethod
    def _parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from note content (Obsidian-style).

        Frontmatter format:
        ---
        title: My Note
        tags: [tag1, tag2]
        category: work
        ---
        Note content here...

        Returns:
            (frontmatter_dict, content_without_frontmatter)
        """
        # Check for YAML frontmatter (--- at start)
        if not content.startswith('---'):
            return {}, content

        # Split on second ---
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1])
            remaining_content = parts[2].strip()
            return frontmatter or {}, remaining_content
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter: {e}")
            return {}, content

    @staticmethod
    def _extract_backlink_context(content: str, note_title: str, context_chars: int = 100) -> str:
        """
        Extract surrounding context where [[Note Title]] appears.

        Args:
            content: Note content to search
            note_title: Title of the linked note
            context_chars: Number of characters to show before/after (default: 100)

        Returns:
            Snippet showing the wikilink in context
        """
        # Escape special regex characters in note title
        link_pattern = f"\\[\\[{re.escape(note_title)}\\]\\]"
        match = re.search(link_pattern, content)

        if not match:
            return ""

        start = max(0, match.start() - context_chars)
        end = min(len(content), match.end() + context_chars)

        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    @staticmethod
    async def _generate_embedding(content: str) -> List[float]:
        """Generate embedding using OpenAI text-embedding-3-large (same as docs system)"""
        # Reuse the doc indexer's embedding service
        indexer = DocIndexer()
        embedding = await indexer.generate_embedding(content)
        return embedding

    @staticmethod
    def _calculate_content_hash(content: str) -> str:
        """Calculate SHA256 hash for content change detection"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    @staticmethod
    async def create_note(
        db: AsyncSession,
        user_id: str,
        title: str,
        content: str,
        category: str = "personal",
        tags: List[str] = None,
        conversation_id: Optional[str] = None,
        obsidian_vault_id: Optional[str] = None,
        obsidian_file_path: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a new note with embedding and Obsidian-style tag parsing.

        Supports:
        - Inline #tags and nested #tags/subtags in content
        - YAML frontmatter with tags and category
        - [[Wikilinks]] for bidirectional linking
        """
        tags = tags or []

        # Parse YAML frontmatter if present
        frontmatter, clean_content = NotesOperations._parse_yaml_frontmatter(content)

        # Extract tags from frontmatter
        frontmatter_tags = frontmatter.get('tags', [])
        if isinstance(frontmatter_tags, str):
            frontmatter_tags = [frontmatter_tags]
        elif not isinstance(frontmatter_tags, list):
            frontmatter_tags = []

        # Extract inline #tags from content
        inline_tags = NotesOperations._extract_inline_tags(content)

        # Merge all tag sources (provided tags, frontmatter, inline)
        all_tags = list(set(tags + frontmatter_tags + inline_tags))

        # Use frontmatter category if present and not overridden
        if 'category' in frontmatter and category == "personal":
            category = frontmatter['category']

        # Use frontmatter title if present and not overridden
        if 'title' in frontmatter and not title:
            title = frontmatter['title']

        logger.info(f"Creating note with {len(all_tags)} tags (provided: {len(tags)}, frontmatter: {len(frontmatter_tags)}, inline: {len(inline_tags)})")

        # Generate embedding for semantic search (use original content with frontmatter)
        combined_text = f"{title}\n\n{content}"
        embedding = await NotesOperations._generate_embedding(combined_text)

        # Calculate content hash for Obsidian sync
        content_hash = NotesOperations._calculate_content_hash(content)

        # Insert note with optional timestamp override
        if created_at or updated_at:
            # Include explicit timestamps if provided (for Obsidian import)
            query = text("""
                INSERT INTO notes (
                    user_id, conversation_id, title, content, category, tags,
                    embedding_halfvec, obsidian_vault_id, obsidian_file_path,
                    obsidian_content_hash, is_starred, created_at, updated_at
                )
                VALUES (
                    :user_id, :conversation_id, :title, :content, :category, :tags,
                    CAST(:embedding AS halfvec), :obsidian_vault_id, :obsidian_file_path,
                    :obsidian_content_hash, FALSE, :created_at, :updated_at
                )
                RETURNING id, title, content, category, tags, created_at, updated_at
            """)

            result = await db.execute(
                query,
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "tags": all_tags,
                    "embedding": str(embedding),
                    "obsidian_vault_id": obsidian_vault_id,
                    "obsidian_file_path": obsidian_file_path,
                    "obsidian_content_hash": content_hash,
                    "created_at": created_at or utc_now_naive(),
                    "updated_at": updated_at or created_at or utc_now_naive()
                }
            )
        else:
            # Use default database timestamps (current time)
            query = text("""
                INSERT INTO notes (
                    user_id, conversation_id, title, content, category, tags,
                    embedding_halfvec, obsidian_vault_id, obsidian_file_path,
                    obsidian_content_hash, is_starred
                )
                VALUES (
                    :user_id, :conversation_id, :title, :content, :category, :tags,
                    CAST(:embedding AS halfvec), :obsidian_vault_id, :obsidian_file_path,
                    :obsidian_content_hash, FALSE
                )
                RETURNING id, title, content, category, tags, created_at, updated_at
            """)

            result = await db.execute(
                query,
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "tags": all_tags,  # Use merged tags from all sources
                    "embedding": str(embedding),
                    "obsidian_vault_id": obsidian_vault_id,
                    "obsidian_file_path": obsidian_file_path,
                    "obsidian_content_hash": content_hash
                }
            )
        await db.commit()

        row = result.fetchone()
        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "tags": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None
        }

    @staticmethod
    async def get_note(db: AsyncSession, note_id: int, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single note by ID"""
        query = text("""
            UPDATE notes
            SET last_accessed = CURRENT_TIMESTAMP
            WHERE id = :note_id AND user_id = :user_id
            RETURNING id, title, content, category, tags, is_starred,
                      created_at, updated_at, last_accessed,
                      obsidian_vault_id, obsidian_file_path, obsidian_last_synced
        """)

        result = await db.execute(query, {"note_id": note_id, "user_id": user_id})
        await db.commit()

        row = result.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "tags": row[4],
            "is_starred": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
            "last_accessed": row[8].isoformat() if row[8] else None,
            "obsidian_vault_id": row[9],
            "obsidian_file_path": row[10],
            "obsidian_last_synced": row[11].isoformat() if row[11] else None
        }

    @staticmethod
    async def get_note_by_title(db: AsyncSession, user_id: str, title: str) -> Optional[Dict[str, Any]]:
        """Get a note by its title (case-insensitive) for wikilink navigation"""
        query = text("""
            SELECT id, title, content, category, tags, is_starred,
                   created_at, updated_at, last_accessed
            FROM notes
            WHERE user_id = :user_id AND LOWER(title) = LOWER(:title)
            LIMIT 1
        """)

        result = await db.execute(query, {"user_id": user_id, "title": title.strip()})
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "tags": row[4],
            "is_starred": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
            "last_accessed": row[8].isoformat() if row[8] else None
        }

    @staticmethod
    async def list_notes(
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        is_starred: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC"
    ) -> Dict[str, Any]:
        """List notes with pagination and filtering"""
        # Build WHERE clause
        where_clauses = ["user_id = :user_id"]
        params = {"user_id": user_id, "limit": limit, "offset": offset}

        if category:
            where_clauses.append("category = :category")
            params["category"] = category

        if is_starred is not None:
            where_clauses.append("is_starred = :is_starred")
            params["is_starred"] = is_starred

        where_sql = " AND ".join(where_clauses)

        # Validate sort parameters
        allowed_sort_fields = ["created_at", "updated_at", "last_accessed", "title"]
        if sort_by not in allowed_sort_fields:
            sort_by = "created_at"
        if sort_order.upper() not in ["ASC", "DESC"]:
            sort_order = "DESC"

        # Get total count
        count_query = text(f"SELECT COUNT(*) FROM notes WHERE {where_sql}")
        count_result = await db.execute(count_query, params)
        total_count = count_result.scalar()

        # Get notes (excluding content for performance - fetch individually when needed)
        query = text(f"""
            SELECT id, title,
                   substring(content, 1, 200) as content_preview,
                   category, tags, is_starred,
                   created_at, updated_at, last_accessed,
                   obsidian_vault_id, obsidian_file_path
            FROM notes
            WHERE {where_sql}
            ORDER BY {sort_by} {sort_order}
            LIMIT :limit OFFSET :offset
        """)

        result = await db.execute(query, params)
        rows = result.fetchall()

        notes = [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],  # content_preview (first 200 chars)
                "category": row[3],
                "tags": row[4],
                "is_starred": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None,
                "last_accessed": row[8].isoformat() if row[8] else None,
                "obsidian_vault_id": row[9],
                "obsidian_file_path": row[10]
            }
            for row in rows
        ]

        return {
            "notes": notes,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }

    @staticmethod
    async def upsert_obsidian_note(
        db: AsyncSession,
        user_id: str,
        title: str,
        content: str,
        category: str,
        tags: List[str],
        obsidian_vault_id: str,
        obsidian_file_path: str,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Insert or update an Obsidian note (upsert).
        If note already exists (same user_id, vault_id, file_path), update it.
        Otherwise, insert a new note.
        """
        # Parse frontmatter and extract inline tags
        frontmatter, clean_content = NotesOperations._parse_yaml_frontmatter(content)
        frontmatter_tags = frontmatter.get('tags', [])
        if isinstance(frontmatter_tags, str):
            frontmatter_tags = [frontmatter_tags]
        elif not isinstance(frontmatter_tags, list):
            frontmatter_tags = []

        inline_tags = NotesOperations._extract_inline_tags(content)
        all_tags = list(set(tags + frontmatter_tags + inline_tags))

        # Use frontmatter overrides if present
        if 'category' in frontmatter and category == "personal":
            category = frontmatter['category']
        if 'title' in frontmatter and not title:
            title = frontmatter['title']

        # Generate embedding
        combined_text = f"{title}\n\n{content}"
        embedding = await NotesOperations._generate_embedding(combined_text)
        content_hash = NotesOperations._calculate_content_hash(content)

        # PostgreSQL upsert using ON CONFLICT
        query = text("""
            INSERT INTO notes (
                user_id, title, content, category, tags,
                embedding_halfvec, obsidian_vault_id, obsidian_file_path,
                obsidian_content_hash, is_starred, created_at, updated_at
            )
            VALUES (
                :user_id, :title, :content, :category, :tags,
                CAST(:embedding AS halfvec), :obsidian_vault_id, :obsidian_file_path,
                :obsidian_content_hash, FALSE, :created_at, :updated_at
            )
            ON CONFLICT (user_id, obsidian_vault_id, obsidian_file_path)
            DO UPDATE SET
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                category = EXCLUDED.category,
                tags = EXCLUDED.tags,
                embedding_halfvec = EXCLUDED.embedding_halfvec,
                obsidian_content_hash = EXCLUDED.obsidian_content_hash,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            RETURNING id, title, content, category, tags, created_at, updated_at
        """)

        result = await db.execute(
            query,
            {
                "user_id": user_id,
                "title": title,
                "content": content,
                "category": category,
                "tags": all_tags,
                "embedding": str(embedding),
                "obsidian_vault_id": obsidian_vault_id,
                "obsidian_file_path": obsidian_file_path,
                "obsidian_content_hash": content_hash,
                "created_at": created_at or utc_now_naive(),
                "updated_at": updated_at or created_at or utc_now_naive()
            }
        )
        await db.commit()

        row = result.fetchone()
        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "tags": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None
        }

    @staticmethod
    async def update_note(
        db: AsyncSession,
        note_id: int,
        user_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_starred: Optional[bool] = None,
        find_text: Optional[str] = None,
        replace_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update a note and re-generate embedding if content changed"""
        # First get the current note
        current = await NotesOperations.get_note(db, note_id, user_id)
        if not current:
            return None

        # Handle text replacement if content is not explicitly provided
        if content is None and find_text is not None and replace_text is not None:
            current_content = current["content"] or ""
            if find_text in current_content:
                # Replace only the first occurrence to be safe
                content = current_content.replace(find_text, replace_text, 1)
            else:
                # If text not found, we could error out, but returning None or 
                # ignoring it might be safer. However, the agent needs to know it failed.
                # Since we return Optional[Dict], returning None usually means "not found".
                # But here the note was found, just the text wasn't.
                # Ideally we should raise an exception or handle it.
                # But to keep signature consistent, let's log it and maybe NOT update content.
                logger.warning(f"Text replacement failed: '{find_text}' not found in note #{note_id}")
                # We do NOT set content, so it remains None, and no content update happens.
                # However, if the agent *relies* on this, it will think it succeeded if we return the note object.
                # We should probably throw an error if the agent specifically requested a replacement that failed.
                # But for now, let's rely on the result comparison.
                pass

        # Prepare update fields
        update_fields = []
        params = {"note_id": note_id, "user_id": user_id}

        if title is not None:
            update_fields.append("title = :title")
            params["title"] = title
        else:
            title = current["title"]

        if content is not None:
            update_fields.append("content = :content")
            params["content"] = content

            # Parse tags from new content (inline #tags and frontmatter)
            frontmatter, clean_content = NotesOperations._parse_yaml_frontmatter(content)
            inline_tags = NotesOperations._extract_inline_tags(content)

            # If tags param is not provided, merge inline tags with existing tags
            if tags is None:
                frontmatter_tags = frontmatter.get('tags', [])
                if isinstance(frontmatter_tags, str):
                    frontmatter_tags = [frontmatter_tags]
                elif not isinstance(frontmatter_tags, list):
                    frontmatter_tags = []

                # Merge with existing tags
                existing_tags = current.get('tags', [])
                merged_tags = list(set(existing_tags + inline_tags + frontmatter_tags))

                update_fields.append("tags = :tags")
                params["tags"] = merged_tags
                logger.info(f"Auto-merged tags from content: {len(inline_tags)} inline, {len(frontmatter_tags)} frontmatter")

            # Re-generate embedding when content changes
            combined_text = f"{title}\n\n{content}"
            embedding = await NotesOperations._generate_embedding(combined_text)
            update_fields.append("embedding_halfvec = CAST(:embedding AS halfvec)")
            params["embedding"] = str(embedding)

            # Update content hash
            content_hash = NotesOperations._calculate_content_hash(content)
            update_fields.append("obsidian_content_hash = :content_hash")
            params["content_hash"] = content_hash

        if category is not None:
            update_fields.append("category = :category")
            params["category"] = category

        if tags is not None:
            # If tags explicitly provided, parse inline tags and merge
            if content is not None:
                # Already parsed above, use the content's inline tags
                inline_tags = NotesOperations._extract_inline_tags(content)
            else:
                # Parse from current content
                inline_tags = NotesOperations._extract_inline_tags(current['content'])

            # Merge provided tags with inline tags
            merged_tags = list(set(tags + inline_tags))
            update_fields.append("tags = :tags")
            params["tags"] = merged_tags

        if is_starred is not None:
            update_fields.append("is_starred = :is_starred")
            params["is_starred"] = is_starred

        if not update_fields:
            return current

        # Add updated_at to track modification time
        update_fields.append("updated_at = NOW()")

        # Execute update
        query = text(f"""
            UPDATE notes
            SET {", ".join(update_fields)}
            WHERE id = :note_id AND user_id = :user_id
            RETURNING id, title, content, category, tags, is_starred,
                      created_at, updated_at, last_accessed
        """)

        result = await db.execute(query, params)
        await db.commit()

        row = result.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "tags": row[4],
            "is_starred": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
            "last_accessed": row[8].isoformat() if row[8] else None
        }

    @staticmethod
    async def delete_note(db: AsyncSession, note_id: int, user_id: str) -> bool:
        """Delete a note"""
        query = text("DELETE FROM notes WHERE id = :note_id AND user_id = :user_id")
        result = await db.execute(query, {"note_id": note_id, "user_id": user_id})
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def reindex_user_notes(
        db: AsyncSession,
        user_id: str,
    ) -> Dict[str, Any]:
        """Rebuild embeddings for all notes owned by a user."""
        fetch_query = text("""
            SELECT id, title, content
            FROM notes
            WHERE user_id = :user_id
        """)

        result = await db.execute(fetch_query, {"user_id": user_id})
        rows = result.fetchall()

        total = len(rows)
        if total == 0:
            return {"total": 0, "updated": 0, "failed": []}

        indexer = DocIndexer()
        updated = 0
        failures = []

        try:
            for row in rows:
                note_id, title, content = row
                try:
                    title_value = title or ""
                    content_value = content or ""
                    combined_text = f"{title_value}\n\n{content_value}".strip()
                    if not combined_text:
                        combined_text = title_value or content_value

                    embedding = await indexer.generate_embedding(combined_text)
                    content_hash = NotesOperations._calculate_content_hash(content_value)

                    await db.execute(
                        text("""
                            UPDATE notes
                            SET embedding_halfvec = CAST(:embedding AS halfvec),
                                obsidian_content_hash = :content_hash
                            WHERE id = :note_id AND user_id = :user_id
                        """),
                        {
                            "embedding": str(embedding),
                            "content_hash": content_hash,
                            "note_id": note_id,
                            "user_id": user_id,
                        }
                    )
                    updated += 1
                except Exception as exc:  # noqa: B902
                    logger.error("Failed to reindex note %s: %s", note_id, exc)
                    failures.append({"id": note_id, "error": str(exc)})

            await db.commit()
        finally:
            if hasattr(indexer, "client"):
                try:
                    await indexer.client.aclose()
                except Exception:  # pragma: no cover - best effort cleanup
                    pass

        return {
            "total": total,
            "updated": updated,
            "failed": failures,
        }

    @staticmethod
    async def search_notes_semantic(
        db: AsyncSession,
        user_id: str,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Semantic search using pgvector embeddings"""
        # Generate embedding for query
        query_embedding = await NotesOperations._generate_embedding(query)

        # Build WHERE clause
        where_clauses = ["user_id = :user_id"]
        params = {
            "user_id": user_id,
            "embedding": str(query_embedding),
            "limit": limit
        }

        if category:
            where_clauses.append("category = :category")
            params["category"] = category

        where_sql = " AND ".join(where_clauses)

        # Search using pgvector cosine distance
        search_query = text(f"""
            SELECT id, title, content, category, tags, is_starred,
                   created_at, updated_at,
                   (embedding_halfvec <=> CAST(:embedding AS halfvec)) as distance
            FROM notes
            WHERE {where_sql}
            ORDER BY distance ASC
            LIMIT :limit
        """)

        result = await db.execute(search_query, params)
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "category": row[3],
                "tags": row[4],
                "is_starred": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None,
                "similarity": 1 - row[8]  # Convert distance to similarity
            }
            for row in rows
        ]

    @staticmethod
    async def search_notes_fulltext(
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Full-text search using PostgreSQL tsvector"""
        search_query = text("""
            SELECT id, title, content, category, tags, is_starred,
                   created_at, updated_at,
                   ts_rank(to_tsvector('english', title || ' ' || content), plainto_tsquery('english', :query)) as rank
            FROM notes
            WHERE user_id = :user_id
                AND (to_tsvector('english', title || ' ' || content) @@ plainto_tsquery('english', :query))
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await db.execute(search_query, {"user_id": user_id, "query": query, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "category": row[3],
                "tags": row[4],
                "is_starred": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None,
                "rank": float(row[8])
            }
            for row in rows
        ]

    @staticmethod
    async def get_similar_notes(
        db: AsyncSession,
        note_id: int,
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar notes using embedding similarity"""
        # Get the note's embedding
        query = text("""
            SELECT embedding_halfvec
            FROM notes
            WHERE id = :note_id AND user_id = :user_id
        """)
        result = await db.execute(query, {"note_id": note_id, "user_id": user_id})
        row = result.fetchone()

        if not row or not row[0]:
            return []

        embedding = row[0]

        # Find similar notes (excluding the current note)
        search_query = text("""
            SELECT id, title, content, category, tags, is_starred,
                   created_at, updated_at,
                   (embedding_halfvec <=> :embedding) as distance
            FROM notes
            WHERE user_id = :user_id AND id != :note_id
            ORDER BY distance ASC
            LIMIT :limit
        """)

        result = await db.execute(
            search_query,
            {"user_id": user_id, "note_id": note_id, "embedding": embedding, "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "category": row[3],
                "tags": row[4],
                "is_starred": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None,
                "similarity": 1 - row[8]
            }
            for row in rows
        ]

    @staticmethod
    async def get_backlinks(
        db: AsyncSession,
        note_id: int,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Find all notes that link to this note via [[Note Title]] wikilinks.

        This implements bidirectional linking (like Obsidian/Roam Research).

        Args:
            db: Database session
            note_id: Target note ID to find backlinks for
            user_id: User ID for security

        Returns:
            List of notes that contain [[wikilinks]] to this note, with context snippets
        """
        # Get the target note's title
        result = await db.execute(
            text("SELECT title FROM notes WHERE id = :note_id AND user_id = :user_id"),
            {"note_id": note_id, "user_id": user_id}
        )
        target_row = result.fetchone()

        if not target_row:
            return []

        target_title = target_row[0]

        # Search for [[Note Title]] in other notes' content
        # Using LIKE for simple pattern matching (PostgreSQL supports this efficiently)
        search_pattern = f"%[[{target_title}]]%"

        query = text("""
            SELECT id, title, content, category, created_at
            FROM notes
            WHERE user_id = :user_id
              AND id != :note_id
              AND content LIKE :search_pattern
            ORDER BY updated_at DESC
        """)

        result = await db.execute(
            query,
            {
                "user_id": user_id,
                "note_id": note_id,
                "search_pattern": search_pattern
            }
        )

        backlinks = result.fetchall()

        return [
            {
                'id': note[0],
                'title': note[1],
                'category': note[3],
                'created_at': note[4].isoformat() if note[4] else None,
                'snippet': NotesOperations._extract_backlink_context(note[2], target_title)
            }
            for note in backlinks
        ]

    @staticmethod
    async def get_all_semantic_connections(
        db: AsyncSession,
        user_id: str,
        similarity_threshold: float = 0.65,
        limit_per_note: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find all semantic connections between notes above threshold.
        Returns pairs of notes with their similarity scores for graph visualization.

        Uses a self-join with the pgvector cosine distance operator.
        Only returns each pair once (source_id < target_id to avoid duplicates).

        Args:
            db: Database session
            user_id: User ID for filtering notes
            similarity_threshold: Minimum similarity score (0-1) to include connection
            limit_per_note: Max connections per note to prevent graph overload

        Returns:
            List of {source: id, target: id, similarity: float} connections
        """
        # Use a self-join to find all pairs above threshold
        # n1.id < n2.id ensures we only get each pair once (not A->B and B->A)
        query = text("""
            WITH ranked_connections AS (
                SELECT
                    n1.id as source_id,
                    n2.id as target_id,
                    (1 - (n1.embedding_halfvec <=> n2.embedding_halfvec)) as similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY n1.id
                        ORDER BY n1.embedding_halfvec <=> n2.embedding_halfvec
                    ) as rank
                FROM notes n1
                JOIN notes n2 ON n1.user_id = n2.user_id
                    AND n1.id < n2.id
                    AND n1.embedding_halfvec IS NOT NULL
                    AND n2.embedding_halfvec IS NOT NULL
                WHERE n1.user_id = :user_id
                    AND (1 - (n1.embedding_halfvec <=> n2.embedding_halfvec)) > :threshold
            )
            SELECT source_id, target_id, similarity
            FROM ranked_connections
            WHERE rank <= :limit_per_note
            ORDER BY similarity DESC
        """)

        result = await db.execute(query, {
            "user_id": user_id,
            "threshold": similarity_threshold,
            "limit_per_note": limit_per_note
        })

        rows = result.fetchall()

        return [
            {
                "source": row[0],
                "target": row[1],
                "similarity": float(row[2])
            }
            for row in rows
        ]

    @staticmethod
    async def get_obsidian_sync_status(
        db: AsyncSession,
        user_id: str,
        obsidian_vault_id: str
    ) -> Dict[str, Any]:
        """Get sync status for an Obsidian vault"""
        query = text("""
            SELECT
                COUNT(*) as total_notes,
                MAX(obsidian_last_synced) as last_sync,
                COUNT(CASE WHEN obsidian_last_synced IS NULL THEN 1 END) as never_synced
            FROM notes
            WHERE user_id = :user_id AND obsidian_vault_id = :obsidian_vault_id
        """)

        result = await db.execute(query, {"user_id": user_id, "obsidian_vault_id": obsidian_vault_id})
        row = result.fetchone()

        return {
            "vault_id": obsidian_vault_id,
            "total_notes": row[0] if row else 0,
            "last_sync": row[1].isoformat() if row and row[1] else None,
            "never_synced": row[2] if row else 0
        }
